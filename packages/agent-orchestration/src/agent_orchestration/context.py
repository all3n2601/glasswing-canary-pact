import os

from contracts_py.agents import AgentContext, AgentSettingsView, AgentSpec
from contracts_py.decision import CandidatePlan, DecisionBrief
from contracts_py.engine import Impact, SimulationResult
from contracts_py.twin import AgentView, OrganizationSettings, Twin

from agent_orchestration.ports import EnginePort

DEFAULT_CONTEXT_HOPS = 2


def context_hops() -> int:
    value = os.environ.get("CANARY_AGENT_CONTEXT_HOPS", "").strip()
    if not value:
        return DEFAULT_CONTEXT_HOPS
    hops = int(value)
    if hops < 0:
        raise ValueError(f"CANARY_AGENT_CONTEXT_HOPS must be 0 or more, got {hops}")
    return hops


def visible_effects(result: SimulationResult, view: AgentView) -> list[Impact]:
    visible = {e.id for e in view.entities}
    return [i for i in result.impacts if i.affected_entity in visible]


def _impact_entity_ids(impacts: list[Impact]) -> set[str]:
    return {i for impact in impacts for i in (impact.affected_entity, impact.source_entity, *impact.dependency_path)}


def trim_view(view: AgentView, *, twin: Twin, engine: EnginePort, brief: DecisionBrief, department_id: str | None,
              impacts: list[Impact], hops: int) -> AgentView:
    """Keeps what is near the decision for this agent: a filter over the view, never adding hidden entities.

    Kept: entities within `hops` edges of the brief's intervention targets or the agent's department, every entity
    an engine impact names, and entities a kept evidence snippet names (so a documented but unmodelled link,
    such as a planted missing dependency, stays discoverable). Edges need both ends kept; evidence needs a
    kept entity, edge or impact citing it (or its document), and documents need kept evidence or entities.
    """
    visible = {e.id: e for e in view.entities}
    # Hops are graph edges from the intervention targets and from the agent's department node.
    depth = {i.target_entity_id: hops for i in brief.candidate_interventions}
    if department_id:
        depth.setdefault(department_id, hops)
    kept = (set(depth) | _impact_entity_ids(impacts)) & set(visible)
    for seed, seed_hops in sorted(depth.items()):
        if seed in visible and seed_hops:
            for edge in engine.list_dependencies(twin, seed, "both", seed_hops):
                kept |= {edge.source, edge.target} & set(visible)

    # Person tokens link to roles by role_id rather than by edges; a kept role keeps its (HR-visible) tokens.
    kept |= {e.id for e in view.entities if e.role_id and e.role_id in kept}

    names = {entity_id: {entity_id.lower(), visible[entity_id].name.lower()} for entity_id in visible}
    in_scope = set(kept)
    evidence = []
    for record in view.evidence:
        snippet = record.snippet.lower()
        mentioned = {entity_id for entity_id, labels in names.items() if any(label in snippet for label in labels)}
        cited = any(record.id in visible[entity_id].evidence_refs for entity_id in in_scope)
        if cited or mentioned & in_scope:
            evidence.append(record)
            kept |= mentioned
    edges = [e for e in view.edges if e.source in kept and e.target in kept]
    cited = {ref for e in edges for ref in e.evidence_refs} | {ref for i in impacts for ref in i.evidence_refs}
    evidence += [r for r in view.evidence if r.id in cited and r not in evidence]
    evidence_docs = {r.document_id for r in evidence}
    documents = [d for d in view.documents if d.id in evidence_docs or set(d.covers_entity_ids) & kept]
    doc_ids = {d.id for d in documents}
    evidence += [r for r in view.evidence if r.document_id in doc_ids and r not in evidence]
    return view.model_copy(update={
        "entities": [e for e in view.entities if e.id in kept],
        "edges": edges,
        "evidence": [r for r in view.evidence if r in evidence],
        "documents": documents,
    })


def build_context(spec: AgentSpec, *, run_id: str, brief: DecisionBrief, plan: CandidatePlan, twin: Twin,
                  engine: EnginePort, act_now: SimulationResult, inaction: SimulationResult,
                  settings: OrganizationSettings, known_impact_summaries: list[str] | None = None,
                  hops: int | None = None, trim: bool = True) -> AgentContext:
    full_view = engine.build_agent_view(
        twin,
        agent_id=spec.agent_id,
        department_id=spec.department_id,
        visible_entity_types=spec.visible_entity_types,
        visible_sensitivity=spec.visible_sensitivity,
    )
    act_now_effects, inaction_effects = visible_effects(act_now, full_view), visible_effects(inaction, full_view)
    view = full_view
    if trim:
        view = trim_view(full_view, twin=twin, engine=engine, brief=brief, department_id=spec.department_id,
                         impacts=[*act_now_effects, *inaction_effects],
                         hops=context_hops() if hops is None else hops)
    return AgentContext(
        run_id=run_id,
        agent=spec,
        brief=brief,
        plan=plan,
        view=view,
        act_now_effects=act_now_effects,
        inaction_effects=inaction_effects,
        known_impact_summaries=known_impact_summaries or [],
        settings=AgentSettingsView(
            risk_appetite=settings.risk_appetite,
            optimizer_objective=settings.optimizer_objective,
            display_currency=settings.display_currency,
            money_display_scale=settings.money_display_scale,
        ),
        max_tool_calls=settings.max_tool_calls,
    )
