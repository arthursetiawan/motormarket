from django.core.management.base import BaseCommand

from market.models import Motorcycle
from market.services.pricing import score_queryset
from market.services.sentiment import score_listing_sentiment


class Command(BaseCommand):
    help = "Batch-score listings with the price model and listing-text sentiment"

    def handle(self, *args, **options):
        n = score_queryset()
        sent = 0
        for bike in Motorcycle.objects.all().iterator():
            score_listing_sentiment(bike)
            sent += 1
        self.stdout.write(self.style.SUCCESS(f"scored {n} listings (price); sentiment {sent}"))
