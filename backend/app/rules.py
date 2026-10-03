"""Business rules as pure functions (BLUEPRINT.md Section 6). No ML, no database, no I/O.

Every threshold comes from config/config.yaml; nothing here is a claim about upay policy.
"""

import math
from datetime import datetime, timedelta
from typing import Any

from app.config import load_config
from app.enums import OrderStatus, TrustBand

Config = dict[str, Any]

SCORE_MIN = 0
SCORE_MAX = 100

# Order states from which a buyer may still open a dispute ("dispute filed within window").
DISPUTE_WINDOW_STATUSES = frozenset(
    {OrderStatus.HELD, OrderStatus.DELIVERED, OrderStatus.DISPUTABLE}
)


def _rules(cfg: Config | None) -> Config:
    return (cfg or load_config())["rules"]


def hold_until(delivered_at: datetime, cfg: Config | None = None) -> datetime:
    """When the hold ends: delivery time plus the configured hold period."""
    return delivered_at + timedelta(hours=_rules(cfg)["hold_period_hours"])


def dispatch_deadline(placed_at: datetime, cfg: Config | None = None) -> datetime:
    """Latest time the seller may still dispatch before the order becomes DISPUTABLE."""
    return placed_at + timedelta(hours=_rules(cfg)["dispatch_deadline_hours"])


def claim_deadline(placed_at: datetime, cfg: Config | None = None) -> datetime:
    """Latest time the seller may enter the order number of a wallet payment."""
    return placed_at + timedelta(hours=_rules(cfg)["seller_claim_deadline_hours"])


def silence_deadline(proof_at: datetime, cfg: Config | None = None) -> datetime:
    """When a clean seller proof may release the money if the buyer stayed silent."""
    return proof_at + timedelta(hours=_rules(cfg)["buyer_silence_hours"])


def seller_response_deadline(opened_at: datetime, cfg: Config | None = None) -> datetime:
    return opened_at + timedelta(hours=_rules(cfg)["seller_response_deadline_hours"])


def can_file_dispute(status: OrderStatus) -> bool:
    return status in DISPUTE_WINDOW_STATUSES


def score_from_probability(p_high_risk: float) -> int:
    """score = round(100 x (1 - P(high risk))), rounding halves up, clamped to 0-100."""
    if not 0.0 <= p_high_risk <= 1.0:
        raise ValueError("probability must be between 0 and 1")
    raw = math.floor(SCORE_MAX * (1.0 - p_high_risk) + 0.5)
    return max(SCORE_MIN, min(SCORE_MAX, raw))


def band_for_score(score: int, cfg: Config | None = None) -> TrustBand:
    """TRUSTED 70-100, CAUTION 40-69, HIGH_RISK 0-39 (thresholds from config)."""
    trust = _rules(cfg)["trust"]
    if score >= trust["trusted_min"]:
        return TrustBand.TRUSTED
    if score >= trust["caution_min"]:
        return TrustBand.CAUTION
    return TrustBand.HIGH_RISK


def is_limited_history(
    account_age_days: float, order_count: int, cfg: Config | None = None
) -> bool:
    """Young or thin accounts get a neutral band instead of a low score (fairness)."""
    trust = _rules(cfg)["trust"]
    return (
        account_age_days < trust["limited_history_max_age_days"]
        or order_count < trust["limited_history_min_orders"]
    )


def trust_band(
    score: int, account_age_days: float, order_count: int, cfg: Config | None = None
) -> TrustBand:
    """Band shown to the buyer.

    Limited-history sellers get the neutral band, unless the model score is at or below
    ``limited_history_override_max_score`` (strong behavioural evidence). Set that value to null
    in the config for the literal blueprint behaviour.
    """
    if is_limited_history(account_age_days, order_count, cfg):
        override = _rules(cfg)["trust"].get("limited_history_override_max_score")
        if override is not None and score <= override:
            return TrustBand.HIGH_RISK
        return TrustBand.LIMITED_HISTORY
    return band_for_score(score, cfg)


def requires_extra_confirmation(band: TrustBand, cfg: Config | None = None) -> bool:
    """HIGH_RISK shows a strong warning and one more click. It never blocks the order."""
    return band == TrustBand.HIGH_RISK and _rules(cfg)["trust"]["high_risk_requires_confirmation"]
