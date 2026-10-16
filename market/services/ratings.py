"""Dual-role reputation (as seller / as buyer) after closed deals."""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Avg, Count, Q
from market.models import Bid, ClosedDeal, Motorcycle, UserRating


@dataclass
class RoleStats:
    average: float | None
    count: int

    @property
    def display(self) -> str:
        if not self.count or self.average is None:
            return "Belum ada rating"
        return f"{self.average:.1f}★ ({self.count})"


@dataclass
class ReputationSnapshot:
    as_seller: RoleStats
    as_buyer: RoleStats


def reputation_for(user: User) -> ReputationSnapshot:
    rows = (
        UserRating.objects.filter(ratee=user)
        .values("ratee_role")
        .annotate(avg=Avg("score"), n=Count("id"))
    )
    by_role = {row["ratee_role"]: row for row in rows}

    def _stats(role: str) -> RoleStats:
        row = by_role.get(role)
        if not row:
            return RoleStats(average=None, count=0)
        return RoleStats(average=round(float(row["avg"]), 2), count=int(row["n"]))

    return ReputationSnapshot(
        as_seller=_stats(UserRating.ROLE_SELLER),
        as_buyer=_stats(UserRating.ROLE_BUYER),
    )


def can_rate(user: User, deal: ClosedDeal) -> bool:
    if user.pk not in (deal.buyer_id, deal.seller_id):
        return False
    return not UserRating.objects.filter(deal=deal, rater=user).exists()


def counterpart_role(user: User, deal: ClosedDeal) -> str:
    """Role of the person being rated when `user` submits a rating."""
    if user.pk == deal.buyer_id:
        return UserRating.ROLE_SELLER
    if user.pk == deal.seller_id:
        return UserRating.ROLE_BUYER
    raise ValueError("User is not a party to this deal")


def submit_rating(
    *,
    deal: ClosedDeal,
    rater: User,
    score: int,
    review: str = "",
) -> UserRating:
    if not can_rate(rater, deal):
        raise PermissionError("Tidak bisa memberi rating untuk transaksi ini.")
    ratee_role = counterpart_role(rater, deal)
    ratee_id = deal.seller_id if ratee_role == UserRating.ROLE_SELLER else deal.buyer_id
    return UserRating.objects.create(
        deal=deal,
        rater=rater,
        ratee_id=ratee_id,
        ratee_role=ratee_role,
        score=score,
        review=(review or "").strip()[:400],
    )


@transaction.atomic
def close_deal(
    *,
    motorcycle: Motorcycle,
    seller: User,
    buyer: User,
    sale_price=None,
    winning_bid: Bid | None = None,
    notes: str = "",
) -> ClosedDeal:
    """Mark listing sold and open the dual-rating window."""
    if motorcycle.seller_id != seller.pk:
        raise PermissionError("Hanya penjual yang bisa menutup transaksi.")
    if buyer.pk == seller.pk:
        raise ValueError("Pembeli tidak boleh sama dengan penjual.")
    existing = ClosedDeal.objects.filter(motorcycle=motorcycle).first()
    if existing:
        return existing

    if winning_bid is None:
        winning_bid = (
            motorcycle.bids.filter(bidder=buyer).order_by("-amount").first()
            or motorcycle.bids.order_by("-amount").first()
        )
        if winning_bid and winning_bid.bidder_id != buyer.pk:
            winning_bid = None

    price = sale_price
    if price is None and winning_bid is not None:
        price = winning_bid.amount
    if price is None:
        price = motorcycle.start_price

    motorcycle.is_sold = True
    motorcycle.sold_price = price
    update_fields = ["is_sold", "sold_price"]
    if hasattr(motorcycle, "deal_status"):
        motorcycle.deal_status = "closed_on_platform"
        update_fields.append("deal_status")
    motorcycle.save(update_fields=update_fields)

    return ClosedDeal.objects.create(
        motorcycle=motorcycle,
        seller=seller,
        buyer=buyer,
        winning_bid=winning_bid,
        sale_price=price,
        notes=notes[:200],
    )


def pending_ratings_for(user: User) -> list[ClosedDeal]:
    rated_ids = UserRating.objects.filter(rater=user).values_list("deal_id", flat=True)
    return list(
        ClosedDeal.objects.filter(Q(buyer=user) | Q(seller=user))
        .exclude(pk__in=rated_ids)
        .select_related("motorcycle", "seller", "buyer")
        .order_by("-closed_at")
    )
