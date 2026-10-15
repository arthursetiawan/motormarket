from django.core.management.base import BaseCommand

from ml.score import clear_model_cache
from ml.train import train_price_model


class Command(BaseCommand):
    help = "Train the sold-price model from the synthetic market extract"

    def add_arguments(self, parser):
        parser.add_argument("--n", type=int, default=4000)
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **options):
        metrics = train_price_model(n=options["n"], seed=options["seed"])
        clear_model_cache()
        self.stdout.write(self.style.SUCCESS(
            f"Trained. MAE={metrics['mae_idr']:.0f} MAPE={metrics['mape_pct']}% R2={metrics['r2']}"
        ))
