from django.db import models
from django.contrib.auth.models import User


class Motorcycle(models.Model):
    CONDITION_CHOICES = [
        ("excellent", "Excellent"),
        ("good", "Good"),
        ("fair", "Fair"),
        ("poor", "Poor"),
    ]
    FUEL_CHOICES = [("petrol", "Petrol"), ("electric", "Electric")]
    TRANS_CHOICES = [("automatic", "Automatic"), ("manual", "Manual")]

    title = models.CharField(max_length=200)
    description = models.TextField()
    start_price = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    seller = models.ForeignKey(User, on_delete=models.CASCADE)
    make = models.CharField(max_length=100, blank=True, null=True)
    model_name = models.CharField(max_length=100, blank=True, default="")
    segment = models.CharField(max_length=40, blank=True, default="")
    year = models.PositiveSmallIntegerField(blank=True, null=True)
    image = models.ImageField(upload_to="motorcycles/", blank=True, null=True)
    mileage_km = models.PositiveIntegerField(default=0)
    engine_cc = models.PositiveIntegerField(default=150)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default="good")
    city = models.CharField(max_length=80, blank=True, default="Jakarta")
    fuel_type = models.CharField(max_length=20, choices=FUEL_CHOICES, default="petrol")
    transmission = models.CharField(max_length=20, choices=TRANS_CHOICES, default="automatic")
    owners_count = models.PositiveSmallIntegerField(default=1)
    is_sold = models.BooleanField(default=False)
    sold_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def asking_price(self):
        return self.start_price


class Bid(models.Model):
    motorcycle = models.ForeignKey(Motorcycle, related_name="bids", on_delete=models.CASCADE)
    bidder = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bidder.username} - {self.amount}"


class ListingPrediction(models.Model):
    TRUST_LABELS = [
        ("high_trust", "High trust"),
        ("review", "Review"),
        ("caution", "Caution"),
    ]

    motorcycle = models.OneToOneField(Motorcycle, related_name="prediction", on_delete=models.CASCADE)
    predicted_price = models.DecimalField(max_digits=12, decimal_places=2)
    deal_score = models.FloatField(help_text="Percent under model fair value; positive is a deal")
    deal_label = models.CharField(max_length=20)
    model_version = models.CharField(max_length=64, default="price_model.joblib")
    scored_at = models.DateTimeField(auto_now=True)
    features = models.JSONField(default=dict, blank=True)
    trust_score = models.PositiveSmallIntegerField(null=True, blank=True)
    trust_label = models.CharField(max_length=20, blank=True, default="", choices=TRUST_LABELS)
    trust_flags = models.JSONField(default=list, blank=True)
    trust_completeness = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.motorcycle_id} {self.deal_label} {self.predicted_price}"


class FleetInquiry(models.Model):
    USE_CHOICES = [
        ("delivery", "Last-mile delivery"),
        ("ride_hailing", "Ride-hailing"),
        ("tourism", "Tourism rental"),
        ("field", "Field sales"),
    ]
    INTENT_CHOICES = [("buy", "Buy"), ("rent", "Rent")]

    company_name = models.CharField(max_length=160)
    contact_name = models.CharField(max_length=120)
    email = models.EmailField()
    city = models.CharField(max_length=80)
    use_case = models.CharField(max_length=40, choices=USE_CHOICES)
    intent = models.CharField(max_length=10, choices=INTENT_CHOICES, default="buy")
    fleet_size = models.PositiveSmallIntegerField()
    notes = models.TextField(blank=True)
    pack_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="Recommended pack quote captured at inquiry time",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company_name} · {self.get_use_case_display()} · {self.fleet_size}"
