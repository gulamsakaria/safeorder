"""Plain-language reasons for a trust score, in Bangla and English.

Reasons come from LightGBM's built-in per-feature contributions (``pred_contrib=True``): a
positive contribution pushes towards HIGH_RISK, a negative one towards trusted. The wording lives
in ``i18n/reasons_en.json`` and ``i18n/reasons_bn.json`` and is filled from templates only, so
nothing is generated freely.
"""

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import load_config

I18N_DIR = Path(__file__).resolve().parents[1] / "i18n"
BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
MINUTES_PER_HOUR = 60
MINUTES_PER_DAY = 1_440
HOURS_SHOWN_BELOW_MIN = 120  # show minutes under 2 hours
DAYS_SHOWN_FROM_MIN = 2 * MINUTES_PER_DAY
PERCENT = 100

RISK, PROTECTIVE, NEUTRAL = "risk", "protective", "neutral"
HIGH, LOW, ANY = "high", "low", "any"
LIMITED_HISTORY_KEY = "LIMITED_HISTORY"

# (feature, direction, level) -> reason key. "any" matches either level.
REASON_KEYS: dict[tuple[str, str, str], str] = {
    ("account_age_days", RISK, LOW): "ACCOUNT_VERY_NEW",
    ("account_age_days", PROTECTIVE, HIGH): "ACCOUNT_ESTABLISHED",
    ("account_age_days", PROTECTIVE, LOW): "YOUNG_BUT_NOT_A_WARNING",
    ("orders_7d", RISK, HIGH): "ORDER_SURGE_7D",
    ("orders_7d", RISK, LOW): "FEW_ORDERS_7D",
    ("orders_7d", PROTECTIVE, HIGH): "ACTIVE_RECENT_ORDERS",
    ("orders_7d", PROTECTIVE, LOW): "NO_ORDER_RUSH_7D",
    ("orders_30d", RISK, HIGH): "ORDER_SURGE_30D",
    ("orders_30d", RISK, LOW): "FEW_ORDERS_30D",
    ("orders_30d", PROTECTIVE, HIGH): "STEADY_ORDERS_30D",
    ("orders_30d", PROTECTIVE, LOW): "NO_ORDER_RUSH_30D",
    ("unique_buyers_24h", RISK, HIGH): "BUYER_BURST",
    ("unique_buyers_24h", PROTECTIVE, ANY): "NORMAL_DAILY_BUYERS",
    ("unique_buyers_30d", RISK, HIGH): "MANY_BUYERS_30D",
    ("unique_buyers_30d", RISK, LOW): "FEW_BUYERS_30D",
    ("unique_buyers_30d", PROTECTIVE, HIGH): "BROAD_CUSTOMER_BASE",
    ("buyer_burst_ratio", RISK, HIGH): "SUDDEN_BUYER_SPIKE",
    ("buyer_burst_ratio", PROTECTIVE, ANY): "STABLE_BUYER_FLOW",
    ("repeat_buyer_ratio", RISK, LOW): "FEW_REPEAT_BUYERS",
    ("repeat_buyer_ratio", RISK, HIGH): "REPEAT_BUYER_CIRCLE",
    ("repeat_buyer_ratio", PROTECTIVE, HIGH): "REPEAT_BUYERS",
    ("buyer_concentration", RISK, HIGH): "FEW_BUYERS_DOMINATE",
    ("buyer_concentration", PROTECTIVE, ANY): "ORDERS_SPREAD_OUT",
    ("refund_rate", RISK, HIGH): "HIGH_REFUND_RATE",
    ("refund_rate", PROTECTIVE, ANY): "LOW_REFUND_RATE",
    ("dispute_rate", RISK, HIGH): "HIGH_DISPUTE_RATE",
    ("dispute_rate", PROTECTIVE, ANY): "LOW_DISPUTE_RATE",
    ("median_cashout_latency_min", RISK, LOW): "FAST_CASHOUT",
    ("median_cashout_latency_min", PROTECTIVE, HIGH): "NORMAL_CASHOUT_RHYTHM",
    ("median_cashout_latency_min", PROTECTIVE, LOW): "CASHOUT_NOT_UNUSUAL",
    ("ticket_vs_category_ratio", RISK, HIGH): "HIGH_TICKET",
    ("ticket_vs_category_ratio", PROTECTIVE, ANY): "NORMAL_TICKET",
    ("shared_buyer_overlap", RISK, HIGH): "SHARED_BUYER_GROUP",
    ("shared_buyer_overlap", PROTECTIVE, ANY): "NO_SHARED_BUYERS",
}

COUNT_FEATURES = {
    "account_age_days", "orders_7d", "orders_30d", "unique_buyers_24h", "unique_buyers_30d",
}  # fmt: skip
PERCENT_FEATURES = {
    "repeat_buyer_ratio", "buyer_concentration", "refund_rate", "dispute_rate",
    "shared_buyer_overlap",
}  # fmt: skip
TIMES_FEATURES = {"buyer_burst_ratio", "ticket_vs_category_ratio"}


@dataclass(frozen=True)
class Reason:
    key: str
    direction: str
    text_en: str
    text_bn: str
    feature: str | None = None
    contribution: float = 0.0

    def to_api(self) -> dict[str, str]:
        return {
            "key": self.key,
            "direction": self.direction,
            "text_en": self.text_en,
            "text_bn": self.text_bn,
        }


@lru_cache(maxsize=2)
def catalog(lang: str) -> dict[str, Any]:
    with (I18N_DIR / f"reasons_{lang}.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def _duration(minutes: float, lang: str) -> str:
    units = catalog(lang)["units"]
    if minutes < HOURS_SHOWN_BELOW_MIN:
        return units["minutes"].format(n=max(1, round(minutes)))
    if minutes < DAYS_SHOWN_FROM_MIN:
        return units["hours"].format(n=round(minutes / MINUTES_PER_HOUR))
    return units["days"].format(n=round(minutes / MINUTES_PER_DAY))


def format_value(feature: str, value: float, lang: str) -> str:
    if feature == "median_cashout_latency_min":
        return _duration(value, lang)
    if feature in COUNT_FEATURES:
        return str(round(value))
    if feature in PERCENT_FEATURES:
        return str(round(value * PERCENT))
    if feature in TIMES_FEATURES:
        return f"{value:.1f}"
    return f"{value:.2f}"


def _level(value: float, median: float) -> str:
    return HIGH if value >= median else LOW


def select_key(feature: str, direction: str, level: str) -> str:
    for candidate in (level, ANY):
        key = REASON_KEYS.get((feature, direction, candidate))
        if key:
            return key
    return "GENERIC_RISK" if direction == RISK else "GENERIC_PROTECTIVE"


def render(key: str, feature: str | None, value: float | None, lang: str) -> str:
    cat = catalog(lang)
    template = cat["reasons"][key]
    fields = {"value": "", "label": ""}
    if feature is not None and value is not None:
        fields["value"] = format_value(feature, value, lang)
        fields["label"] = cat["labels"][feature]
        if key.startswith("GENERIC"):  # generic wording has no unit of its own
            fields["value"] += _unit_suffix(feature, lang)
    text = template.format(**fields)
    return text.translate(BN_DIGITS) if lang == "bn" else text


def _unit_suffix(feature: str, lang: str) -> str:
    if feature in PERCENT_FEATURES:
        return "%"
    if feature == "account_age_days":
        return " days" if lang == "en" else " দিন"
    return ""


def limited_history_reason() -> Reason:
    return Reason(
        key=LIMITED_HISTORY_KEY,
        direction=NEUTRAL,
        text_en=render(LIMITED_HISTORY_KEY, None, None, "en"),
        text_bn=render(LIMITED_HISTORY_KEY, None, None, "bn"),
    )


def build_reasons(
    values: Mapping[str, float],
    contributions: Mapping[str, float],
    medians: Mapping[str, float],
    score: int,
    limited_history: bool = False,
    cfg: dict[str, Any] | None = None,
) -> list[Reason]:
    """Pick 2 to 4 reasons, strongest first, favouring the direction of the overall verdict."""
    config = cfg or load_config()
    settings = config["trust_model"]["reasons"]
    trusted_min = config["rules"]["trust"]["trusted_min"]
    primary = RISK if score < trusted_min else PROTECTIVE

    candidates = []
    for feature, contribution in contributions.items():
        value = values.get(feature)
        if value is None or (isinstance(value, float) and math.isnan(value)) or contribution == 0:
            continue
        direction = RISK if contribution > 0 else PROTECTIVE
        candidates.append((direction != primary, -abs(contribution), feature, direction))
    candidates.sort()

    reasons: list[Reason] = [limited_history_reason()] if limited_history else []
    minimum, maximum = settings["min"], settings["max"]
    for _, neg_strength, feature, direction in candidates:
        if len(reasons) >= maximum:
            break
        strong = -neg_strength >= settings["min_abs_contribution"]
        if len(reasons) >= minimum and not strong:
            continue
        key = select_key(feature, direction, _level(values[feature], medians[feature]))
        reasons.append(
            Reason(
                key=key,
                direction=direction,
                text_en=render(key, feature, values[feature], "en"),
                text_bn=render(key, feature, values[feature], "bn"),
                feature=feature,
                contribution=-neg_strength if direction == RISK else neg_strength,
            )
        )
    return reasons
