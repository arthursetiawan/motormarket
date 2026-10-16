"""Contact / meetup unlock after platform fee payment."""

from __future__ import annotations

from django.utils import timezone

from market.models import BypassFlag, DealSheet, PlatformFee, UserSafetyProfile
from market.services.fees import compute_platform_fee, fee_basis_for_listing


def buyer_has_paid_fee(motorcycle, buyer) -> bool:
    if not buyer or not buyer.is_authenticated:
        return False
    return PlatformFee.objects.filter(
        motorcycle=motorcycle, buyer=buyer, status="paid"
    ).exists()


def contact_unlock_blocked(user) -> bool:
    try:
        profile = user.safety_profile
    except UserSafetyProfile.DoesNotExist:
        return False
    return profile.contact_blocked or profile.is_banned


def ensure_safety_profile(user) -> UserSafetyProfile:
    profile, _ = UserSafetyProfile.objects.get_or_create(user=user)
    return profile


def simulate_pay_fee(*, motorcycle, buyer, deal_sheet: DealSheet | None = None) -> PlatformFee:
    """MVP checkout: mark fee paid in DB (no Midtrans/Xendit yet)."""
    if contact_unlock_blocked(buyer):
        raise PermissionError("Akun diblokir membuka kontak (bypass / forfeit).")

    existing = PlatformFee.objects.filter(
        motorcycle=motorcycle, buyer=buyer, status="paid"
    ).first()
    if existing:
        return existing

    basis = fee_basis_for_listing(motorcycle)
    fee_amount = compute_platform_fee(basis)
    fee = PlatformFee.objects.create(
        motorcycle=motorcycle,
        buyer=buyer,
        deal_sheet=deal_sheet,
        basis_amount=basis,
        fee_amount=fee_amount,
        status="paid",
        simulated=True,
        paid_at=timezone.now(),
    )
    if deal_sheet and deal_sheet.status == "open":
        deal_sheet.status = "unlocked"
        deal_sheet.save(update_fields=["status"])
    return fee


def flag_bypass(*, user, motorcycle=None, reason: str, action: str = "warn") -> BypassFlag:
    ensure_safety_profile(user)
    flag = BypassFlag.objects.create(
        user=user,
        motorcycle=motorcycle,
        reason=reason,
        action=action,
    )
    profile = user.safety_profile
    if action == "block_contact":
        profile.contact_blocked = True
        profile.save(update_fields=["contact_blocked", "updated_at"])
    elif action == "ban":
        profile.is_banned = True
        profile.contact_blocked = True
        profile.save(update_fields=["is_banned", "contact_blocked", "updated_at"])
        user.is_active = False
        user.save(update_fields=["is_active"])
    return flag


def reveal_contact(motorcycle, viewer) -> dict | None:
    """Return seller contact dict if viewer may see it; else None."""
    if not viewer.is_authenticated:
        return None
    if viewer == motorcycle.seller:
        return {
            "phone": motorcycle.seller_phone or "",
            "wa": motorcycle.seller_wa or "",
            "self": True,
        }
    if contact_unlock_blocked(viewer):
        return None
    if not buyer_has_paid_fee(motorcycle, viewer):
        return None
    return {
        "phone": motorcycle.seller_phone or "(penjual belum mengisi nomor)",
        "wa": motorcycle.seller_wa or "(penjual belum mengisi WA)",
        "self": False,
    }
