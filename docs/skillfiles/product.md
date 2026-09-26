# Product - agent `product`

**Represents / protects.** Roadmap, product analytics, and the transformation projects. In the vendor
demo it owns two of the seven vendors and the unique account-intelligence data.
**Blast dimensions.** Business, Operational, Financial.

## Owns (twin ids)
- `dept_product`; roles `role_pm`, `role_product_lead`, `role_ux`
- workflow `wf_product_analytics`; knowledge `kn_roadmap_context`; dataset `ds_usage`
- vendors `vendor_echo` (EchoMarket), `vendor_flux` (FluxBehavior)
- projects `proj_billing_modernization`, `proj_soc2_type2`

## Hidden dependencies it uniquely knows (defense)
- **EchoMarket is redundant on most of its data but unique on one.** Its firmographics, intent and
  market-intel overlap ApexData and CinderSignals, but `ds_account_intel` is unique to EchoMarket and
  feeds product analytics. So EchoMarket can be terminated
  only after `ds_account_intel` is migrated (the plan's migrate-before-terminate step).
- **FluxBehavior is genuinely unique** (`ds_usage` for product analytics) and low overlap - not a safe cut.

## Failure modes
- Terminating EchoMarket without migrating `ds_account_intel` loses account intelligence.
- Cutting FluxBehavior removes product-usage data with no substitute.

## Negotiation posture
- **Concede:** the redundant parts of EchoMarket (firmographics / intent / market-intel already covered
  by Apex and Cinder), once account_intel is migrated.
- **Trade:** resequence `proj_soc2_type2` if no control is at risk.
- **Red line:** dropping `ds_account_intel` or FluxBehavior usage data without a replacement.

## Evidence it can cite
Vendor data-catalog lineage, product-analytics feature registry, project charters.
