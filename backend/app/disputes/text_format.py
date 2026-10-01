"""One string per dispute for the text classifier (BLUEPRINT.md Section 9.2).

Example: [COURIER=delivered] [CODE=true] [AMOUNT_BAND=2k-5k] BUYER: ... SELLER: ...
BUYER_EVIDENCE: ... SELLER_EVIDENCE: ...
"""

import re
from typing import Any

from app.config import load_config

MISSING = "NONE"
THOUSAND = 1_000
_SPACES = re.compile(r"\s+")


def amount_band(amount_bdt: int, cfg: dict[str, Any] | None = None) -> str:
    """Coarse amount bucket, so the model sees the size of the order but not the exact figure."""
    edges = (cfg or load_config())["analyzer"]["amount_bands_bdt"]
    if amount_bdt < edges[0]:
        return f"<{edges[0] // THOUSAND}k"
    for low, high in zip(edges, edges[1:], strict=False):
        if low <= amount_bdt < high:
            return f"{low // THOUSAND}k-{high // THOUSAND}k"
    return f">={edges[-1] // THOUSAND}k"


def _clean(text: str | None) -> str:
    collapsed = _SPACES.sub(" ", text or "").strip()
    return collapsed or MISSING


def build_text(
    *,
    courier_status: str,
    code_used: bool,
    amount_bdt: int,
    buyer_claim: str | None,
    seller_response: str | None,
    buyer_evidence: str | None,
    seller_evidence: str | None,
    cfg: dict[str, Any] | None = None,
) -> str:
    return (
        f"[COURIER={courier_status}] [CODE={str(code_used).lower()}] "
        f"[AMOUNT_BAND={amount_band(amount_bdt, cfg)}] "
        f"BUYER: {_clean(buyer_claim)} SELLER: {_clean(seller_response)} "
        f"BUYER_EVIDENCE: {_clean(buyer_evidence)} SELLER_EVIDENCE: {_clean(seller_evidence)}"
    )
