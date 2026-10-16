"""Strip / redact phone, WA, IG, TPM from public listing text and chat."""

from __future__ import annotations

import re
from dataclasses import dataclass


# Indo mobile: 08xx, +62, 62…; also spaced / dashed variants
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?62|0)\s*8[\d\s\-.]{7,14}\d|\b\d{3,4}[\s\-.]?\d{3,4}[\s\-.]?\d{3,5}\b",
    re.IGNORECASE,
)
_WA_RE = re.compile(
    r"\b(?:wa|whats?app|w\.?a\.?|tpm|chat\s*wa|hubungi\s*wa|dm\s*ig|instagram|insta|@[\w.]{3,})\b",
    re.IGNORECASE,
)
_IG_HANDLE_RE = re.compile(r"(?<!\w)@[\w.]{3,30}\b")
_CONTACT_PHRASE_RE = re.compile(
    r"\b(?:hubungi|call|telp|telepon|sms|line\s*id|kontak\s*saya|pm\s*saya)\b",
    re.IGNORECASE,
)

REDACT = "[kontak disembunyikan]"


@dataclass
class FilterResult:
    text: str
    redacted: bool
    blocked: bool
    reason: str = ""


def scrub_public_text(text: str | None) -> FilterResult:
    """For listing title/description — always redact, never store raw contacts in public fields."""
    if not text:
        return FilterResult(text="", redacted=False, blocked=False)
    original = text
    out = _PHONE_RE.sub(REDACT, text)
    out = _IG_HANDLE_RE.sub(REDACT, out)
    out = _WA_RE.sub(REDACT, out)
    out = _CONTACT_PHRASE_RE.sub(REDACT, out)
    changed = out != original
    return FilterResult(text=out, redacted=changed, blocked=False)


def filter_chat_message(text: str | None, *, strict_block: bool = True) -> FilterResult:
    """Chat: redact phones/WA/IG; optionally block message if heavy contact share."""
    if not text:
        return FilterResult(text="", redacted=False, blocked=True, reason="Pesan kosong.")
    stripped = text.strip()
    if len(stripped) > 2000:
        return FilterResult(text="", redacted=False, blocked=True, reason="Pesan terlalu panjang.")

    phone_hits = len(_PHONE_RE.findall(stripped))
    wa_hits = len(_WA_RE.findall(stripped))
    ig_hits = len(_IG_HANDLE_RE.findall(stripped))

    if strict_block and (phone_hits >= 1 or (wa_hits + ig_hits) >= 2):
        return FilterResult(
            text="",
            redacted=True,
            blocked=True,
            reason="Jangan bagikan nomor / WA / IG di chat. Bayar biaya platform untuk buka kontak resmi.",
        )

    out = _PHONE_RE.sub(REDACT, stripped)
    out = _IG_HANDLE_RE.sub(REDACT, out)
    out = _WA_RE.sub(REDACT, out)
    changed = out != stripped
    reason = ""
    if changed:
        reason = "Kontak di-redaksi. Pakai chat NegoMotor; buka kontak setelah bayar biaya platform."
    return FilterResult(text=out, redacted=changed, blocked=False, reason=reason)


def contains_contact_leak(text: str | None) -> bool:
    if not text:
        return False
    return bool(_PHONE_RE.search(text) or _WA_RE.search(text) or _IG_HANDLE_RE.search(text))
