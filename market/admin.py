from django.contrib import admin

from .models import Bid, FleetInquiry, ListingPrediction, Motorcycle


@admin.register(Motorcycle)
class MotorcycleAdmin(admin.ModelAdmin):
    list_display = ("title", "make", "year", "city", "start_price", "condition", "seller", "created_at")
    search_fields = ("title", "description", "make", "model_name", "city")
    list_filter = ("make", "year", "city", "condition")


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ("motorcycle", "bidder", "amount", "created_at")
    search_fields = ("bidder__username", "motorcycle__title")


@admin.register(FleetInquiry)
class FleetInquiryAdmin(admin.ModelAdmin):
    list_display = ("company_name", "city", "use_case", "intent", "fleet_size", "created_at")
    list_filter = ("use_case", "intent", "city")
    search_fields = ("company_name", "contact_name", "email")


@admin.register(ListingPrediction)
class ListingPredictionAdmin(admin.ModelAdmin):
    list_display = ("motorcycle", "predicted_price", "deal_score", "deal_label", "scored_at")
    list_filter = ("deal_label",)
