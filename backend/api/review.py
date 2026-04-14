"""
backend/api/review.py
GET  /review-queue  — fetch pending blocked decisions for human review
POST /resolve       — HR reviewer resolves a blocked case
Segment 3 — Intervention Engine.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.core.firestore_client import get_fs_client
from backend.core.tenant_middleware import check_domain

logger = logging.getLogger(__name__)
router = APIRouter()


# ── schemas ───────────────────────────────────────────────────────────────────

class ResolveRequest(BaseModel):
    doc_id: str
    resolved_by: str
    resolution_note: Optional[str] = None


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/review-queue")
async def get_review_queue(
    request: Request,
    domain: Optional[str] = Query(None, description="Filter by domain"),
    status: str = Query("pending", description="pending | resolved"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Returns blocked decisions pending human review for this tenant.
    Results are ALWAYS scoped to the calling tenant — never cross-tenant data.
    """
    tenant_id: str = request.state.tenant_id

    if domain:
        domain_err = check_domain(request, domain)
        if domain_err:
            return domain_err

    try:
        fs = get_fs_client()
        items = fs.get_review_queue(
            tenant_id=tenant_id,        # REQUIRED — Firestore query filtered by tenant_id
            domain=domain,
            status=status,
            limit=limit,
        )
        return {
            "tenant_id": tenant_id,
            "tenant_name": request.state.tenant_name,
            "domain_filter": domain,
            "status_filter": status,
            "count": len(items),
            "items": items,
        }
    except Exception as e:
        logger.error("review-queue error: %s", e)
        return JSONResponse({"error": "Failed to fetch review queue"}, status_code=500)


@router.post("/resolve")
async def resolve_case(payload: ResolveRequest, request: Request):
    """
    HR reviewer marks a blocked case as resolved.
    Verifies the doc belongs to the calling tenant before updating.
    """
    tenant_id: str = request.state.tenant_id

    try:
        fs = get_fs_client()
        success = fs.resolve_review_item(
            doc_id=payload.doc_id,
            tenant_id=tenant_id,        # REQUIRED — prevents cross-tenant modification
            resolved_by=payload.resolved_by,
            resolution_note=payload.resolution_note,
        )

        if not success:
            return JSONResponse(
                {"error": "Case not found or not owned by this tenant"},
                status_code=404,
            )

        return {
            "success": True,
            "doc_id": payload.doc_id,
            "resolved_by": payload.resolved_by,
            "message": "Case resolved successfully",
        }
    except Exception as e:
        logger.error("resolve error: %s", e)
        return JSONResponse({"error": "Failed to resolve case"}, status_code=500)


# ── test ──────────────────────────────────────────────────────────────────────
# curl "http://localhost:8000/review-queue?domain=hiring" -H "X-API-Key: fw-demo-key-2026"
# curl -X POST http://localhost:8000/resolve \
#   -H "Content-Type: application/json" -H "X-API-Key: fw-demo-key-2026" \
#   -d '{"doc_id":"review_abc123","resolved_by":"hr_reviewer@company.com","resolution_note":"Manually reviewed and approved"}'
