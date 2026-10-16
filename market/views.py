import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from ml.paths import IMPORTANCE_PATH, METRICS_PATH
from ml.recommend import similar_listings
from market.models import Bid, DealSheet, ListingMessage, Motorcycle
from market.services.contact_filter import filter_chat_message
from market.services.desk import listing_desk, market_board
from market.services.fees import fee_summary
from market.services.fleet_intel import enrich_programs, market_coverage, pack_snapshot, recommend_pack
from market.services.fleets import PROGRAMS
from market.services.anomaly import ANOMALY_COPY, anomaly_from_prediction, listing_anomaly
from market.services.pricing import listings_frame, score_listing, suggest_fair_value
from market.services.trust import TRUST_COPY, listing_trust
from market.services.unlock import (
    buyer_has_paid_fee,
    flag_bypass,
    reveal_contact,
    simulate_pay_fee,
)
from .forms import DealSheetForm, FleetInquiryForm, ListingMessageForm, MotorcycleForm

TRUST_FILTERS = {"high_trust", "review", "caution"}
ANOMALY_FILTERS = {"ok", "waspada", "waspada_tinggi"}


def index(request):
    qs = Motorcycle.objects.all().order_by("-created_at")

    make = request.GET.get("make")
    year = request.GET.get("year")
    city = request.GET.get("city")
    deal = request.GET.get("deal")
    trust = request.GET.get("trust")
    anomaly = request.GET.get("anomaly")
    q = request.GET.get("q")
    sort = request.GET.get("sort")
    surat = request.GET.get("surat")

    if make:
        qs = qs.filter(make__iexact=make)
    if year:
        qs = qs.filter(year=year)
    if city:
        qs = qs.filter(city__iexact=city)
    if deal:
        qs = qs.filter(prediction__deal_label=deal)
    if trust in TRUST_FILTERS:
        qs = qs.filter(prediction__trust_label=trust)
    if surat == "lengkap":
        qs = qs.filter(
            stnk_status="lengkap",
            bpkb_status__in=["ada", "di_leasing"],
            pajak_mati=False,
        )
    if anomaly in ANOMALY_FILTERS:
        qs = qs.filter(prediction__anomaly_label=anomaly)
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(model_name__icontains=q)
        )

    if sort == "price_asc":
        qs = qs.order_by("start_price")
    elif sort == "price_desc":
        qs = qs.order_by("-start_price")
    elif sort == "deal":
        qs = qs.order_by("-prediction__deal_score")
    elif sort == "trust":
        qs = qs.order_by("-prediction__trust_score")
    elif sort == "anomaly":
        qs = qs.order_by("prediction__anomaly_score")

    paginator = Paginator(qs.select_related("prediction"), 12)
    motorcycles = paginator.get_page(request.GET.get("page"))
    board = market_board()
    return render(
        request,
        "market/index.html",
        {"motorcycles": motorcycles, "makes": board["makes"], "cities": board["cities"]},
    )


def motorcycle_detail(request, pk):
    motorcycle = get_object_or_404(Motorcycle.objects.select_related("prediction", "seller"), pk=pk)
    highest_bid = motorcycle.bids.order_by("-amount").first()
    try:
        prediction = motorcycle.prediction
    except Exception:
        prediction = None
    if prediction is None:
        prediction = score_listing(motorcycle)
        if prediction is not None:
            motorcycle.prediction = prediction

    similar = []
    all_frame = listings_frame(Motorcycle.objects.all()[:120])
    if not all_frame.empty and str(motorcycle.pk) in set(all_frame["listing_id"].astype(str)):
        try:
            idx = list(all_frame["listing_id"].astype(str)).index(str(motorcycle.pk))
            neighbors = similar_listings(all_frame, idx, k=4)
            ids = [int(x) for x in neighbors["listing_id"].tolist()]
            similar = list(Motorcycle.objects.filter(pk__in=ids).select_related("prediction"))
        except (ValueError, KeyError):
            similar = []

    trust = listing_trust(motorcycle)
    deal_form = DealSheetForm(initial={"meetup_city": motorcycle.city})
    deal_sheets = []
    my_deal = None
    fee_paid = False
    unlocked_contact = None
    chat_messages = []
    message_form = ListingMessageForm()
    fees = fee_summary(motorcycle)

    can_chat = False
    reply_buyers = []
    if request.user.is_authenticated:
        fee_paid = buyer_has_paid_fee(motorcycle, request.user)
        unlocked_contact = reveal_contact(motorcycle, request.user)
        if request.user == motorcycle.seller:
            deal_sheets = list(motorcycle.deal_sheets.select_related("buyer")[:20])
            chat_messages = list(
                motorcycle.messages.filter(was_blocked=False)
                .select_related("sender", "recipient")[:100]
            )
            reply_buyers = list(
                {
                    m.sender_id: m.sender
                    for m in chat_messages
                    if m.sender_id != motorcycle.seller_id
                }.values()
            )
            can_chat = bool(reply_buyers)
        else:
            my_deal = (
                motorcycle.deal_sheets.filter(buyer=request.user).order_by("-created_at").first()
            )
            chat_messages = list(
                motorcycle.messages.filter(was_blocked=False)
                .filter(
                    Q(sender=request.user, recipient=motorcycle.seller)
                    | Q(sender=motorcycle.seller, recipient=request.user)
                )
                .select_related("sender", "recipient")[:100]
            )
            can_chat = True

    anomaly = anomaly_from_prediction(prediction) or listing_anomaly(motorcycle)
    return render(
        request,
        "market/detail.html",
        {
            "motorcycle": motorcycle,
            "highest_bid": highest_bid,
            "prediction": prediction,
            "similar": similar,
            "desk": listing_desk(motorcycle),
            "trust": trust,
            "trust_copy": TRUST_COPY.get(trust.label, ""),
            "deal_form": deal_form,
            "deal_sheets": deal_sheets,
            "my_deal": my_deal,
            "min_bid": float(highest_bid.amount) if highest_bid else float(motorcycle.start_price),
            "fee": fees,
            "fee_paid": fee_paid,
            "unlocked_contact": unlocked_contact,
            "chat_messages": chat_messages,
            "message_form": message_form,
            "can_chat": can_chat,
            "reply_buyers": reply_buyers,
            "anomaly": anomaly,
            "anomaly_copy": ANOMALY_COPY.get(anomaly.label, ""),
        },
    )


@login_required
def place_bid(request, pk):
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    amount = request.POST.get("amount")
    fees = fee_summary(motorcycle)
    if amount:
        try:
            amount = float(amount)
            highest = motorcycle.bids.order_by("-amount").first()
            floor = float(highest.amount) if highest else float(motorcycle.start_price)
            if amount <= floor:
                if highest:
                    messages.error(
                        request,
                        f"Tawaran harus lebih tinggi dari tawaran tertinggi saat ini (Rp {int(floor):,}).".replace(
                            ",", "."
                        ),
                    )
                else:
                    messages.error(
                        request,
                        f"Tawaran harus lebih tinggi dari harga awal (Rp {int(floor):,}).".replace(",", "."),
                    )
            else:
                bid = Bid.objects.create(motorcycle=motorcycle, bidder=request.user, amount=amount)
                messages.success(
                    request,
                    "Tawaran berhasil dikirim. Biaya platform pembeli ~"
                    f"{fees['rate_pct']:.0f}% (min/max berlaku) dibayar saat unlock kontak — "
                    f"estimasi saat ini Rp {int(fees['fee']):,}".replace(",", ".")
                    + ".",
                )
                try:
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        "auctions",
                        {
                            "type": "auction.message",
                            "message": {
                                "type": "new_bid",
                                "motorcycle": motorcycle.pk,
                                "amount": str(bid.amount),
                                "bidder": request.user.username,
                            },
                        },
                    )
                except Exception:
                    pass
        except ValueError:
            messages.error(request, "Nominal tawaran tidak valid")
    return redirect("motorcycle_detail", pk=pk)


@login_required
def submit_deal_sheet(request, pk):
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    if request.user == motorcycle.seller:
        messages.error(request, "Penjual tidak mengirim lembar deal untuk listing sendiri.")
        return redirect("motorcycle_detail", pk=pk)
    if request.method != "POST":
        return redirect("motorcycle_detail", pk=pk)

    form = DealSheetForm(request.POST)
    if form.is_valid():
        sheet = form.save(commit=False)
        sheet.motorcycle = motorcycle
        sheet.buyer = request.user
        sheet.save()
        fees = fee_summary(motorcycle)
        messages.success(
            request,
            "Lembar deal terkirim. Bayar biaya platform "
            f"(~{fees['rate_pct']:.0f}%, sekarang Rp {int(fees['fee']):,})".replace(",", ".")
            + " untuk buka kontak penjual & alamat exact.",
        )
    else:
        messages.error(request, "Lembar deal belum lengkap. Cek kota temu dan cara bayar.")
    return redirect("motorcycle_detail", pk=pk)


@login_required
@require_POST
def send_listing_message(request, pk):
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    form = ListingMessageForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Pesan tidak valid.")
        return redirect("motorcycle_detail", pk=pk)

    # Seller may reply; buyers may message seller. No third-party spam.
    is_seller = request.user == motorcycle.seller
    if not is_seller:
        # buyer path ok
        pass
    elif not motorcycle.messages.exists():
        messages.error(request, "Belum ada pembeli yang chat — tunggu pesan masuk.")
        return redirect("motorcycle_detail", pk=pk)

    raw = form.cleaned_data["body"]
    if is_seller:
        from django.contrib.auth.models import User

        buyer_id = request.POST.get("recipient_id")
        recipient = get_object_or_404(User, pk=buyer_id)
        if not motorcycle.messages.filter(sender=recipient).exists():
            messages.error(request, "Pembeli tidak ditemukan di thread ini.")
            return redirect("motorcycle_detail", pk=pk)
    else:
        recipient = motorcycle.seller

    result = filter_chat_message(raw, strict_block=True)
    if result.blocked:
        ListingMessage.objects.create(
            motorcycle=motorcycle,
            sender=request.user,
            recipient=recipient,
            body=raw[:500],
            was_redacted=True,
            was_blocked=True,
        )
        flag_bypass(
            user=request.user,
            motorcycle=motorcycle,
            reason="Attempted contact share in chat",
            action="warn",
        )
        messages.error(request, result.reason)
        return redirect("motorcycle_detail", pk=pk)

    ListingMessage.objects.create(
        motorcycle=motorcycle,
        sender=request.user,
        recipient=recipient,
        body=result.text,
        was_redacted=result.redacted,
        was_blocked=False,
    )
    if result.redacted:
        messages.warning(request, result.reason)
    else:
        messages.success(request, "Pesan terkirim.")
    return redirect("motorcycle_detail", pk=pk)


@login_required
@require_POST
def pay_platform_fee(request, pk):
    """Simulated checkout — marks fee paid and unlocks contact."""
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    if request.user == motorcycle.seller:
        messages.error(request, "Penjual tidak membayar biaya platform untuk listing sendiri.")
        return redirect("motorcycle_detail", pk=pk)

    deal = motorcycle.deal_sheets.filter(buyer=request.user).order_by("-created_at").first()
    try:
        fee = simulate_pay_fee(motorcycle=motorcycle, buyer=request.user, deal_sheet=deal)
    except PermissionError as exc:
        messages.error(request, str(exc))
        return redirect("motorcycle_detail", pk=pk)

    messages.success(
        request,
        f"Biaya platform Rp {int(fee.fee_amount):,}".replace(",", ".")
        + " ditandai lunas (simulasi). Kontak & lokasi exact terbuka.",
    )
    return redirect("motorcycle_detail", pk=pk)


@login_required
@require_POST
def mark_deal_closed(request, pk):
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    mode = request.POST.get("mode", "on_platform")
    if request.user != motorcycle.seller and not buyer_has_paid_fee(motorcycle, request.user):
        messages.error(request, "Hanya penjual atau pembeli yang sudah bayar biaya yang bisa menutup deal.")
        return redirect("motorcycle_detail", pk=pk)

    if mode == "on_platform":
        motorcycle.deal_status = "closed_on_platform"
        motorcycle.is_sold = True
        if not motorcycle.sold_price:
            highest = motorcycle.bids.order_by("-amount").first()
            motorcycle.sold_price = highest.amount if highest else motorcycle.start_price
        motorcycle.save(update_fields=["deal_status", "is_sold", "sold_price"])
        DealSheet.objects.filter(motorcycle=motorcycle, status="unlocked").update(
            status="closed_on_platform"
        )
        messages.success(request, "Deal ditandai selesai di NegoMotor — ada perlindungan platform.")
    elif mode == "off_app":
        motorcycle.deal_status = "sold_off_app"
        motorcycle.is_sold = True
        motorcycle.save(update_fields=["deal_status", "is_sold"])
        messages.warning(
            request,
            "Deal ditandai di luar aplikasi — tidak ada perlindungan NegoMotor.",
        )
        if request.user != motorcycle.seller:
            flag_bypass(
                user=request.user,
                motorcycle=motorcycle,
                reason="Marked sold off-app",
                action="warn",
            )
    return redirect("motorcycle_detail", pk=pk)


@login_required
@require_POST
def report_bypass(request, pk):
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    reason = (request.POST.get("reason") or "User reported off-platform contact attempt").strip()[:240]
    target_id = request.POST.get("user_id")
    from django.contrib.auth.models import User

    target = get_object_or_404(User, pk=target_id) if target_id else request.user
    flag_bypass(user=target, motorcycle=motorcycle, reason=reason, action="warn")
    messages.success(request, "Laporan bypass tercatat untuk ditinjau admin.")
    return redirect("motorcycle_detail", pk=pk)


def home(request):
    board = market_board()
    featured = Motorcycle.objects.select_related("prediction").order_by("-created_at")[:3]
    return render(
        request,
        "home.html",
        {
            "featured": featured,
            "deals": board["top_deals"][:4],
            "stats": board["totals"],
            "cities": board["city_stats"][:4],
            "city_count": board["city_count"],
        },
    )


@require_GET
@login_required
def suggest_ask(request):
    """JSON fair-value hint for the create-listing form (GET avoids CSRF friction)."""
    required = ("make", "model_name", "year", "mileage_km", "condition", "city")
    if any(not request.GET.get(key) for key in required):
        return JsonResponse({"detail": "need make, model_name, year, mileage_km, condition, city"}, status=400)
    data = {key: request.GET.get(key) for key in request.GET}
    try:
        ask = float(request.GET["start_price"]) if request.GET.get("start_price") else None
    except (TypeError, ValueError):
        ask = None
    suggestion = suggest_fair_value(data, asking_price=ask)
    if suggestion is None:
        return JsonResponse({"detail": "model not trained"}, status=503)
    return JsonResponse(suggestion)


@login_required
def create_listing(request):
    suggestion = None
    if request.method == "POST":
        form = MotorcycleForm(request.POST, request.FILES)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.seller = request.user
            listing.save()
            score_listing(listing)
            messages.success(
                request,
                "Listing dibuat. Nomor HP/WA hanya muncul setelah pembeli bayar biaya platform.",
            )
            return redirect("motorcycle_detail", pk=listing.pk)
        suggestion = suggest_fair_value(form.data)
    else:
        form = MotorcycleForm()
    return render(request, "market/create.html", {"form": form, "suggestion": suggestion})


@login_required
def profile(request):
    listings = Motorcycle.objects.filter(seller=request.user).select_related("prediction")
    return render(request, "account/profile.html", {"profile_user": request.user, "listings": listings})


def terms(request):
    return render(request, "market/terms.html")


def fleets(request):
    program = request.GET.get("program")
    size_raw = request.GET.get("size")
    size = int(size_raw) if size_raw and size_raw.isdigit() else 10
    size = max(5, min(size, 200))
    city = (request.GET.get("city") or "").strip()
    exclude_caution = request.GET.get("exclude_caution") in ("1", "true", "on", "yes")
    ojol_ready = request.GET.get("ojol_ready") in ("1", "true", "on", "yes")

    if request.method == "POST":
        form = FleetInquiryForm(request.POST)
        if form.is_valid():
            inquiry = form.save(commit=False)
            pack = recommend_pack(
                inquiry.use_case,
                size=inquiry.fleet_size,
                preferred_city=inquiry.city or None,
            )
            inquiry.pack_snapshot = pack_snapshot(pack)
            inquiry.save()
            coverage = inquiry.pack_snapshot.get("coverage_pct")
            extra = f" Pack snapshot saved ({coverage}% coverage)." if coverage is not None else ""
            messages.success(
                request,
                f"Permintaan tersimpan untuk {inquiry.company_name}. Armada {inquiry.fleet_size} unit "
                f"({inquiry.get_use_case_display()}) di {inquiry.city}.{extra}",
            )
            return redirect("fleets")
    else:
        initial = {}
        if program in {row["slug"] for row in PROGRAMS}:
            initial["use_case"] = program
        if request.GET.get("intent") in ("buy", "rent"):
            initial["intent"] = request.GET["intent"]
        if 5 <= size <= 500:
            initial["fleet_size"] = size
        if city:
            initial["city"] = city
        form = FleetInquiryForm(initial=initial)

    pack = None
    if program in {row["slug"] for row in PROGRAMS}:
        pack = recommend_pack(
            program,
            size=size,
            preferred_city=city or None,
            exclude_caution=exclude_caution,
            ojol_ready=ojol_ready,
        )

    return render(
        request,
        "market/fleets.html",
        {
            "programs": enrich_programs(size=10),
            "form": form,
            "pack": pack,
            "pack_program": program or "",
            "pack_size": size,
            "pack_city": city,
            "pack_sizes": (10, 25, 50, 100),
            "exclude_caution": exclude_caution,
            "ojol_ready": ojol_ready,
        },
    )


def insights(request):
    metrics = {}
    importance = []
    if METRICS_PATH.exists():
        metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    if IMPORTANCE_PATH.exists():
        importance = json.loads(IMPORTANCE_PATH.read_text(encoding="utf-8"))[:8]
    peak = max((row["importance"] for row in importance), default=0) or 1
    for row in importance:
        row["share"] = round(100 * max(row["importance"], 0) / peak)

    board = market_board()
    return render(
        request,
        "market/insights.html",
        {
            "metrics": metrics,
            "importance": importance,
            "fleet_coverage": market_coverage(),
            **board,
        },
    )
