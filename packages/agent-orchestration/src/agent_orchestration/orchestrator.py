import logging
import operator
import os
import threading
from datetime import datetime, timezone
from typing import Annotated, Any, Callable, Protocol, TypedDict

from contracts_py.agents import ChallengerOutput, Claim
from contracts_py.decision import CandidatePlan, DecisionBrief, Scenario
from contracts_py.engine import (
    BlastRadius,
    FutureComparison,
    Portfolio,
    PortfolioComparison,
    SimulationResult,
    VendorOverlap,
)
from contracts_py.enums import ActionType, Future, RunStatus
from contracts_py.events import (
    AgentFailed,
    AgentStarted,
    CandidateRejected,
    DependencyValidated,
    EventType,
    PhaseChanged,
    PressureActivated,
    RunFailed,
)
from contracts_py.package import DecisionPackage, Recommendation
from contracts_py.twin import Edge, OrganizationSettings, Twin, VersionInfo
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, TypeAdapter

from agent_orchestration.context import build_context
from agent_orchestration.llm import LLMClient
from agent_orchestration.merge import MergeOutcome, merge
from agent_orchestration.ports import EnginePort
from agent_orchestration.prompts import assemble
from agent_orchestration.roster import CHALLENGER, PROMPT_VERSION, ROSTER, model_tier
from agent_orchestration.router import route_agents

FAILED_STATUSES = {"fallback_cached", "unavailable", "invalid"}
# A fallback answer came from a different prompt, so its department counts as unheard.
MISSING_STATUSES = {"fallback_cached", "unavailable", "invalid"}
PLAN_SOURCE = {"naive": "naive", "recommended": "optimizer", "alternative": "enumerated"}


class Emit(Protocol):
    def __call__(self, type: EventType, payload: BaseModel, *, actor: str, scenario_id: str | None = None,
                 future: Future | None = None) -> None: ...


class RunGraphState(TypedDict, total=False):
    twin: Twin
    twin_changed: bool
    portfolio: PortfolioComparison
    plan: CandidatePlan
    results: dict[Future, SimulationResult]
    routed: list[str]
    outcomes: Annotated[list[MergeOutcome], operator.add]
    new_edges: Annotated[list[Edge], operator.add]
    comparison: FutureComparison
    blasts: dict[Future, BlastRadius]
    package: DecisionPackage


log = logging.getLogger(__name__)
SIM_MODES = ("full", "quick")


def simulation_mode() -> str:
    """CANARY_SIM_MODE picks the engine's simulate mode; full is the default until the engine implements it."""
    mode = os.environ.get("CANARY_SIM_MODE", "full").strip() or "full"
    if mode not in SIM_MODES:
        raise ValueError(f"CANARY_SIM_MODE must be one of {', '.join(SIM_MODES)}, got {mode!r}")
    return mode


class RunFailure(RuntimeError):
    pass


class RunCancelled(RuntimeError):
    pass


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


class _Run:
    def __init__(self, brief: DecisionBrief, twin: Twin, engine: EnginePort, settings: OrganizationSettings,
                 llm: LLMClient, emit: Emit, run_id: str, clock: Callable[[], datetime],
                 should_stop: Callable[[], bool] | None = None, *, challenger: bool = True,
                 agent_evidence: bool = True, feedback: bool = True) -> None:
        self.challenger, self.agent_evidence, self.feedback = challenger, agent_evidence, feedback
        self.sim_mode = simulation_mode()
        self.brief, self.twin, self.engine, self.settings = brief, twin, engine, settings
        self.llm, self.emit, self.run_id, self.clock = llm, emit, run_id, clock
        self.status = RunStatus.created
        self.scenarios: dict[tuple[Future, str | None], Scenario] = {}
        self.engine_issues: list[str] = []
        self.emitted_plans: set[str] = set()
        self.rejected_plans: set[str] = set()
        self.should_stop = should_stop
        self.cancelled = False
        self.lock = threading.Lock()

    def publish(self, kind: EventType, payload: BaseModel, *, actor: str = "orchestrator",
                scenario_id: str | None = None, future: Future | None = None) -> None:
        with self.lock:
            if self.cancelled:
                return
            self.emit(kind, payload, actor=actor, scenario_id=scenario_id, future=future)

    def stop_if_requested(self, where: str) -> None:
        if self.cancelled or (self.should_stop is not None and self.should_stop()):
            # Set under the lock so agents still running in parallel cannot publish afterwards.
            with self.lock:
                self.cancelled = True
            raise RunCancelled(f"run {self.run_id} cancelled before {where}")

    def phase(self, status: RunStatus) -> None:
        # awaiting_approval follows package_ready directly; the package is already out by then.
        if status not in (RunStatus.awaiting_approval, RunStatus.failed):
            self.stop_if_requested(status.value)
        self.publish(EventType.phase_changed, PhaseChanged(from_status=self.status, to_status=status))
        self.status = status

    def scenario(self, future: Future, plan: CandidatePlan | None) -> Scenario:
        plan_id = plan.plan_id if plan and future is not Future.inaction else None
        key = (future, plan_id)
        if key not in self.scenarios:
            scenario = Scenario(
                scenario_id=f"scn_{self.run_id}_{future.value}_{plan_id or 'none'}",
                run_id=self.run_id,
                future=future,
                plan_id=plan_id,
                delay_days=self.brief.delay_days if future is Future.delay else 0,
                baseline_twin_version=self.twin.version.twin_version,
                created_at=self.clock(),
            )
            self.scenarios[key] = scenario
            self.publish(EventType.scenario_created, scenario, scenario_id=scenario.scenario_id, future=future)
        return self.scenarios[key]

    def check(self, obj: Any, twin: Twin) -> None:
        for issue in self.engine.check_result(obj, twin):
            if issue.severity == "error":
                self.engine_issues.append(f"Engine check rule {issue.rule}: {issue.message}")

    def simulate(self, twin: Twin, future: Future, plan: CandidatePlan | None) -> SimulationResult:
        scenario = self.scenario(future, plan)
        result = self.engine.simulate(twin, self.brief, scenario, plan if scenario.plan_id else None, self.sim_mode,
                                      settings=self.settings)
        self.check(result, twin)
        where = {"scenario_id": scenario.scenario_id, "future": future}
        self.publish(EventType.simulation_completed, result, actor="engine", **where)
        for impact in result.impacts:
            self.publish(EventType.impact_computed, impact, actor="engine", **where)
        for constraint in result.constraint_results:
            if not constraint.passed:
                self.publish(EventType.constraint_violated, constraint, actor="engine", **where)
        return result

    def scenario_ids(self, plan: CandidatePlan) -> dict[str, str]:
        return {"act_now": self.scenario(Future.act_now, plan).scenario_id,
                "inaction": self.scenario(Future.inaction, None).scenario_id}

    def run_agent(self, agent_id: str, state: RunGraphState, pass_type: str, summaries: list[str]) -> MergeOutcome:
        spec = ROSTER[agent_id]
        plan, results = state["plan"], state["results"]
        context = build_context(spec, run_id=self.run_id, brief=self.brief, plan=plan, twin=state["twin"],
                                engine=self.engine, act_now=results[Future.act_now],
                                inaction=results[Future.inaction], settings=self.settings,
                                known_impact_summaries=summaries)
        if not self.agent_evidence:
            context = context.model_copy(update={"view": context.view.model_copy(update={"evidence": []})})
        prompt = assemble(agent_id, context)
        self.stop_if_requested(f"the {agent_id} agent call")
        result = self.llm.call(agent_id, prompt.messages, prompt.output_model, prompt_version=PROMPT_VERSION,
                               context=context, fast=model_tier(agent_id) == "fast")
        outcome = merge(agent_id, result, context=context, pass_type=pass_type,  # type: ignore[arg-type]
                        scenario_ids=self.scenario_ids(plan), created_at=self.clock())
        assessment = outcome.assessment
        if assessment.status in FAILED_STATUSES:
            reason = "; ".join(assessment.validation.errors) or assessment.status
            self.publish(EventType.agent_failed, AgentFailed(agent_id=agent_id, reason=reason,
                                                             fallback_used=assessment.status == "fallback_cached"),
                         actor=agent_id)
        self.publish(EventType.agent_completed, assessment, actor=agent_id)
        return outcome

    def plans(self, portfolio: PortfolioComparison) -> list[tuple[CandidatePlan, Portfolio]]:
        entries = [("naive", portfolio.naive)]
        if portfolio.recommended:
            entries.append(("recommended", portfolio.recommended))
        entries += [("alternative", p) for p in portfolio.alternatives]
        seen, plans = set(), []
        for role, item in entries:
            if item.plan_id in seen:
                continue
            seen.add(item.plan_id)
            label = f"{role.capitalize()} plan ({', '.join(item.intervention_ids)})"
            plans.append((CandidatePlan(plan_id=item.plan_id, label=label, intervention_ids=item.intervention_ids,
                                        source=PLAN_SOURCE[role]), item))  # type: ignore[arg-type]
        return plans

    # Nodes

    def validating(self, state: RunGraphState) -> RunGraphState:
        self.phase(RunStatus.validating)
        known = {e.id for e in self.twin.entities}
        pressures = {p.id for p in self.twin.pressures}
        missing = [i.target_entity_id for i in self.brief.candidate_interventions if i.target_entity_id not in known]
        missing += [p for p in self.brief.active_pressure_ids or [] if p not in pressures]
        if missing:
            raise RunFailure(f"brief references ids missing from the twin: {missing}")
        return {"twin": self.twin, "twin_changed": False, "results": {}}

    def building_futures(self, state: RunGraphState) -> RunGraphState:
        self.phase(RunStatus.building_futures)
        inaction = self.simulate(state["twin"], Future.inaction, None)
        for trigger in inaction.pressures_triggered:
            if not trigger.neutralised:
                self.publish(EventType.pressure_activated,
                             PressureActivated(pressure_id=trigger.pressure_id, future=Future.inaction,
                                               expected_cost_usd=trigger.expected_cost_usd),
                             actor="engine", scenario_id=inaction.scenario_id, future=Future.inaction)
        return {"results": {**state["results"], Future.inaction: inaction}}

    def optimizing(self, state: RunGraphState) -> RunGraphState:
        self.phase(RunStatus.optimizing)
        twin = state["twin"]
        portfolio = self.engine.optimize(twin, self.brief, settings=self.settings, run_id=self.run_id)
        self.check(portfolio, twin)
        plans = self.plans(portfolio)
        for plan, item in plans:
            if plan.plan_id not in self.emitted_plans:
                self.emitted_plans.add(plan.plan_id)
                self.publish(EventType.candidate_generated, plan, actor="engine")
            # A plan announced as feasible can become infeasible after re-optimization, so rejection is tracked apart.
            if not item.result.feasible and plan.plan_id not in self.rejected_plans:
                self.rejected_plans.add(plan.plan_id)
                reasons = item.result.rejection_reasons or [
                    c.explanation for c in item.result.constraint_results if c.hard and not c.passed
                ]
                self.publish(EventType.candidate_rejected, CandidateRejected(plan_id=plan.plan_id, reasons=reasons),
                             actor="engine")
        self.publish(EventType.portfolio_ranked, portfolio, actor="engine")
        chosen_id = (portfolio.recommended or portfolio.naive).plan_id
        plan = next(p for p, _ in plans if p.plan_id == chosen_id)
        act_now = self.simulate(twin, Future.act_now, plan)
        return {"portfolio": portfolio, "plan": plan, "results": {**state["results"], Future.act_now: act_now}}

    def running_agents(self, state: RunGraphState) -> RunGraphState:
        self.phase(RunStatus.running_agents)
        routed = route_agents(self.brief, twin=state["twin"], engine=self.engine, settings=self.settings)
        for agent_id in routed:
            self.publish(EventType.agent_started, AgentStarted(agent_id=agent_id, plan_id=state["plan"].plan_id),
                         actor=agent_id)
        return {"routed": routed}

    def fan_out(self, state: RunGraphState) -> list[Send]:
        return [Send("agent", {**state, "agent_id": agent_id}) for agent_id in state["routed"]]

    def agent(self, task: dict[str, Any]) -> RunGraphState:
        return {"outcomes": [self.run_agent(task["agent_id"], task, "first_pass", [])]}  # type: ignore[arg-type]

    def propagate(self, pass_type: str) -> Callable[[RunGraphState], RunGraphState]:
        def node(state: RunGraphState) -> RunGraphState:
            self.phase(RunStatus.propagating)
            known = {(e.source, e.target, e.relation) for e in state["twin"].edges}
            new: list[Edge] = []
            for outcome in state["outcomes"]:
                if outcome.assessment.pass_type != pass_type:
                    continue
                for edge in outcome.validated_edges:
                    if (edge.source, edge.target, edge.relation) in known:
                        continue
                    known.add((edge.source, edge.target, edge.relation))
                    new.append(edge)
                    self.publish(EventType.dependency_validated,
                                 DependencyValidated(assessment_id=outcome.assessment.assessment_id, edge=edge),
                                 actor=outcome.assessment.agent_id)
            if not new or not self.feedback:
                return {}
            twin = self.engine.clone_with_edges(state["twin"], new)
            act_now = self.simulate(twin, Future.act_now, state["plan"])
            return {"twin": twin, "twin_changed": True, "new_edges": new,
                    "results": {**state["results"], Future.act_now: act_now}}

        return node

    def challenging(self, state: RunGraphState) -> RunGraphState:
        self.phase(RunStatus.challenging)
        summaries = [
            f"{o.assessment.agent_id}: act now: {o.assessment.output.act_now_view.summary} "
            f"inaction: {o.assessment.output.inaction_view.summary}"
            for o in state["outcomes"] if o.assessment.output is not None
        ]
        self.publish(EventType.agent_started, AgentStarted(agent_id=CHALLENGER, plan_id=state["plan"].plan_id),
                     actor=CHALLENGER)
        outcome = self.run_agent(CHALLENGER, state, "challenge", summaries)
        challenge = outcome.assessment.challenge
        if challenge is not None and challenge != ChallengerOutput(confidence=challenge.confidence):
            self.publish(EventType.challenge_raised, outcome.assessment, actor=CHALLENGER)
        return {"outcomes": [outcome]}

    def after_challenge(self, state: RunGraphState) -> str:
        return "reoptimizing" if state.get("twin_changed") else "comparing_futures"

    def missing_agents(self, state: RunGraphState) -> list[str]:
        return _unique([o.assessment.agent_id for o in state["outcomes"] if o.assessment.status in MISSING_STATUSES])

    def comparing_futures(self, state: RunGraphState) -> RunGraphState:
        self.phase(RunStatus.comparing_futures)
        twin, plan = state["twin"], state["plan"]
        departments = [d for a in self.missing_agents(state) if (d := ROSTER[a].department_id)]
        if departments:
            twin = self.engine.widen_uncertainty(twin, departments)
        futures = _unique([f.value for f in [Future.act_now, Future.inaction, *self.brief.futures]])
        results = {Future(f): self.simulate(twin, Future(f), plan) for f in futures if f != Future.alternative}
        comparison = self.engine.compare_futures(twin, self.brief, plan, alternatives=[], settings=self.settings,
                                                 run_id=self.run_id)
        self.check(comparison, twin)
        self.publish(EventType.futures_compared, comparison, actor="engine")
        blasts = {}
        for future in (Future.act_now, Future.inaction):
            blast = self.engine.blast_radius(results[future], twin)
            self.check(blast, twin)
            blasts[future] = blast
            self.publish(EventType.blast_radius_ready, blast, actor="engine", scenario_id=blast.scenario_id,
                         future=future)
        return {"twin": twin, "results": results, "comparison": comparison, "blasts": blasts}

    def generating_package(self, state: RunGraphState) -> RunGraphState:
        self.phase(RunStatus.generating_package)
        package = self.build_package(state)
        self.publish(EventType.package_ready, package)
        self.phase(RunStatus.awaiting_approval)
        return {"package": package}

    def vendor_overlaps(self, twin: Twin) -> list[VendorOverlap]:
        vendor_ids = _unique([i.target_entity_id for i in self.brief.candidate_interventions
                              if i.type is ActionType.remove_vendor])
        if not vendor_ids:
            return []
        try:
            return self.engine.vendor_overlap(twin, vendor_ids)
        except Exception as exc:
            # Overlap is supporting detail (bad vendor id, engine not ready); report it, never fail the run for it.
            log.warning("vendor_overlap failed for run %s: %s", self.run_id, type(exc).__name__)
            self.engine_issues.append(f"Engine vendor_overlap: {exc}")
            return []

    def build_package(self, state: RunGraphState) -> DecisionPackage:
        comparison, act_now, blasts = state["comparison"], state["results"][Future.act_now], state["blasts"]
        best = comparison.rows[comparison.best_row_index] if comparison.best_row_index is not None else None
        recommendation = None
        if best is not None and best.plan_id is not None:
            claims = [Claim(text=comparison.headline, source="calculation", ref=comparison.comparison_id)]
            claims += [Claim(text=c.explanation, source="calculation", ref=c.constraint_id)
                       for c in act_now.constraint_results]
            claims += [Claim(text=f"{e.source} {e.relation.value} {e.target}", source="agent_validated",
                             ref=e.evidence_refs[0]) for e in state.get("new_edges", []) if e.evidence_refs]
            recommendation = Recommendation(plan_id=best.plan_id, future=best.future, result_id=best.result_id,
                                            headline=comparison.headline, claims=claims)
        assessments = [o.assessment for o in state["outcomes"]]
        questions = [q.text for a in assessments if a.output for q in a.output.questions]
        twin = state["twin"]
        fields = {
            "package_id": f"pkg_{self.run_id}",
            "run_id": self.run_id,
            "decision_id": self.brief.decision_id,
            "versions": VersionInfo(
                twin_version=twin.version.twin_version,
                settings_version=self.settings.settings_version,
                prompt_version=PROMPT_VERSION,
                model_id=self.llm.model_label,
                engine_version=twin.version.engine_version,
                created_at=self.clock(),
                as_of_date=twin.version.as_of_date,
            ),
            "brief": self.brief,
            "recommendation": recommendation,
            "futures": comparison,
            "portfolios": state["portfolio"],
            "blast_radius_act_now": blasts[Future.act_now],
            "blast_radius_inaction": blasts[Future.inaction],
            "department_impacts": blasts[Future.act_now].departments,
            "critical_risks": [i for i in act_now.impacts if i.severity >= 4],
            "vendor_overlaps": self.vendor_overlaps(twin),
            "assumptions": _unique([*act_now.assumptions, *self.engine_issues]),
            "open_questions": _unique(questions),
            "missing_perspectives": self.missing_agents(state),
            "created_at": self.clock(),
        }
        plain = TypeAdapter(dict[str, Any]).dump_python(fields, mode="json")
        # Person tokens become role IDs here, before the package's own guard sees them.
        return DecisionPackage.model_validate(self.engine.to_role_level(plain, self.twin))

    def graph(self) -> Any:
        graph = StateGraph(RunGraphState)
        nodes: dict[str, Callable[..., Any]] = {
            "validating": self.validating,
            "building_futures": self.building_futures,
            "optimizing": self.optimizing,
            "running_agents": self.running_agents,
            "agent": self.agent,
            "propagating_first_pass": self.propagate("first_pass"),
            "challenging": self.challenging,
            "propagating_challenge": self.propagate("challenge"),
            "reoptimizing": self.optimizing,
            "comparing_futures": self.comparing_futures,
            "generating_package": self.generating_package,
        }
        if not self.challenger:
            del nodes["challenging"], nodes["propagating_challenge"]
        for name, node in nodes.items():
            graph.add_node(name, node)
        graph.add_edge(START, "validating")
        graph.add_edge("validating", "building_futures")
        graph.add_edge("building_futures", "optimizing")
        graph.add_edge("optimizing", "running_agents")
        graph.add_conditional_edges("running_agents", self.fan_out, ["agent"])
        graph.add_edge("agent", "propagating_first_pass")
        targets = ["reoptimizing", "comparing_futures"]
        if self.challenger:
            graph.add_edge("propagating_first_pass", "challenging")
            graph.add_edge("challenging", "propagating_challenge")
            graph.add_conditional_edges("propagating_challenge", self.after_challenge, targets)
        else:
            graph.add_conditional_edges("propagating_first_pass", self.after_challenge, targets)
        graph.add_edge("reoptimizing", "comparing_futures")
        graph.add_edge("comparing_futures", "generating_package")
        graph.add_edge("generating_package", END)
        return graph.compile()


def run_decision(brief: DecisionBrief, *, engine: EnginePort, settings: OrganizationSettings, llm: LLMClient,
                 emit: Emit, run_id: str, twin: Twin,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 should_stop: Callable[[], bool] | None = None, challenger: bool = True,
                 agent_evidence: bool = True, feedback: bool = True) -> DecisionPackage:
    """Raises RunCancelled, with no further events and no package, once should_stop returns True.

    The last three flags exist for evaluation ablations: skip the challenger, hide evidence from agent views,
    or report validated edges without feeding them back into the engine.
    """
    run = _Run(brief, twin, engine, settings, llm, emit, run_id, clock, should_stop, challenger=challenger,
               agent_evidence=agent_evidence, feedback=feedback)
    run.stop_if_requested("run_created")
    run.publish(EventType.run_created, brief)
    try:
        final = run.graph().invoke({}, {"recursion_limit": 50})
    except RunCancelled:
        raise
    except Exception as exc:
        run.phase(RunStatus.failed)
        run.publish(EventType.run_failed, RunFailed(reason=str(exc)))
        raise
    return final["package"]
