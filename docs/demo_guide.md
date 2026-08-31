# 10-minute technical demo guide

A script for walking a reviewer through the project end to end, either with a
local Poetry environment or entirely through Docker. Pick one track.

## What the demo shows

1. Synthetic, PHI-free healthcare-network data generation.
2. Fixed-origin recursive demand forecasting with calibrated uncertainty.
3. A prospectively frozen capacity-aware hybrid staffing policy.
4. A versioned read-only API that exposes both the legacy and hybrid contracts.

---

## Track A — local (Poetry)

```bash
# 0. One-time setup
make install

# 1. Generate the four contract datasets
make data

# 2a. Run the legacy completed-visits batch path
make batch-forecast

# 2b. Run the operational role-specific hybrid path
poetry run python scripts/run_role_specific_batch.py --horizon 28

# 3. Serve the results
make api
# -> http://127.0.0.1:8000/docs
```

The hybrid path writes:

```text
outputs/role_specific/forecasts/latest.csv
outputs/role_specific/staffing/latest.csv
outputs/role_specific/monitoring/latest.csv
```

With the server up, in another terminal:

```bash
# Legacy compatibility surface
curl "http://127.0.0.1:8000/health"
curl "http://127.0.0.1:8000/forecasts?clinic_id=CLINIC_001" | head
curl "http://127.0.0.1:8000/staffing?clinic_id=CLINIC_001" | head

# Versioned hybrid surface
curl "http://127.0.0.1:8000/v2/health"
curl "http://127.0.0.1:8000/v2/forecasts?clinic_id=CLINIC_001" | head
curl "http://127.0.0.1:8000/v2/staffing?clinic_id=CLINIC_001" | head
curl "http://127.0.0.1:8000/v2/hybrid-monitoring" | head
```

## Track B — Docker

```bash
make docker-build
make docker-test
make docker-batch
make docker-api
```

The existing Docker convenience path demonstrates the legacy batch contract.
For the hybrid decision path, run `scripts/run_role_specific_batch.py` in the
same project environment before starting the API.

---

## The narrative to tell while it runs

- **Data:** "Everything is synthetic and free of patient data, but engineered
  to include overdispersion, demand episodes, changepoints, closures and
  capacity censoring."
- **Evaluation:** "The primary contract is fixed-origin multi-day forecasting.
  The complete holdout horizon is forecast recursively; realised future targets
  never become lag inputs."
- **Uncertainty:** "Split-conformal intervals are calibrated from the same
  recursive rolling-fold residuals used by deployment-style forecasts."
- **Target problem:** "Completed visits are throughput, but on busy days they
  are capacity-censored and can understate the demand clinical staffing needs
  to serve."
- **Decision evidence:** "We first benchmarked completed visits against
  reconstructed attended demand, then benchmarked staffing consequences, then
  froze a prospective switch before testing it. We did not tune the switch
  after seeing the result."
- **Hybrid policy:** "Clinical staffing uses completed visits by default and
  switches to attended demand only when the completed-visits 90% upper
  conformal bound reaches known clinic capacity. Front desk always uses
  scheduled appointments."
- **Result:** "Across four outer folds, the frozen hybrid reduced unmet demand
  by about 9.31% versus completed-visits-only staffing for about 0.70% higher
  total cost, and it strictly beat attended-demand-only staffing overall on
  both cost and unmet demand."
- **Limitation:** "The trigger is useful, not magical: it also fires on some
  uncensored days, and all decision evidence is synthetic."
- **Serving:** "The old API contract remains unchanged. `/v2` exposes the
  hybrid artefacts and enough fields to audit why a target was selected. The
  API trains nothing and recomputes no decision at request time."

## Evidence to open during review

- `reports/evidence/capacity_target_benchmark/RESULTS.md`
- `reports/evidence/staffing_decision_benchmark/interpretation.md`
- `reports/evidence/hybrid_policy_benchmark/RESULT.md`
- `docs/hybrid_policy.md`
- `docs/api_v2_contract.md`
- `reports/model_card.md`

For the original notebook narrative, open
`notebooks/10_executive_summary_forecasting_to_staffing.ipynb`. Treat its older
single-target staffing story as historical context where it differs from the
committed hybrid evidence above.
