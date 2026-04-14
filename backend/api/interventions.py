"""
backend/api/interventions.py
GET /interventions — real-time intervention event feed for dashboard.
Segment 3 — Intervention Engine.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

from backend.core.firestore_client import get_fs_client
from backend.core.tenant_middleware import check_domain

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/interventions")
async def get_interventions(
    request: Request,
    domain: Optional[str] = Query(None, description="Filter by domain"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Returns the most recent intervention events for this tenant.
    Used by the React dashboard InterventionFeed component (polled every 5s).
    Always scoped to the calling tenant.
    """
    tenant_id: str = request.state.tenant_id

    if domain:
        domain_err = check_domain(request, domain)
        if domain_err:
            return domain_err

    try:
        fs = get_fs_client()
        events = fs.get_intervention_feed(
            tenant_id=tenant_id,      # REQUIRED — tenant scoped
            domain=domain,
            limit=limit,
        )
        return {
            "tenant_id": tenant_id,
            "domain_filter": domain,
            "count": len(events),
            "events": events,
        }
    except Exception as e:
        logger.error("interventions feed error: %s", e)
        return JSONResponse({"error": "Failed to fetch interventions"}, status_code=500)


# ── test ──────────────────────────────────────────────────────────────────────
# After sending biased predictions:
# curl "http://localhost:8000/interventions?domain=hiring" -H "X-API-Key: fw-demo-key-2026"
# curl "http://localhost:8000/interventions?domain=hiring&limit=5" -H "X-API-Key: fw-demo-key-2026"
