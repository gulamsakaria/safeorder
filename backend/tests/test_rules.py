from datetime import UTC, datetime, timedelta

import pytest

from app import rules
from app.enums import OrderStatus, TrustBand

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def test_hold_and_deadlines_come_from_config() -> None:
    assert rules.hold_until(T0) == T0 + timedelta(hours=72)
    assert rules.seller_response_deadline(T0) == T0 + timedelta(hours=48)
    assert rules.dispatch_deadline(T0) == T0 + timedelta(hours=72)


@pytest.mark.parametrize(
    ("probability", "score"),
    [(0.0, 100), (1.0, 0), (0.77, 23), (0.5, 50), (0.285, 72), (0.2849, 72), (0.715, 29)],
)
def test_score_from_probability(probability: float, score: int) -> None:
    assert rules.score_from_probability(probability) == score


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_score_rejects_invalid_probability(bad: float) -> None:
    with pytest.raises(ValueError):
        rules.score_from_probability(bad)


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (100, TrustBand.TRUSTED),
        (70, TrustBand.TRUSTED),
        (69, TrustBand.CAUTION),
        (40, TrustBand.CAUTION),
        (39, TrustBand.HIGH_RISK),
        (0, TrustBand.HIGH_RISK),
    ],
)
def test_band_boundaries(score: int, band: TrustBand) -> None:
    assert rules.band_for_score(score) == band


@pytest.mark.parametrize(
    ("age_days", "orders", "limited"),
    [(13, 50, True), (14, 50, False), (200, 9, True), (200, 10, False), (3, 2, True)],
)
def test_limited_history(age_days: float, orders: int, limited: bool) -> None:
    assert rules.is_limited_history(age_days, orders) is limited


def test_trust_band_prefers_limited_history_over_a_low_score() -> None:
    assert rules.trust_band(5, account_age_days=3, order_count=2) == TrustBand.LIMITED_HISTORY
    assert rules.trust_band(5, account_age_days=300, order_count=80) == TrustBand.HIGH_RISK


def test_only_high_risk_needs_extra_confirmation() -> None:
    assert rules.requires_extra_confirmation(TrustBand.HIGH_RISK)
    for band in (TrustBand.TRUSTED, TrustBand.CAUTION, TrustBand.LIMITED_HISTORY):
        assert not rules.requires_extra_confirmation(band)


def test_dispute_window_statuses() -> None:
    allowed = {s for s in OrderStatus if rules.can_file_dispute(s)}
    assert allowed == {OrderStatus.HELD, OrderStatus.DELIVERED, OrderStatus.DISPUTABLE}
