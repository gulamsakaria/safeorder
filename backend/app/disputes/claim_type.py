"""Keyword fallback that spots a "not received" claim in free text (English, Bangla, Banglish).

The buyer form can send a structured ``claim_type``; this fallback is used only when it is
missing. It is a deterministic heuristic and misses unusual phrasing, so the structured value
wins whenever it is present.
"""

import re
import unicodedata

from app.enums import ClaimType

_I = re.IGNORECASE
NOT_RECEIVED_PATTERNS = (
    re.compile(
        r"\b(?:not|never|didn'?t|did not|haven'?t|have not|hasn'?t|has not|yet to)\s+"
        r"(?:\w+\s+){0,2}(?:receive[d]?|get|got|deliver(?:ed)?|arrive[d]?)\b",
        _I,
    ),
    re.compile(r"\bnever (?:arrived|came)\b", _I),
    re.compile(
        r"পাইনি|পাই নাই|পাইনা|পাওয়া যায়নি|পাওয়া যায় নি|আসেনি|আসে নাই|পৌঁছায়নি|পৌঁছায় নাই"
        r"|পৌছায়নি|পৌছায় নাই|ডেলিভারি হয়নি|ডেলিভারি হয় নাই"
    ),
    re.compile(
        r"\b(?:pai ?nai|pai ?ni|paini|painai|pai na|pelam na|ashe ?nai|ase ?nai|asheni|aseni|"
        r"pouchay ?nai|pouchaini|pouche ?nai|receive kori ?nai|receive hoy ?nai|"
        r"delivery hoy ?nai)\b",
        _I,
    ),
)


def detect_claim_type(text: str | None) -> ClaimType | None:
    """NOT_RECEIVED when the claim says the parcel never arrived; otherwise None (unknown)."""
    if not text:
        return None
    normalized = unicodedata.normalize("NFKC", text)
    if any(p.search(normalized) for p in NOT_RECEIVED_PATTERNS):
        return ClaimType.NOT_RECEIVED
    return None
