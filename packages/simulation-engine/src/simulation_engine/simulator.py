from hashlib import sha256

from company_twin import CompanyTwin, build_graph, downstream_paths, entity_map

from .models import Impact, ImpactLevel, ScenarioRequest, ScenarioResult, Severity


def _severity(importance: float, substitutability: float) -> Severity:
    risk = importance * (1 - substitutability)
    if risk >= 0.8:
        return Severity.CRITICAL
    if risk >= 0.5:
        return Severity.HIGH
    if risk >= 0.25:
        return Severity.MEDIUM
    return Severity.LOW


def simulate(twin: CompanyTwin, request: ScenarioRequest) -> ScenarioResult:
    graph = build_graph(twin)
    entities = entity_map(twin)
    impacts: list[Impact] = []
    violations: list[str] = []
    gross_savings = 0.0
    transition_cost = 0.0

    for entity_id in request.remove_entity_ids:
        entity = entities.get(entity_id)
        if entity is None:
            violations.append(f"Unknown resource: {entity_id}")
            continue

        gross_savings += entity.annual_cost_usd or 0
        transition_cost += float(
            (entity.one_time_exit_cost_usd or 0) + (entity.migration_cost_usd or 0)
        )
        if entity.criticality.value == "critical":
            violations.append(f"{entity.name} is marked as a critical resource")

        for target_id, path in downstream_paths(graph, entity_id).items():
            target = entities[target_id]
            first_edge = graph.edges[path[0], path[1]]
            distance = len(path) - 1
            level = (
                ImpactLevel.DIRECT
                if distance == 1
                else ImpactLevel.INDIRECT
                if distance == 2
                else ImpactLevel.SECOND_ORDER
            )
            department = target.department_id or "company-wide"
            impacts.append(
                Impact(
                    entity_id=target_id,
                    department=department,
                    description=f"Removing {entity.name} affects {target.name}",
                    level=level,
                    severity=_severity(
                        float(first_edge["strength"]),
                        float(first_edge["substitutability"]),
                    ),
                    confidence=float(first_edge["confidence"]),
                    path=path,
                )
            )

    net_savings = gross_savings - transition_cost
    if net_savings < request.savings_target:
        violations.append(
            f"Net savings ${net_savings:,.0f} do not reach the "
            f"${request.savings_target:,.0f} target"
        )

    critical_impacts = [impact for impact in impacts if impact.severity == Severity.CRITICAL]
    if critical_impacts:
        violations.append("Scenario creates at least one critical downstream impact")

    status = "feasible" if not violations else "infeasible"
    digest = sha256(request.model_dump_json().encode()).hexdigest()[:12]
    recommendation = (
        "Proceed to human review with monitoring and rollback conditions."
        if status == "feasible"
        else "Do not proceed unchanged; evaluate substitutions or mitigations."
    )
    return ScenarioResult(
        scenario_id=f"scenario_{digest}",
        status=status,
        gross_savings=gross_savings,
        transition_cost=transition_cost,
        net_savings=net_savings,
        impacts=impacts,
        violations=violations,
        recommendation=recommendation,
    )
