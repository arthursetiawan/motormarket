"""BaT-style auction mechanics: reserve, soft close, proxy / max bid."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from market.models import Bid, InAppNotification, Motorcycle, Watchlist


def min_increment() -> Decimal:
    return Decimal(str(getattr(settings, "AUCTION_MIN_INCREMENT_IDR", "50000")))


def soft_close_minutes() -> int:
    return int(getattr(settings, "AUCTION_SOFT_CLOSE_MINUTES", 2))


def soft_close_extend_minutes() -> int:
    return int(getattr(settings, "AUCTION_SOFT_CLOSE_EXTEND_MINUTES", 2))


def round_money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def current_high_bid(motorcycle: Motorcycle) -> Optional[Bid]:
    return motorcycle.bids.order_by("-amount", "-created_at").first()


def standing_amount(motorcycle: Motorcycle) -> Decimal:
    high = current_high_bid(motorcycle)
    if high:
        return Decimal(high.amount)
    return Decimal(motorcycle.start_price)


def minimum_next_bid(motorcycle: Motorcycle) -> Decimal:
    high = current_high_bid(motorcycle)
    if high:
        return round_money(Decimal(high.amount) + min_increment())
    return round_money(Decimal(motorcycle.start_price))


def reserve_met(motorcycle: Motorcycle, amount: Optional[Decimal] = None) -> bool:
    if not motorcycle.has_reserve or motorcycle.reserve_price is None:
        return True
    if amount is None:
        high = current_high_bid(motorcycle)
        if high is None:
            return False
        amount = Decimal(high.amount)
    return Decimal(amount) >= Decimal(motorcycle.reserve_price)


def ensure_auction_window(motorcycle: Motorcycle) -> None:
    if motorcycle.auction_status != Motorcycle.STATUS_OPEN:
        return
    if motorcycle.ends_at and timezone.now() >= motorcycle.ends_at:
        close_auction(motorcycle)


def close_auction(motorcycle: Motorcycle) -> Motorcycle:
    if motorcycle.auction_status != Motorcycle.STATUS_OPEN:
        return motorcycle
    high = current_high_bid(motorcycle)
    if high is None:
        motorcycle.auction_status = Motorcycle.STATUS_ENDED
        motorcycle.save(update_fields=["auction_status"])
        return motorcycle
    if reserve_met(motorcycle, Decimal(high.amount)):
        motorcycle.auction_status = Motorcycle.STATUS_SOLD
        motorcycle.is_sold = True
        motorcycle.sold_price = high.amount
        motorcycle.save(update_fields=["auction_status", "is_sold", "sold_price"])
    else:
        motorcycle.auction_status = Motorcycle.STATUS_RESERVE_NOT_MET
        motorcycle.save(update_fields=["auction_status"])
    return motorcycle


def apply_soft_close(motorcycle: Motorcycle) -> bool:
    if not motorcycle.ends_at:
        return False
    now = timezone.now()
    window = timezone.timedelta(minutes=soft_close_minutes())
    if now < motorcycle.ends_at - window:
        return False
    extend = timezone.timedelta(minutes=soft_close_extend_minutes())
    motorcycle.ends_at = max(motorcycle.ends_at, now) + extend
    motorcycle.save(update_fields=["ends_at"])
    return True


def _notify(user, kind: str, motorcycle: Motorcycle, message: str) -> None:
    if user is None:
        return
    InAppNotification.objects.create(
        user=user,
        kind=kind,
        motorcycle=motorcycle,
        message=message,
    )


def _notify_watchers_ending_soon(motorcycle: Motorcycle) -> None:
    if not motorcycle.ends_at:
        return
    remaining = motorcycle.ends_at - timezone.now()
    if remaining.total_seconds() > 3600 or remaining.total_seconds() < 0:
        return
    for watch in Watchlist.objects.filter(motorcycle=motorcycle).select_related("user"):
        if not InAppNotification.objects.filter(
            user=watch.user,
            motorcycle=motorcycle,
            kind=InAppNotification.KIND_ENDING_SOON,
        ).exists():
            _notify(
                watch.user,
                InAppNotification.KIND_ENDING_SOON,
                motorcycle,
                f"Lelang {motorcycle.title} segera berakhir.",
            )


def _user_max_map(motorcycle: Motorcycle) -> dict[int, tuple[Decimal, Bid]]:
    """user_id -> (max ceiling, earliest bid that established that ceiling)."""
    ceilings: dict[int, tuple[Decimal, Bid]] = {}
    for bid in motorcycle.bids.order_by("created_at"):
        ceiling = Decimal(bid.max_amount if bid.max_amount is not None else bid.amount)
        prev = ceilings.get(bid.bidder_id)
        if prev is None or ceiling > prev[0]:
            ceilings[bid.bidder_id] = (ceiling, bid)
        elif ceiling == prev[0]:
            # keep earliest
            pass
    return ceilings


def _compute_standing(
    start: Decimal,
    ceilings: dict[int, tuple[Decimal, Bid]],
    *,
    has_reserve: bool = False,
    reserve_price: Optional[Decimal] = None,
) -> tuple[Optional[int], Decimal]:
    if not ceilings:
        return None, start
    ranked = sorted(ceilings.items(), key=lambda kv: (-kv[1][0], kv[1][1].created_at))
    leader_id, (leader_max, _) = ranked[0]
    if len(ranked) == 1:
        standing = start
        # Lift toward hidden reserve when sole proxy covers it (eBay-style).
        if has_reserve and reserve_price and leader_max >= Decimal(reserve_price):
            standing = min(leader_max, max(standing, round_money(Decimal(reserve_price))))
        return leader_id, standing
    second_max = ranked[1][1][0]
    standing = min(leader_max, round_money(second_max + min_increment()))
    standing = max(standing, start)
    if has_reserve and reserve_price and leader_max >= Decimal(reserve_price):
        standing = max(standing, min(leader_max, round_money(Decimal(reserve_price))))
    return leader_id, standing


@transaction.atomic
def place_proxy_bid(
    motorcycle: Motorcycle,
    bidder,
    max_amount: Decimal,
) -> tuple[Bid, str]:
    """
    Place or raise a proxy (max) bid.
    Returns (standing Bid row for the new high, Bahasa status message).
    """
    motorcycle = Motorcycle.objects.select_for_update().get(pk=motorcycle.pk)
    ensure_auction_window(motorcycle)
    motorcycle.refresh_from_db()

    if motorcycle.auction_status != Motorcycle.STATUS_OPEN:
        raise ValueError("Lelang sudah ditutup.")
    if motorcycle.is_sold:
        raise ValueError("Unit sudah terjual.")
    if motorcycle.seller_id == bidder.id:
        raise ValueError("Penjual tidak bisa menawar unit sendiri.")
    if motorcycle.ends_at and timezone.now() >= motorcycle.ends_at:
        close_auction(motorcycle)
        raise ValueError("Waktu lelang sudah habis.")

    max_amount = round_money(Decimal(max_amount))
    start = round_money(Decimal(motorcycle.start_price))
    high = current_high_bid(motorcycle)
    floor = start if high is None else round_money(Decimal(high.amount) + min_increment())

    # Allow raising max while already leading without needing floor > standing
    ceilings_before = _user_max_map(motorcycle)
    already = ceilings_before.get(bidder.id)
    if already and already[0] >= max_amount:
        raise ValueError("Tawaran maksimum baru harus lebih tinggi dari maks Anda sebelumnya.")
    if not already and max_amount < floor:
        raise ValueError(f"Tawaran maksimum minimal {floor}.")
    if already and max_amount < floor and already[0] < floor:
        raise ValueError(f"Tawaran maksimum minimal {floor}.")

    previous_high = high
    previous_leader = previous_high.bidder_id if previous_high else None

    Bid.objects.create(
        motorcycle=motorcycle,
        bidder=bidder,
        amount=min(max_amount, floor),
        max_amount=max_amount,
        is_proxy=True,
        is_automatic=False,
    )

    ceilings = _user_max_map(motorcycle)
    leader_id, standing = _compute_standing(
        start,
        ceilings,
        has_reserve=motorcycle.has_reserve,
        reserve_price=motorcycle.reserve_price,
    )

    # Materialize standing as an automatic bid if needed
    current = current_high_bid(motorcycle)
    if leader_id is not None and (current is None or Decimal(current.amount) != standing or current.bidder_id != leader_id):
        leader_user = User.objects.get(pk=leader_id)
        leader_max = ceilings[leader_id][0]
        standing_bid = Bid.objects.create(
            motorcycle=motorcycle,
            bidder=leader_user,
            amount=standing,
            max_amount=leader_max,
            is_proxy=True,
            is_automatic=True,
        )
    else:
        standing_bid = current_high_bid(motorcycle)

    extended = apply_soft_close(motorcycle)

    new_high = current_high_bid(motorcycle)
    if previous_leader and new_high and previous_leader != new_high.bidder_id:
        prev_user = User.objects.filter(pk=previous_leader).first()
        _notify(
            prev_user,
            InAppNotification.KIND_OUTBID,
            motorcycle,
            f"Anda digeser di {motorcycle.title}. Tawaran teratas sekarang {new_high.amount}.",
        )
    _notify_watchers_ending_soon(motorcycle)

    if new_high and new_high.bidder_id == bidder.id:
        msg = f"Tawaran tercatat. Anda teratas hingga maks. Rp {max_amount:,.0f}."
    else:
        msg = (
            f"Tawaran diterima, tetapi proxy lain lebih tinggi. "
            f"Harga saat ini Rp {new_high.amount:,.0f}."
            if new_high
            else "Tawaran diterima."
        )
    if extended:
        msg += " Soft close: waktu lelang diperpanjang."
    return standing_bid, msg


@transaction.atomic
def buy_now(motorcycle: Motorcycle, buyer) -> Motorcycle:
    motorcycle = Motorcycle.objects.select_for_update().get(pk=motorcycle.pk)
    ensure_auction_window(motorcycle)
    motorcycle.refresh_from_db()
    if not motorcycle.buy_now_price:
        raise ValueError("Beli Sekarang tidak tersedia untuk unit ini.")
    if motorcycle.auction_status != Motorcycle.STATUS_OPEN or motorcycle.is_sold:
        raise ValueError("Unit tidak lagi tersedia.")
    if motorcycle.seller_id == buyer.id:
        raise ValueError("Penjual tidak bisa membeli unit sendiri.")
    price = round_money(Decimal(motorcycle.buy_now_price))
    Bid.objects.create(
        motorcycle=motorcycle,
        bidder=buyer,
        amount=price,
        max_amount=price,
        is_proxy=False,
        is_automatic=False,
    )
    motorcycle.auction_status = Motorcycle.STATUS_SOLD
    motorcycle.is_sold = True
    motorcycle.sold_price = price
    motorcycle.ends_at = timezone.now()
    motorcycle.save(update_fields=["auction_status", "is_sold", "sold_price", "ends_at"])
    _notify(
        motorcycle.seller,
        InAppNotification.KIND_SOLD,
        motorcycle,
        f"{motorcycle.title} terjual via Beli Sekarang seharga {price}.",
    )
    return motorcycle


def auction_badge(motorcycle: Motorcycle) -> dict:
    ensure_auction_window(motorcycle)
    motorcycle.refresh_from_db()
    met = None
    if motorcycle.auction_status == Motorcycle.STATUS_OPEN:
        high = current_high_bid(motorcycle)
        if not motorcycle.has_reserve:
            met = True
        elif high is not None:
            met = reserve_met(motorcycle, Decimal(high.amount))
    return {
        "no_reserve": not motorcycle.has_reserve,
        "reserve_met": met,
        "status": motorcycle.auction_status,
        "status_label": motorcycle.get_auction_status_display(),
        "min_next": minimum_next_bid(motorcycle),
        "ends_at": motorcycle.ends_at,
    }


def surat_announcements(motorcycle: Motorcycle) -> list[str]:
    """Manheim-lite sale announcements derived from surat fields."""
    flags: list[str] = []
    if getattr(motorcycle, "pajak_mati", False):
        flags.append("Pajak mati")
    stnk = getattr(motorcycle, "stnk_status", "unknown")
    bpkb = getattr(motorcycle, "bpkb_status", "unknown")
    if stnk == "lengkap" and bpkb in ("ada", "di_leasing") and not getattr(motorcycle, "pajak_mati", False):
        flags.append("Surat lengkap")
    elif stnk == "lengkap" and bpkb in ("unknown", "") and not getattr(motorcycle, "pajak_mati", False):
        flags.append("STNK only")
    if bpkb == "di_leasing":
        flags.append("BPKB proses / di leasing")
    elif bpkb == "hilang":
        flags.append("BPKB hilang")
    if stnk == "hilang":
        flags.append("STNK hilang")
    elif stnk == "atas_nama_lain":
        flags.append("STNK atas nama lain")
    return flags
