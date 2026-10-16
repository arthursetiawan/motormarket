"""Listing copy sentiment / tone signals (Bahasa + English).

Practical lexicon + heuristics — not a neural NLP model. Scores whether
title/description read clear and professional vs aggressive, spammy, or
evasive. Used as a trust *signal* next to star ratings, not a replacement.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

METHOD_VERSION = "lexicon_v1"

# Positive / professional cues (Bahasa + English)
POSITIVE_TERMS = {
    "ori",
    "original",
    "surat lengkap",
    "bpkb",
    "stnk",
    "pajak hidup",
    "service record",
    "terawat",
    "rawat rutin",
    "mesin halus",
    "nego",
    "nego wajar",
    "bisa survey",
    "bisa dicek",
    "kondisi bagus",
    "baik",
    "excellent",
    "well maintained",
    "single owner",
    "pemilik pertama",
    "first owner",
    "full service",
    "garage kept",
    "ready",
    "siap pakai",
}

# Aggressive / spammy / evasive cues
NEGATIVE_TERMS = {
    "wa only",
    "whatsapp only",
    "chat wa",
    "hubungi wa",
    "call me",
    "dm ig",
    "instagram",
    "no lowball",
    "no low ball",
    "jangan nawar",
    "harga pas",
    "fixi",
    "fixi!",
    "serius aja",
    "serius saja",
    "buang waktu",
    "spam",
    "!!!",
    "urgent",
    "cepat laku",
    "must sell",
    "cash only asap",
    "murah banget",
    "super murah",
    "harga di bawah pasar",
    "no time wasters",
    "first come",
}

UPPER_RATIO_ALERT = 0.45
EXCLAIM_ALERT = 3
PHONE_RE = re.compile(r"(?:\+62|62|0)8\d{7,12}|\b08\d{2}[\s-]?\d{3,4}[\s-]?\d{3,5}\b")
URL_RE = re.compile(r"https?://|www\.|t\.me/|wa\.me/", re.I)
REPEAT_PUNCT_RE = re.compile(r"[!?]{3,}|\.{4,}")
WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9]+", re.UNICODE)


@dataclass
class SentimentSignal:
    code: str
    polarity: str  # positive | negative | info
    message: str


@dataclass
class SentimentReport:
    score: float  # 0–100, higher = clearer / more professional
    label: str  # professional | mixed | caution
    signals: list[SentimentSignal] = field(default_factory=list)
    method_version: str = METHOD_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _count_phrase_hits(haystack: str, phrases: set[str]) -> list[str]:
    hits = []
    for phrase in phrases:
        if phrase in haystack:
            hits.append(phrase)
    return hits


def assess_listing_text(*, title: str | None, description: str | None) -> SentimentReport:
    """Score listing title + description for tone / trust of copy."""
    title = title or ""
    description = description or ""
    combined = f"{title}\n{description}".strip()
    norm = _normalize(combined)
    signals: list[SentimentSignal] = []
    score = 72.0  # neutral-professional baseline

    if len(norm) < 40:
        score -= 18
        signals.append(
            SentimentSignal(
                "short_copy",
                "negative",
                "Deskripsi terlalu singkat — kurang detail untuk pembeli.",
            )
        )
    elif len(norm) >= 120:
        score += 6
        signals.append(
            SentimentSignal(
                "detailed_copy",
                "positive",
                "Deskripsi cukup lengkap.",
            )
        )

    pos_hits = _count_phrase_hits(norm, POSITIVE_TERMS)
    neg_hits = _count_phrase_hits(norm, NEGATIVE_TERMS)
    score += min(len(pos_hits) * 3.5, 14)
    score -= min(len(neg_hits) * 7, 28)
    for phrase in pos_hits[:4]:
        signals.append(
            SentimentSignal("positive_cue", "positive", f"Sinyal positif: “{phrase}”.")
        )
    for phrase in neg_hits[:5]:
        signals.append(
            SentimentSignal("negative_cue", "negative", f"Sinyal agresif/spam: “{phrase}”.")
        )

    letters = [c for c in combined if c.isalpha()]
    if letters:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio >= UPPER_RATIO_ALERT and len(letters) > 20:
            score -= 12
            signals.append(
                SentimentSignal(
                    "shouting",
                    "negative",
                    "Terlalu banyak huruf kapital (terkesan teriak/spam).",
                )
            )

    exclaims = combined.count("!")
    if exclaims >= EXCLAIM_ALERT:
        score -= 8
        signals.append(
            SentimentSignal(
                "exclaim_heavy",
                "negative",
                "Terlalu banyak tanda seru.",
            )
        )

    if REPEAT_PUNCT_RE.search(combined):
        score -= 6
        signals.append(
            SentimentSignal(
                "repeat_punct",
                "negative",
                "Tanda baca berulang (spammy).",
            )
        )

    if PHONE_RE.search(combined) or URL_RE.search(combined):
        score -= 10
        signals.append(
            SentimentSignal(
                "off_platform_contact",
                "negative",
                "Ada nomor/tautan kontak di luar platform.",
            )
        )

    words = WORD_RE.findall(norm)
    if words:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.45 and len(words) > 12:
            score -= 10
            signals.append(
                SentimentSignal(
                    "repetitive",
                    "negative",
                    "Teks sangat berulang.",
                )
            )

    score = max(0.0, min(100.0, round(score, 1)))
    if score >= 70:
        label = "professional"
    elif score >= 45:
        label = "mixed"
    else:
        label = "caution"

    return SentimentReport(score=score, label=label, signals=signals)
