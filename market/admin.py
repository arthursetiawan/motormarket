from django.contrib import admin

from .models import Bid, DealSheet, FleetInquiry, ListingPrediction, Motorcycle


@admin.register(Motorcycle)
class MotorcycleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "make",
        "year",
        "city",
        "start_price",
        "stnk_status",
        "bpkb_status",
        "pajak_mati",
        "condition",
        "seller",
        "created_at",
    )
    search_fields = ("title", "description", "make", "model_name", "city", "plate_number")
    list_filter = ("make", "year", "city", "condition", "stnk_status", "bpkb_status", "pajak_mati")


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ("motorcycle", "bidder", "amount", "created_at")
    search_fields = ("bidder__username", "motorcycle__title")


@admin.register(FleetInquiry)
class FleetInquiryAdmin(admin.ModelAdmin):
    list_display = ("company_name", "city", "use_case", "intent", "fleet_size", "coverage", "created_at")
    list_filter = ("use_case", "intent", "city")
    search_fields = ("company_name", "contact_name", "email")
    readonly_fields = ("pack_snapshot",)

    @admin.display(description="Coverage")
    def coverage(self, obj):
        snap = obj.pack_snapshot or {}
        pct = snap.get("coverage_pct")
        return f"{pct}%" if pct is not None else "—"


@admin.register(ListingPrediction)
class ListingPredictionAdmin(admin.ModelAdmin):
    list_display = (
        "motorcycle",
        "predicted_price",
        "deal_score",
        "deal_label",
        "trust_score",
        "trust_label",
        "scored_at",
    )
    list_filter = ("deal_label", "trust_label")
    readonly_fields = ("trust_flags", "features")


@admin.register(DealSheet)
class DealSheetAdmin(admin.ModelAdmin):
    list_display = (
        "motorcycle",
        "buyer",
        "meetup_city",
        "payment_preference",
        "dp_amount",
        "created_at",
    )
    list_filter = ("payment_preference", "meetup_city")
    search_fields = ("buyer__username", "motorcycle__title", "meetup_area")
