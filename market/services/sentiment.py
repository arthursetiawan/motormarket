"""Persist and aggregate listing copy sentiment for NegoMotor."""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import User
from django.db.models import Avg, Count

from market.models import ListingSentiment, Motorcycle
from ml.sentiment import SentimentReport, assess_listing_text


LABEL_COPY = {
    "professional": "Jelas & profesional",
    "mixed": "Campuran",
    "caution": "Agresif / spam",
}


@dataclass
class SellerSentimentAggregate:
    average: float | None
    count: int
    label: str

    @property
    def display(self) -> str:
        if not self.count or self.average is None:
            return "Belum ada skor teks"
        return f"{self.average:.0f}/100 · {LABEL_COPY.get(self.label, self.label)} ({self.count} iklan)"


def score_listing_sentiment(bike: Motorcycle, *, persist: bool = True) -> SentimentReport:
    report = assess_listing_text(title=bike.title, description=bike.description)
    if persist:
        ListingSentiment.objects.update_or_create(
            motorcycle=bike,
            defaults={
                "score": report.score,
                "label": report.label,
                "signals": [s.__dict__ for s in report.signals],
                "method_version": report.method_version,
            },
        )
    return report


def listing_sentiment(bike: Motorcycle) -> ListingSentiment | SentimentReport:
    try:
        return bike.sentiment
    except ListingSentiment.DoesNotExist:
        return score_listing_sentiment(bike)


def seller_listing_sentiment(user: User) -> SellerSentimentAggregate:
    agg = ListingSentiment.objects.filter(motorcycle__seller=user).aggregate(
        avg=Avg("score"), n=Count("id")
    )
    n = int(agg["n"] or 0)
    avg = round(float(agg["avg"]), 1) if agg["avg"] is not None else None
    if avg is None:
        label = "mixed"
    elif avg >= 70:
        label = "professional"
    elif avg >= 45:
        label = "mixed"
    else:
        label = "caution"
    return SellerSentimentAggregate(average=avg, count=n, label=label)
