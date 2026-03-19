from django.contrib import admin
from .models import Motorcycle, Bid


@admin.register(Motorcycle)
class MotorcycleAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'start_price', 'created_at')
    search_fields = ('title', 'description', 'make')
    list_filter = ('make', 'year')


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ('motorcycle', 'bidder', 'amount', 'created_at')
    search_fields = ('bidder__username', 'motorcycle__title')
