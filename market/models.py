from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator


class Motorcycle(models.Model):
    GRADE_CHOICES = [
        ("A", "Grade A — siap jalan"),
        ("B", "Grade B — perlu perawatan ringan"),
        ("C", "Grade C — perlu perbaikan"),
    ]
    STATUS_OPEN = "open"
    STATUS_SOLD = "sold"
    STATUS_RESERVE_NOT_MET = "reserve_not_met"
    STATUS_ENDED = "ended"
    AUCTION_STATUS_CHOICES = [
        (STATUS_OPEN, "Lelang dibuka"),
        (STATUS_SOLD, "Terjual"),
        (STATUS_RESERVE_NOT_MET, "Reserve tidak tercapai"),
        (STATUS_ENDED, "Selesai tanpa tawaran"),
    ]

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
    
    # Auction (BaT-lite)
    has_reserve = models.BooleanField(
        default=False,
        help_text="Jika False, badge Tanpa reserve. Reserve amount tetap disembunyikan dari buyer.",
    )
    reserve_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Hidden from buyers. Only used when has_reserve=True.",
    )
    buy_now_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Optional Beli Sekarang alongside lelang.",
    )
    ends_at = models.DateTimeField(null=True, blank=True)
    auction_status = models.CharField(
        max_length=20, choices=AUCTION_STATUS_CHOICES, default=STATUS_OPEN,
    )
    condition_grade = models.CharField(max_length=1, choices=GRADE_CHOICES, default="B")
    known_flaws = models.TextField(
        blank=True, default="", help_text="Kekurangan diketahui — forced disclosure for buyers.",
    )
    is_dealer = models.BooleanField(default=False, help_text="Dealer inventory vs C2C.")
    is_published = models.BooleanField(
        default=True, help_text="New listings require photo + checklist gate before True.",
    )
    checklist_front = models.BooleanField(default=False)
    checklist_side = models.BooleanField(default=False)
    checklist_odometer = models.BooleanField(default=False)
    checklist_engine = models.BooleanField(default=False)
    checklist_surat = models.BooleanField(default=False)
    ppi_available = models.BooleanField(default=False, help_text="Seller allows cek unit / PPI request.")
    ppi_notes = models.CharField(max_length=200, blank=True, default="")

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

    def checklist_score(self) -> int:
        return sum(
            [
                self.checklist_front,
                self.checklist_side,
                self.checklist_odometer,
                self.checklist_engine,
                self.checklist_surat,
            ]
        )

    def can_publish(self) -> bool:
        has_photo = bool(self.image)
        if not has_photo and self.pk:
            has_photo = self.photos.exists()
        return has_photo and self.checklist_score() >= 3

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
    max_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Proxy ceiling — private to system.",
    )
    is_proxy = models.BooleanField(default=False)
    is_automatic = models.BooleanField(
        default=False,
        help_text="True when system auto-incremented to defend a max bid.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

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

class ClosedDeal(models.Model):
    """On-platform completed sale — gate for buyer↔seller ratings.

    Close signal on current `dev`: seller marks listing sold with a buyer
    (usually the winning bidder). When commission/unlock lands, fee-paid
    wins can also create/close a deal without changing rating rules.
    """

    motorcycle = models.OneToOneField(
        Motorcycle, related_name="closed_deal", on_delete=models.CASCADE
    )
    seller = models.ForeignKey(
        User, related_name="deals_as_seller", on_delete=models.CASCADE
    )
    buyer = models.ForeignKey(
        User, related_name="deals_as_buyer", on_delete=models.CASCADE
    )
    winning_bid = models.ForeignKey(
        Bid, related_name="closed_deals", on_delete=models.SET_NULL, null=True, blank=True
    )
    sale_price = models.DecimalField(max_digits=12, decimal_places=2)
    closed_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-closed_at"]

    def __str__(self):
        return f"Deal #{self.pk} · {self.motorcycle_id} · {self.buyer_id}←{self.seller_id}"

class UserRating(models.Model):
    """One star rating per party per closed deal (Uber / FB Marketplace style)."""

    ROLE_SELLER = "seller"
    ROLE_BUYER = "buyer"
    ROLE_CHOICES = [
        (ROLE_SELLER, "Sebagai penjual"),
        (ROLE_BUYER, "Sebagai pembeli"),
    ]

    deal = models.ForeignKey(ClosedDeal, related_name="ratings", on_delete=models.CASCADE)
    rater = models.ForeignKey(
        User, related_name="ratings_given", on_delete=models.CASCADE
    )
    ratee = models.ForeignKey(
        User, related_name="ratings_received", on_delete=models.CASCADE
    )
    # Perspective of the ratee for this deal (seller or buyer).
    ratee_role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    review = models.CharField(max_length=400, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["deal", "rater"], name="uniq_rating_per_deal_rater"),
        ]

    def __str__(self):
        return f"{self.rater_id}→{self.ratee_id} ({self.ratee_role}) {self.score}★"

class ListingSentiment(models.Model):
    """Persisted tone/trust score for listing title + description."""

    LABEL_CHOICES = [
        ("professional", "Jelas / profesional"),
        ("mixed", "Campuran"),
        ("caution", "Agresif / spam"),
    ]

    motorcycle = models.OneToOneField(
        Motorcycle, related_name="sentiment", on_delete=models.CASCADE
    )
    score = models.FloatField(help_text="0–100; higher is clearer / more professional")
    label = models.CharField(max_length=20, choices=LABEL_CHOICES)
    signals = models.JSONField(default=list, blank=True)
    method_version = models.CharField(max_length=32, default="lexicon_v1")
    scored_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.motorcycle_id} {self.label} {self.score}"


class Watchlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="watchlist")
    motorcycle = models.ForeignKey(Motorcycle, on_delete=models.CASCADE, related_name="watchers")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "motorcycle")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} ♥ {self.motorcycle_id}"


class ListingComment(models.Model):
    """Public diligence Q&A thread on a listing."""

    motorcycle = models.ForeignKey(Motorcycle, related_name="comments", on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="listing_comments")
    body = models.TextField()
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="replies",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author.username} on {self.motorcycle_id}"


class ListingPhoto(models.Model):
    motorcycle = models.ForeignKey(Motorcycle, related_name="photos", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="motorcycles/gallery/")
    caption = models.CharField(max_length=120, blank=True, default="")
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"Photo {self.pk} · {self.motorcycle_id}"


class InAppNotification(models.Model):
    KIND_OUTBID = "outbid"
    KIND_ENDING_SOON = "ending_soon"
    KIND_SOLD = "sold"
    KIND_COMMENT = "comment"
    KIND_CHOICES = [
        (KIND_OUTBID, "Digeser (outbid)"),
        (KIND_ENDING_SOON, "Segera berakhir"),
        (KIND_SOLD, "Terjual"),
        (KIND_COMMENT, "Komentar baru"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    motorcycle = models.ForeignKey(
        Motorcycle,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    message = models.CharField(max_length=280)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} · {self.kind} · {self.message[:40]}"


class PpiRequest(models.Model):
    """Soft hook: buyer requests cek unit / PPI. No ops workflow yet."""

    motorcycle = models.ForeignKey(Motorcycle, related_name="ppi_requests", on_delete=models.CASCADE)
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ppi_requests")
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PPI {self.motorcycle_id} · {self.requester.username}"


class UserProfile(models.Model):
    """
    Private KYC / company-record fields for NegoMotor registration.

    KTP number and selfie must never be rendered on public marketplace profiles.
    Staff may view them in Django admin for verifikasi & catatan perusahaan.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    ktp_number = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="NIK 16 digit — private company record only.",
    )
    date_of_birth = models.DateField(null=True, blank=True)
    selfie = models.ImageField(
        upload_to="kyc/selfies/%Y/%m/",
        blank=True,
        null=True,
        help_text="Foto diri for company records — never public.",
    )
    kyc_completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User KYC profile"
        verbose_name_plural = "User KYC profiles"

    def __str__(self):
        # Never include raw KTP in string/logs.
        status = "lengkap" if self.is_complete else "belum lengkap"
        return f"KYC · {self.user.username} · {status}"

    @property
    def is_complete(self) -> bool:
        return bool(
            self.ktp_number
            and len(self.ktp_number) == 16
            and self.ktp_number.isdigit()
            and self.date_of_birth
            and self.selfie
        )

    def masked_ktp(self) -> str:
        n = self.ktp_number or ""
        if len(n) != 16:
            return "—"
        return f"{n[:4]}••••••••{n[-4:]}"
