# Segment 3 — Intervention Engine
## SUMMARY

**Status:** ✅ Complete — 12/12 tests passed

---

## What was built

The full FLAG / ADJUST / BLOCK intervention engine. FairWall now intercepts biased decisions
before they are released. Every POST /predict goes through the complete pipeline:
detect bias → compute trust score → classify severity → intervene.

---

## Files created / updated

| File | What it does |
|------|-------------|
| `backend/core/intervention.py` | `SeverityClassifier` + 3 handlers: `FlagHandler`, `ThresholdAdjuster`, `BlockAndRouteHandler` |
| `backend/core/router.py` | `DecisionRouter` — maps severity to handler, writes Firestore + BigQuery |
| `backend/core/firewall.py` | `@fw.protect` decorator — universal 3-line plug-in for any Python AI model |
| `backend/api/review.py` | `GET /review-queue` + `POST /resolve` — human review queue endpoints |
| `backend/api/interventions.py` | `GET /interventions` — real-time intervention feed for dashboard |
| `backend/api/predict.py` | Updated — full FLAG/ADJUST/BLOCK pipeline wired in |
| `backend/main.py` | Updated — review + interventions routers mounted |

---

## API endpoints active after Segment 3

| Method | Path | What it does |
|--------|------|-------------|
| `POST` | `/predict` | Full pipeline — returns `final_decision`, `blocked`, `intervention_type` |
| `GET` | `/trust-score?domain=X` | Current Trust Score + status |
| `GET` | `/metrics?domain=X` | Per-metric fairness results |
| `GET` | `/review-queue?domain=X` | Blocked decisions awaiting human review |
| `POST` | `/resolve` | Mark a review case as resolved |
| `GET` | `/interventions?domain=X` | Real-time intervention event feed |
| `GET` | `/health` | Server status |
| `GET` | `/tenant-info` | Calling tenant's name + allowed domains |

---

## How intervention severity maps to actions

| Trust Score | Severity | Action | Result |
|-------------|----------|--------|--------|
| None (warmup) | NONE | none | Prediction released unchanged |
| 80–100 | NONE | none | Prediction released unchanged |
| 50–79 | LOW | flag_only | Released with `flagged=true` tag |
| 40–49 | MEDIUM | adjust_threshold | Low-conf rejections flipped; high-conf flagged |
| 0–39 | HIGH | block_and_review | Blocked, added to Firestore review queue |
| Any + 2 FAILs | HIGH (escalated) | block_and_review | 2 simultaneous metric FAILs always escalate |

---

## Pass criteria — all verified ✅

- [x] Warm-up predictions → `final_decision=released`, `intervention_type=none`
- [x] Strong bias at prediction 10 → `blocked`, `action=block_and_review`
- [x] Sustained bias → `final_decision=blocked`, `final_prediction=None`
- [x] `affected_attribute=gender`, `affected_group=female` populated in response
- [x] Balanced predictions → `score=100`, `final_decision=released`, no intervention
- [x] `GET /review-queue` → 200, tenant-scoped
- [x] `GET /review-queue` wrong domain → 403
- [x] `GET /interventions` → 200, tenant-scoped
- [x] `POST /resolve` → valid HTTP response
- [x] Tenant isolation → acme_corp review queue shows 0 items
- [x] `ThresholdAdjuster` flips low-confidence rejections at MEDIUM severity
- [x] `SeverityClassifier` escalates to HIGH on 2+ simultaneous metric FAILs

---

## What Segment 4 builds on top of this

Adds Gemma explainability — every flagged/blocked decision gets a plain-English explanation.
Also adds the What-If Bias Replay engine (`POST /replay`) for the judge demo.
