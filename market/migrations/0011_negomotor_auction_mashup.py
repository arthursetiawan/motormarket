# Auction mashup (BaT + Manheim lite) — surat fields already in 0007

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0010_ratings_and_sentiment"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="bid",
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddField(
            model_name="bid",
            name="is_automatic",
            field=models.BooleanField(default=False, help_text="True when system auto-incremented to defend a max bid."),
        ),
        migrations.AddField(
            model_name="bid",
            name="is_proxy",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="bid",
            name="max_amount",
            field=models.DecimalField(blank=True, decimal_places=2, help_text="Proxy ceiling — private to system.", max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="auction_status",
            field=models.CharField(choices=[("open", "Lelang dibuka"), ("sold", "Terjual"), ("reserve_not_met", "Reserve tidak tercapai"), ("ended", "Selesai tanpa tawaran")], default="open", max_length=20),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="buy_now_price",
            field=models.DecimalField(blank=True, decimal_places=2, help_text="Optional Beli Sekarang alongside lelang.", max_digits=12, null=True),
        ),
        migrations.AddField(model_name="motorcycle", name="checklist_engine", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="motorcycle", name="checklist_front", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="motorcycle", name="checklist_odometer", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="motorcycle", name="checklist_side", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="motorcycle", name="checklist_surat", field=models.BooleanField(default=False)),
        migrations.AddField(
            model_name="motorcycle",
            name="condition_grade",
            field=models.CharField(choices=[("A", "Grade A — siap jalan"), ("B", "Grade B — perlu perawatan ringan"), ("C", "Grade C — perlu perbaikan")], default="B", max_length=1),
        ),
        migrations.AddField(model_name="motorcycle", name="ends_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            model_name="motorcycle",
            name="has_reserve",
            field=models.BooleanField(default=False, help_text="Jika False, badge Tanpa reserve. Reserve amount tetap disembunyikan dari buyer."),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="is_dealer",
            field=models.BooleanField(default=False, help_text="Dealer inventory vs C2C."),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="is_published",
            field=models.BooleanField(default=True, help_text="New listings require photo + checklist gate before True."),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="known_flaws",
            field=models.TextField(blank=True, default="", help_text="Kekurangan diketahui — forced disclosure for buyers."),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="ppi_available",
            field=models.BooleanField(default=False, help_text="Seller allows cek unit / PPI request."),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="ppi_notes",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="motorcycle",
            name="reserve_price",
            field=models.DecimalField(blank=True, decimal_places=2, help_text="Hidden from buyers. Only used when has_reserve=True.", max_digits=12, null=True),
        ),
        migrations.CreateModel(
            name="InAppNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("outbid", "Digeser (outbid)"), ("ending_soon", "Segera berakhir"), ("sold", "Terjual"), ("comment", "Komentar baru")], max_length=20)),
                ("message", models.CharField(max_length=280)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("motorcycle", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="market.motorcycle")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ListingComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="listing_comments", to=settings.AUTH_USER_MODEL)),
                ("motorcycle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="market.motorcycle")),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="replies", to="market.listingcomment")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="ListingPhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="motorcycles/gallery/")),
                ("caption", models.CharField(blank=True, default="", max_length=120)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("motorcycle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="photos", to="market.motorcycle")),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="PpiRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("note", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("motorcycle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ppi_requests", to="market.motorcycle")),
                ("requester", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ppi_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Watchlist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("motorcycle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="watchers", to="market.motorcycle")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="watchlist", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"], "unique_together": {("user", "motorcycle")}},
        ),
    ]
