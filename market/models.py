from django.db import models
from django.contrib.auth.models import User


class Motorcycle(models.Model):
    CONDITION_CHOICES = [
        ("excellent", "Istimewa"),
        ("good", "Baik"),
        ("fair", "Cukup"),
        ("poor", "Kurang"),
    ]
    FUEL_CHOICES = [("petrol", "Bensin"), ("electric", "Listrik")]
    TRANS_CHOICES = [("automatic", "Matic"), ("manual", "Manual")]
    STNK_CHOICES = [
        ("lengkap", "STNK lengkap"),
        ("atas_nama_lain", "STNK atas nama lain"),
        ("hilang", "STNK hilang"),
        ("unknown", "Belum diisi"),
    ]
    BPKB_CHOICES = [
        ("ada", "BPKB ada"),
        ("di_leasing", "BPKB di leasing"),
        ("hilang", "BPKB hilang"),
        ("unknown", "Belum diisi"),
    ]

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

    # Surat-surat (Indonesian vehicle papers)
    stnk_status = models.CharField(max_length=20, choices=STNK_CHOICES, default="unknown")
    bpkb_status = models.CharField(max_length=20, choices=BPKB_CHOICES, default="unknown")
    pajak_mati = models.BooleanField(
        default=False,
        help_text="True when vehicle tax / STNK year is expired (pajak mati).",
    )
    tax_valid_through = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        help_text="Year STNK/pajak is valid through, e.g. 2026.",
    )
    plate_number = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="Nomor polisi, e.g. B 1234 ABC",
    )
    # Private seller contact — never shown on public detail until buyer fee unlock
    seller_phone = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Private. Revealed only after buyer pays platform fee.",
    )
    seller_wa = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Private WhatsApp number. Revealed only after fee unlock.",
    )
    deal_status = models.CharField(
        max_length=24,
        choices=[
            ("open", "Open"),
            ("closed_on_platform", "Closed on NegoMotor"),
            ("sold_off_app", "Sold off-app (no protection)"),
        ],
        default="open",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def asking_price(self):
        return self.start_price

    @property
    def plate_region(self) -> str:
        """Leading letter code from plate (e.g. B, DK, AB)."""
        raw = (self.plate_number or "").strip().upper()
        if not raw:
            return ""
        parts = raw.replace("-", " ").split()
        if not parts:
            return ""
        code = parts[0]
        # Two-letter codes like DK, AB, BK
        if len(code) >= 2 and code[:2].isalpha():
            two = code[:2]
            if two in {"DK", "AB", "AA", "AD", "AE", "AG", "BK", "BH", "BL", "BM", "BN", "BG", "BA", "BB", "BD", "BE", "DD", "DE", "DG", "DH", "DN", "DR", "DT", "DW", "EA", "EB", "ED", "KB", "KH", "KT", "KU", "PB", "PK", "KB"}:
                return two
        if code[0].isalpha():
            return code[0]
        return ""

    @property
    def surat_lengkap(self) -> bool:
        """Buyer shorthand: STNK lengkap, BPKB present (or at leasing), pajak hidup."""
        return (
            self.stnk_status == "lengkap"
            and self.bpkb_status in ("ada", "di_leasing")
            and not self.pajak_mati
        )

    @property
    def ojol_ready(self) -> bool:
        """Heuristic: matic ≥125cc, surat lengkap, not sold."""
        return (
            not self.is_sold
            and self.transmission == "automatic"
            and (self.engine_cc or 0) >= 125
            and self.surat_lengkap
        )


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
    # Market-dataset anomaly (peer bands / catalog) — NegoMotor "waspada" signal
    ANOMALY_LABELS = [
        ("ok", "OK"),
        ("waspada", "Waspada"),
        ("waspada_tinggi", "Waspada tinggi"),
    ]
    anomaly_score = models.PositiveSmallIntegerField(null=True, blank=True)
    anomaly_label = models.CharField(max_length=20, blank=True, default="", choices=ANOMALY_LABELS)
    anomaly_flags = models.JSONField(default=list, blank=True)
    anomaly_confidence = models.FloatField(default=0.0)
    anomaly_peer_n = models.PositiveSmallIntegerField(default=0)
    anomaly_peer_source = models.CharField(max_length=32, blank=True, default="")

    def __str__(self):
        return f"{self.motorcycle_id} {self.deal_label} {self.predicted_price}"


class FleetInquiry(models.Model):
    USE_CHOICES = [
        ("delivery", "Last-mile delivery"),
        ("ride_hailing", "Ride-hailing / ojol"),
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


class DealSheet(models.Model):
    """Buyer intent to close — meetup + payment preference; exact meetup gated by fee."""

    PAYMENT_CHOICES = [
        ("cash", "Cash / tunai"),
        ("transfer", "Transfer bank"),
        ("cicilan", "Cicilan / leasing"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("unlocked", "Contact unlocked"),
        ("closed_on_platform", "Closed on NegoMotor"),
        ("bypass_suspected", "Bypass suspected"),
    ]

    motorcycle = models.ForeignKey(Motorcycle, related_name="deal_sheets", on_delete=models.CASCADE)
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="deal_sheets")
    meetup_city = models.CharField(max_length=80)
    meetup_area = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Area-level only (e.g. Kelapa Gading). Visible before unlock.",
    )
    meetup_exact = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Exact pin / address — shown only after platform fee paid.",
    )
    payment_preference = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default="transfer")
    dp_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Optional down payment (DP) if cicilan.",
    )
    notes = models.TextField(blank=True, default="")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Deal {self.motorcycle_id} · {self.buyer.username} · {self.payment_preference}"


class ListingMessage(models.Model):
    """In-app buyer↔seller thread on a listing (pre-unlock messaging)."""

    motorcycle = models.ForeignKey(Motorcycle, related_name="messages", on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="listing_messages")
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_listing_messages",
        null=True,
        blank=True,
    )
    body = models.TextField()
    was_redacted = models.BooleanField(default=False)
    was_blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Msg {self.motorcycle_id} · {self.sender.username}"


class PlatformFee(models.Model):
    """Buyer platform / success fee — unlocks seller contact + exact meetup."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("refunded", "Refunded"),
    ]

    motorcycle = models.ForeignKey(Motorcycle, related_name="platform_fees", on_delete=models.CASCADE)
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="platform_fees")
    deal_sheet = models.ForeignKey(
        DealSheet,
        related_name="fees",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    basis_amount = models.DecimalField(max_digits=12, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    simulated = models.BooleanField(
        default=True,
        help_text="True for MVP simulated checkout; wire Midtrans/Xendit later.",
    )
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Fee {self.fee_amount} · bike {self.motorcycle_id} · {self.buyer.username} · {self.status}"

    @property
    def is_paid(self) -> bool:
        return self.status == "paid"


class BypassFlag(models.Model):
    """Lightweight ops flag when users try to move off-platform / share contact."""

    ACTION_CHOICES = [
        ("warn", "Warn"),
        ("block_contact", "Block contact unlock"),
        ("ban", "Ban account"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bypass_flags")
    motorcycle = models.ForeignKey(
        Motorcycle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bypass_flags",
    )
    reason = models.CharField(max_length=240)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default="warn")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} · {self.action} · {self.reason[:40]}"


class UserSafetyProfile(models.Model):
    """Per-user contact unlock / ban state for anti-bypass."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="safety_profile")
    contact_blocked = models.BooleanField(
        default=False,
        help_text="If True, fee unlock is refused (bypass forfeit).",
    )
    is_banned = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Safety {self.user.username}"
