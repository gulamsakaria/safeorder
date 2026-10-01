"""Shared enumerations. Names equal values so they are stable in the database and the API."""

from enum import StrEnum


class OrderStatus(StrEnum):
    HELD = "HELD"
    DELIVERED = "DELIVERED"
    DISPUTABLE = "DISPUTABLE"
    DISPUTED = "DISPUTED"
    RELEASED = "RELEASED"
    REFUNDED = "REFUNDED"
    ESCALATED = "ESCALATED"


class LedgerAccount(StrEnum):
    BUYER_WALLET = "BUYER_WALLET"
    HOLD = "HOLD"
    SELLER_WALLET = "SELLER_WALLET"
    REFUND = "REFUND"


class CourierStatus(StrEnum):
    NOT_DISPATCHED = "not_dispatched"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    RETURNED = "returned"
    LOST = "lost"


class Party(StrEnum):
    BUYER = "BUYER"
    SELLER = "SELLER"


class DisputeStatus(StrEnum):
    OPEN = "OPEN"
    SELLER_RESPONDED = "SELLER_RESPONDED"
    ANALYZED = "ANALYZED"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class EvidenceKind(StrEnum):
    TEXT_DESCRIPTION = "TEXT_DESCRIPTION"
    IMAGE = "IMAGE"  # P2: file_hash is used by the perceptual-hash check


class AnalystDecisionType(StrEnum):
    REFUND_BUYER = "REFUND_BUYER"
    REJECT_CLAIM = "REJECT_CLAIM"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    ESCALATE = "ESCALATE"


class TrustBand(StrEnum):
    TRUSTED = "TRUSTED"
    CAUTION = "CAUTION"
    HIGH_RISK = "HIGH_RISK"
    LIMITED_HISTORY = "LIMITED_HISTORY"


class SnapshotTrigger(StrEnum):
    INITIAL = "INITIAL"
    DISPUTE_RESOLVED = "DISPUTE_RESOLVED"
    MANUAL = "MANUAL"
