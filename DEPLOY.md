# FairWall — Cloud Deployment Guide
## Google Cloud Run (backend) + Firebase Hosting (frontend)

---

## Prerequisites (install once)

```bash
# Google Cloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# Firebase CLI
npm install -g firebase-tools
firebase login

# Bun (frontend)
curl -fsSL https://bun.sh/install | bash
```

---

## Step 1 — Create GCP Project

```bash
gcloud projects create fairwall-2026 --name="FairWall"
gcloud config set project fairwall-2026

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  containerregistry.googleapis.com \
  bigquery.googleapis.com \
  firestore.googleapis.com \
  aiplatform.googleapis.com

# Set billing (required for Cloud Run)
# Go to: console.cloud.google.com → Billing → Link account
```

---

## Step 2 — Setup BigQuery + Firestore

```bash
# BigQuery dataset
bq mk --dataset --location=US fairwall-2026:fairwall_logs

# Create tables
python backend/setup/create_tables.py

# Firestore (native mode)
gcloud firestore databases create --location=us-central1

# Init Firestore collections
python backend/setup/init_firestore.py
```

---

## Step 3 — Deploy Backend to Cloud Run

```bash
cd Fair-Wall   # repo root

# Build and push Docker image
docker build -t gcr.io/fairwall-2026/fairwall-api .
docker push gcr.io/fairwall-2026/fairwall-api

# Deploy to Cloud Run
gcloud run deploy fairwall-api \
  --image gcr.io/fairwall-2026/fairwall-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --set-env-vars "GCP_PROJECT=fairwall-2026,GEMMA_BACKEND=none,APP_ENV=production,LOG_LEVEL=INFO"

# Get your live URL
gcloud run services describe fairwall-api \
  --platform managed --region us-central1 \
  --format 'value(status.url)'
# → https://fairwall-api-xxxx-uc.a.run.app
```

**Verify it works:**
```bash
curl https://fairwall-api-xxxx-uc.a.run.app/health
# → {"status":"ok","version":"1.2.0","loaded_domains":["admissions","healthcare","hiring","lending"]}
```

---

## Step 4 — Deploy Frontend to Firebase

```bash
# Init Firebase (first time only)
firebase login
firebase init hosting
# → Select: fairwall-2026
# → Public directory: dist
# → Single-page app: Yes
# → Don't overwrite index.html

# Build frontend with your Cloud Run URL
VITE_API_URL=https://fairwall-api-xxxx-uc.a.run.app \
VITE_DEFAULT_API_KEY=fw-demo-key-2026 \
bun run build

# Deploy
firebase deploy --only hosting

# → Dashboard live at: https://fairwall-2026.web.app
```

---

## Step 5 — Test the live deployment

```bash
# 1. Check health
curl https://fairwall-api-xxxx-uc.a.run.app/health

# 2. Send a test prediction
curl -X POST https://fairwall-api-xxxx-uc.a.run.app/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: fw-demo-key-2026" \
  -d '{"domain":"hiring","features":{"age":28,"skills_score":0.85},"sensitive_attrs":{"gender":"female"},"prediction":0}'

# 3. Run full simulation against live URL
python demo/simulate_bias.py \
  --api-url https://fairwall-api-xxxx-uc.a.run.app \
  --api-key fw-demo-key-2026

# 4. Open dashboard
open https://fairwall-2026.web.app
# Go to Settings → set Backend URL to your Cloud Run URL
```

---

## Step 6 — Setup GitHub Actions (automated deploys)

```bash
# Create service account for GitHub Actions
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions"

# Grant required roles
gcloud projects add-iam-policy-binding fairwall-2026 \
  --member="serviceAccount:github-actions@fairwall-2026.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding fairwall-2026 \
  --member="serviceAccount:github-actions@fairwall-2026.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding fairwall-2026 \
  --member="serviceAccount:github-actions@fairwall-2026.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Export key
gcloud iam service-accounts keys create gcp-key.json \
  --iam-account=github-actions@fairwall-2026.iam.gserviceaccount.com

# Add to GitHub Secrets:
# GCP_SA_KEY     → contents of gcp-key.json
# BACKEND_URL    → https://fairwall-api-xxxx-uc.a.run.app
# FIREBASE_SA_KEY → Firebase service account key

# Now every push to main auto-deploys both backend + frontend
```

---

## URLs to add to README after deployment

```
Backend API:  https://fairwall-api-xxxx-uc.a.run.app
Dashboard:    https://fairwall-2026.web.app
GitHub:       https://github.com/ShriHarsan64K/Fair-Wall
```

---

## Troubleshooting

**Cloud Run cold start timeout:**
Add `--min-instances 1` to keep one instance warm (costs ~$5/month).

**BigQuery auth error:**
Set `GOOGLE_APPLICATION_CREDENTIALS` env var to your service account key path,
or use `gcloud auth application-default login`.

**Frontend can't reach backend (CORS):**
Backend already has `allow_origins=["*"]` in main.py — CORS is open.
Check the URL in dashboard Settings doesn't have a trailing slash.

**Gemma not working on Cloud Run:**
`GEMMA_BACKEND=none` uses template explanations (no GPU needed).
For real Gemma: set `GEMMA_BACKEND=vertex` and configure Vertex AI endpoint.
