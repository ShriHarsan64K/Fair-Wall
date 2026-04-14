"""
backend/api/predict.py
POST /predict — receives a prediction, runs the full FairWall pipeline.
GET  /tenant-info — returns tenant name and allowed domains.
Updated in Segment 4: Gemma explanation generated for every flagged/blocked decision.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.core.bias_engine import get_bias_engine
from backend.core.logger import get_prediction_logger
from backend.core.metrics import SeverityLevel
from backend.core.router import get_router
from backend.core.explainer import get_explainer
from backend.core.tenant_middleware import check_domain
from backend.core.trust_score import get_trust_calculator, TrustScoreResult

logger = logging.getLogger(__name__)
router = APIRouter()


# ── schemas ───────────────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    domain: str = Field(..., description="hiring | lending | admissions | healthcare")
    features: dict[str, Any] = Field(..., description="Full feature dict for the candidate")
    sensitive_attrs: dict[str, str] = Field(..., description="e.g. {gender: female, age_group: senior}")
    prediction: int = Field(..., ge=0, le=1, description="0=rejected, 1=accepted")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    true_label: Optional[int] = Field(default=None, ge=0, le=1)


class PredictResponse(BaseModel):
    prediction_id: str
    domain: str
    tenant_id: str
    original_prediction: int
    final_prediction: Optional[int]       # None when blocked
    final_decision: str                   # released | flagged | adjusted | blocked
    trust_score: Optional[int]
    trust_status: str
    severity_level: str
    flagged: bool
    blocked: bool
    threshold_adjusted: bool
    intervention_type: str                # none | flag_only | adjust_threshold | block_and_review
    affected_attribute: Optional[str]
    affected_group: Optional[str]
    review_queue_id: Optional[str]        # set when blocked
    explanation: Optional[str]            # filled in Segment 4
    window_size: int
    warming_up: bool
    message: str


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_profiles():
    from backend.main import get_profiles
    return get_profiles()


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/predict", response_model=PredictResponse)
async def predict(payload: PredictRequest, request: Request):
    """
    Main FairWall endpoint — full pipeline active from Segment 3.
    Logs prediction → detects bias → computes trust score → intervenes.
    """
    tenant_id: str = request.state.tenant_id

    domain_err = check_domain(request, payload.domain)
    if domain_err:
        return domain_err

    profiles = _get_profiles()
    if payload.domain not in profiles:
        return JSONResponse(
            {"error": f"Domain '{payload.domain}' profile not loaded"},
            status_code=404,
        )

    profile = profiles[payload.domain]
    prediction_logger = get_prediction_logger()

    # 1. Log to BigQuery (stores full features JSON — replay engine depends on this)
    prediction_id = prediction_logger.log_prediction(
        tenant_id=tenant_id,
        domain=payload.domain,
        features=payload.features,
        sensitive_attrs=payload.sensitive_attrs,
        prediction=payload.prediction,
        confidence=payload.confidence,
    )

    # 2. Bias detection — add to sliding window
    engine = get_bias_engine()
    metric_results = engine.add_prediction(
        tenant_id=tenant_id,
        domain=payload.domain,
        prediction_id=prediction_id,
        prediction=payload.prediction,
        sensitive_attrs=payload.sensitive_attrs,
        profile=profile,
        true_label=payload.true_label,
    )

    # 3. Trust score — null-safe
    window_info = engine.get_window_info(tenant_id, payload.domain, profile)
    calculator = get_trust_calculator()
    trust_result = calculator.compute(
        metrics=metric_results,
        window_size=window_info["window_size"],
        window_capacity=window_info["window_capacity"],
        min_for_scoring=window_info["min_for_scoring"],
    )

    # 4. Intervention engine — FLAG / ADJUST / BLOCK
    decision_router = get_router()
    intervention = decision_router.route(
        prediction_id=prediction_id,
        original_prediction=payload.prediction,
        confidence=payload.confidence,
        trust_result=trust_result,
        tenant_id=tenant_id,
        domain=payload.domain,
        features=payload.features,
        sensitive_attrs=payload.sensitive_attrs,
    )

    # 5. Update BigQuery log with final state
    prediction_logger.log_prediction(
        tenant_id=tenant_id,
        domain=payload.domain,
        features=payload.features,
        sensitive_attrs=payload.sensitive_attrs,
        prediction=payload.prediction,
        confidence=payload.confidence,
        flagged=intervention.flagged,
        intervention_type=intervention.action_taken,
        trust_score=float(trust_result.trust_score) if trust_result.trust_score is not None else None,
        prediction_id=prediction_id,
    )

    # Build message
    if trust_result.trust_score is None:
        msg = f"Warming up ({trust_result.window_size}/{trust_result.min_for_scoring} predictions collected)"
    elif intervention.blocked:
        msg = f"BLOCKED — Trust Score {trust_result.trust_score}/100. Routed to human review."
    elif intervention.threshold_adjusted:
        msg = f"ADJUSTED — Threshold moved +{intervention.adjustment_delta:.2f} (score={trust_result.trust_score})"
    elif intervention.flagged:
        msg = f"FLAGGED — Trust Score {trust_result.trust_score}/100 ({trust_result.status})"
    else:
        msg = f"Released — Trust Score {trust_result.trust_score}/100 ({trust_result.status})"

    logger.info(
        "predict: id=%s tenant=%s domain=%s pred=%d→%s score=%s action=%s",
        prediction_id, tenant_id, payload.domain, payload.prediction,
        intervention.final_decision, trust_result.trust_score, intervention.action_taken,
    )

    # 6. Generate Gemma explanation for flagged/blocked decisions
    explanation: Optional[str] = None
    if intervention.flagged or intervention.blocked:
        try:
            explainer = get_explainer()
            worst_metric = None
            if trust_result.metrics:
                worst_metric = max(trust_result.metrics, key=lambda m: m.severity)
            explanation = explainer.explain_intervention(
                domain=payload.domain,
                intervention=intervention,
                trust_result=trust_result,
                worst_metric=worst_metric,
            )
            # Update intervention records with explanation
            if intervention.review_queue_id:
                try:
                    from backend.core.firestore_client import get_fs_client
                    get_fs_client()._get_client().collection("review_queue").document(
                        intervention.review_queue_id
                    ).update({"explanation": explanation})
                except Exception:
                    pass  # Firestore not configured in dev
        except Exception as e:
            logger.warning("Explanation generation failed: %s", e)

    return PredictResponse(
        prediction_id=prediction_id,
        domain=payload.domain,
        tenant_id=tenant_id,
        original_prediction=payload.prediction,
        final_prediction=intervention.final_prediction if not intervention.blocked else None,
        final_decision=intervention.final_decision,
        trust_score=trust_result.trust_score,
        trust_status=trust_result.status,
        severity_level=str(intervention.severity_level.value),
        flagged=intervention.flagged,
        blocked=intervention.blocked,
        threshold_adjusted=intervention.threshold_adjusted,
        intervention_type=intervention.action_taken,
        affected_attribute=intervention.affected_attribute,
        affected_group=intervention.affected_group,
        review_queue_id=intervention.review_queue_id,
        explanation=explanation,  # now live from Gemma — Segment 4
        window_size=trust_result.window_size,
        warming_up=trust_result.trust_score is None,
        message=msg,
    )


@router.get("/tenant-info")
async def tenant_info(request: Request):
    return {
        "tenant_id": request.state.tenant_id,
        "name": request.state.tenant_name,
        "allowed_domains": request.state.allowed_domains,
    }


# ── test ──────────────────────────────────────────────────────────────────────
# Send 10+ biased predictions then check:
# - final_decision="blocked" when trust_score < 40
# - review_queue_id is set on blocked predictions
# - final_decision="flagged" for moderate bias
# - final_decision="released" for healthy predictions
