"""
backend/api/metrics.py
GET /trust-score — current Trust Score for the calling tenant+domain
GET /metrics     — current per-metric fairness results
Segment 2 — Bias Detection Engine.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

from backend.core.bias_engine import get_bias_engine
from backend.core.profile_loader import load_all_profiles
from backend.core.tenant_middleware import check_domain
from backend.core.trust_score import get_trust_calculator

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_profiles():
    """Lazy-load profiles — avoids circular import with main.py."""
    from backend.main import get_profiles
    return get_profiles()


@router.get("/trust-score")
async def trust_score(
    request: Request,
    domain: str = Query(..., description="hiring | lending | admissions | healthcare"),
):
    """
    Returns the current AI Trust Score (0-100) for this tenant + domain.

    During warm-up (window < min_window_for_scoring):
        { trust_score: null, status: "warming_up", window_size: N, min_for_scoring: 10 }

    After warm-up:
        { trust_score: 73, status: "warning", severity_level: "low", window_size: 30, ... }
    """
    tenant_id: str = request.state.tenant_id

    domain_err = check_domain(request, domain)
    if domain_err:
        return domain_err

    profiles = _get_profiles()
    if domain not in profiles:
        return JSONResponse({"error": f"Domain '{domain}' profile not loaded"}, status_code=404)

    profile = profiles[domain]
    engine = get_bias_engine()
    calculator = get_trust_calculator()

    window_info = engine.get_window_info(tenant_id, domain, profile)
    window = engine._buffer.get(tenant_id, domain)

    # Compute metrics on current window (None if warming up)
    if window_info["is_warming_up"]:
        current_metrics = None
    else:
        current_metrics = engine._compute_metrics(window, profile, tenant_id, domain)

    result = calculator.compute(
        metrics=current_metrics,
        window_size=window_info["window_size"],
        window_capacity=window_info["window_capacity"],
        min_for_scoring=window_info["min_for_scoring"],
    )

    return {
        "tenant_id": tenant_id,
        "domain": domain,
        "trust_score": result.trust_score,
        "status": result.status,
        "severity_level": result.severity_level,
        "window_size": result.window_size,
        "window_capacity": result.window_capacity,
        "min_for_scoring": result.min_for_scoring,
        "is_warming_up": result.trust_score is None,
    }


@router.get("/metrics")
async def metrics_detail(
    request: Request,
    domain: str = Query(..., description="hiring | lending | admissions | healthcare"),
):
    """
    Returns full per-metric fairness results for this tenant + domain.
    Includes value, threshold, status, affected group, and description.
    """
    tenant_id: str = request.state.tenant_id

    domain_err = check_domain(request, domain)
    if domain_err:
        return domain_err

    profiles = _get_profiles()
    if domain not in profiles:
        return JSONResponse({"error": f"Domain '{domain}' profile not loaded"}, status_code=404)

    profile = profiles[domain]
    engine = get_bias_engine()
    calculator = get_trust_calculator()

    window_info = engine.get_window_info(tenant_id, domain, profile)
    window = engine._buffer.get(tenant_id, domain)

    if window_info["is_warming_up"]:
        return {
            "tenant_id": tenant_id,
            "domain": domain,
            "status": "warming_up",
            "window_size": window_info["window_size"],
            "min_for_scoring": window_info["min_for_scoring"],
            "metrics": [],
        }

    current_metrics = engine._compute_metrics(window, profile, tenant_id, domain)
    result = calculator.compute(
        metrics=current_metrics,
        window_size=window_info["window_size"],
        window_capacity=window_info["window_capacity"],
        min_for_scoring=window_info["min_for_scoring"],
    )

    metrics_out = []
    if result.metrics:
        for m in result.metrics:
            metrics_out.append({
                "name": m.name,
                "value": m.value,
                "threshold": m.threshold,
                "status": m.status,
                "affected_group": m.affected_group,
                "affected_attribute": m.affected_attribute,
                "severity": m.severity,
                "description": m.description,
            })

    return {
        "tenant_id": tenant_id,
        "domain": domain,
        "trust_score": result.trust_score,
        "status": result.status,
        "severity_level": result.severity_level,
        "window_size": result.window_size,
        "metrics": metrics_out,
        "penalty_breakdown": result.penalty_breakdown,
    }


# ── test ──────────────────────────────────────────────────────────────────────
# After sending 15+ predictions via POST /predict:
# curl "http://localhost:8000/trust-score?domain=hiring" -H "X-API-Key: fw-demo-key-2026"
# curl "http://localhost:8000/metrics?domain=hiring"     -H "X-API-Key: fw-demo-key-2026"
