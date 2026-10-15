from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from market.models import Motorcycle
from market.services.pricing import score_queryset
from ml.generate import generate_live_listings
from ml.paths import PRICE_MODEL_PATH
from ml.score import clear_model_cache
from ml.train import train_price_model


class Command(BaseCommand):
    help = "Train if needed, then load live Indonesian inventory and score every listing"

    def add_arguments(self, parser):
        parser.add_argument("--n", type=int, default=80)
        parser.add_argument("--retrain", action="store_true")

    def handle(self, *args, **options):
        if options["retrain"] or not PRICE_MODEL_PATH.exists():
            metrics = train_price_model(n=2500, seed=42)
            clear_model_cache()
            self.stdout.write(f"model trained MAPE={metrics['mape_pct']}%")

        seller, created = User.objects.get_or_create(
            username="motormarket_seller",
            defaults={"email": "seller@motormarket.dev"},
        )
        if created:
            seller.set_password("motormarket")
            seller.save()

        live = generate_live_listings(n=options["n"], seed=11)
        created_n = 0
        for row in live.to_dict(orient="records"):
            title = f"{row['year']} {row['make']} {row['model_name']}"
            if Motorcycle.objects.filter(title=title, mileage_km=int(row["mileage_km"])).exists():
                continue
            Motorcycle.objects.create(
                title=title,
                description=(
                    f"{row['condition'].title()} condition {row['model_name']} in {row['city']}. "
                    f"{int(row['mileage_km']):,} km, {row['owners_count']} owner(s), "
                    f"{row['engine_cc']}cc {row['transmission']}."
                ),
                start_price=Decimal(str(int(row["asking_price"]))),
                seller=seller,
                make=row["make"],
                model_name=row["model_name"],
                segment=row["segment"],
                year=int(row["year"]),
                mileage_km=int(row["mileage_km"]),
                engine_cc=int(row["engine_cc"]),
                condition=row["condition"],
                city=row["city"],
                fuel_type=row["fuel_type"],
                transmission=row["transmission"],
                owners_count=int(row["owners_count"]),
            )
            created_n += 1
        scored = score_queryset()
        self.stdout.write(self.style.SUCCESS(f"created {created_n} listings, scored {scored}"))
