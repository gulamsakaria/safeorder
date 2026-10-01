"""Ordered event list for the analyst console (BLUEPRINT.md Section 9.3, stage 3). Deterministic."""

from typing import Any

from app.analyzer.case import DisputeCase
from app.clock import to_iso

ORDER_PLACED = "ORDER_PLACED_AND_HELD"
CODE_CONFIRMED = "DELIVERY_CODE_CONFIRMED"
DISPUTE_FILED = "BUYER_DISPUTE_FILED"
SELLER_RESPONDED = "SELLER_RESPONDED"


def build_timeline(case: DisputeCase) -> list[dict[str, Any]]:
    """Events sorted by time. Ties keep the logical order in which they were added."""
    events = [(case.placed_at, ORDER_PLACED)]
    events += [(when, f"COURIER_{status.upper()}") for status, when in case.courier_events]
    if case.code_confirmed_at is not None:
        events.append((case.code_confirmed_at, CODE_CONFIRMED))
    events.append((case.opened_at, DISPUTE_FILED))
    if case.seller_responded_at is not None:
        events.append((case.seller_responded_at, SELLER_RESPONDED))
    ordered = sorted(enumerate(events), key=lambda item: (item[1][0], item[0]))
    return [{"t": to_iso(when), "event": name} for _, (when, name) in ordered]
