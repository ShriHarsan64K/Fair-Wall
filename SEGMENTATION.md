# FAIRWALL — Complete Segmentation Document
## All 6 Build Segments — Reference Guide

> This doc is the master reference for the entire build plan.
> Each segment is self-contained. Build in order.
> Each segment has its own SUMMARY.md (what was built) and STEPS.md (how to build it).

---

## Quick Status Board

| Segment | Name | Files | Deliverable | Status |
|---------|------|-------|-------------|--------|
| 1 | Foundation + Data Pipeline | 15 files | `POST /predict` logs to BigQuery, `/health` works | ✅ Complete |
| 2 | Bias Detection + Trust Score | 5 files | `/trust-score` and `/metrics` return live data | ✅ Complete |
| 3 | Intervention Engine | 7 files | FLAG / ADJUST / BLOCK active, review queue | ✅ Complete |
| 4 | Gemma Explainability + Replay | 14 files | `/explain` and `/replay/demo` working, Gemma fallback active | ✅ Complete |
| 5 | React Dashboard | 11 components | Live Firebase dashboard showing all data | ⬜ Next |
| 6 | Demo Simulator + Cloud Deploy | 4 files | Everything live on Cloud Run + Firebase | ⬜ Pending |

---

## Segment 1 — Foundation + Data Pipeline ✅

**Goal:** The skeleton everything runs on.

**What was built:**
- `backend/main.py` — FastAPI app with `TenantMiddleware`, profile loading at startup
- `backend/core/tenant_registry.py` — 3 hardcoded API keys → tenant map
- `backend/core/tenant_middleware.py` — validates `X-API-Key`, injects `tenant_id` into `request.state`
- `backend/core/profile_loader.py` — loads all YAML profiles into `dict[str, DomainProfile]`
- `backend/core/bigquery_client.py` — BigQuery wrapper (stores full `features` JSON per row)
- `backend/core/logger.py` — `PredictionLogger` with `generate_prediction_id()`
- `backend/core/firestore_client.py` — review queue + intervention feed (tenant-scoped)
- `backend/api/predict.py` — `POST /predict` + `GET /tenant-info`
- `backend/profiles/*.yaml` — 4 domain profiles (hiring, lending, admissions, healthcare)
- `backend/setup/create_tables.py` — BigQuery table creation
- `backend/setup/init_firestore.py` — Firestore collection setup
- `demo/generate_dataset.py` — 1000-row synthetic biased hiring dataset

**Endpoints added:**
```
GET  /health         — public, no key
POST /predict        — logs prediction, returns prediction_id
GET  /tenant-info    — returns tenant name + allowed domains
```

**Pass criteria:**
- `GET /health` → 200, 4 loaded domains
- `POST /predict` valid key → 200, `pred_` ID returned
- `POST /predict` no key → 401
- `POST /predict` wrong domain for tenant → 403
- `python demo/generate_dataset.py` → CSV with ~42% gender disparity

---

## Segment 2 — Bias Detection Engine + Trust Score ✅

**Goal:** Detect bias on every prediction. Score it 0–100. No batching.

**What was built:**
- `backend/core/sliding_window.py` — `SlidingWindowBuffer` using `collections.deque` (built-in)
- `backend/core/metrics.py` — `MetricResult` dataclass, `compute_status()`, `compute_severity()`
- `backend/core/bias_engine.py` — 3 Fairlearn metrics computed after every single prediction
- `backend/core/trust_score.py` — 0–100 weighted `TrustScoreCalculator`, null-safe
- `backend/api/metrics.py` — `GET /trust-score` + `GET /metrics`
- `backend/api/predict.py` — updated to run full bias pipeline

**Endpoints added:**
```
GET /trust-score?domain=X  — current Trust Score, window size, status
GET /metrics?domain=X      — per-metric results with affected group
```

**How the Trust Score works:**
```
score = 100
for each metric:
    if FAIL: score -= weight × 100 × severity
    if WARN: score -= weight ×  40 × severity
score = clamp(round(score), 0, 100)

Weights: demographic_parity=0.40, equal_opportunity=0.35, selection_rate=0.25
```

**Warming-up state:**
```json
{ "trust_score": null, "status": "warming_up", "window_size": 7, "min_for_scoring": 10 }
```

**Pass criteria:**
- First 9 predictions → `warming_up=true`, `trust_score=null`
- Prediction 10 with bias → trust score appears
- Sustained gender bias → score drops to ~35 (critical)
- Balanced predictions → score = 100 (healthy)
- Two tenants → completely separate scores

---

## Segment 3 — Intervention Engine ✅

**Goal:** Bias detected → FairWall takes action. FLAG / ADJUST / BLOCK.

**What was built:**
- `backend/core/intervention.py` — `SeverityClassifier` + 3 handlers
- `backend/core/router.py` — `DecisionRouter` orchestrating everything
- `backend/core/firewall.py` — `@fw.protect` decorator (universal 3-line plug-in)
- `backend/api/review.py` — `GET /review-queue` + `POST /resolve`
- `backend/api/interventions.py` — `GET /interventions`
- `backend/api/predict.py` — updated with full FLAG/ADJUST/BLOCK pipeline
- `backend/main.py` — updated with 2 new routers

**Endpoints added:**
```
GET  /review-queue?domain=X     — blocked decisions pending human review
POST /resolve                   — HR marks a blocked case as resolved
GET  /interventions?domain=X    — real-time intervention event feed
```

**Intervention severity mapping:**
```
Trust Score    Severity    Action              Result
───────────────────────────────────────────────────────────
None (warmup)  NONE        none                Released unchanged
80-100         NONE        none                Released unchanged
50-79          LOW         flag_only           Released, flagged=true
40-49          MEDIUM      adjust_threshold    Low-conf flipped; high-conf flagged
0-39           HIGH        block_and_review    Blocked, added to review queue
2+ FAILs       HIGH        block_and_review    Escalated regardless of score
```

**POST /predict response — new fields in Segment 3:**
```json
{
  "final_decision": "blocked",
  "final_prediction": null,
  "blocked": true,
  "flagged": true,
  "threshold_adjusted": false,
  "intervention_type": "block_and_review",
  "affected_attribute": "gender",
  "affected_group": "female",
  "review_queue_id": "review_a3f2c1d8"
}
```

**Pass criteria:**
- Sustained bias → `final_decision=blocked`, `final_prediction=null`
- Balanced predictions → `final_decision=released`, `flagged=false`
- 2 simultaneous metric FAILs → escalated to HIGH (block)
- `GET /review-queue` → tenant-scoped, never cross-tenant
- Wrong domain → 403

---

## Segment 4 — Gemma Explainability + Replay Engine ⬜

**Goal:** Every flagged decision gets a plain-English explanation. What-If replay makes bias undeniable.

**Files to build:**
- `backend/core/gemma_client.py` — abstract `GemmaClient` base class
- `backend/core/ollama_client.py` — `OllamaGemmaClient` → `POST http://localhost:11434/api/generate`
- `backend/core/vertex_client.py` — `VertexGemmaClient` → Vertex AI endpoint
- `backend/core/explainer.py` — `ExplanationService` — assembles prompt + calls Gemma
- `backend/core/replay_engine.py` — `ReplayEngine.run()` — full 8-step counterfactual
- `backend/prompts/hiring.txt` + `lending.txt` + `admissions.txt`
- `backend/api/explain.py` — `GET /explain/{id}`
- `backend/api/replay.py` — `POST /replay`

**Gemma model swap ladder (your RTX 3050 — 6GB VRAM):**
```
PRIMARY   → gemma4:e4b   (6GB VRAM — best quality, uses all available)
FALLBACK1 → gemma4:e2b   (3GB VRAM — slightly smaller)
FALLBACK2 → gemma3:4b    (3GB VRAM — proven stable, always works)
```
Select via env var: `GEMMA_BACKEND=ollama` (local) or `GEMMA_BACKEND=vertex` (cloud)

**Endpoints to add:**
```
GET  /explain/{prediction_id}   — Gemma explanation for a flagged decision
POST /replay                    — What-If bias replay (counterfactual)
```

**Replay API contract:**
```json
POST /replay
Body: { "prediction_id": "pred_031", "attribute_overrides": {"gender": "male"}, "domain": "hiring" }

Response: {
  "original":       { "gender": "female", "prediction": 0, "label": "REJECTED" },
  "counterfactual": { "gender": "male",   "prediction": 1, "label": "ACCEPTED" },
  "bias_confirmed": true,
  "explanation":    "Identical qualifications. Outcome changed when gender was flipped."
}
```

**Ollama setup (run once on your machine):**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma4:e4b        # primary — 6GB VRAM
ollama pull gemma4:e2b        # fallback1 — 3GB VRAM
ollama pull gemma3:4b         # fallback2 — always works
ollama serve                  # http://localhost:11434
```

**Pass criteria:**
- `GET /explain/{id}` → non-empty explanation string (3 sentences, plain English)
- `POST /replay` flipping gender on blocked female candidate → `bias_confirmed=true`
- `POST /replay` non-existent ID → 404
- Fallback: if `gemma4:e4b` OOM → auto-falls back to `gemma4:e2b`, then `gemma3:4b`

---

## Segment 5 — React Dashboard ⬜

**Goal:** The visual centrepiece. Live Trust Score, bias charts, intervention feed, What-If panel.

**Files to build (all in `frontend/src/`):**
- `App.jsx` — main layout, domain state, 5-second polling
- `api.js` — Axios with `X-API-Key` interceptor from localStorage
- `components/TrustScoreGauge.jsx` — circular gauge, warming-up state
- `components/BiasChart.jsx` — Recharts LineChart, Trust Score history
- `components/InterventionFeed.jsx` — scrolling FLAG/ADJUST/BLOCK log
- `components/MetricsPanel.jsx` — 3 metric cards with PASS/WARN/FAIL badges
- `components/ReviewQueue.jsx` — blocked cases with View/Resolve/What-If buttons
- `components/DomainSwitcher.jsx` — Hiring AI / Lending AI / Admissions tabs
- `components/SimulatorButton.jsx` — triggers `POST /simulate`
- `components/TenantBadge.jsx` — reads key from localStorage → `[🏢 Acme Corp]`
- `components/WhatIfPanel.jsx` — attribute flipper, calls `POST /replay`, shows diff

**Dashboard layout:**
```
┌────────────────────────────────────────────────────────────────┐
│ FairWall   [Hiring AI]  [Lending AI]  [Admissions]  [🏢 Acme] │
├───────────────┬────────────────────────────────────────────────┤
│  TRUST SCORE  │  Bias Trend (per-prediction line chart)        │
│   ◉  67       │  100 ──────╮                                   │
│  WARNING      │   50       ╰──╮                                │
│  (live)       │    0          ╰── now                          │
├───────────────┼────────────────────────────────────────────────┤
│ DPD: 0.23 ✗   │  BLOCK #031 — female bias 34%                 │
│ EOD: 0.18 ✗   │  FLAG  #029 — age disparity 12%               │
│ SRD: 0.09 ✓   │  ADJUST #027 — threshold moved                │
├───────────────┴────────────────────────────────────────────────┤
│  Review Queue                                  [Run Demo]      │
│  #031 Priya S.  BLOCKED  [View] [Resolve] [🔁 What-If]        │
├────────────────────────────────────────────────────────────────┤
│  🔁 WhatIfPanel                                                 │
│  Flip: [Gender ▼]  female → [male ▼]  [▶ Run]                │
│  ORIGINAL: REJECTED  |  COUNTERFACTUAL: ACCEPTED               │
│  ⚠ BIAS CONFIRMED                                              │
└────────────────────────────────────────────────────────────────┘
```

**Setup:**
```bash
cd frontend
npm install
npm start            # localhost:3000
```

**Pass criteria:**
- Dashboard loads with API key from localStorage
- TrustScoreGauge shows "Warming up (N/10)" until 10 predictions sent
- BiasChart updates in real time as simulate runs
- WhatIfPanel returns correct bias_confirmed result
- Domain switcher scopes all panels correctly
- `firebase deploy` → live URL accessible

---

## Segment 6 — Demo Simulator + Cloud Deployment ⬜

**Goal:** Live hackathon demo ready. Everything on Google Cloud.

**Files to build:**
- `demo/simulate_bias.py` — 60 predictions with escalating bias
- `backend/api/simulate.py` — `POST /simulate` server-side trigger
- `Dockerfile` — containerise backend
- `.github/workflows/deploy.yml` — CI/CD on push to main

**Simulate script design:**
```
Predictions 1–15:  clean (balanced gender, all accepted) → Trust Score stays 90+
Predictions 16–35: mild gender bias → Score drops to ~70, FLAGs appear
Predictions 36–60: strong bias → Score ~35, BLOCKs fire
GUARANTEE: at least one BLOCK fires before prediction #20 (Rule 14 from CLAUDE.md)
```

**Cloud deployment:**
```bash
# 1. GCP project
gcloud projects create fairwall-2026
gcloud services enable run.googleapis.com bigquery.googleapis.com \
  firestore.googleapis.com aiplatform.googleapis.com firebase.googleapis.com

# 2. BigQuery + Firestore
bq mk --dataset fairwall-2026:fairwall_logs
python backend/setup/create_tables.py
python backend/setup/init_firestore.py

# 3. Backend on Cloud Run
docker build -t gcr.io/fairwall-2026/api .
docker push gcr.io/fairwall-2026/api
gcloud run deploy fairwall-api \
  --image gcr.io/fairwall-2026/api \
  --platform managed --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMMA_BACKEND=vertex,GCP_PROJECT=fairwall-2026

# 4. Frontend on Firebase
cd frontend && npm run build
firebase init hosting && firebase deploy

# 5. Update .env
REACT_APP_API_URL=https://fairwall-api-xxxx.run.app
REACT_APP_DEFAULT_KEY=fw-demo-key-2026
```

**Pass criteria:**
- `GET https://[cloud-run-url]/health` → 200
- Simulate script runs against Cloud Run URL end-to-end
- At least one BLOCK fires before prediction #20
- Firebase dashboard loads and polls Cloud Run API
- Demo video recorded — 3 minutes following demo script
- GitHub repo public with complete README

---

## 3-Minute Judge Demo Script

| Time | Say | Show |
|------|-----|------|
| 0:00–0:20 | "Every company using AI to make decisions about people is flying blind on fairness. FairWall fixes that." | Dashboard, Trust Score=95, TenantBadge="FairWall Demo" |
| 0:20–0:40 | "Any AI plugs in with 3 lines of code. No retraining, no changes." | `@fw.protect` decorator code |
| 0:40–0:50 | "Each company gets an isolated instance via API key." | Switch TenantBadge to "Acme Corp" |
| 0:50–1:20 | "I'll inject bias into their hiring AI. Watch the Trust Score — updates on every prediction." | Run Simulation → score drops 95 → 78 → 61 → 43 |
| 1:20–1:40 | "Trust Score 41. Two metrics failed. FairWall is blocking decisions." | BLOCK #031 in feed |
| 1:40–2:00 | "Gemma explains it in plain English. This is what HR sees." | Click #031 → explanation |
| 2:00–2:25 | "I'll flip her gender to male. Same CV. Watch." | What-If → REJECTED → ACCEPTED → BIAS CONFIRMED |
| 2:25–2:40 | "Same person. Same CV. Different gender. Different outcome." | Hold on WhatIfPanel |
| 2:40–3:00 | "One system. Any AI. Any domain. Google free tier." | Lending AI tab + GitHub URL |

---

## Submission Checklist

| Item | Status |
|------|--------|
| Challenge selected | ✅ [Unbiased AI Decision] |
| PPT deck (PDF) | ✅ FairWall_AI_Prototype_Submission.pptx |
| Solution overview | ⬜ Copy from CLAUDE.md Section 11 |
| Live prototype link | ⬜ Firebase URL after Segment 6 |
| GitHub repo (public) | ⬜ Create after Segment 1 |
| Demo video (3 min) | ⬜ Record after Segment 6 |
| Google Cloud deployed | ⬜ Cloud Run + Firebase |
| Google AI model used | ⬜ Gemma 2B via Vertex AI |

---

## Key Commands Reference

```bash
# Start backend
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# Start frontend (Segment 5+)
cd frontend && npm start

# Gemma local (Segment 4+)
ollama pull gemma4:e4b && ollama serve

# Run demo simulation
python demo/simulate_bias.py --api-url http://localhost:8000 --api-key fw-demo-key-2026

# Test pipeline manually (after 10+ predictions)
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" -H "X-API-Key: fw-demo-key-2026" \
  -d '{"domain":"hiring","features":{"age":28,"skills_score":0.85},"sensitive_attrs":{"gender":"female"},"prediction":0}'

curl "http://localhost:8000/trust-score?domain=hiring" -H "X-API-Key: fw-demo-key-2026"
curl "http://localhost:8000/metrics?domain=hiring" -H "X-API-Key: fw-demo-key-2026"
curl "http://localhost:8000/review-queue?domain=hiring" -H "X-API-Key: fw-demo-key-2026"
curl "http://localhost:8000/interventions?domain=hiring" -H "X-API-Key: fw-demo-key-2026"
```

---

*FairWall — AI Fairness Firewall | Build with AI, Solution Challenge 2026*
*Team: Madhusuthanan G, Gaggula Eshwara Aryan, Rohith A, Shri Harsan M*
