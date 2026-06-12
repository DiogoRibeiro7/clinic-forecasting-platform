# 10-minute technical demo guide

A script for walking a reviewer through the project end to end, either with a
local Poetry environment or entirely through Docker. Pick one track.

## What the demo shows

1. Synthetic, PHI-free healthcare-network data generation.
2. A global ML demand forecast with calibrated prediction intervals.
3. Conversion of forecasts into costed staffing recommendations.
4. A serving API exposing forecasts, staffing and a marketing what-if.

---

## Track A — local (Poetry)

```bash
# 0. One-time setup (~1-2 min)
make install

# 1. Generate the four contract datasets        (~5 s)
make data

# 2. Run the batch pipeline: forecast + intervals + staffing  (~15 s)
make batch-forecast
#    -> writes outputs/forecasts/latest.csv and outputs/staffing/latest.csv
#    -> registers the model under outputs/model_registry/

# 3. Serve the results
make api
#    -> http://127.0.0.1:8000/docs for interactive docs
```

With the server up, in another terminal:

```bash
curl "http://127.0.0.1:8000/health"
curl "http://127.0.0.1:8000/forecasts?clinic_id=CLINIC_001" | head
curl "http://127.0.0.1:8000/staffing?clinic_id=CLINIC_001" | head
curl -X POST "http://127.0.0.1:8000/scenario/marketing" \
  -H "Content-Type: application/json" \
  -d '{"clinic_ids": ["CLINIC_001"], "spend_multiplier": 2.0}'
```

## Track B — Docker (no local Python)

```bash
# Build the demo image (generates data at build time)   (~2-3 min first build)
make docker-build

# Run the test suite inside the container
make docker-test

# Run the batch pipeline, writing outputs to ./outputs on the host
make docker-batch

# Serve the API (after docker-batch has populated ./outputs)
make docker-api
#    -> http://127.0.0.1:8000/docs
```

The image installs only the main dependency group, so it stays light; the
optional LSTM/TimeGPT extras are deliberately excluded.

---

## The narrative to tell while it runs

- **Data (notebook 01):** "Everything is synthetic and free of patient data,
  but engineered to be *hard* — overdispersed counts, multi-week demand
  episodes, trend breaks, holiday closures. Easy data would make any model
  look good."
- **Model (notebook 04):** "One global model serves the whole network and
  beats the seasonal-naive baseline on every validation fold, at constant
  training cost in the number of clinics."
- **Uncertainty (notebook 04/06):** "Conformal intervals turn past
  out-of-sample errors into a calibrated range, so each clinic gets a safety
  margin sized to its own unpredictability — not a flat guess."
- **Decision (notebook 06):** "The interval upper bound drives a conservative
  staffing plan; we cost it in money against realised demand and compare it
  to the current static roster. That table is the business case."
- **Serving (API):** "All of this is one batch run plus a read-only API — no
  training at request time, no database, runs anywhere the CSV outputs exist."

## For the deepest dive

Open `notebooks/10_executive_summary_forecasting_to_staffing.ipynb` — the
whole story with every number computed live.
