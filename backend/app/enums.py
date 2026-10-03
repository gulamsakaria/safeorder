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


class OrderEvent(StrEnum):
    PLACE_ORDER = "PLACE_ORDER"
    DELIVERY_CONFIRMED = "DELIVERY_CONFIRMED"  # courier delivered, or buyer entered the code
    COURIER_LOST = "COURIER_LOST"
    DISPATCH_DEADLINE_MISSED = "DISPATCH_DEADLINE_MISSED"
    HOLD_EXPIRED = "HOLD_EXPIRED"
    DISPUTE_FILED = "DISPUTE_FILED"
    ANALYST_REFUND = "ANALYST_REFUND"
    ANALYST_REJECT = "ANALYST_REJECT"
    ANALYST_REQUEST_EVIDENCE = "ANALYST_REQUEST_EVIDENCE"
    ANALYST_ESCALATE = "ANALYST_ESCALATE"
    APPEAL = "APPEAL"
    BUYER_ACCEPTED = "BUYER_ACCEPTED"  # the buyer says "I received it": the seller is paid
    PROOF_RELEASE = "PROOF_RELEASE"  # seller delivery proof accepted (by an admin, or the timer)
    ADMIN_REFUND = "ADMIN_REFUND"  # an admin sends the held money back to the buyer
    SELLER_NO_CLAIM = "SELLER_NO_CLAIM"  # the seller never entered the order number in time


class DisputeClass(StrEnum):
    SELLER_FAULT = "SELLER_FAULT"
    BUYER_FALSE_CLAIM = "BUYER_FALSE_CLAIM"
    COURIER_ISSUE = "COURIER_ISSUE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class Recommendation(StrEnum):
    SUGGEST_REFUND_BUYER = "SUGGEST_REFUND_BUYER"
    SUGGEST_REJECT_CLAIM = "SUGGEST_REJECT_CLAIM"
    SUGGEST_COURIER_ISSUE = "SUGGEST_COURIER_ISSUE"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"


class Route(StrEnum):
    FAST_LANE_CONFIRM = "FAST_LANE_CONFIRM"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class ClaimType(StrEnum):
    NOT_RECEIVED = "NOT_RECEIVED"
    WRONG_ITEM = "WRONG_ITEM"
    DAMAGED = "DAMAGED"
    NOT_AS_DESCRIBED = "NOT_AS_DESCRIBED"
    OTHER = "OTHER"


class FlagCode(StrEnum):
    CODE_CONTRADICTION = "CODE_CONTRADICTION"
    NO_COURIER_PROOF = "NO_COURIER_PROOF"
    EVIDENCE_EMPTY_OR_VAGUE = "EVIDENCE_EMPTY_OR_VAGUE"
    REPEAT_CLAIMANT = "REPEAT_CLAIMANT"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    LATE_REPORT = "LATE_REPORT"
    INJECTION_DETECTED = "INJECTION_DETECTED"


class UserRole(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


class WalletTxKind(StrEnum):
    SIGNUP_BONUS = "SIGNUP_BONUS"
    ADD_MONEY = "ADD_MONEY"
    SEND_MONEY_OUT = "SEND_MONEY_OUT"
    SEND_MONEY_IN = "SEND_MONEY_IN"
    PAYMENT_HELD = "PAYMENT_HELD"  # buyer: money left the wallet and is held for the order
    PAYMENT_RECEIVED_HELD = "PAYMENT_RECEIVED_HELD"  # seller: money arrived, held
    RELEASED = "RELEASED"  # seller: held money moved to the main wallet
    REFUNDED = "REFUNDED"  # buyer: held money came back
    REFUND_OUT = "REFUND_OUT"  # seller: held money went back to the buyer
    ADMIN_GRANT = "ADMIN_GRANT"
