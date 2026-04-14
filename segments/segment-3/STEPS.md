# Segment 3 — Step-by-Step Build Guide

## Prerequisites

- Segment 1 ✅ and Segment 2 ✅ complete and verified on your machine
- `fairlearn`, `scikit-learn`, `pandas`, `numpy` installed in venv
- Server was running fine after Segment 2

---

## Step 1: Copy all Segment 3 files into place

New files to add:
```
backend/core/intervention.py
backend/core/router.py
backend/core/firewall.py
backend/api/review.py
backend/api/interventions.py
```

Updated files (replace existing):
```
backend/api/predict.py      ← full intervention pipeline now wired in
backend/main.py             ← mounts review_router + interventions_router
```

---

## Step 2: Verify main.py has all 4 routers mounted

Open `backend/main.py` and confirm these lines exist:

```python
from backend.api.predict import router as predict_router
from backend.api.metrics import router as metrics_router
from backend.api.review import router as review_router
from backend.api.interventions import router as interventions_router

app.include_router(predict_router, tags=["Predictions"])
app.include_router(metrics_router, tags=["Metrics"])
app.include_router(review_router, tags=["Review Queue"])
app.include_router(interventions_router, tags=["Interventions"])
```

---

## Step 3: Start the server

```bash
cd /path/to/fairwall
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

Expected startup:
```
INFO  FairWall starting up...
INFO  Loaded 4 domain profiles: ['admissions', 'healthcare', 'hiring', 'lending']
INFO  Application startup complete.
INFO  Uvicorn running on http://127.0.0.1:8000
```

---

## Step 4: Verify all pass criteria

### Test 1 — Warm-up still works

```bash
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" -H "X-API-Key: fw-demo-key-2026" \
  -d '{"domain":"hiring","features":{"age":28},"sensitive_attrs":{"gender":"female"},"prediction":0}' \
  | python3 -m json.tool
```

Expected: `"warming_up": true`, `"final_decision": "released"`, `"intervention_type": "none"`

---

### Test 2 — Trigger bias detection + blocking

Send 15 biased predictions (all women rejected):

```bash
for i in {1..15}; do
  curl -s -X POST http://localhost:8000/predict \
    -H "Content-Type: application/json" -H "X-API-Key: fw-demo-key-2026" \
    -d '{"domain":"hiring","features":{"age":28,"skills_score":0.85},"sensitive_attrs":{"gender":"female"},"prediction":0}' \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'pred {'"'"'${i}'"'"'}: score={d[\"trust_score\"]} decision={d[\"final_decision\"]} action={d[\"intervention_type\"]}')"
done
```

Expected after prediction 10: score drops to ~35, `final_decision=blocked`, `intervention_type=block_and_review`

---

### Test 3 — Check review queue

```bash
curl -s "http://localhost:8000/review-queue?domain=hiring" \
  -H "X-API-Key: fw-demo-key-2026" | python3 -m json.tool
```

Expected: `"count": N`, `"items": [...]` with blocked prediction details
Note: Items only appear if Firestore is configured. In dev without GCP credentials,
the review queue will return `"count": 0` — that's expected.

---

### Test 4 — Tenant isolation

```bash
# acme_corp should have empty queue (no predictions sent with acme key)
curl -s "http://localhost:8000/review-queue?domain=hiring" \
  -H "X-API-Key: fw-acme-corp-2026" | python3 -m json.tool
```

Expected: `"count": 0`

---

### Test 5 — Intervention feed

```bash
curl -s "http://localhost:8000/interventions?domain=hiring" \
  -H "X-API-Key: fw-demo-key-2026" | python3 -m json.tool
```

Expected: `"events": [...]` (empty if Firestore not configured)

---

### Test 6 — Open Swagger UI

Go to `http://localhost:8000/docs` — you should see 4 tag groups:
- Predictions: `/predict`, `/tenant-info`
- Metrics: `/trust-score`, `/metrics`
- Review Queue: `/review-queue`, `/resolve`
- Interventions: `/interventions`

---

### Test 7 — Wrong domain → 403

```bash
curl -s "http://localhost:8000/review-queue?domain=hiring" \
  -H "X-API-Key: fw-university-2026"
```

Expected: `{"error": "Domain 'hiring' is not enabled for this tenant", ...}`, HTTP 403

---

## Checkpoint — before moving to Segment 4

- [ ] Server starts cleanly with 4 domain profiles loaded
- [ ] POST /predict with 10+ female rejections → `final_decision=blocked`
- [ ] Blocked predictions have `final_prediction=null`
- [ ] `affected_attribute` and `affected_group` populated in response
- [ ] Balanced predictions → `final_decision=released`, `flagged=false`
- [ ] GET /review-queue → 200, `tenant_id` matches calling key
- [ ] GET /interventions → 200
- [ ] Wrong domain → 403
- [ ] acme_corp queue empty (tenant isolation)
- [ ] `http://localhost:8000/docs` shows all endpoints

If all pass → update CLAUDE.md Section 6 Segment 3 to `[x] Complete` and start Segment 4.

---

## Note on Firestore in local dev

Firestore is not available without GCP credentials. This means:
- `GET /review-queue` returns `count: 0` (no error)
- `GET /interventions` returns `count: 0` (no error)
- `POST /resolve` returns 404 (doc not found)

This is all expected behaviour. The full flow works when deployed to Cloud Run
with GCP credentials set up in Segment 6.

To test Firestore locally, set up Application Default Credentials:
```bash
gcloud auth application-default login
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json
```
