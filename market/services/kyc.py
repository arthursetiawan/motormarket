"""KYC completeness helpers for sell/bid gates."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from market.models import UserProfile


def get_or_create_profile(user: AbstractBaseUser) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def kyc_is_complete(user: AbstractBaseUser | None) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    try:
        return user.profile.is_complete
    except UserProfile.DoesNotExist:
        return False


def kyc_incomplete_message() -> str:
    return (
        "Lengkapi verifikasi akun (email, KTP/NIK, tanggal lahir, dan foto diri) "
        "sebelum jual atau menawar di NegoMotor."
    )
