from django.contrib import admin

from .models import (
    Bid,
    BypassFlag,
    DealSheet,
    FleetInquiry,
    ListingMessage,
    ListingPrediction,
    Motorcycle,
    PlatformFee,
    UserSafetyProfile,
)


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
        "deal_status",
        "condition",
        "seller",
        "created_at",
    )
    search_fields = ("title", "description", "make", "model_name", "city", "plate_number")
    list_filter = (
        "make",
        "year",
        "city",
        "condition",
        "stnk_status",
        "bpkb_status",
        "pajak_mati",
        "deal_status",
    )
    readonly_fields = ("seller_phone", "seller_wa")


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
        "status",
        "dp_amount",
        "created_at",
    )
    list_filter = ("payment_preference", "status", "meetup_city")
    search_fields = ("buyer__username", "motorcycle__title", "meetup_area")


@admin.register(ListingMessage)
class ListingMessageAdmin(admin.ModelAdmin):
    list_display = ("motorcycle", "sender", "recipient", "was_redacted", "was_blocked", "created_at")
    list_filter = ("was_blocked", "was_redacted")
    search_fields = ("body", "sender__username", "motorcycle__title")


@admin.register(PlatformFee)
class PlatformFeeAdmin(admin.ModelAdmin):
    list_display = (
        "motorcycle",
        "buyer",
        "basis_amount",
        "fee_amount",
        "status",
        "simulated",
        "paid_at",
    )
    list_filter = ("status", "simulated")
    search_fields = ("buyer__username", "motorcycle__title")


@admin.register(BypassFlag)
class BypassFlagAdmin(admin.ModelAdmin):
    list_display = ("user", "motorcycle", "action", "active", "reason", "created_at")
    list_filter = ("action", "active")
    search_fields = ("user__username", "reason")
    actions = ["apply_block_contact", "apply_ban"]

    @admin.action(description="Block contact unlock for selected users")
    def apply_block_contact(self, request, queryset):
        from market.services.unlock import flag_bypass

        for flag in queryset:
            flag_bypass(
                user=flag.user,
                motorcycle=flag.motorcycle,
                reason=f"Admin block from flag #{flag.pk}",
                action="block_contact",
            )
        self.message_user(request, "Contact unlock blocked for selected users.")

    @admin.action(description="Ban selected users (deactivate)")
    def apply_ban(self, request, queryset):
        from market.services.unlock import flag_bypass

        for flag in queryset:
            flag_bypass(
                user=flag.user,
                motorcycle=flag.motorcycle,
                reason=f"Admin ban from flag #{flag.pk}",
                action="ban",
            )
        self.message_user(request, "Users banned.")


@admin.register(UserSafetyProfile)
class UserSafetyProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "contact_blocked", "is_banned", "updated_at")
    list_filter = ("contact_blocked", "is_banned")
    search_fields = ("user__username",)
