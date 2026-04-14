"""
backend/core/router.py
DecisionRouter — maps severity to the correct handler, calls Firestore
for BLOCK cases, and returns a complete InterventionResult.
Segment 3 — Intervention Engine.
"""

import logging
from typing import Optional

from .firestore_client import get_fs_client
from .intervention import (
    BlockAndRouteHandler,
    FlagHandler,
    InterventionResult,
    SeverityClassifier,
    ThresholdAdjuster,
)
from .logger import get_prediction_logger
from .metrics import SeverityLevel
from .trust_score import TrustScoreResult

logger = logging.getLogger(__name__)

_classifier = SeverityClassifier()
_flag_handler = FlagHandler()
_adjust_handler = ThresholdAdjuster()
_block_handler = BlockAndRouteHandler()


class DecisionRouter:
    """
    Single entry point for the Intervention Engine.

    Given a prediction + trust score result, decides what to do:
        NONE   → pass through unchanged
        LOW    → FlagHandler  — flag, release
        MEDIUM → ThresholdAdjuster — maybe flip, release
        HIGH   → BlockAndRouteHandler — block, write to Firestore queue

    Also logs the intervention to BigQuery via PredictionLogger.
    """

    def route(
        self,
        *,
        prediction_id: str,
        original_prediction: int,
        confidence: float,
        trust_result: TrustScoreResult,
        tenant_id: str,
        domain: str,
        features: dict,
        sensitive_attrs: dict,
    ) -> InterventionResult:
        """
        Main entry point — call from POST /predict after trust score is computed.
        Returns an InterventionResult with final_decision and all metadata.
        """
        severity = _classifier.classify(trust_result)

        # No intervention during warm-up or healthy state
        if severity == SeverityLevel.NONE:
            return InterventionResult(
                original_prediction=original_prediction,
                final_prediction=original_prediction,
                final_decision="released",
                severity_level=SeverityLevel.NONE,
                action_taken="none",
                flagged=False,
                blocked=False,
                threshold_adjusted=False,
                adjustment_delta=0.0,
                affected_attribute=None,
                affected_group=None,
                review_queue_id=None,
                explanation=None,
            )

        # Route to correct handler
        if severity == SeverityLevel.LOW:
            result = _flag_handler.handle(original_prediction, trust_result)

        elif severity == SeverityLevel.MEDIUM:
            result = _adjust_handler.handle(original_prediction, trust_result, confidence)

        else:  # HIGH
            result = _block_handler.handle(original_prediction, trust_result)

            # Write to Firestore human review queue
            review_id = self._write_review_queue(
                prediction_id=prediction_id,
                tenant_id=tenant_id,
                domain=domain,
                features=features,
                sensitive_attrs=sensitive_attrs,
                original_prediction=original_prediction,
                trust_result=trust_result,
            )
            result.review_queue_id = review_id

        # Write to Firestore real-time intervention feed
        self._write_intervention_feed(
            prediction_id=prediction_id,
            tenant_id=tenant_id,
            domain=domain,
            result=result,
            trust_result=trust_result,
        )

        # Log to BigQuery interventions table
        self._log_intervention_bq(
            prediction_id=prediction_id,
            tenant_id=tenant_id,
            domain=domain,
            result=result,
            trust_result=trust_result,
        )

        return result

    # ── Firestore helpers ─────────────────────────────────────────────────────

    def _write_review_queue(
        self,
        *,
        prediction_id: str,
        tenant_id: str,
        domain: str,
        features: dict,
        sensitive_attrs: dict,
        original_prediction: int,
        trust_result: TrustScoreResult,
    ) -> Optional[str]:
        """Write a blocked prediction to the Firestore human review queue."""
        try:
            fs = get_fs_client()
            return fs.add_to_review_queue(
                prediction_id=prediction_id,
                tenant_id=tenant_id,        # REQUIRED — tenant scoped
                domain=domain,
                features=features,
                sensitive_attrs=sensitive_attrs,
                original_prediction=original_prediction,
                trust_score=float(trust_result.trust_score) if trust_result.trust_score else None,
                explanation=None,           # filled by Gemma in Segment 4
            )
        except Exception as e:
            logger.error("Failed to write review queue entry: %s", e)
            return None

    def _write_intervention_feed(
        self,
        *,
        prediction_id: str,
        tenant_id: str,
        domain: str,
        result: InterventionResult,
        trust_result: TrustScoreResult,
    ) -> None:
        """Write to Firestore real-time intervention feed for the dashboard."""
        try:
            fs = get_fs_client()
            from .logger import generate_intervention_id
            intv_id = generate_intervention_id()
            fs.log_intervention_event(
                intervention_id=intv_id,
                prediction_id=prediction_id,
                tenant_id=tenant_id,        # REQUIRED — tenant scoped
                domain=domain,
                severity=result.severity_level.value,
                action=result.action_taken,
                trust_score=float(trust_result.trust_score) if trust_result.trust_score else None,
                explanation=None,
            )
        except Exception as e:
            logger.error("Failed to write intervention feed: %s", e)

    def _log_intervention_bq(
        self,
        *,
        prediction_id: str,
        tenant_id: str,
        domain: str,
        result: InterventionResult,
        trust_result: TrustScoreResult,
    ) -> None:
        """Write intervention to BigQuery audit log."""
        try:
            pl = get_prediction_logger()
            pl.log_intervention(
                prediction_id=prediction_id,
                tenant_id=tenant_id,
                domain=domain,
                severity=result.severity_level.value,
                action=result.action_taken,
                trust_score=float(trust_result.trust_score) if trust_result.trust_score else None,
                explanation=None,
            )
        except Exception as e:
            logger.error("Failed to log intervention to BQ: %s", e)


# ── singleton ──────────────────────────────────────────────────────────────────
_router: Optional[DecisionRouter] = None


def get_router() -> DecisionRouter:
    global _router
    if _router is None:
        _router = DecisionRouter()
    return _router


# ── test ──────────────────────────────────────────────────────────────────────
# python -c "
# from backend.core.router import get_router
# r = get_router()
# print('DecisionRouter created:', r)
# "
