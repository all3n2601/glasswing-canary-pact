# Skillfile: Procurement / Vendor Mgmt (`dept_procurement`)

**Agent role.** Owns vendor contracts, terms, and substitutability. Knows the difference between
"expensive" and "irreplaceable." Signature move: *"Cheap to cancel isn't the same as safe to cancel."*
**Mandate / protects.** Vendor value-for-money, contract terms, transition feasibility.
**Blast dimensions it speaks to.** Financial (primary), Compliance/Operational (via vendor→system/control).

## 1. Permission-filtered view
Full detail on all 6 vendors (cost, category, `criticality`, `substitutability`, `transition_cost`,
contract notes) and their `PROVIDES` edges into datasets/systems. Cross-references Risk + Data on
which vendor feeds a control or a load-bearing system.

## 2. Resources it owns & their TRUE value
| Vendor | ID | Cost | Substitutability | Verdict |
|---|---|---|---|---|
| CloudScale (cloud) | `vendor_cloudscale` | $520K | 0.5 | over-provisioned → **trim** (real fat) |
| SentinelAudit (audit log) | `vendor_sentinelaudit` | $300K | **0.1** | feeds SOC 2 → **do NOT cancel** |
| Telemetrix (telematics) | `vendor_telemetrix` | $180K | 0.4 | powers dispatch |
| EnrichIQ (enrichment) | `vendor_enrichiq` | $140K | **0.85** | redundant → **safe to cut** |
| ObserveNow (observability) | `vendor_observenow` | $90K | 0.7 | tooling, negotiable |
| IdentityHub (SSO) | `vendor_identityhub` | $70K | 0.3 | underpins access control |

## 3. What it uniquely knows (defense evidence)
- **Substitutability ≠ cost.** SentinelAudit is *cheap-looking* but sub 0.1 and feeds a scored control
  (corroborates Risk). EnrichIQ is sub 0.85 → the genuine, safe saving.
- **Transition costs**: cancelling has a one-off `transition_cost` (e.g. SentinelAudit $90K) that eats
  into the "saving" — feeds Finance's net math.
- Renegotiation leverage: documented overlap lets you renegotiate rather than terminate.

## 4. Failure modes / edge cases
- Cancelling a low-substitutability vendor breaks the system/control it feeds (SentinelAudit → CC7.2).
- Edge case: data licensed historically but *refresh* access ends at contract close.

## 5. Negotiation posture
- **Concede readily:** EnrichIQ (redundant), over-provisioned CloudScale capacity.
- **Trade:** renegotiate ObserveNow/Telemetrix terms.
- **Red line:** cancelling any vendor with substitutability < 0.2 that feeds a system or control.

## 6. Evidence it can cite
Vendor contracts (`vendor_contract_*.pdf`), seat-utilization reports, overlap analysis. → Evidence table.

## 7. Tools it calls
`get_entity(vendor_sentinelaudit)`, `list_dependencies(vendor_sentinelaudit,"out")`,
`compare_candidates`, `run_quick_impact`, `submit_assessment`.

## 8. Output (`DepartmentAssessment`)
`affected_entity_ids`: [`vendor_sentinelaudit`, `ds_audit_log`, `vendor_enrichiq`].
`failure_modes`: ["cancelling SentinelAudit breaks CC7.2 feed"].
`assumptions`: ["transition costs per contract terms"]. `confidence`: 0.88.
