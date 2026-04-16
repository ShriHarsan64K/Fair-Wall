"""
backend/main.py
FastAPI application entry point.
Registers TenantMiddleware, mounts all routers, exposes /health.
Segments 1-4 complete. Segment 6 adds simulate_router.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.tenant_middleware import TenantMiddleware
from backend.core.profile_loader import load_all_profiles
from backend.api.predict import router as predict_router
from backend.api.metrics import router as metrics_router
from backend.api.review import router as review_router
from backend.api.interventions import router as interventions_router
from backend.api.explain import router as explain_router
from backend.api.replay import router as replay_router

# ── env + logging ─────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── app state shared across requests ──────────────────────────────────────────
_app_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load domain profiles once at startup; clean up on shutdown."""
    logger.info("FairWall starting up...")
    profiles_dir = Path(__file__).parent / "profiles"
    profiles = load_all_profiles(profiles_dir)
    _app_state["profiles"] = profiles
    logger.info("Loaded %d domain profiles: %s", len(profiles), list(profiles.keys()))
    yield
    logger.info("FairWall shutting down.")
    _app_state.clear()


# ── app ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="FairWall — AI Fairness Firewall",
    description="Real-time fairness middleware that intercepts biased AI decisions before they reach users.",
    version="1.2.0",
    lifespan=lifespan,
)

# ── middleware ─────────────────────────────────────────────────────────────────
app.add_middleware(TenantMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── routers ───────────────────────────────────────────────────────────────────
app.include_router(predict_router,      tags=["Predictions"])
app.include_router(metrics_router,      tags=["Metrics"])
app.include_router(review_router,       tags=["Review Queue"])
app.include_router(interventions_router,tags=["Interventions"])
app.include_router(explain_router,      tags=["Explainability"])
app.include_router(replay_router,       tags=["What-If Replay"])
# Segment 6 adds: simulate_router


# ── health (no API key required) ──────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    """Public health check — no auth needed. Used by Cloud Run probes."""
    return {
        "status": "ok",
        "version": "1.2.0",
        "loaded_domains": list(_app_state.get("profiles", {}).keys()),
        "segment": 4,
    }


def get_profiles() -> dict:
    """Helper used by API endpoints to access loaded profiles."""
    return _app_state.get("profiles", {})
