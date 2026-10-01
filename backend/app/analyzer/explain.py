"""Template-based explanation in Bangla and English (BLUEPRINT.md Section 9.3, stage 6).

Every sentence is filled from flags, probabilities and the case facts, so nothing is invented.
The three sections answer the guideline questions: what happened, why is it risky, what should
upay do next.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.analyzer.case import DisputeCase
from app.analyzer.consistency import Flag
from app.analyzer.router import Routing
from app.enums import FlagCode

I18N_DIR = Path(__file__).resolve().parents[1] / "i18n"
BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
PERCENT = 100
LANGUAGES = ("en", "bn")


@lru_cache(maxsize=2)
def templates(lang: str) -> dict[str, Any]:
    with (I18N_DIR / f"explain_{lang}.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def _digits(text: str, lang: str) -> str:
    return text.translate(BN_DIGITS) if lang == "bn" else text


def _flag_sentences(flag: Flag, lang: str) -> list[str]:
    t = templates(lang)
    template = t["flags"][flag.code]
    if flag.code == FlagCode.EVIDENCE_EMPTY_OR_VAGUE:
        return [template.format(party=t["parties"][p]) for p in flag.detail["parties"]]
    return [template.format(**flag.detail)]


def explain_language(
    case: DisputeCase,
    flags: list[Flag],
    probs: dict[str, float],
    routing: Routing,
    lang: str,
) -> dict[str, str]:
    t = templates(lang)
    happened = [t["order"].format(amount=case.amount_bdt)]
    happened.append(t["courier"][case.courier_status])
    if case.delivery_code_used or case.courier_status == "delivered":
        happened.append(t["code"]["used" if case.delivery_code_used else "not_used"])
    when = case.opened_at.strftime("%Y-%m-%d %H:%M UTC")
    happened.append(t["dispute"].format(when=when))
    happened.append(t["seller"]["responded" if case.seller_responded else "pending"])

    risky = [s for flag in flags for s in _flag_sentences(flag, lang)] or [t["no_flags"]]
    risky.append(
        t["model"].format(
            percent=round(routing.top_probability * PERCENT),
            class_description=t["classes"][routing.top_class],
        )
    )

    reasons = t["reason_separator"].join(t["route_reasons"][r] for r in routing.route_reasons)
    route_text = t["route"][routing.route.value].format(reasons=reasons)
    next_step = [t["recommendation"][routing.recommendation.value], route_text]

    sections = {
        "what_happened": " ".join(happened),
        "why_risky": " ".join(risky),
        "next_step": " ".join(next_step),
    }
    return {key: _digits(text, lang) for key, text in sections.items()}


def explain(
    case: DisputeCase, flags: list[Flag], probs: dict[str, float], routing: Routing
) -> dict[str, Any]:
    """Sections and a joined text per language."""
    out: dict[str, Any] = {"sections": {}, "text": {}}
    for lang in LANGUAGES:
        sections = explain_language(case, flags, probs, routing, lang)
        headings = templates(lang)["headings"]
        out["sections"][lang] = sections
        out["text"][lang] = "\n".join(f"{headings[k]}: {v}" for k, v in sections.items())
    return out
