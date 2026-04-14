# Segment 1 — Step-by-Step Setup Guide

## Prerequisites

- Ubuntu 24.04 (your system)
- Python 3.11+ installed (`python3 --version`)
- Git installed
- GCP project created (or will create during Segment 6 deployment)
- No Ollama needed yet — that's Segment 4

---

## Step 1: Create the project folder and venv

```bash
mkdir fairwall && cd fairwall
python3 -m venv venv
source venv/bin/activate
```

> All commands from here run inside the venv. Always `source venv/bin/activate` first in each terminal session.

---

## Step 2: Copy all Segment 1 files into place

Copy every file from the Segment 1 output exactly as given into the folder structure:

```
fairwall/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── core/
│   │   ├── tenant_registry.py
│   │   ├── tenant_middleware.py
│   │   ├── profile_loader.py
│   │   ├── bigquery_client.py
│   │   ├── logger.py
│   │   └── firestore_client.py
│   ├── api/
│   │   └── predict.py
│   ├── profiles/
│   │   ├── hiring.yaml
│   │   ├── lending.yaml
│   │   ├── admissions.yaml
│   │   └── healthcare.yaml
│   └── setup/
│       ├── create_tables.py
│       └── init_firestore.py
├── demo/
│   └── generate_dataset.py
└── segments/
    └── segment-1/
        ├── SUMMARY.md
        └── STEPS.md
```

---

## Step 3: Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

> This installs FastAPI, uvicorn, pydantic, pyyaml, etc.
> BigQuery and Firestore packages are included but won't connect until you set up GCP credentials (Segment 6).

---

## Step 4: Create your .env file

```bash
cp .env.example .env
```

Edit `.env` — for local dev you only need to change:
```
GEMMA_BACKEND=ollama         # already default
APP_ENV=development          # already default
```

Leave GCP fields blank for now — BigQuery and Firestore will gracefully skip when no credentials exist.

---

## Step 5: Create `__init__.py` files

Python needs these to treat folders as packages:

```bash
cd /path/to/fairwall   # project root
touch backend/__init__.py
touch backend/core/__init__.py
touch backend/api/__init__.py
touch backend/setup/__init__.py
touch demo/__init__.py
```

---

## Step 6: Start the server

```bash
cd /path/to/fairwall   # must be run from project root
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

Expected startup output:
```
INFO     FairWall starting up...
INFO     Loaded 4 domain profiles: ['admissions', 'healthcare', 'hiring', 'lending']
INFO     Application startup complete.
INFO     Uvicorn running on http://127.0.0.1:8000
```

---

## Step 7: Verify all pass criteria

Run these in a second terminal (venv activated):

```bash
# 1. Health check — no key needed
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"1.2.0","loaded_domains":["admissions","healthcare","hiring","lending"],"segment":1}

# 2. Protected endpoint with no key → 401
curl http://localhost:8000/tenant-info
# Expected: {"error":"Invalid or missing API key","code":"INVALID_KEY"}

# 3. Valid key → tenant info
curl http://localhost:8000/tenant-info -H "X-API-Key: fw-demo-key-2026"
# Expected: {"tenant_id":"demo","name":"FairWall Demo","allowed_domains":[...]}

# 4. Valid prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: fw-demo-key-2026" \
  -d '{"domain":"hiring","features":{"age":28,"experience":5,"skills_score":0.85},"sensitive_attrs":{"gender":"female"},"prediction":0}'
# Expected: {"prediction_id":"pred_xxxxxxxx","final_decision":"released",...}

# 5. Wrong domain for tenant → 403
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: fw-university-2026" \
  -d '{"domain":"hiring","features":{"age":20},"sensitive_attrs":{"gender":"male"},"prediction":1}'
# Expected: 403 {"error":"Domain 'hiring' is not enabled for this tenant",...}

# 6. Interactive docs
open http://localhost:8000/docs
```

---

## Step 8: Generate the synthetic dataset

```bash
cd /path/to/fairwall
python demo/generate_dataset.py
```

Expected output:
```
Total candidates : 1000
Male             : ~504  selected rate: ~43%
Female           : ~496  selected rate: ~25%
Gender disparity : ~42% lower selection rate for women
Saved to: demo/hiring_dataset.csv
```

---

## Step 9: Initialise GitHub repo

```bash
cd /path/to/fairwall
git init
echo "venv/" > .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
echo ".env" >> .gitignore
echo "demo/hiring_dataset.csv" >> .gitignore
git add .
git commit -m "Segment 1: Foundation + data pipeline"
git remote add origin https://github.com/YOUR_TEAM/fairwall.git
git push -u origin main
```

---

## Checkpoint — before moving to Segment 2

All of these must pass:

- [ ] `GET /health` → 200 with 4 loaded domains
- [ ] `GET /tenant-info` (no key) → 401
- [ ] `GET /tenant-info` (valid key) → 200 with correct tenant name
- [ ] `POST /predict` (valid) → 200 with `pred_` ID
- [ ] `POST /predict` (wrong domain) → 403
- [ ] `python demo/generate_dataset.py` → `demo/hiring_dataset.csv` created
- [ ] `git push` successful — repo is public on GitHub

If all pass → update CLAUDE.md Section 6 Segment 1 status to `[x] Complete` and start Segment 2.
