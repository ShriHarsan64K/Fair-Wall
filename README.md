# FairWall — AI Fairness Firewall

> "Every network has a firewall. FairWall is the missing fairness layer for AI."

**Build with AI — Solution Challenge 2026** | [Unbiased AI Decision] Challenge

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-cyan)](https://react.dev)
[![Google Cloud](https://img.shields.io/badge/Google_Cloud-Run-orange)](https://cloud.google.com/run)
[![Gemma](https://img.shields.io/badge/Google_AI-Gemma_4-red)](https://ai.google.dev/gemma)

---

## What is FairWall?

FairWall is a **real-time AI fairness middleware** that sits between any AI model and its output, intercepting biased decisions **before** they reach people.

Unlike existing tools (IBM OpenScale, Azure Monitor, Fairlearn) that audit bias *after* decisions are made, FairWall is **prospective** — it catches and blocks bias at inference time.

```
WITHOUT FAIRWALL:
AI Model → biased decision released → person harmed → audit discovers bias (too late)

WITH FAIRWALL:
AI Model → FairWall intercepts → bias detected → decision blocked → human review → fair outcome
```

---

## Key Features

| Feature | Description |
|---------|-------------|
| **3-Line Integration** | Any Python AI wraps with `@fw.protect` — no model changes |
| **Real-Time Sliding Window** | Trust Score updates after every prediction — no batch delays |
| **FLAG / ADJUST / BLOCK** | Three-tier intervention engine, proportional to severity |
| **Gemma Explainability** | Plain-English explanations for every flagged decision |
| **What-If Bias Replay** | Flip gender/age/race → see if outcome changes → confirm bias |
| **Multi-Tenant Isolation** | API keys scope each company's data completely separately |
| **4 Domain Profiles** | Hiring (EEOC), Lending (ECOA), Admissions (Title IX), Healthcare (FDA) |

---

## Live Demo

**Dashboard:** [Firebase URL — coming after deployment]

**API:** [Cloud Run URL — coming after deployment]

**Demo video:** [3-minute walkthrough — coming soon]

---

## Architecture

```
Client AI Model
      │  POST /predict
      ▼
FairWall API  (FastAPI — Google Cloud Run)
      │
      ├── Tenant Auth Gate        X-API-Key → tenant isolation
      ├── Prediction Logger       BigQuery — full features JSON stored
      ├── Bias Detection Engine   Fairlearn — DPD, EOD, SRD on sliding window
      ├── Trust Score Calculator  0–100 weighted score, per-prediction
      ├── Intervention Engine     FLAG / ADJUST / BLOCK
      ├── Gemma Explainability    gemma4:e4b → plain English explanation
      └── Bias Replay Engine      What-If counterfactual pipeline
      │
      ├── BigQuery  ← audit log (tenant_id on every row)
      └── Firestore ← human review queue (tenant-scoped)

Dashboard (React — Firebase Hosting)
  Trust Score Gauge | Bias Chart | Intervention Feed | Review Queue | WhatIfPanel
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend)
- Ollama (for local Gemma)

### Backend

```bash
# 1. Clone and setup
git clone https://github.com/ShriHarsan64K/Fair-Wall.git
cd Fair-Wall

# 2. Create venv
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Create .env from example
cp backend/.env.example backend/.env
# Edit backend/.env — set GEMMA_BACKEND=ollama for local dev

# 5. Create __init__.py files
touch backend/__init__.py backend/core/__init__.py backend/api/__init__.py backend/setup/__init__.py demo/__init__.py

# 6. Start backend
uvicorn backend.main:app --reload --port 8000
```

### Verify it's working
```bash
curl http://localhost:8000/health
# → {"status":"ok","version":"1.2.0","loaded_domains":["admissions","healthcare","hiring","lending"]}

# Send a test prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: fw-demo-key-2026" \
  -d '{"domain":"hiring","features":{"age":28,"skills_score":0.85},"sensitive_attrs":{"gender":"female"},"prediction":0}'
```

### Local Gemma (optional but recommended)
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull models (swap ladder for 6GB VRAM)
ollama pull gemma4:e4b     # Primary — 6GB VRAM
ollama pull gemma4:e2b     # Fallback — 3GB VRAM
ollama pull gemma3:4b      # Safe fallback — always works

ollama serve               # http://localhost:11434
```

### Frontend (Lovable — React + TypeScript)
```bash
# Install bun (faster than npm for this project)
curl -fsSL https://bun.sh/install | bash

cd Fair-Wall  # repo root
bun install
bun dev
# Dashboard at http://localhost:5173
```

---

## Integration — 3 Lines of Code

```python
from backend.core.firewall import FairWall

fw = FairWall(domain="hiring", sensitive_attrs=["gender", "age"], api_key="fw-acme-corp-2026")

@fw.protect
def my_hiring_model(candidate_features, **kwargs):
    return sklearn_model.predict(candidate_features)

# Every prediction now automatically:
# - Logged to BigQuery
# - Checked for bias (Fairlearn metrics on sliding window)
# - Trust Score computed (0-100)
# - Intervention applied (FLAG/ADJUST/BLOCK)
# - Gemma explanation generated if flagged
# - Dashboard updated live
```

**Or via HTTP API (any language):**
```bash
curl -X POST https://fairwall-api.run.app/predict \
  -H "X-API-Key: fw-acme-corp-2026" \
  -d '{"domain":"hiring","features":{...},"sensitive_attrs":{"gender":"female"},"prediction":0}'
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check (no auth) |
| `POST` | `/predict` | Submit prediction — runs full pipeline |
| `GET` | `/trust-score?domain=X` | Current Trust Score + status |
| `GET` | `/metrics?domain=X` | Per-metric fairness results |
| `GET` | `/review-queue?domain=X` | Blocked decisions for human review |
| `POST` | `/resolve` | Mark a review case as resolved |
| `GET` | `/interventions?domain=X` | Real-time intervention feed |
| `GET` | `/explain/{id}` | Gemma explanation for a prediction |
| `POST` | `/replay` | What-If bias replay (requires BigQuery) |
| `POST` | `/replay/demo` | What-If replay without BigQuery |
| `GET` | `/tenant-info` | Calling tenant's name + allowed domains |

Full docs: `http://localhost:8000/docs` (Swagger UI)

---

## Demo API Keys

| Key | Tenant | Domains |
|-----|--------|---------|
| `fw-demo-key-2026` | FairWall Demo | All 4 domains |
| `fw-acme-corp-2026` | Acme Corp | Hiring + Lending |
| `fw-university-2026` | State University | Admissions only |

---

## Trust Score Explained

```
Score = 100
For each metric:
  if FAIL: score -= weight × 100 × severity
  if WARN: score -= weight ×  40 × severity

Weights: DPD=0.40  EOD=0.35  SRD=0.25

80–100 → HEALTHY  — system is fair, no intervention
50–79  → WARNING  — bias building, FLAG interventions active
40–49  → WARNING  — MEDIUM severity, threshold adjustment active
0–39   → CRITICAL — BLOCK interventions, human review queue active
2+ FAILs simultaneously → always escalate to BLOCK regardless of score
```

---

## Gemma Model Swap Ladder

FairWall automatically falls back through models based on available VRAM:

```
PRIMARY   gemma4:e4b  — 6GB VRAM — best quality
FALLBACK1 gemma4:e2b  — 3GB VRAM
FALLBACK2 gemma3:4b   — 3GB VRAM — always works
FALLBACK3 template    — no GPU   — hardcoded response
```

Configure in `backend/.env`:
```
GEMMA_BACKEND=ollama          # local dev
GEMMA_BACKEND=vertex          # Cloud Run production
```

---

## Project Structure

```
Fair-Wall/
├── backend/                  # FastAPI backend
│   ├── main.py               # App entry point
│   ├── requirements.txt
│   ├── .env.example
│   ├── core/                 # Core modules
│   │   ├── bias_engine.py    # Fairlearn metrics
│   │   ├── trust_score.py    # 0-100 scoring
│   │   ├── intervention.py   # FLAG/ADJUST/BLOCK
│   │   ├── router.py         # Decision routing
│   │   ├── firewall.py       # @fw.protect decorator
│   │   ├── explainer.py      # Gemma explanations
│   │   ├── replay_engine.py  # What-If counterfactual
│   │   ├── sliding_window.py # Per-prediction buffer
│   │   └── ...
│   ├── api/                  # FastAPI endpoints
│   ├── profiles/             # Domain YAML configs
│   ├── prompts/              # Gemma prompt templates
│   └── setup/                # BigQuery/Firestore setup
├── src/                      # React frontend (Lovable)
│   ├── components/fairwall/  # Dashboard components
│   └── hooks/                # API hooks
├── demo/                     # Demo scripts + datasets
├── segments/                 # Build documentation
├── Dockerfile                # Cloud Run container
├── SEGMENTATION.md           # Full build plan
└── README.md
```

---

## Deployment — Google Cloud

```bash
# 1. Create GCP project
gcloud projects create fairwall-2026
gcloud config set project fairwall-2026
gcloud services enable run.googleapis.com bigquery.googleapis.com \
  firestore.googleapis.com aiplatform.googleapis.com firebase.googleapis.com

# 2. Setup data stores
bq mk --dataset fairwall-2026:fairwall_logs
python backend/setup/create_tables.py
python backend/setup/init_firestore.py

# 3. Deploy backend to Cloud Run
docker build -t gcr.io/fairwall-2026/api .
docker push gcr.io/fairwall-2026/api
gcloud run deploy fairwall-api \
  --image gcr.io/fairwall-2026/api \
  --platform managed --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMMA_BACKEND=vertex,GCP_PROJECT=fairwall-2026

# 4. Deploy frontend to Firebase
bun run build
firebase init hosting && firebase deploy
```

---

## Team

| Name | Role | Email |
|------|------|-------|
| Madhusuthanan G | Team Lead | madhusudhanan0001@gmail.com |
| Gaggula Eshwara Aryan | Developer | aryanyagami490@gmail.com |
| Rohith A | Developer | steele.d.aaron@gmail.com |
| Shri Harsan M | Developer | shriharsang@gmail.com |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI (Python 3.11) |
| Bias Metrics | Fairlearn + AIF360 |
| AI Explainability | Google Gemma 4 (Ollama local / Vertex AI cloud) |
| Audit Log | Google BigQuery |
| Review Queue | Google Firestore |
| Backend Host | Google Cloud Run |
| Frontend | React 18 + TypeScript + Tailwind + Recharts |
| Frontend Host | Firebase Hosting |
| ML Models | Scikit-learn (demo) |

---

*FairWall — Build with AI, Solution Challenge 2026*
*Every network has a firewall. FairWall is the missing fairness layer for AI.*
