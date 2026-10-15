"""Buyer-facing market desk: live comps and a plain-language price read."""

from __future__ import annotations

from django.db.models import Avg, Count

from market.models import ListingPrediction, Motorcycle

DEAL_ORDER = ["great_deal", "good_deal", "fair", "rich", "overpriced"]

DEAL_COPY = {
    "great_deal": "The ask sits well under the model's fair value.",
    "good_deal": "The ask is under the model's fair value.",
    "fair": "The ask is close to the model's fair value.",
    "rich": "The ask is above the model's fair value.",
    "overpriced": "The ask is well above the model's fair value.",
}


def market_board() -> dict:
    listings = Motorcycle.objects.all()
    predictions = (
        ListingPrediction.objects.select_related("motorcycle")
        .filter(motorcycle__year__isnull=False)
        .exclude(motorcycle__model_name="")
    )
    totals = listings.aggregate(n=Count("id"), avg_ask=Avg("start_price"))
    fair = predictions.aggregate(avg_fair=Avg("predicted_price"))

    raw_labels = {
        row["deal_label"]: row["n"]
        for row in predictions.values("deal_label").annotate(n=Count("id"))
    }
    label_total = sum(raw_labels.values()) or 1
    label_counts = [
        {
            "deal_label": label,
            "n": raw_labels.get(label, 0),
            "share": round(100 * raw_labels.get(label, 0) / label_total),
        }
        for label in DEAL_ORDER
        if raw_labels.get(label, 0)
    ]

    city_stats = list(
        listings.values("city")
        .annotate(n=Count("id"), avg_ask=Avg("start_price"), avg_fair=Avg("prediction__predicted_price"))
        .order_by("-n")[:8]
    )
    model_stats = list(
        listings.exclude(model_name="")
        .values("make", "model_name")
        .annotate(n=Count("id"), avg_ask=Avg("start_price"), avg_fair=Avg("prediction__predicted_price"))
        .order_by("-n")[:10]
    )
    return {
        "totals": totals,
        "avg_fair": fair["avg_fair"],
        "label_counts": label_counts,
        "city_stats": city_stats,
        "model_stats": model_stats,
        "top_deals": predictions.order_by("-deal_score")[:8],
        "rich": predictions.order_by("deal_score")[:8],
        "makes": list(
            listings.exclude(make__isnull=True).exclude(make="").values_list("make", flat=True).distinct().order_by("make")
        ),
        "cities": list(listings.exclude(city="").values_list("city", flat=True).distinct().order_by("city")),
        "city_count": listings.exclude(city="").values("city").distinct().count(),
    }


def listing_desk(bike: Motorcycle) -> dict:
    peers = (
        Motorcycle.objects.filter(make=bike.make, model_name=bike.model_name)
        .exclude(pk=bike.pk)
        .select_related("prediction")
    )
    peer_stats = peers.aggregate(
        n=Count("id"),
        avg_ask=Avg("start_price"),
        avg_fair=Avg("prediction__predicted_price"),
        avg_km=Avg("mileage_km"),
        avg_year=Avg("year"),
    )
    segment = bike.segment or "scooter"
    city_segment = Motorcycle.objects.filter(city=bike.city, segment=segment).aggregate(
        n=Count("id"), avg_ask=Avg("start_price")
    )
    national_segment = Motorcycle.objects.filter(segment=segment).aggregate(
        n=Count("id"), avg_ask=Avg("start_price")
    )
    city_stats = Motorcycle.objects.filter(city=bike.city).aggregate(
        n=Count("id"), avg_ask=Avg("start_price"), avg_fair=Avg("prediction__predicted_price")
    )

    prediction = ListingPrediction.objects.filter(motorcycle=bike).first()
    gap = None
    abs_gap = None
    if prediction is not None:
        gap = float(prediction.predicted_price) - float(bike.start_price)
        abs_gap = abs(gap)

    return {
        "prediction": prediction,
        "gap": gap,
        "abs_gap": abs_gap,
        "copy": DEAL_COPY.get(getattr(prediction, "deal_label", ""), ""),
        "peers": peers.order_by("-created_at")[:5],
        "peer_stats": peer_stats,
        "city_stats": city_stats,
        "drivers": _drivers(bike, peer_stats, city_segment, national_segment),
    }


def _drivers(bike, peer_stats, city_segment, national_segment) -> list[str]:
    notes: list[str] = []
    name = bike.model_name or bike.make or "this model"
    if not peer_stats["n"]:
        notes.append(f"No other {name} listings are on the book yet, so this read uses the wider market.")
    else:
        avg_km = peer_stats["avg_km"] or 0
        if bike.mileage_km and avg_km:
            delta = bike.mileage_km - avg_km
            if delta >= 4000:
                notes.append(f"{int(delta):,} km above the other {name} listings.")
            elif delta <= -4000:
                notes.append(f"{int(abs(delta)):,} km below the other {name} listings.")
        avg_year = peer_stats["avg_year"]
        if bike.year and avg_year:
            if bike.year >= avg_year + 1:
                notes.append(f"Newer than the typical {name} listing ({bike.year} vs {avg_year:.0f}).")
            elif bike.year <= avg_year - 1:
                notes.append(f"Older than the typical {name} listing ({bike.year} vs {avg_year:.0f}).")
        if bike.condition == "excellent":
            notes.append("Excellent condition supports a higher fair value than a typical good bike.")
        elif bike.condition == "fair":
            notes.append("Fair condition pulls fair value down versus a good bike.")
        elif bike.condition == "poor":
            notes.append("Poor condition is the main discount versus the rest of the book.")

    city_ask = city_segment["avg_ask"]
    national_ask = national_segment["avg_ask"]
    if (
        (city_segment["n"] or 0) >= 5
        and (national_segment["n"] or 0) >= city_segment["n"] + 5
        and city_ask
        and national_ask
        and float(national_ask) > 0
    ):
        pct = (float(city_ask) - float(national_ask)) / float(national_ask) * 100
        label = (bike.segment or "scooter").replace("_", " ")
        if 4 <= pct <= 20:
            notes.append(f"{label.title()} asks in {bike.city} run about {pct:.0f}% above the same segment elsewhere.")
        elif -20 <= pct <= -4:
            notes.append(f"{label.title()} asks in {bike.city} run about {abs(pct):.0f}% below the same segment elsewhere.")
    return notes[:4]
