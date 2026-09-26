from contracts_py.agents import AgentContext, AgentSettingsView, AgentSpec
from contracts_py.decision import CandidatePlan, DecisionBrief
from contracts_py.engine import Impact, SimulationResult
from contracts_py.twin import AgentView, OrganizationSettings, Twin

from agent_orchestration.ports import EnginePort


def visible_effects(result: SimulationResult, view: AgentView) -> list[Impact]:
    visible = {e.id for e in view.entities}
    return [i for i in result.impacts if i.affected_entity in visible]


def build_context(spec: AgentSpec, *, run_id: str, brief: DecisionBrief, plan: CandidatePlan, twin: Twin,
                  engine: EnginePort, act_now: SimulationResult, inaction: SimulationResult,
                  settings: OrganizationSettings, known_impact_summaries: list[str] | None = None) -> AgentContext:
    view = engine.build_agent_view(
        twin,
        agent_id=spec.agent_id,
        department_id=spec.department_id,
        visible_entity_types=spec.visible_entity_types,
        visible_sensitivity=spec.visible_sensitivity,
    )
    return AgentContext(
        run_id=run_id,
        agent=spec,
        brief=brief,
        plan=plan,
        view=view,
        act_now_effects=visible_effects(act_now, view),
        inaction_effects=visible_effects(inaction, view),
        known_impact_summaries=known_impact_summaries or [],
        settings=AgentSettingsView(
            risk_appetite=settings.risk_appetite,
            optimizer_objective=settings.optimizer_objective,
            display_currency=settings.display_currency,
            money_display_scale=settings.money_display_scale,
        ),
        max_tool_calls=settings.max_tool_calls,
    )
