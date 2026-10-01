"""Rule-based consistency checks (BLUEPRINT.md Section 9.3, stage 1). Pure Python, no ML.

Texts passed in must already be sanitised by the injection screen, so instruction-like sentences
cannot steer any flag.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from app.analyzer.case import DisputeCase
from app.config import load_config
from app.disputes.claim_type import detect_claim_type
from app.enums import ClaimType, CourierStatus, FlagCode, Party

BN_TO_ASCII = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_CURRENCY = r"(?:৳|tk\.?|taka|bdt|টাকা)"
_NUMBER = r"(\d[\d,]*(?:\.\d+)?)"
AMOUNT_PATTERNS = (
    re.compile(_NUMBER + r"\s*" + _CURRENCY, re.IGNORECASE),
    re.compile(_CURRENCY + r"\s*" + _NUMBER, re.IGNORECASE),
)
SECONDS_PER_HOUR = 3_600
PROOF_STATUSES = (CourierStatus.IN_TRANSIT, CourierStatus.DELIVERED, CourierStatus.RETURNED)


@dataclass(frozen=True)
class Flag:
    code: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CaseTexts:
    """The case texts after the injection screen."""

    claim: str
    seller_response: str
    buyer_evidence: list[str]
    seller_evidence: list[str]

    def all(self) -> list[str]:
        return [self.claim, self.seller_response, *self.buyer_evidence, *self.seller_evidence]


def extract_amounts(text: str) -> list[float]:
    """Amounts written next to a currency word or sign (৳, tk, taka, bdt, টাকা)."""
    folded = unicodedata.normalize("NFKC", text).translate(BN_TO_ASCII)
    amounts = []
    for pattern in AMOUNT_PATTERNS:
        for match in pattern.finditer(folded):
            try:
                amounts.append(float(match.group(1).replace(",", "")))
            except ValueError:
                continue
    return amounts


def _is_vague(text: str, min_chars: int, min_words: int) -> bool:
    stripped = text.strip()
    return len(stripped) < min_chars or len(stripped.split()) < min_words


def check(case: DisputeCase, texts: CaseTexts, cfg: dict[str, Any] | None = None) -> list[Flag]:
    """Flags in a fixed order: contradiction, proof, evidence, repeat, amount, lateness."""
    config = cfg or load_config()
    settings = config["analyzer"]
    routing = config["rules"]["routing"]
    flags: list[Flag] = []

    claim_type = case.claim_type or detect_claim_type(texts.claim)
    if (
        case.delivered_at is not None
        and case.delivery_code_used
        and claim_type == ClaimType.NOT_RECEIVED
    ):
        flags.append(Flag(FlagCode.CODE_CONTRADICTION))

    dispatched = any(status in PROOF_STATUSES for status, _ in case.courier_events)
    seller_text = " ".join([texts.seller_response, *texts.seller_evidence]).lower()
    has_proof_text = any(word.lower() in seller_text for word in settings["proof_keywords"])
    if not dispatched and not has_proof_text:
        flags.append(Flag(FlagCode.NO_COURIER_PROOF))

    vague = []
    limits = (settings["min_evidence_chars"], settings["min_evidence_words"])
    if _is_vague(" ".join(texts.buyer_evidence), *limits):
        vague.append(Party.BUYER.value)
    if case.seller_responded and _is_vague(" ".join(texts.seller_evidence), *limits):
        vague.append(Party.SELLER.value)
    if vague:
        flags.append(Flag(FlagCode.EVIDENCE_EMPTY_OR_VAGUE, {"parties": vague}))

    if case.buyer_disputes_in_window >= routing["repeat_claimant_count"]:
        detail = {
            "count": case.buyer_disputes_in_window,
            "days": routing["repeat_claimant_window_days"],
        }
        flags.append(Flag(FlagCode.REPEAT_CLAIMANT, detail))

    stated = [a for t in texts.all() for a in extract_amounts(t)]
    tolerance = settings["amount_tolerance"] * case.amount_bdt
    if stated and not any(abs(a - case.amount_bdt) <= tolerance for a in stated):
        flags.append(
            Flag(
                FlagCode.AMOUNT_MISMATCH,
                {"stated": round(stated[0]), "order_amount": case.amount_bdt},
            )
        )

    if case.delivered_at is not None:
        hours = (case.opened_at - case.delivered_at).total_seconds() / SECONDS_PER_HOUR
        if hours > settings["late_report_hours"]:
            flags.append(Flag(FlagCode.LATE_REPORT, {"hours": round(hours)}))
    return flags
