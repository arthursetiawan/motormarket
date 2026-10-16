"""Fleet pack intelligence: recommend buy/rent packs from the live book.

Uses scored inventory (fair value + deal labels) plus city demand density so
B2B quotes are grounded in what MotorMarket can actually source today.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Avg, Count, Q

from market.models import Motorcycle
from market.services.fleets import LEASE_FACTOR, LEASE_MONTHS, PROGRAMS


@dataclass(frozen=True)
class PackUnit:
    pk: int
    title: str
    city: str
    year: int | None
    mileage_km: int
    ask: int
    fair: int | None
    deal_score: float | None
    deal_label: str
    pack_score: float


def _program(slug: str) -> dict | None:
    return next((p for p in PROGRAMS if p["slug"] == slug), None)


def city_demand(program: dict) -> list[dict]:
    """Relative supply of program-matching bikes by city (0–100 index)."""
    qs = (
        Motorcycle.objects.filter(is_sold=False, model_name__in=program["models"])
        .values("city")
        .annotate(n=Count("id"), avg_ask=Avg("start_price"), avg_fair=Avg("prediction__predicted_price"))
        .order_by("-n")
    )
    rows = list(qs)
    peak = max((r["n"] for r in rows), default=0) or 1
    out = []
    for row in rows[:8]:
        in_program_city = row["city"] in program["cities"]
        out.append(
            {
                "city": row["city"],
                "n": row["n"],
                "index": int(round(100 * row["n"] / peak)),
                "avg_ask": int(round(float(row["avg_ask"]))) if row["avg_ask"] else None,
                "avg_fair": int(round(float(row["avg_fair"]))) if row["avg_fair"] else None,
                "program_city": in_program_city,
            }
        )
    return out


def _unit_pack_score(bike: Motorcycle, program: dict, preferred_city: str | None) -> float:
    """Higher is better for a fleet buyer (value + readiness)."""
    pred = getattr(bike, "prediction", None)
    deal = float(pred.deal_score) if pred else 0.0
    fair = float(pred.predicted_price) if pred else float(bike.start_price)
    ask = float(bike.start_price)

    score = 40.0 + deal  # deals push selection
    if bike.city in program["cities"]:
        score += 12
    if preferred_city and bike.city.lower() == preferred_city.lower():
        score += 18
    # Prefer lower km for fleet utilization
    score -= min(bike.mileage_km, 80000) / 8000
    if bike.condition == "excellent":
        score += 6
    elif bike.condition == "good":
        score += 3
    elif bike.condition == "poor":
        score -= 10
    if bike.owners_count >= 3:
        score -= 4
    # Prefer bikes not wildly over fair value
    if fair > 0 and ask > fair * 1.08:
        score -= 8
    return score


def recommend_pack(
    program_slug: str,
    size: int = 10,
    preferred_city: str | None = None,
    *,
    exclude_caution: bool = False,
    ojol_ready: bool = False,
) -> dict | None:
    from market.services.trust import listing_trust

    program = _program(program_slug)
    if program is None:
        return None
    size = max(5, min(int(size), 200))

    book = (
        Motorcycle.objects.filter(is_sold=False, model_name__in=program["models"])
        .select_related("prediction")
        .order_by("id")
    )
    if ojol_ready:
        book = book.filter(
            transmission="automatic",
            engine_cc__gte=125,
            pajak_mati=False,
            stnk_status="lengkap",
            bpkb_status__in=["ada", "di_leasing"],
        )
    if preferred_city:
        # Soft preference: score handles city boost; optional hard filter if enough supply
        city_book = book.filter(city__iexact=preferred_city)
        if city_book.count() >= min(size, 5):
            candidates = list(city_book)
        else:
            candidates = list(book)
    else:
        candidates = list(book)

    if exclude_caution:
        candidates = [b for b in candidates if listing_trust(b).label != "caution"]

    ranked: list[PackUnit] = []
    for bike in candidates:
        pred = getattr(bike, "prediction", None)
        fair = int(round(float(pred.predicted_price))) if pred else None
        ranked.append(
            PackUnit(
                pk=bike.pk,
                title=bike.title,
                city=bike.city,
                year=bike.year,
                mileage_km=bike.mileage_km,
                ask=int(round(float(bike.start_price))),
                fair=fair,
                deal_score=round(float(pred.deal_score), 2) if pred else None,
                deal_label=pred.deal_label if pred else "unscored",
                pack_score=round(_unit_pack_score(bike, program, preferred_city), 2),
            )
        )
    ranked.sort(key=lambda u: u.pack_score, reverse=True)
    selected = ranked[:size]
    on_book = len(selected)
    sourcing_gap = max(size - on_book, 0)
    coverage_pct = int(round(100 * on_book / size)) if size else 0

    buy_asks = sum(u.ask for u in selected)
    buy_fair = sum(u.fair or u.ask for u in selected)
    # Blended quote: use ask for selected units, fair-value fill for gap
    unit_fill = None
    if selected:
        unit_fill = int(round(buy_fair / on_book))
    elif book.exists():
        avg = book.aggregate(v=Avg("prediction__predicted_price"), a=Avg("start_price"))
        unit_fill = int(round(float(avg["v"] or avg["a"] or 0))) or None

    gap_cost = (unit_fill or 0) * sourcing_gap
    buy_total = buy_asks + gap_cost
    monthly = int(round(buy_total / LEASE_MONTHS * LEASE_FACTOR)) if buy_total else None
    savings_vs_fair = buy_fair - buy_asks if on_book else 0

    deal_mix: dict[str, int] = {}
    for u in selected:
        deal_mix[u.deal_label] = deal_mix.get(u.deal_label, 0) + 1

    demand = city_demand(program)
    top_city = demand[0] if demand else None

    return {
        "program": program,
        "size": size,
        "preferred_city": preferred_city or "",
        "exclude_caution": exclude_caution,
        "ojol_ready": ojol_ready,
        "units": [u.__dict__ for u in selected],
        "on_book": on_book,
        "sourcing_gap": sourcing_gap,
        "coverage_pct": coverage_pct,
        "buy_asks": buy_asks,
        "buy_fair": buy_fair,
        "buy_total": buy_total,
        "monthly": monthly,
        "savings_vs_fair": savings_vs_fair,
        "unit_fill": unit_fill,
        "deal_mix": deal_mix,
        "demand": demand,
        "top_city": top_city,
        "avg_km": int(round(sum(u.mileage_km for u in selected) / on_book)) if on_book else None,
    }


def pack_snapshot(pack: dict | None) -> dict:
    """Compact JSON-safe quote captured onto FleetInquiry at submit time."""
    if not pack:
        return {}
    program = pack.get("program") or {}
    units = pack.get("units") or []
    demand = pack.get("demand") or []
    return {
        "program_slug": program.get("slug"),
        "program_name": program.get("name"),
        "size": pack.get("size"),
        "preferred_city": pack.get("preferred_city") or "",
        "unit_ids": [u.get("pk") for u in units],
        "units": [
            {
                "pk": u.get("pk"),
                "title": u.get("title"),
                "city": u.get("city"),
                "ask": u.get("ask"),
                "fair": u.get("fair"),
                "deal_label": u.get("deal_label"),
            }
            for u in units
        ],
        "on_book": pack.get("on_book"),
        "sourcing_gap": pack.get("sourcing_gap"),
        "coverage_pct": pack.get("coverage_pct"),
        "buy_asks": pack.get("buy_asks"),
        "buy_total": pack.get("buy_total"),
        "monthly": pack.get("monthly"),
        "deal_mix": pack.get("deal_mix") or {},
        "demand_top": [
            {"city": row.get("city"), "n": row.get("n"), "index": row.get("index")}
            for row in demand[:4]
        ],
    }


def enrich_programs(size: int = 10) -> list[dict]:
    """Attach a default recommended pack summary to each fleet program card."""
    from market.services.fleets import fleet_programs

    cards = fleet_programs()
    enriched = []
    for card in cards:
        pack = recommend_pack(card["slug"], size=size)
        enriched.append(
            {
                **card,
                "pack": pack,
                "demand": pack["demand"] if pack else [],
            }
        )
    return enriched


def market_coverage() -> dict:
    """Cross-program snapshot for the insights desk."""
    rows = []
    for program in PROGRAMS:
        book = Motorcycle.objects.filter(is_sold=False, model_name__in=program["models"])
        stats = book.aggregate(
            n=Count("id"),
            deals=Count("id", filter=Q(prediction__deal_label__in=["great_deal", "good_deal"])),
            avg_fair=Avg("prediction__predicted_price"),
        )
        rows.append(
            {
                "slug": program["slug"],
                "name": program["name"],
                "available": stats["n"] or 0,
                "deals": stats["deals"] or 0,
                "avg_fair": int(round(float(stats["avg_fair"]))) if stats["avg_fair"] else None,
                "demand": city_demand(program)[:4],
            }
        )
    return {"programs": rows}
