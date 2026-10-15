from django.contrib import admin

from .models import Bid, ListingPrediction, Motorcycle


@admin.register(Motorcycle)
class MotorcycleAdmin(admin.ModelAdmin):
    list_display = ("title", "make", "year", "city", "start_price", "condition", "seller", "created_at")
    search_fields = ("title", "description", "make", "model_name", "city")
    list_filter = ("make", "year", "city", "condition")


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ("motorcycle", "bidder", "amount", "created_at")
    search_fields = ("bidder__username", "motorcycle__title")


@admin.register(ListingPrediction)
class ListingPredictionAdmin(admin.ModelAdmin):
    list_display = ("motorcycle", "predicted_price", "deal_score", "deal_label", "scored_at")
    list_filter = ("deal_label",)
