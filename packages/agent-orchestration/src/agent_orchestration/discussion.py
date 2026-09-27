"""Route one bounded response round using explicit references to prior assessments."""

import hashlib

from contracts_py.agents import AgentAssessment, AgentContext, ReviewIssue

from agent_orchestration.roster import ROSTER

MAX_RESPONSE_AGENTS = 3
MAX_ISSUES_PER_AGENT = 3


def review_issues(assessments: list[AgentAssessment]) -> list[ReviewIssue]:
    first = sorted((a for a in assessments if a.pass_type == "first_pass" and a.status == "ok" and a.output),
                   key=lambda a: a.agent_id)
    issues = []
    for source in sorted(assessments, key=lambda a: a.assessment_id):
        if source.status != "ok" or source.pass_type == "response":
            continue
        output = source.challenge or source.output
        if output is None:
            continue
        candidates = [(f"objections.{n}", o.text, o.severity, [o.target_ref], [], [])
                      for n, o in enumerate(output.objections)]
        if source.challenge:
            for field in ("unsupported_assumptions", "circular_logic", "inaction_underestimated"):
                for n, finding in enumerate(getattr(source.challenge, field)):
                    candidates.append((f"{field}.{n}", finding.text, finding.severity,
                                       finding.entity_ids, finding.entity_ids, finding.evidence_refs))
        for field, text, severity, targets, entities, evidence in candidates:
            for target in first:
                if source.agent_id == target.agent_id:
                    continue
                assert target.output is not None
                owned = {target.assessment_id, target.agent_id, ROSTER[target.agent_id].department_id,
                         *target.output.affected_entities}
                if not owned.intersection(targets):
                    continue
                token = f"{source.assessment_id}:{field}:{target.assessment_id}"
                issues.append(ReviewIssue(
                    issue_id="issue_" + hashlib.sha256(token.encode()).hexdigest()[:24],
                    source_assessment_id=source.assessment_id, source_agent_id=source.agent_id,
                    source_ref=field, target_assessment_id=target.assessment_id,
                    text=text, severity=severity, entity_ids=entities, evidence_refs=evidence,
                ))
    return sorted(issues, key=lambda issue: (-issue.severity, issue.issue_id))


def visible_issues(issues: list[ReviewIssue], context: AgentContext) -> list[ReviewIssue]:
    """Never broaden a recipient's access to share another agent's criticism."""
    entities = {e.id for e in context.view.entities}
    evidence = {e.id for e in context.view.evidence}
    sensitivity = set(context.agent.visible_sensitivity)
    return [issue for issue in issues
            if set(ROSTER[issue.source_agent_id].visible_sensitivity) <= sensitivity
            and set(issue.entity_ids) <= entities and set(issue.evidence_refs) <= evidence]
