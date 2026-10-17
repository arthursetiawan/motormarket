"""Shared field validators — keep KYC rules out of views/logs."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Basic Indonesian NIK: exactly 16 digits (no checksum in MVP).
NIK_RE = re.compile(r"^\d{16}$")

# Selfie upload ceiling (also mirrored in settings FILE upload knobs).
SELFIE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
SELFIE_ALLOWED_CONTENT_PREFIXES = ("image/",)


def validate_nik(value: str) -> str:
    """Return normalized NIK or raise ValidationError. Never log the raw value."""
    raw = (value or "").strip().replace(" ", "").replace("-", "")
    if not NIK_RE.match(raw):
        raise ValidationError(
            _("Nomor KTP (NIK) harus tepat 16 digit angka."),
            code="invalid_nik",
        )
    if raw == "0" * 16:
        raise ValidationError(
            _("Nomor KTP (NIK) tidak valid."),
            code="invalid_nik",
        )
    return raw


def validate_selfie_file(uploaded) -> None:
    """Reject missing, oversized, or non-image selfie uploads."""
    if uploaded is None:
        raise ValidationError(
            _("Foto diri (selfie) wajib diunggah."),
            code="selfie_required",
        )
    size = getattr(uploaded, "size", None)
    if size is not None and size > SELFIE_MAX_BYTES:
        raise ValidationError(
            _("Ukuran foto diri maksimal 5 MB."),
            code="selfie_too_large",
        )
    content_type = getattr(uploaded, "content_type", "") or ""
    if content_type and not content_type.startswith(SELFIE_ALLOWED_CONTENT_PREFIXES):
        raise ValidationError(
            _("Unggah file gambar (JPG, PNG, atau WebP)."),
            code="selfie_not_image",
        )
