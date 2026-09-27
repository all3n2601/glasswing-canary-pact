import hashlib
import logging
import operator
import os
import threading
from datetime import datetime, timezone
from typing import Annotated, Any, Callable, Literal, Protocol, TypedDict

from contracts_py.agents import AgentContext, ChallengerOutput, Claim
from contracts_py.decision import CandidatePlan, DecisionBrief, Intervention, Scenario
from contracts_py.engine import (
    BlastRadius,
    FutureComparison,
    Portfolio,
    PortfolioComparison,
    MissingQuestion,
    MitigationComparison,
    SimulationResult,
    VendorOverlap,
)
from contracts_py.enums import ActionType, Future, Polarity, RunStatus
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
from agent_orchestration.discussion import MAX_ISSUES_PER_AGENT, MAX_RESPONSE_AGENTS, review_issues, visible_issues
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
    mitigations: list[MitigationComparison]
    package: DecisionPackage
    response_contexts: dict[str, AgentContext]


log = logging.getLogger(__name__)
SIM_MODES = ("full", "quick")


def simulation_mode() -> str:
    """CANARY_SIM_MODE picks the engine's simulate mode; full (expected value until Monte Carlo lands) is the default."""
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


MAX_ID_LENGTH = 80


def bounded_id(prefix: str, body: str) -> str:
    """``prefix + body``, or ``prefix`` plus a hash of ``body`` when that would pass the 80-character ID limit."""
    # Same scheme as simulation_engine's bounded_id, so the engine and the orchestrator name a scenario alike.
    candidate = prefix + body
    if len(candidate) <= MAX_ID_LENGTH:
        return candidate
    return prefix + hashlib.sha256(body.encode()).hexdigest()[:24]


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
        self.compared_alternatives: list[str] = []
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
                scenario_id=bounded_id("scn_", f"{self.run_id}_{future.value}_{plan_id or 'none'}"),
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
        leveled = self.engine.to_role_level(result, twin)
        result = leveled if isinstance(leveled, SimulationResult) else SimulationResult.model_validate(leveled)
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

    def run_agent(self, agent_id: str, state: RunGraphState, pass_type: Literal["first_pass", "challenge", "response"], summaries: list[str],
                  response_context: AgentContext | None = None) -> MergeOutcome:
        spec = ROSTER[agent_id]
        plan, results = state["plan"], state["results"]
        context = response_context or build_context(spec, run_id=self.run_id, brief=self.brief, plan=plan, twin=state["twin"],
                                engine=self.engine, act_now=results[Future.act_now],
                                inaction=results[Future.inaction], settings=self.settings,
                                known_impact_summaries=summaries)
        if not self.agent_evidence:
            context = context.model_copy(update={"view": context.view.model_copy(update={"evidence": []})})
        # The prompt carries the trimmed context; the merge validates against the agent's full permitted view.
        full_view = self.engine.build_agent_view(
            state["twin"], agent_id=spec.agent_id, department_id=spec.department_id,
            visible_entity_types=spec.visible_entity_types, visible_sensitivity=spec.visible_sensitivity)
        if not self.agent_evidence:
            full_view = full_view.model_copy(update={"evidence": []})
        prompt = assemble(agent_id, context)
        self.stop_if_requested(f"the {agent_id} agent call")
        result = self.llm.call(agent_id, prompt.messages, prompt.output_model, prompt_version=PROMPT_VERSION,
                               context=context, fast=model_tier(agent_id) == "fast")
        outcome = merge(agent_id, result, context=context, pass_type=pass_type,  # type: ignore[arg-type]
                        scenario_ids=self.scenario_ids(plan), created_at=self.clock(), known_view=full_view)
        assessment = outcome.assessment
        if assessment.status in FAILED_STATUSES:
            reason = "; ".join(assessment.validation.errors) or assessment.status
            self.publish(EventType.agent_failed, AgentFailed(agent_id=agent_id, reason=reason,
                                                             plan_id=plan.plan_id, pass_type=pass_type,
                                                             fallback_used=assessment.status == "fallback_cached"),
                         actor=agent_id)
        self.publish(EventType.agent_completed, assessment, actor=agent_id)
        return outcome

    def compare_alternatives(self, portfolio: PortfolioComparison, plan: CandidatePlan) -> list[CandidatePlan]:
        """The optimizer's feasible alternatives, or at least its first-listed one, so futures compare real options."""
        options = [(p, item) for p, item in self.plans(portfolio)
                   if p.source == "enumerated" and p.plan_id != plan.plan_id]
        feasible = [p for p, item in options if item.result.feasible]
        return feasible or [p for p, _ in options[:1]]

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
        known.update(c.department_id for c in self.brief.organization_changes if c.operation == "create")
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
            f"{o.assessment.agent_id} (assessment_id={o.assessment.assessment_id}): act now: {o.assessment.output.act_now_view.summary} "
            f"inaction: {o.assessment.output.inaction_view.summary}"
            for o in state["outcomes"] if o.assessment.output is not None
        ]
        self.publish(EventType.agent_started, AgentStarted(agent_id=CHALLENGER, plan_id=state["plan"].plan_id,
                                                         pass_type="challenge"),
                     actor=CHALLENGER)
        outcome = self.run_agent(CHALLENGER, state, "challenge", summaries)
        challenge = outcome.assessment.challenge
        if challenge is not None and challenge != ChallengerOutput(confidence=challenge.confidence):
            self.publish(EventType.challenge_raised, outcome.assessment, actor=CHALLENGER)
        return {"outcomes": [outcome]}

    def preparing_responses(self, state: RunGraphState) -> RunGraphState:
        assessments = [o.assessment for o in state["outcomes"]]
        issues = review_issues(assessments)
        originals = {a.assessment_id: a for a in assessments}
        contexts: dict[str, AgentContext] = {}
        for issue in issues:
            prior = originals[issue.target_assessment_id]
            if prior.agent_id in contexts:
                continue
            context = build_context(ROSTER[prior.agent_id], run_id=self.run_id, brief=self.brief,
                                    plan=state["plan"], twin=state["twin"], engine=self.engine,
                                    act_now=state["results"][Future.act_now],
                                    inaction=state["results"][Future.inaction], settings=self.settings)
            assigned = visible_issues([i for i in issues if i.target_assessment_id == prior.assessment_id], context)
            if not assigned:
                continue
            contexts[prior.agent_id] = context.model_copy(update={
                "review_issues": assigned[:MAX_ISSUES_PER_AGENT],
                "previous_assessment_id": prior.assessment_id, "previous_output": prior.output,
            })
            if len(contexts) == MAX_RESPONSE_AGENTS:
                break
        if contexts:
            self.phase(RunStatus.running_agents)
        for agent_id, context in contexts.items():
            self.publish(EventType.agent_started, AgentStarted(agent_id=agent_id, plan_id=state["plan"].plan_id,
                         pass_type="response", review_issues=context.review_issues), actor=agent_id)
        return {"response_contexts": contexts}

    def response_routes(self, state: RunGraphState) -> list[Send] | str:
        if not state["response_contexts"]:
            return self.after_challenge(state)
        return [Send("response", {**state, "agent_id": agent_id, "response_context": context})
                for agent_id, context in state["response_contexts"].items()]

    def response(self, task: dict[str, Any]) -> RunGraphState:
        return {"outcomes": [self.run_agent(task["agent_id"], task, "response", [], task["response_context"])]}  # type: ignore[arg-type]

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
        alternatives = self.compare_alternatives(state["portfolio"], plan)
        self.compared_alternatives = [a.plan_id for a in alternatives]
        comparison = self.engine.compare_futures(twin, self.brief, plan, alternatives=alternatives,
                                                 settings=self.settings, run_id=self.run_id)
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

    def engine_issue(self, name: str, exc: Exception) -> None:
        log.warning("%s failed for run %s: %s", name, self.run_id, type(exc).__name__)
        self.engine_issues.append(f"Engine {name}: {exc}")

    def plans_by_id(self, state: RunGraphState) -> dict[str, CandidatePlan]:
        plans = {plan.plan_id: plan for plan, _ in self.plans(state["portfolio"])}
        plans[state["plan"].plan_id] = state["plan"]
        return plans

    @staticmethod
    def applicable_mitigations(catalog: list[Intervention], result: SimulationResult) -> list[Intervention]:
        """Catalog entries aimed at what the plan's own act-now result shows as harmed; the engine has no finder."""
        harmed = {w.workflow_id for w in result.workflow_coverage if w.stranded}
        harmed |= {k.knowledge_id for k in result.knowledge_coverage if k.lost}
        harmed |= {i.affected_entity for i in result.impacts if i.polarity is Polarity.harm}
        return [m for m in catalog if m.target_entity_id in harmed]

    def mitigating(self, state: RunGraphState) -> RunGraphState:
        self.phase(RunStatus.mitigating)
        twin, portfolio = state["twin"], state["portfolio"]
        try:
            catalog = self.engine.load_mitigation_catalog(None, twin)
        except Exception as exc:
            self.engine_issue("load_mitigation_catalog", exc)
            catalog = []
        plans = self.plans_by_id(state)
        # The naive plan and the plan under consideration, each judged on its own act-now result.
        candidates = {portfolio.naive.plan_id: portfolio.naive.result,
                      state["plan"].plan_id: state["results"][Future.act_now]}
        comparisons: list[MitigationComparison] = []
        for plan_id, result in candidates.items():
            actions = self.applicable_mitigations(catalog, result)
            if not actions:
                continue
            try:
                comparison = self.engine.mitigate(twin, self.brief, plans[plan_id], actions, settings=self.settings,
                                                  run_id=self.run_id)
            except Exception as exc:
                self.engine_issue("mitigate", exc)
                continue
            self.check(comparison, twin)
            self.publish(EventType.mitigation_applied, comparison, actor="engine", future=Future.act_now)
            comparisons.append(comparison)
        return {"mitigations": comparisons}

    def missing_information(self, state: RunGraphState, recommendation: Recommendation | None) -> list[MissingQuestion]:
        plans = self.plans_by_id(state)
        if recommendation is None or recommendation.plan_id is None:
            plan = plans[state["portfolio"].naive.plan_id]
        else:
            plan = plans.get(recommendation.plan_id, state["plan"])
        try:
            questions = self.engine.missing_questions(state["twin"], self.brief, plan, settings=self.settings,
                                                      run_id=self.run_id)
        except Exception as exc:
            self.engine_issue("missing_questions", exc)
            return []
        if questions:
            self.publish(EventType.question_selected, questions[0], actor="engine")
        return questions

    @staticmethod
    def _entity_name(twin: Twin, entity_id: str) -> str:
        return next((e.name for e in twin.entities if e.id == entity_id), entity_id)

    def _describe_action(self, action: Intervention, twin: Twin, removed: set[str]) -> str:
        target = self._entity_name(twin, action.target_entity_id)
        replacement = action.params.get("replacement_vendor_id")
        if action.type == "add_replacement_feed" and replacement:
            # The vendor the plan removes that currently provides this feed: one edge lookup, no traversal.
            source = next((self._entity_name(twin, e.source) for e in twin.edges
                           if e.target == action.target_entity_id and e.source in removed and e.relation.value == "PROVIDES"),
                          None)
            origin = f" from {source}" if source else ""
            return f"Migrate {target}{origin} to {self._entity_name(twin, str(replacement))}"
        return f"{str(action.type).replace('_', ' ').capitalize()} for {target}"

    # How a group of same-type mitigations reads in a headline: (singular noun, plural noun) after a verb.
    ACTION_PHRASES = {
        "document_runbook": ("document", "runbook", "runbooks"),
        "reassign_owner": ("reassign", "owner", "owners"),
        "reassign_on_call": ("reassign", "on-call rota", "on-call rotas"),
        "add_replacement_feed": ("add", "replacement feed", "replacement feeds"),
        "resequence_project": ("resequence", "project", "projects"),
        "retain_capacity_temporarily": ("temporarily retain capacity in", "team", "teams"),
    }

    def _action_summary(self, actions: list[Intervention], steps: list[str]) -> str:
        """Replacement feeds are named one by one; other mitigations are counted by type."""
        parts = [step[0].lower() + step[1:] for step, a in zip(steps, actions) if step.startswith("Migrate ")]
        counts: dict[str, int] = {}
        for step, action in zip(steps, actions):
            if not step.startswith("Migrate "):
                counts[str(action.type)] = counts.get(str(action.type), 0) + 1
        for kind, count in counts.items():
            verb, one, many = self.ACTION_PHRASES.get(kind, (kind.replace("_", " "), "item", "items"))
            parts.append(f"{verb} {count} {one if count == 1 else many}")
        return ", ".join(parts)

    def mitigated_recommendation(self, state: RunGraphState, mitigations: list[MitigationComparison],
                                 best: Any) -> Recommendation | None:
        """A feasible mitigated plan wins when the engine's own net value beats the best unmitigated row."""
        # Only a mitigation of a plan with an act-now futures row can be recommended: that row and its assessments
        # are what the package shows, and the mitigated plan rides along in mitigated_plan_id.
        base_rows = {row.plan_id: row for row in state["comparison"].rows if row.future is Future.act_now and row.plan_id}
        winner = None
        for comparison in mitigations:
            if comparison.plan_id_before not in base_rows:
                continue
            value = comparison.after.value.net_value_usd
            beats_best = best is None or value > best.net_value_p50_usd
            if comparison.feasible_after and beats_best and (
                    winner is None or value > winner.after.value.net_value_usd):
                winner = comparison
        if winner is None:
            return None
        twin, before, after = state["twin"], winner.before, winner.after
        plans = self.plans_by_id(state)
        parent = plans.get(winner.plan_id_before)
        removed = {i.target_entity_id for i in self.brief.candidate_interventions
                   if parent and i.id in parent.intervention_ids}
        steps = [self._describe_action(a, twin, removed) for a in winner.actions]
        restored = [self._entity_name(twin, e) for e in winner.restored_entity_ids]
        conditions = [n for n in after.assumptions if n.startswith("Conditionally feasible")]
        count = len(winner.actions)
        risk = (f"Engine risk {before.risk.score:.1f} ({before.risk.level.value}) before, "
                f"{after.risk.score:.1f} ({after.risk.level.value}) after.")
        lead = f"Proceed with {count} mitigation{'s' if count != 1 else ''} first: {self._action_summary(winner.actions, steps)}."
        if not winner.feasible_before:
            # The engine only calls the plan feasible under conditions; its full condition note is the first claim.
            headline = (f"{lead} The plan becomes conditionally feasible with coverage restored for "
                        f"{len(restored)} entit{'ies' if len(restored) != 1 else 'y'}. {risk}")
        else:
            headline = f"{lead} {risk}"
        claims = [Claim(text=note, source="calculation", ref=after.result_id) for note in conditions]
        claims += [Claim(text=f"{step} ({a.id}: {a.type} on {a.target_entity_id})", source="calculation", ref=a.id)
                   for step, a in zip(steps, winner.actions)]
        claims += [Claim(text=f"Restores {name}", source="calculation", ref=entity_id)
                   for name, entity_id in zip(restored, winner.restored_entity_ids)]
        claims.append(Claim(text=f"Engine risk score {before.risk.score:.1f} ({before.risk.level.value}) before "
                                 f"mitigation, {after.risk.score:.1f} ({after.risk.level.value}) after",
                            source="calculation", ref=after.result_id))
        claims.append(Claim(text=f"Engine net value with mitigations: {after.value.net_value_usd:,} USD",
                            source="calculation", ref=after.result_id))
        return Recommendation(plan_id=winner.plan_id_before, future=Future.act_now, action="proceed_with_mitigations",
                              result_id=base_rows[winner.plan_id_before].result_id, headline=headline, claims=claims,
                              mitigated_plan_id=winner.plan_id_after, mitigated_result_id=after.result_id)

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
        if best is not None:
            claims = [Claim(text=comparison.headline, source="calculation", ref=comparison.comparison_id)]
            if best.plan_id is not None:
                claims += [Claim(text=c.explanation, source="calculation", ref=c.constraint_id)
                           for c in act_now.constraint_results]
            else:
                # Doing nothing wins: the act-now plan's broken constraints are the reasons, in the engine's words.
                claims += [Claim(text=c.explanation, source="calculation", ref=c.constraint_id)
                           for c in act_now.constraint_results if not c.passed]
            claims += [Claim(text=f"{e.source} {e.relation.value} {e.target}", source="agent_validated",
                             ref=e.evidence_refs[0]) for e in state.get("new_edges", []) if e.evidence_refs]
            recommendation = Recommendation(plan_id=best.plan_id, future=best.future, result_id=best.result_id,
                                            headline=comparison.headline, claims=claims)
        mitigations = state.get("mitigations", [])
        recommendation = self.mitigated_recommendation(state, mitigations, best) or recommendation
        missing = self.missing_information(state, recommendation)
        assessments = [o.assessment for o in state["outcomes"]]
        # The engine's most valuable missing fact leads; agent questions and review concerns follow.
        questions = [q.text for q in missing[:1]] + [q.text for a in assessments if a.output for q in a.output.questions]
        # Retain unanswered and unrouted criticisms; a model's supported/revised position is not a resolution.
        for assessment in assessments:
            review = assessment.challenge or assessment.output
            if review is not None:
                questions += [f"Review concern ({assessment.agent_id}): {o.text}" for o in review.objections]
            if assessment.challenge:
                questions += [f"Review concern ({assessment.agent_id}): {f.text}" for f in [
                    *assessment.challenge.unsupported_assumptions, *assessment.challenge.circular_logic,
                    *assessment.challenge.inaction_underestimated]]
            if assessment.output:
                questions += [f"Unresolved response ({assessment.agent_id}): {r.explanation}"
                              for r in assessment.output.review_replies if r.position == "unresolved"]
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
            "mitigations": mitigations,
            "missing_information": missing,
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
            "preparing_responses": self.preparing_responses,
            "response": self.response,
            "propagating_response": self.propagate("response"),
            "reoptimizing": self.optimizing,
            "comparing_futures": self.comparing_futures,
            "mitigating": self.mitigating,
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
            graph.add_edge("propagating_challenge", "preparing_responses")
        else:
            graph.add_edge("propagating_first_pass", "preparing_responses")
        graph.add_conditional_edges("preparing_responses", self.response_routes, ["response", *targets])
        graph.add_edge("response", "propagating_response")
        graph.add_conditional_edges("propagating_response", self.after_challenge, targets)
        graph.add_edge("reoptimizing", "comparing_futures")
        graph.add_edge("comparing_futures", "mitigating")
        graph.add_edge("mitigating", "generating_package")
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
