from datetime import datetime, timezone
from typing import Any

from contracts_py.decision import DecisionBrief
from contracts_py.enums import Future, RunStatus
from contracts_py.events import (
    AgentStarted,
    CandidateRejected,
    Event,
    EventLog,
    EventType,
    PhaseChanged,
    PressureActivated,
)
from contracts_py.twin import VersionInfo

from canary_api.stubs import results
from canary_api.stubs.twin import sample_brief, stub_twin

SAMPLE_RUN_ID = "run_sample"

PHASES = [
    RunStatus.created,
    RunStatus.validating,
    RunStatus.building_futures,
    RunStatus.optimizing,
    RunStatus.running_agents,
    RunStatus.propagating,
    RunStatus.challenging,
    RunStatus.propagating,
    RunStatus.comparing_futures,
    RunStatus.generating_package,
    RunStatus.awaiting_approval,
]


def stub_run_events(brief: DecisionBrief, run_id: str, versions: VersionInfo | None = None) -> list[Event]:
    versions = versions or stub_twin().version
    decision_id = brief.decision_id
    story = results.story(decision_id)
    naive_plan, recommended_plan = story.naive_plan, story.recommended_plan
    plans = {p.plan_id: p for p in results.plans(decision_id)}
    futures = results.future_results(run_id, decision_id)
    phase = iter(zip(PHASES, PHASES[1:]))
    steps: list[tuple[EventType, Any, str, str | None, Future | None]] = []

    def emit(kind: EventType, payload: Any, actor: str = "orchestrator", scenario_id: str | None = None,
             future: Future | None = None) -> None:
        steps.append((kind, payload, actor, scenario_id, future))

    def advance() -> None:
        before, after = next(phase)
        emit(EventType.phase_changed, PhaseChanged(from_status=before, to_status=after))

    def scenario(future: Future, plan_id: str | None) -> None:
        s = results.scenario(run_id, future, plan_id)
        emit(EventType.scenario_created, s, scenario_id=s.scenario_id, future=future)

    emit(EventType.run_created, brief, actor="api")
    advance()
    advance()
    scenario(Future.inaction, None)
    inaction = futures[Future.inaction]
    for trigger in inaction.pressures_triggered:
        emit(EventType.pressure_activated,
             PressureActivated(pressure_id=trigger.pressure_id, future=Future.inaction,
                               expected_cost_usd=trigger.expected_cost_usd),
             actor="engine", scenario_id=inaction.scenario_id, future=Future.inaction)
    advance()
    emit(EventType.candidate_generated, plans[naive_plan], actor="engine")
    emit(EventType.candidate_rejected,
         CandidateRejected(plan_id=naive_plan, reasons=[story.rejection]),
         actor="engine")
    emit(EventType.candidate_generated, plans[recommended_plan], actor="engine")
    emit(EventType.portfolio_ranked, results.portfolio_comparison(run_id, decision_id), actor="engine")
    scenario(Future.act_now, recommended_plan)
    scenario(Future.delay, recommended_plan)
    advance()
    first_pass = [a for a in results.STUB_AGENTS if a != "challenger"]
    for agent_id in first_pass:
        emit(EventType.agent_started, AgentStarted(agent_id=agent_id, plan_id=recommended_plan), actor=agent_id)
    for agent_id in first_pass:
        emit(EventType.agent_completed, results.assessment(run_id, agent_id), actor=agent_id)
    advance()
    act_now = futures[Future.act_now]
    emit(EventType.simulation_completed, act_now, actor="engine", scenario_id=act_now.scenario_id, future=Future.act_now)
    advance()
    emit(EventType.agent_started, AgentStarted(agent_id="challenger", plan_id=recommended_plan), actor="challenger")
    emit(EventType.agent_completed, results.assessment(run_id, "challenger"), actor="challenger")
    advance()
    for result in futures.values():
        emit(EventType.simulation_completed, result, actor="engine", scenario_id=result.scenario_id, future=result.future)
    advance()
    emit(EventType.futures_compared, results.future_comparison(run_id, decision_id), actor="engine")
    for blast in (results.act_now_blast_radius(run_id, decision_id), results.inaction_blast_radius(run_id, decision_id)):
        emit(EventType.blast_radius_ready, blast, actor="engine", scenario_id=blast.scenario_id, future=blast.future)
    advance()
    emit(EventType.package_ready, results.decision_package(run_id, brief, versions))
    advance()

    return [
        Event(
            event_id=f"evt_{run_id}_{sequence}",
            run_id=run_id,
            sequence=sequence,
            type=kind,
            actor=actor,
            scenario_id=scenario_id,
            future=future,
            # One fixed wall-clock second per event inside 17:00; the sample run stays under 60 events.
            timestamp=datetime(2026, 9, 26, 17, 0, sequence, tzinfo=timezone.utc),
            payload=payload,
        )
        for sequence, (kind, payload, actor, scenario_id, future) in enumerate(steps, start=1)
    ]


def sample_run() -> EventLog:
    return EventLog(stub_run_events(sample_brief(), SAMPLE_RUN_ID))
