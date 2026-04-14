# Segment 4 — Step-by-Step Build Guide

## Prerequisites

- Segments 1, 2, 3 complete and verified on your machine
- Server running fine after Segment 3
- `requests` installed in venv: `pip install requests`

---

## Step 1: Install Ollama (one-time setup)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull Gemma models — swap ladder for your RTX 3050
ollama pull gemma4:e4b        # PRIMARY — 6GB VRAM, best quality
ollama pull gemma4:e2b        # FALLBACK1 — 3GB VRAM
ollama pull gemma3:4b         # FALLBACK2 — always works

# Start Ollama server (keep this running in a separate terminal)
ollama serve
# Runs at http://localhost:11434
```

**Verify Ollama is working:**
```bash
curl http://localhost:11434/api/generate \
  -d '{"model":"gemma4:e4b","prompt":"In one sentence: what is fairness in AI?","stream":false}'
```

---

## Step 2: Copy all Segment 4 files into place

New files:
```
backend/core/gemma_client.py
backend/core/ollama_client.py
backend/core/vertex_client.py
backend/core/explainer.py
backend/core/replay_engine.py
backend/prompts/hiring.txt
backend/prompts/lending.txt
backend/prompts/admissions.txt
backend/prompts/healthcare.txt
backend/prompts/replay.txt
backend/api/explain.py
backend/api/replay.py
```

Updated files (replace existing):
```
backend/api/predict.py    — Gemma explanation now generated for flagged/blocked
backend/main.py           — explain_router + replay_router mounted
```

---

## Step 3: Update your .env file

```bash
# Gemma backend
GEMMA_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434

# Model swap ladder
GEMMA_MODEL_PRIMARY=gemma4:e4b
GEMMA_MODEL_FALLBACK1=gemma4:e2b
GEMMA_MODEL_FALLBACK2=gemma3:4b
```

---

## Step 4: Install requests (if not already installed)

```bash
source venv/bin/activate
pip install requests
```

---

## Step 5: Start the server

```bash
cd /path/to/fairwall
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

Expected: 6 routers mounted, 4 profiles loaded.

---

## Step 6: Verify all pass criteria

### Test 1 — Send biased predictions and check for explanation

```bash
# Send 15 biased predictions (women rejected)
for i in {1..15}; do
  curl -s -X POST http://localhost:8000/predict \
    -H "Content-Type: application/json" \
    -H "X-API-Key: fw-demo-key-2026" \
    -d '{"domain":"hiring","features":{"age":28,"skills_score":0.85,"experience":5},"sensitive_attrs":{"gender":"female"},"prediction":0}' \
    | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'pred {'"'"'${i}'"'"'}: decision={d[\"final_decision\"]} expl_len={len(d[\"explanation\"]) if d[\"explanation\"] else 0}')
if d['explanation']:
    print(f'  → {d[\"explanation\"][:100]}...')
"
done
```

Expected after prediction 10: `decision=blocked`, explanation appears (from Gemma or template).

---

### Test 2 — GET /explain/{id}

```bash
# Get a prediction_id from the output above, then:
curl "http://localhost:8000/explain/pred_XXXXXXXX" \
  -H "X-API-Key: fw-demo-key-2026" | python3 -m json.tool
```

Expected: `{"explanation": "...", "source": "gemma" or "demo_fallback", ...}`

---

### Test 3 — POST /replay/demo (What-If — works without BigQuery)

```bash
curl -X POST http://localhost:8000/replay/demo \
  -H "Content-Type: application/json" \
  -H "X-API-Key: fw-demo-key-2026" \
  -d '{
    "domain": "hiring",
    "features": {"age": 28, "skills_score": 0.85, "experience": 5},
    "sensitive_attrs": {"gender": "female"},
    "attribute_overrides": {"gender": "male"}
  }' | python3 -m json.tool
```

Expected:
```json
{
  "original":        {"gender": "female", "label": "REJECTED"},
  "counterfactual":  {"gender": "male",   "label": "ACCEPTED"},
  "bias_confirmed":  true,
  "explanation":     "The decision changed from REJECTED to ACCEPTED when gender was flipped..."
}
```

This is the exact What-If demo you show judges at 2:00 in the 3-minute demo.

---

### Test 4 — POST /replay (production mode — requires BigQuery)

```bash
# Use a real prediction_id from a prior POST /predict call
curl -X POST http://localhost:8000/replay \
  -H "Content-Type: application/json" \
  -H "X-API-Key: fw-demo-key-2026" \
  -d '{
    "prediction_id": "pred_XXXXXXXX",
    "attribute_overrides": {"gender": "male"},
    "domain": "hiring"
  }' | python3 -m json.tool
```

Note: Returns 404 in dev without BigQuery. Fully functional after Segment 6 GCP setup.

---

### Test 5 — Check OpenAPI docs

```bash
open http://localhost:8000/docs
```

Should now show 6 tag groups:
- Predictions
- Metrics
- Review Queue
- Interventions
- **Explainability** (new)
- **What-If Replay** (new)

---

### Test 6 — Verify Gemma swap ladder

```bash
# Check which models Ollama has available
curl http://localhost:11434/api/tags | python3 -m json.tool

# Check FairWall is using Ollama
curl http://localhost:8000/health | python3 -m json.tool
```

---

## Checkpoint — before moving to Segment 5

- [ ] Ollama running: `ollama serve` + at least one gemma model pulled
- [ ] Blocked predictions include `explanation` in POST /predict response
- [ ] `GET /explain/{id}` returns 200 with explanation string
- [ ] `POST /replay/demo` returns `bias_confirmed` + `explanation`
- [ ] `POST /replay/demo` with gender flip shows different outcomes for male vs female
- [ ] `http://localhost:8000/docs` shows Explainability + What-If Replay groups
- [ ] Server handles Ollama being unavailable gracefully (returns template, not 500)

If all pass → update CLAUDE.md Section 6 Segment 4 to `[x] Complete` and start Segment 5.

---

## Troubleshooting Gemma / Ollama

**OOM error (out of memory):**
```
Model gemma4:e4b OOM — trying next in ladder
```
→ FairWall automatically falls back to `gemma4:e2b`, then `gemma3:4b`. Normal behaviour.

**Ollama not running:**
```
Cannot connect to Ollama at http://localhost:11434
```
→ Run `ollama serve` in a separate terminal, keep it open.

**Model not pulled:**
```
Model gemma4:e4b failed — trying next
```
→ Run `ollama pull gemma4:e4b` first. Or set `GEMMA_MODEL_PRIMARY=gemma3:4b` in `.env`
if you only want to pull the smallest model.

**Slow first response:**
Normal — first inference loads the model into GPU VRAM. Subsequent calls are fast.

**Switch to template fallback (no Ollama):**
Set `GEMMA_BACKEND=none` in `.env` — returns hardcoded explanation templates.
Useful for testing the rest of the pipeline without running Ollama.
