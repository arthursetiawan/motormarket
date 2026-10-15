from django.core.management.base import BaseCommand

from market.services.pricing import score_queryset


class Command(BaseCommand):
    help = "Batch-score all listings with the current price model"

    def handle(self, *args, **options):
        n = score_queryset()
        self.stdout.write(self.style.SUCCESS(f"scored {n} listings"))
