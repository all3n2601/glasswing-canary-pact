"""Canary Pact API."""

import asyncio
import hashlib
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from contracts_py.api import (
    QuickOfficePreview,
    DepartmentSave,
    OrganizationSave,
    RunEventPage,
    DecisionDraft,
    DecisionCreated,
    DepartmentContextItemCreate,
    DecisionPromptRequest,
    FuturesRequest,
    GraphLevel,
    HealthResponse,
    HumanDecisionRequest,
    OptimizeRequest,
    OrganizationDepartmentSummary,
    OrganizationProfileView,
    QuickSimulateRequest,
    UserPublic,
)
from contracts_py.agents import AgentAssessment, AgentSkillFile
from contracts_py.decision import CandidatePlan, DecisionBrief
from contracts_py.engine import FutureComparison, PortfolioComparison, SimulationResult
from contracts_py.enums import DocumentStatus, DocumentType, EntityType, RunStatus, Sensitivity
from contracts_py.events import EventType, PhaseChanged, RunState
from contracts_py.package import DecisionPackage, HumanDecision, find_person_tokens
from contracts_py.twin import (
    DepartmentDetail,
    DepartmentProfile,
    Document,
    DomainGraph,
    Entity,
    Evidence,
    Organization,
    OrganizationSettings,
    Pressure,
    Twin,
)

from agent_orchestration import IntakeInvalid, IntakeUnavailable, agent_skill_files

from canary_api import auth, engine_port, runs, runtime, storage
from canary_api.engine_port import EngineNotReady
from canary_api.events import Run, utc_now

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    auth.signer()
    auth.seed_demo_approver()
    auth.warn_if_no_approver()
    runtime.check_structured_output()
    runtime.check_thinking()
    runtime.check_sim_mode()
    try:
        yield
    finally:
        runtime.bus.flush()
        storage.close()


app = FastAPI(
    lifespan=lifespan,
    title="Canary Pact API",
    version="0.1.0",
    description="Organizational decision simulation and blast-radius API.",
)
app.include_router(auth.router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(EngineNotReady)
async def engine_not_ready(request: Request, exc: EngineNotReady) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


def _run(run_id: str) -> Run:
    run = runtime.bus.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def _brief_plan(brief: DecisionBrief, intervention_ids: list[str] | None) -> CandidatePlan:
    ids = intervention_ids if intervention_ids is not None else [i.id for i in brief.candidate_interventions]
    known = {i.id for i in brief.candidate_interventions}
    unknown = [i for i in ids if i not in known]
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown intervention ids: {unknown}")
    return CandidatePlan(plan_id="plan_user", label="User selection", intervention_ids=ids, source="user")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    failures = storage.writer.failures
    return HealthResponse(status="degraded" if failures else "ok", storage=storage.backend_name(),  # type: ignore[arg-type]
                          storage_write_failures=failures, engine_impl=engine_port.engine_impl(),  # type: ignore[arg-type]
                          twin_impl=engine_port.twin_impl())  # type: ignore[arg-type]


@app.get("/company", response_model=Twin)
def company() -> Twin:
    return runtime.twin()


@app.get("/company/graph", response_model=DomainGraph)
def company_graph(level: GraphLevel = "entity") -> DomainGraph:
    twin = runtime.twin()
    if level == "domain":
        return engine_port.aggregate_domain_graph(twin)
    return DomainGraph(nodes=twin.entities, edges=twin.edges)


@app.get("/company/pressures", response_model=list[Pressure])
def company_pressures() -> list[Pressure]:
    return runtime.twin().pressures


@app.get("/organization", response_model=Organization)
def organization() -> Organization:
    return runtime.twin().organization


@app.get("/organization/settings", response_model=OrganizationSettings)
def organization_settings() -> OrganizationSettings:
    return runtime.settings()


@app.get("/organization/profile", response_model=OrganizationProfileView)
def organization_profile() -> OrganizationProfileView:
    return _profile(runtime.twin())


def _profile(twin: Twin, settings: OrganizationSettings | None = None) -> OrganizationProfileView:
    settings = settings or twin.organization_settings or runtime.settings()
    names = {e.id: e.name for e in twin.entities if e.type is EntityType.department}
    return OrganizationProfileView(
        twin_version=twin.version.twin_version,
        organization=twin.organization,
        departments=[
            OrganizationDepartmentSummary(
                department_id=p.department_id,
                name=names[p.department_id],
                mission=p.mission,
                actual_fte=p.staffing.actual_fte,
                annual_budget_usd=p.budget.annual_budget_usd,
                utilisation=p.staffing.utilisation,
                maturity_level=p.maturity_level,
                enabled=p.active and (p.agent_id is None or p.agent_id in settings.enabled_agent_ids),
                active=p.active,
                agent_id=p.agent_id,
            )
            for p in twin.department_profiles
        ],
        settings=settings,
    )


@app.get("/organization/agent-skills", response_model=list[AgentSkillFile])
def organization_agent_skills() -> list[AgentSkillFile]:
    return agent_skill_files()


@app.get("/departments", response_model=list[DepartmentProfile])
def departments() -> list[DepartmentProfile]:
    return runtime.twin().department_profiles


@app.get("/departments/{department_id}", response_model=DepartmentDetail)
def department(department_id: str) -> DepartmentDetail:
    twin = runtime.twin()
    if not any(e.id == department_id and e.type is EntityType.department for e in twin.entities):
        raise HTTPException(status_code=404, detail="Department not found")
    return engine_port.department_detail(twin, department_id)


@app.post("/departments/{department_id}/context", response_model=DepartmentDetail)
def add_department_context(
    department_id: str,
    request: DepartmentContextItemCreate,
    user: UserPublic = Depends(auth.require_approver),
) -> DepartmentDetail:
    current = runtime.twin()
    if not any(e.id == department_id and e.type is EntityType.department for e in current.entities):
        raise HTTPException(status_code=404, detail="Department not found")

    suffix = uuid.uuid4().hex[:12]
    entity_type = EntityType(request.entity_type)
    entity_id = f"{entity_type.value}_{suffix}"
    document_id = f"doc_context_{suffix}"
    evidence_id = f"ev_context_{suffix}"
    now = utc_now()
    name = request.name.strip()
    evidence_title = request.evidence_title.strip()
    evidence_snippet = request.evidence_snippet.strip()
    if len(name) < 2 or len(evidence_title) < 2 or len(evidence_snippet) < 10:
        raise HTTPException(status_code=422, detail="Context name, evidence title, and evidence excerpt cannot be blank")
    summary = " ".join(evidence_snippet.split()[:60])

    entity = Entity(
        id=entity_id,
        type=entity_type,
        name=name,
        department_id=department_id,
        criticality=request.criticality,
        sensitivity=Sensitivity.general,
        evidence_refs=[evidence_id],
        annual_cost_usd=request.annual_cost_usd,
        capacity_fte=request.capacity_fte,
        min_qualified_owners=request.min_qualified_owners,
        documented_pct=request.documented_pct,
        failure_cost_per_day_usd=request.failure_cost_per_day_usd,
        completion_pct=request.completion_pct,
        remaining_cost_usd=request.remaining_cost_usd,
        expected_completion_day=request.expected_completion_day,
        time_to_train_days=request.time_to_train_days,
        kpi_baseline=request.kpi_baseline,
        kpi_unit=request.kpi_unit,
        higher_is_better=request.higher_is_better,
    )
    document = Document(
        id=document_id,
        title=evidence_title,
        doc_type=DocumentType.other,
        department_id=department_id,
        uri=f"canary://departments/{department_id}/context/{document_id}",
        mime_type="text/plain",
        status=DocumentStatus.current,
        sensitivity=Sensitivity.general,
        covers_entity_ids=[entity_id],
        summary=summary,
        checksum_sha256=hashlib.sha256(evidence_snippet.encode("utf-8")).hexdigest(),
        synthetic=False,
        ingested=True,
        uploaded_at=now,
    )
    evidence = Evidence(
        id=evidence_id,
        source_type=request.evidence_source,
        document_id=document_id,
        snippet=evidence_snippet,
        synthetic=False,
    )

    candidate = current.model_copy(deep=True)
    candidate.entities.append(entity)
    candidate.documents.append(document)
    candidate.evidence.append(evidence)
    profile = next(p for p in candidate.department_profiles if p.department_id == department_id)
    profile.owned_entity_ids.append(entity_id)
    profile.document_ids.append(document_id)
    if entity_type is EntityType.workflow and request.criticality.value in {"high", "critical"}:
        profile.critical_workflow_ids.append(entity_id)
    if entity_type is EntityType.kpi:
        profile.kpi_ids.append(entity_id)
    candidate.version = candidate.version.model_copy(update={
        "twin_version": f"twin_context_{now.strftime('%Y%m%d%H%M%S%f')}",
        "created_at": now,
        "as_of_date": now.date(),
        "created_by": user.user_id,
    })
    errors = [issue for issue in engine_port.validate_twin(candidate) if issue.severity == "error"]
    if errors:
        raise HTTPException(status_code=422, detail=errors[0].message)
    runtime.activate_twin(candidate)
    return engine_port.department_detail(candidate, department_id)


@app.get("/documents", response_model=list[Document])
def documents(
    department_id: str | None = None,
    doc_type: DocumentType | None = None,
    status: DocumentStatus | None = None,
) -> list[Document]:
    return [
        d
        for d in runtime.twin().documents
        if (department_id is None or d.department_id == department_id)
        and (doc_type is None or d.doc_type is doc_type)
        and (status is None or d.status is status)
    ]


@app.get("/documents/{document_id}", response_model=Document)
def document(document_id: str) -> Document:
    found = next((d for d in runtime.twin().documents if d.id == document_id), None)
    if found is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return found


@app.post("/decisions", response_model=DecisionCreated)
async def create_decision(brief: DecisionBrief, llm_mode: Literal["live"] | None = None,
                          user: UserPublic = Depends(auth.current_user)) -> DecisionCreated:
    try:
        brief = runs.apply_settings_defaults(brief, runtime.settings())
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc
    if runtime.sim_mode_error:
        raise HTTPException(status_code=503, detail=f"Decision runs are disabled: {runtime.sim_mode_error}")
    if not runs.live_allowed():
        raise HTTPException(status_code=503, detail="Live agents are disabled; set CANARY_ALLOW_LIVE=true to enable them")
    if runtime.structured_output_error:
        raise HTTPException(status_code=503, detail=f"Live runs are disabled: {runtime.structured_output_error}")
    if runtime.thinking_error:
        raise HTTPException(status_code=503, detail=f"Live runs are disabled: {runtime.thinking_error}")
    return DecisionCreated(run_id=runs.start_run(brief))


@app.post("/decisions/draft", response_model=DecisionDraft)
def draft_decision(request: DecisionPromptRequest,
                   user: UserPublic = Depends(auth.current_user)) -> DecisionDraft:
    if not runs.live_allowed():
        raise HTTPException(status_code=503, detail="Live agents are disabled; set CANARY_ALLOW_LIVE=true to enable them")
    if runtime.structured_output_error:
        raise HTTPException(status_code=503, detail=f"Live runs are disabled: {runtime.structured_output_error}")
    if runtime.thinking_error:
        raise HTTPException(status_code=503, detail=f"Live runs are disabled: {runtime.thinking_error}")
    try:
        return runtime.build_intake(runtime.settings()).draft(
            request.prompt,
            twin=runtime.twin(),
            created_by=user.user_id,
            horizon_days=request.horizon_days,
        )
    except IntakeUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except IntakeInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/runs/{run_id}", response_model=RunState)
def run_state(run_id: str) -> RunState:
    return _run(run_id).state


PERSPECTIVE_EVENTS = (EventType.agent_completed, EventType.challenge_raised)


@app.get("/runs/{run_id}/perspectives", response_model=list[AgentAssessment])
def run_perspectives(run_id: str) -> list[AgentAssessment]:
    events = sorted(_run(run_id).events, key=lambda e: e.sequence)
    # The challenger's assessment is published as agent_completed and again as challenge_raised; keep the first.
    by_id: dict[str, AgentAssessment] = {}
    for event in events:
        if event.type in PERSPECTIVE_EVENTS and isinstance(event.payload, AgentAssessment):
            by_id.setdefault(event.payload.assessment_id, event.payload)
    assessments = list(by_id.values())
    if find_person_tokens([a.model_dump(mode="json") for a in assessments]):
        log.warning("perspectives for run %s withheld: person tokens in agent output", run_id)
        raise HTTPException(status_code=409, detail="Perspectives withheld: person tokens found in agent output")
    return assessments


@app.websocket("/runs/{run_id}/events")
async def run_events(websocket: WebSocket, run_id: str) -> None:
    if runtime.bus.get(run_id) is None:
        await websocket.close(code=4404)
        return
    await websocket.accept()

    async def until_disconnect() -> None:
        while (await websocket.receive())["type"] != "websocket.disconnect":
            pass

    async def forward() -> None:
        async for event in runtime.bus.stream(run_id):
            await websocket.send_text(event.model_dump_json())

    tasks = [asyncio.create_task(until_disconnect()), asyncio.create_task(forward())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except WebSocketDisconnect:
        pass
    finally:
        for task in tasks:
            task.cancel()


@app.get("/runs/{run_id}/package", response_model=DecisionPackage)
def run_package(run_id: str) -> Response:
    run = _run(run_id)
    if run.package is None:
        raise HTTPException(status_code=409, detail="Package is not ready")
    leveled: Any = engine_port.to_role_level(run.package, runtime.twin())
    data = leveled.model_dump(mode="json") if isinstance(leveled, BaseModel) else leveled
    try:
        package = DecisionPackage.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Package rejected: {exc.errors()[0]['msg']}") from exc
    body = package.model_dump_json().encode()
    runtime.bus.record_served_package(run_id, package, hashlib.sha256(body).hexdigest())
    return Response(content=body, media_type="application/json")


@app.post("/runs/{run_id}/decision", response_model=HumanDecision)
async def record_decision(run_id: str, request: HumanDecisionRequest,
                          user: UserPublic = Depends(auth.require_approver)) -> HumanDecision:
    # decided_by comes from the token; the request's own decided_by value is ignored.
    decided_by = f"{user.display_name} ({user.user_id})"
    run = _run(run_id)
    if run.package is None or run.served_package_hash is None:
        raise HTTPException(status_code=409, detail="Fetch the package before deciding")
    if run.state.status is not RunStatus.awaiting_approval:
        raise HTTPException(status_code=409, detail=f"Run is {run.state.status}, not awaiting_approval")
    if request.package_hash != run.served_package_hash:
        raise HTTPException(status_code=409, detail="package_hash does not match the package served")
    decision = HumanDecision(
        run_id=run_id,
        package_id=run.package.package_id,
        decision=request.decision,
        decided_by=decided_by,
        decided_at=utc_now(),
        notes=request.notes,
        package_hash=run.served_package_hash,
    )
    runtime.bus.publish(run_id, EventType.human_decision_recorded, decision, actor=user.user_id)
    # A scenario request keeps the run open so the same package can still be approved or rejected.
    if request.decision != "request_scenario":
        runtime.bus.publish(
            run_id,
            EventType.phase_changed,
            PhaseChanged(from_status=RunStatus.awaiting_approval, to_status=RunStatus.completed),
            actor="api",
        )
    return decision


@app.post("/simulate/quick", response_model=SimulationResult)
def simulate_quick(request: QuickSimulateRequest) -> SimulationResult:
    plan = _brief_plan(request.brief, request.intervention_ids)
    interventions = [i for i in request.brief.candidate_interventions if i.id in plan.intervention_ids]
    try:
        return engine_port.quick_impact(
            runtime.twin(), interventions, brief=request.brief, settings=runtime.settings()
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/simulate/office-preview", response_model=QuickOfficePreview)
def office_preview(request: QuickSimulateRequest, user: UserPublic = Depends(auth.current_user)) -> QuickOfficePreview:
    baseline = runtime.twin()
    if request.expected_twin_version and baseline.version.twin_version != request.expected_twin_version:
        raise HTTPException(status_code=409, detail="Company changed. Reload before previewing.")
    plan = _brief_plan(request.brief, request.intervention_ids)
    interventions = [i for i in request.brief.candidate_interventions if i.id in plan.intervention_ids]
    try:
        result = engine_port.quick_impact(baseline, interventions, brief=request.brief, settings=runtime.settings())
        return QuickOfficePreview(baseline_twin_version=baseline.version.twin_version, result=result,
                                  blast_radius=engine_port.blast_radius(result, baseline))
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/simulate/futures", response_model=FutureComparison)
def simulate_futures(request: FuturesRequest) -> FutureComparison:
    brief = request.brief
    if request.futures is not None:
        brief = DecisionBrief.model_validate({**brief.model_dump(), "futures": request.futures})
    plan = _brief_plan(brief, request.intervention_ids)
    return engine_port.compare_futures(runtime.twin(), brief, plan, settings=runtime.settings())


@app.post("/simulate/optimize", response_model=PortfolioComparison)
def simulate_optimize(request: OptimizeRequest) -> PortfolioComparison:
    return engine_port.optimize(runtime.twin(), request.brief, settings=runtime.settings())


@app.post("/departments/save", response_model=OrganizationProfileView)
def save_department(request: DepartmentSave, user: UserPublic = Depends(auth.require_approver)) -> OrganizationProfileView:
    from company_twin import edit_department
    with runtime.twin_lock:
        current = runtime.twin()
        if current.version.twin_version != request.expected_twin_version:
            raise HTTPException(status_code=409, detail="Company changed. Reload the department before saving.")
        try:
            candidate = edit_department(current, request.department, actor=user.user_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        runtime.activate_twin(candidate)
        return _profile(candidate)


@app.get("/runs/{run_id}/office-profile", response_model=OrganizationProfileView)
def run_office_profile(run_id: str, user: UserPublic = Depends(auth.current_user)) -> OrganizationProfileView:
    run = _run(run_id)
    snapshot = storage.current().load_twin_version(run.state.baseline_twin_version)
    if snapshot is None:
        raise HTTPException(status_code=409, detail="The baseline snapshot for this run is unavailable")
    return _profile(snapshot, snapshot.organization_settings or OrganizationSettings(organization_id=snapshot.organization.id))


@app.get("/runs/{run_id}/event-log", response_model=RunEventPage)
def run_event_log(run_id: str, after_sequence: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=250),
                  user: UserPublic = Depends(auth.current_user)) -> RunEventPage:
    run = _run(run_id)
    remaining = [e for e in run.events if e.sequence > after_sequence]
    page = sorted(remaining, key=lambda e: e.sequence)[:limit]
    if find_person_tokens([e.model_dump(mode="json") for e in page]):
        raise HTTPException(status_code=409, detail="Event history withheld: person tokens in output")
    return RunEventPage(events=page, next_sequence=page[-1].sequence if page else after_sequence,
                        has_more=len(remaining) > len(page),
                        terminal=run.state.status.value in {"completed", "failed", "awaiting_approval"} or run.state.package_id is not None)


@app.get("/runs/{run_id}/office-evidence/{evidence_id}", response_model=Evidence)
def run_office_evidence(run_id: str, evidence_id: str, user: UserPublic = Depends(auth.current_user)) -> Evidence:
    snapshot = storage.current().load_twin_version(_run(run_id).state.baseline_twin_version)
    if snapshot is None:
        raise HTTPException(status_code=409, detail="Run baseline unavailable")
    evidence = next((e for e in snapshot.evidence if e.id == evidence_id), None)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence is absent from this run baseline")
    if find_person_tokens(evidence.model_dump(mode="json")):
        raise HTTPException(status_code=409, detail="Evidence withheld: person tokens in source")
    return evidence


@app.get("/runs/{run_id}/office-departments/{department_id}", response_model=DepartmentDetail)
def run_office_department(run_id: str, department_id: str, user: UserPublic = Depends(auth.current_user)) -> DepartmentDetail:
    snapshot = storage.current().load_twin_version(_run(run_id).state.baseline_twin_version)
    if snapshot is None:
        raise HTTPException(status_code=409, detail="Run baseline unavailable")
    if not any(p.department_id == department_id for p in snapshot.department_profiles):
        raise HTTPException(status_code=404, detail="Department is absent from this baseline; inspect its scenario declaration")
    return engine_port.department_detail(snapshot, department_id)


@app.get("/runs/{run_id}/office-graph", response_model=DomainGraph)
def run_office_graph(run_id: str, user: UserPublic = Depends(auth.current_user)) -> DomainGraph:
    snapshot = storage.current().load_twin_version(_run(run_id).state.baseline_twin_version)
    if snapshot is None:
        raise HTTPException(status_code=409, detail="Run baseline unavailable")
    return DomainGraph(nodes=snapshot.entities, edges=snapshot.edges)


@app.post("/organization/profile", response_model=OrganizationProfileView)
def save_organization(request: OrganizationSave, user: UserPublic = Depends(auth.require_approver)) -> OrganizationProfileView:
    from company_twin import edit_organization
    with runtime.twin_lock:
        current = runtime.twin()
        if current.version.twin_version != request.expected_twin_version:
            raise HTTPException(status_code=409, detail="Company changed. Reload before saving.")
        try:
            candidate = edit_organization(current, request.organization, request.departments, request.settings, actor=user.user_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        runtime.activate_twin(candidate)
        return _profile(candidate)
