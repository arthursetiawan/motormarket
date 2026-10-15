from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0003_motorcycle_image_motorcycle_make_motorcycle_year"),
    ]

    operations = [
        migrations.AddField(
            model_name="motorcycle",
            name="model_name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="segment",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="mileage_km",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="engine_cc",
            field=models.PositiveIntegerField(default=150),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="condition",
            field=models.CharField(
                choices=[
                    ("excellent", "Excellent"),
                    ("good", "Good"),
                    ("fair", "Fair"),
                    ("poor", "Poor"),
                ],
                default="good",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="city",
            field=models.CharField(blank=True, default="Jakarta", max_length=80),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="fuel_type",
            field=models.CharField(
                choices=[("petrol", "Petrol"), ("electric", "Electric")],
                default="petrol",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="transmission",
            field=models.CharField(
                choices=[("automatic", "Automatic"), ("manual", "Manual")],
                default="automatic",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="owners_count",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="is_sold",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="sold_price",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.CreateModel(
            name="ListingPrediction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("predicted_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("deal_score", models.FloatField(help_text="Percent under model fair value; positive is a deal")),
                ("deal_label", models.CharField(max_length=20)),
                ("model_version", models.CharField(default="price_model.joblib", max_length=64)),
                ("scored_at", models.DateTimeField(auto_now=True)),
                ("features", models.JSONField(blank=True, default=dict)),
                (
                    "motorcycle",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="prediction",
                        to="market.motorcycle",
                    ),
                ),
            ],
        ),
    ]
