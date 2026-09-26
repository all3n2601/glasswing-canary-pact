"""Canary Pact API."""

import asyncio
import hashlib
from typing import Any, get_args

from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from contracts_py.api import (
    DecisionCreated,
    FuturesRequest,
    GraphLevel,
    HealthResponse,
    HumanDecisionRequest,
    OptimizeRequest,
    OrganizationDepartmentSummary,
    OrganizationProfileView,
    QuickSimulateRequest,
    ReplayInfo,
    ReplaySpeed,
    ReplayStarted,
)
from contracts_py.decision import CandidatePlan, DecisionBrief
from contracts_py.engine import FutureComparison, PortfolioComparison, SimulationResult
from contracts_py.enums import DocumentStatus, DocumentType, EntityType, RunStatus
from contracts_py.events import EventType, PhaseChanged, RunState
from contracts_py.package import DecisionPackage, HumanDecision
from contracts_py.twin import (
    DepartmentDetail,
    DepartmentProfile,
    Document,
    DomainGraph,
    Organization,
    OrganizationSettings,
    Pressure,
    Twin,
)

from canary_api import engine_port, runs, runtime
from canary_api.engine_port import EngineNotReady
from canary_api.events import Run, utc_now

app = FastAPI(
    title="Canary Pact API",
    version="0.1.0",
    description="Organizational decision simulation and blast-radius API.",
)
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
    return HealthResponse()


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
    twin = runtime.twin()
    settings = runtime.settings()
    names = {e.id: e.name for e in twin.entities if e.type is EntityType.department}
    return OrganizationProfileView(
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
                enabled=p.agent_id is None or p.agent_id in settings.enabled_agent_ids,
            )
            for p in twin.department_profiles
        ],
        settings=settings,
    )


@app.get("/departments", response_model=list[DepartmentProfile])
def departments() -> list[DepartmentProfile]:
    return runtime.twin().department_profiles


@app.get("/departments/{department_id}", response_model=DepartmentDetail)
def department(department_id: str) -> DepartmentDetail:
    twin = runtime.twin()
    if not any(e.id == department_id and e.type is EntityType.department for e in twin.entities):
        raise HTTPException(status_code=404, detail="Department not found")
    return engine_port.department_detail(twin, department_id)


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
async def create_decision(brief: DecisionBrief) -> DecisionCreated:
    try:
        brief = runs.apply_settings_defaults(brief, runtime.settings())
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc
    return DecisionCreated(run_id=runs.start_run(brief))


@app.get("/runs/{run_id}", response_model=RunState)
def run_state(run_id: str) -> RunState:
    return _run(run_id).state


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
    run.served_package_hash = hashlib.sha256(body).hexdigest()
    return Response(content=body, media_type="application/json")


@app.post("/runs/{run_id}/decision", response_model=HumanDecision)
async def record_decision(run_id: str, request: HumanDecisionRequest) -> HumanDecision:
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
        decided_by=request.decided_by,
        decided_at=utc_now(),
        notes=request.notes,
        package_hash=run.served_package_hash,
    )
    runtime.bus.publish(run_id, EventType.human_decision_recorded, decision, actor=request.decided_by)
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
    return engine_port.quick_impact(
        runtime.twin(), interventions, brief=request.brief, settings=runtime.settings()
    )


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


@app.get("/replays", response_model=list[ReplayInfo])
def replays() -> list[ReplayInfo]:
    return runs.list_replays()


@app.post("/replays/{name}/play", response_model=ReplayStarted)
async def play_replay(name: str, speed: int = Query(1)) -> ReplayStarted:
    # Query strings arrive as text, which a Literal[1, 2, 4] parameter would reject.
    if speed not in get_args(ReplaySpeed):
        raise HTTPException(status_code=422, detail="speed must be 1, 2 or 4")
    log = runs.load_replay(name)
    if log is None:
        raise HTTPException(status_code=404, detail="Replay not found")
    return ReplayStarted(run_id=runs.play_replay(log, speed), name=name, speed=speed)  # type: ignore[arg-type]
