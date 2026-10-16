"""Helpers so sell/bid tests can attach a complete private KYC profile."""

from __future__ import annotations

from datetime import date
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from market.models import UserProfile


def tiny_selfie(name: str = "selfie.jpg") -> SimpleUploadedFile:
    buf = BytesIO()
    Image.new("RGB", (32, 32), color=(40, 90, 160)).save(buf, format="JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


def attach_complete_kyc(user, nik: str | None = None) -> UserProfile:
    """Give ``user`` a complete KYC profile (for tests that exercise sell/bid)."""
    # Deterministic unique-ish NIK from user pk (still 16 digits).
    if nik is None:
        nik = f"{user.pk:016d}"[-16:]
        if nik == "0" * 16:
            nik = "3174010101010001"
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.ktp_number = nik
    profile.date_of_birth = date(1995, 6, 15)
    if not profile.selfie:
        profile.selfie.save(f"{user.username}-selfie.jpg", tiny_selfie(), save=False)
    from django.utils import timezone

    profile.kyc_completed_at = timezone.now()
    profile.save()
    return profile
