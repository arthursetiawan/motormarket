"""Fleet programs for companies buying or leasing Indonesian motorcycles.

Card summaries live here; pack selection and city demand live in
``market.services.fleet_intel``.
"""

from __future__ import annotations

from django.db.models import Avg, Count

from market.models import Motorcycle

PROGRAMS = [
    {
        "slug": "delivery",
        "name": "Last-mile delivery",
        "audience": "Couriers, food apps, and warehouse operators",
        "pitch": "Automatic scooters that stay cheap to run across Jabodetabek and Surabaya.",
        "models": ["BeAT", "Vario 125", "Vario 160", "Nex II", "Address", "Fazzio"],
        "cities": ["Jakarta", "Bekasi", "Tangerang", "Surabaya"],
        "image": "img/fleets/fleet-delivery.jpg",
    },
    {
        "slug": "ride_hailing",
        "name": "Ride-hailing",
        "audience": "Driver pools and ojol fleet owners",
        "pitch": "Higher-spec scooters riders will accept for daily passenger work.",
        "models": ["Vario 160", "PCX 160", "NMAX", "Aerox 155", "ADV 160"],
        "cities": ["Jakarta", "Bandung", "Surabaya", "Medan"],
        "image": "img/fleets/fleet-ridehail.jpg",
    },
    {
        "slug": "tourism",
        "name": "Tourism rental",
        "audience": "Hotels, villas, and rental desks",
        "pitch": "Guest-facing scooters for Bali, Yogyakarta, and Bandung.",
        "models": ["PCX 160", "NMAX", "XMAX", "Sprint 150", "Primavera 150", "ADV 160"],
        "cities": ["Denpasar", "Yogyakarta", "Bandung"],
        "image": "img/fleets/fleet-tourism.jpg",
    },
    {
        "slug": "field",
        "name": "Field sales",
        "audience": "FMCG, pharmacy, and service teams",
        "pitch": "Reliable low-displacement automatics for staff who ride between accounts.",
        "models": ["BeAT", "Vario 125", "Fazzio", "Address", "Nex II"],
        "cities": ["Jakarta", "Semarang", "Surabaya", "Makassar"],
        "image": "img/fleets/fleet-field.jpg",
    },
]

ORDER_SIZES = (10, 25, 50)
LEASE_MONTHS = 36
LEASE_FACTOR = 1.25


def fleet_programs() -> list[dict]:
    cards = []
    for program in PROGRAMS:
        book = Motorcycle.objects.filter(is_sold=False, model_name__in=program["models"])
        stats = book.aggregate(
            n=Count("id"),
            avg_ask=Avg("start_price"),
            avg_fair=Avg("prediction__predicted_price"),
            avg_km=Avg("mileage_km"),
        )
        in_cities = book.filter(city__in=program["cities"]).count()
        unit = stats["avg_fair"] or stats["avg_ask"]
        unit_idr = int(round(float(unit))) if unit else None
        quotes = []
        if unit_idr:
            monthly = int(round(unit_idr / LEASE_MONTHS * LEASE_FACTOR))
            for size in ORDER_SIZES:
                quotes.append(
                    {
                        "size": size,
                        "buy_total": unit_idr * size,
                        "monthly": monthly * size,
                        "on_book": min(stats["n"] or 0, size),
                    }
                )
        cards.append(
            {
                **program,
                "available": stats["n"] or 0,
                "in_cities": in_cities,
                "avg_ask": int(round(float(stats["avg_ask"]))) if stats["avg_ask"] else None,
                "avg_fair": int(round(float(stats["avg_fair"]))) if stats["avg_fair"] else None,
                "avg_km": int(round(float(stats["avg_km"]))) if stats["avg_km"] else None,
                "quotes": quotes,
            }
        )
    return cards
