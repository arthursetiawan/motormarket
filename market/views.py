import json
from decimal import Decimal

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from ml.paths import IMPORTANCE_PATH, METRICS_PATH
from ml.recommend import similar_listings
from market.models import Bid, ClosedDeal, DealSheet, InAppNotification, ListingComment, ListingMessage, Motorcycle, UserRating, Watchlist
from market.services.contact_filter import filter_chat_message
from market.services.desk import listing_desk, market_board
from market.services.fees import fee_summary
from market.services.fleet_intel import enrich_programs, market_coverage, pack_snapshot, recommend_pack
from market.services.fleets import PROGRAMS
from market.services.auction import (
    auction_badge,
    buy_now,
    current_high_bid,
    ensure_auction_window,
    place_proxy_bid,
    surat_announcements,
)
from market.services.anomaly import ANOMALY_COPY, anomaly_from_prediction, listing_anomaly
from market.services.pricing import listings_frame, score_listing, suggest_fair_value
from market.services.ratings import (
    can_rate,
    close_deal,
    counterpart_role,
    pending_ratings_for,
    reputation_for,
    submit_rating,
)
from market.services.sentiment import (
    LABEL_COPY,
    listing_sentiment,
    score_listing_sentiment,
    seller_listing_sentiment,
)
from market.services.kyc import kyc_incomplete_message, kyc_is_complete
from market.services.trust import TRUST_COPY, listing_trust
from market.services.unlock import (
    buyer_has_paid_fee,
    flag_bypass,
    reveal_contact,
    simulate_pay_fee,
)
from .forms import (
    CloseDealForm,
    CompleteKycForm,
    DealSheetForm,
    FleetInquiryForm,
    ListingCommentForm,
    ListingMessageForm,
    MotorcycleForm,
    PpiRequestForm,
    ProxyBidForm,
    UserRatingForm,
)

TRUST_FILTERS = {"high_trust", "review", "caution"}
ANOMALY_FILTERS = {"ok", "waspada", "waspada_tinggi"}


def _live_qs():
    return Motorcycle.objects.filter(is_published=True).exclude(
        auction_status=Motorcycle.STATUS_ENDED,
    )


def _require_complete_kyc(request):
    """Redirect to KYC completion when profile is incomplete. Returns None if OK."""
    if kyc_is_complete(request.user):
        return None
    messages.warning(request, kyc_incomplete_message())
    return redirect("complete_kyc")


def index(request):
    qs = _live_qs().order_by("-created_at")

    make = request.GET.get("make")
    year = request.GET.get("year")
    city = request.GET.get("city")
    deal = request.GET.get("deal")
    trust = request.GET.get("trust")
    anomaly = request.GET.get("anomaly")
    q = request.GET.get("q")
    sort = request.GET.get("sort")
    surat = request.GET.get("surat")
    grade = request.GET.get("grade")
    dealer = request.GET.get("dealer")

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
    if grade in ("A", "B", "C"):
        qs = qs.filter(condition_grade=grade)
    if dealer == "1":
        qs = qs.filter(is_dealer=True)
    elif dealer == "0":
        qs = qs.filter(is_dealer=False)
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
    elif sort == "ending":
        qs = qs.order_by("ends_at")

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
    comments = (
        motorcycle.comments.filter(parent__isnull=True)
        .select_related("author")
        .prefetch_related("replies__author")
    )
    watching = False
    if request.user.is_authenticated:
        watching = Watchlist.objects.filter(user=request.user, motorcycle=motorcycle).exists()
    sentiment = listing_sentiment(motorcycle)
    seller_rep = reputation_for(motorcycle.seller)
    seller_sent = seller_listing_sentiment(motorcycle.seller)
    closed = ClosedDeal.objects.filter(motorcycle=motorcycle).select_related("buyer").first()
    close_form = None
    rate_form = None
    if (
        request.user.is_authenticated
        and request.user.pk == motorcycle.seller_id
        and not motorcycle.is_sold
        and closed is None
    ):
        close_form = CloseDealForm(motorcycle=motorcycle)
    if closed and request.user.is_authenticated and can_rate(request.user, closed):
        rate_form = UserRatingForm()
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
            "sentiment": sentiment,
            "sentiment_copy": LABEL_COPY.get(getattr(sentiment, "label", ""), ""),
            "seller_reputation": seller_rep,
            "seller_sentiment": seller_sent,
            "closed_deal": closed,
            "close_form": close_form,
            "rate_form": rate_form,
            "auction": auction_badge(motorcycle),
            "surat_flags": surat_announcements(motorcycle),
            "bid_form": ProxyBidForm(),
            "comment_form": ListingCommentForm(),
            "ppi_form": PpiRequestForm(),
            "comments": comments,
            "watching": watching,
        },
    )


@login_required
def place_bid(request, pk):
    blocked = _require_complete_kyc(request)
    if blocked:
        return blocked
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    if request.POST.get("max_amount"):
        form = ProxyBidForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Tawaran tidak valid.")
            return redirect("motorcycle_detail", pk=pk)
        try:
            bid, msg = place_proxy_bid(motorcycle, request.user, form.cleaned_data["max_amount"])
            messages.success(request, msg)
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
                            "bidder": bid.bidder.username,
                        },
                    },
                )
            except Exception:
                pass
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("motorcycle_detail", pk=pk)

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
        highest = motorcycle.bids.order_by("-amount").first()
        if not motorcycle.sold_price:
            motorcycle.sold_price = highest.amount if highest else motorcycle.start_price
        motorcycle.save(update_fields=["deal_status", "is_sold", "sold_price"])
        DealSheet.objects.filter(motorcycle=motorcycle, status="unlocked").update(
            status="closed_on_platform"
        )
        buyer = highest.bidder if highest else None
        if buyer and buyer.pk != motorcycle.seller_id:
            try:
                close_deal(
                    motorcycle=motorcycle,
                    seller=motorcycle.seller,
                    buyer=buyer,
                    sale_price=motorcycle.sold_price,
                    winning_bid=highest,
                    notes="Closed via platform fee / seller mark",
                )
            except Exception:
                pass
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
    featured = _live_qs().filter(auction_status=Motorcycle.STATUS_OPEN).select_related("prediction").order_by("-created_at")[:3]
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
    blocked = _require_complete_kyc(request)
    if blocked:
        return blocked
    suggestion = None
    if request.method == "POST":
        form = MotorcycleForm(request.POST, request.FILES)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.seller = request.user
            listing.save()
            listing.is_published = listing.can_publish()
            listing.save(update_fields=["is_published"])
            score_listing(listing)
            score_listing_sentiment(listing)
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
def complete_kyc(request):
    """Fill missing KYC fields for accounts created before the gate, or incomplete signup."""
    if kyc_is_complete(request.user):
        messages.info(request, "Verifikasi akun Anda sudah lengkap.")
        return redirect("profile")
    if request.method == "POST":
        form = CompleteKycForm(request.POST, request.FILES)
        if form.is_valid():
            form.save(request.user)
            messages.success(
                request,
                "Verifikasi tersimpan. Data KTP & foto diri hanya untuk catatan perusahaan — "
                "tidak ditampilkan ke pengguna lain.",
            )
            next_url = request.GET.get("next") or request.POST.get("next") or ""
            if next_url.startswith("/"):
                return redirect(next_url)
            return redirect("profile")
    else:
        form = CompleteKycForm()
    return render(request, "account/kyc_complete.html", {"form": form})


@login_required
def profile(request):
    return _render_profile(request, request.user)


def public_profile(request, username):
    from django.contrib.auth.models import User

    profile_user = get_object_or_404(User, username=username)
    return _render_profile(request, profile_user)


def _render_profile(request, profile_user):
    listings = (
        Motorcycle.objects.filter(seller=profile_user)
        .select_related("prediction", "sentiment")
        .order_by("-created_at")
    )
    received = (
        UserRating.objects.filter(ratee=profile_user)
        .select_related("rater", "deal__motorcycle")
        .order_by("-created_at")[:12]
    )
    pending = []
    is_own = request.user.is_authenticated and request.user.pk == profile_user.pk
    if is_own:
        pending = pending_ratings_for(request.user)
    # Never pass raw KTP / selfie into public profile templates.
    kyc_complete = kyc_is_complete(profile_user) if is_own else None
    return render(
        request,
        "account/profile.html",
        {
            "profile_user": profile_user,
            "listings": listings,
            "reputation": reputation_for(profile_user),
            "seller_sentiment": seller_listing_sentiment(profile_user),
            "received_ratings": received,
            "pending_ratings": pending,
            "kyc_complete": kyc_complete,
            "is_own_profile": is_own,
        },
    )


@login_required
def close_listing_deal(request, pk):
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    if motorcycle.seller_id != request.user.pk:
        messages.error(request, "Hanya penjual yang bisa menutup deal.")
        return redirect("motorcycle_detail", pk=pk)
    if motorcycle.is_sold or ClosedDeal.objects.filter(motorcycle=motorcycle).exists():
        messages.info(request, "Transaksi untuk iklan ini sudah ditutup.")
        return redirect("motorcycle_detail", pk=pk)

    form = CloseDealForm(request.POST or None, motorcycle=motorcycle)
    if request.method == "POST" and form.is_valid():
        try:
            deal = close_deal(
                motorcycle=motorcycle,
                seller=request.user,
                buyer=form.cleaned_data["buyer"],
                sale_price=form.cleaned_data.get("sale_price") or None,
                notes=form.cleaned_data.get("notes") or "",
            )
            motorcycle.deal_status = "closed_on_platform"
            if not motorcycle.sold_price:
                motorcycle.sold_price = deal.sale_price
            motorcycle.save(update_fields=["deal_status", "sold_price", "is_sold"])
            messages.success(
                request,
                f"Deal ditutup dengan {deal.buyer.username}. Kedua pihak bisa saling memberi rating.",
            )
            return redirect("motorcycle_detail", pk=pk)
        except (PermissionError, ValueError) as exc:
            messages.error(request, str(exc))
    elif request.method == "POST":
        messages.error(request, "Pilih pembeli yang valid (harus sudah bid).")
    return redirect("motorcycle_detail", pk=pk)


@login_required
def rate_deal(request, deal_id):
    deal = get_object_or_404(
        ClosedDeal.objects.select_related("motorcycle", "seller", "buyer"), pk=deal_id
    )
    if not can_rate(request.user, deal):
        messages.error(request, "Anda tidak bisa memberi rating untuk transaksi ini.")
        return redirect("motorcycle_detail", pk=deal.motorcycle_id)

    form = UserRatingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            role = counterpart_role(request.user, deal)
            rating = submit_rating(
                deal=deal,
                rater=request.user,
                score=form.cleaned_data["score"],
                review=form.cleaned_data.get("review") or "",
            )
            label = "penjual" if role == UserRating.ROLE_SELLER else "pembeli"
            messages.success(
                request,
                f"Terima kasih — rating {rating.score}★ untuk {label} tersimpan.",
            )
            return redirect("public_profile", username=rating.ratee.username)
        except PermissionError as exc:
            messages.error(request, str(exc))
    return render(
        request,
        "market/rate_deal.html",
        {
            "deal": deal,
            "form": form or UserRatingForm(),
            "ratee_role": counterpart_role(request.user, deal),
        },
    )


def sold_archive(request):
    qs = Motorcycle.objects.filter(
        Q(is_sold=True) | Q(auction_status=Motorcycle.STATUS_SOLD)
    ).order_by("-ends_at", "-created_at")
    paginator = Paginator(qs.select_related("prediction", "seller"), 12)
    motorcycles = paginator.get_page(request.GET.get("page"))
    return render(request, "market/sold.html", {"motorcycles": motorcycles})


@login_required
def buy_now_view(request, pk):
    blocked = _require_complete_kyc(request)
    if blocked:
        return blocked
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    if request.method != "POST":
        return redirect("motorcycle_detail", pk=pk)
    try:
        buy_now(motorcycle, request.user)
        messages.success(request, "Beli Sekarang berhasil — unit terjual.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("motorcycle_detail", pk=pk)


@login_required
def toggle_watch(request, pk):
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    watch, created = Watchlist.objects.get_or_create(user=request.user, motorcycle=motorcycle)
    if created:
        messages.success(request, "Ditambahkan ke watchlist.")
    else:
        watch.delete()
        messages.info(request, "Dihapus dari watchlist.")
    return redirect("motorcycle_detail", pk=pk)


@login_required
def add_comment(request, pk):
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    form = ListingCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.motorcycle = motorcycle
        comment.author = request.user
        parent_id = request.POST.get("parent")
        if parent_id:
            parent = ListingComment.objects.filter(pk=parent_id, motorcycle=motorcycle).first()
            comment.parent = parent
        comment.save()
        if request.user_id != motorcycle.seller_id:
            InAppNotification.objects.create(
                user=motorcycle.seller,
                kind=InAppNotification.KIND_COMMENT,
                motorcycle=motorcycle,
                message=f"Komentar baru di {motorcycle.title} dari {request.user.username}.",
            )
        messages.success(request, "Komentar dipublikasikan.")
    else:
        messages.error(request, "Komentar tidak valid.")
    return redirect("motorcycle_detail", pk=pk)


@login_required
def request_ppi(request, pk):
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    if not motorcycle.ppi_available:
        messages.error(request, "Penjual belum membuka request cek unit.")
        return redirect("motorcycle_detail", pk=pk)
    form = PpiRequestForm(request.POST)
    if form.is_valid():
        req = form.save(commit=False)
        req.motorcycle = motorcycle
        req.requester = request.user
        req.save()
        InAppNotification.objects.create(
            user=motorcycle.seller,
            kind=InAppNotification.KIND_COMMENT,
            motorcycle=motorcycle,
            message=f"Request cek unit dari {request.user.username}.",
        )
        messages.success(request, "Request cek unit terkirim ke penjual.")
    else:
        messages.error(request, "Request tidak valid.")
    return redirect("motorcycle_detail", pk=pk)


@login_required
def notifications(request):
    qs = InAppNotification.objects.filter(user=request.user).select_related("motorcycle")
    if request.method == "POST" and request.POST.get("mark_all"):
        qs.filter(is_read=False).update(is_read=True)
        messages.success(request, "Semua notifikasi ditandai sudah dibaca.")
        return redirect("notifications")
    # Mark ending-soon for watched open auctions within 1h
    for watch in Watchlist.objects.filter(user=request.user).select_related("motorcycle"):
        m = watch.motorcycle
        if m.ends_at and m.auction_status == Motorcycle.STATUS_OPEN:
            remaining = m.ends_at - timezone.now()
            if 0 < remaining.total_seconds() <= 3600:
                InAppNotification.objects.get_or_create(
                    user=request.user,
                    motorcycle=m,
                    kind=InAppNotification.KIND_ENDING_SOON,
                    defaults={"message": f"Lelang {m.title} segera berakhir."},
                )
    qs = InAppNotification.objects.filter(user=request.user).select_related("motorcycle")
    return render(request, "market/notifications.html", {"notifications": qs[:50]})


@login_required
def watchlist_view(request):
    items = (
        Watchlist.objects.filter(user=request.user)
        .select_related("motorcycle", "motorcycle__prediction")
        .order_by("-created_at")
    )
    return render(request, "market/watchlist.html", {"items": items})


def terms(request):
    return render(request, "market/terms.html")


def financing(request):
    """Simulasi kredit / cicilan — estimasi only (no lender API)."""
    from market.services.financing import (
        TENOR_CHOICES,
        default_dp_pct,
        default_effective_rate,
        default_flat_rate,
        default_tenor_months,
        parse_query,
        simulate,
    )

    knobs = parse_query(request.GET)
    listing = None
    otr = knobs["otr"]
    condition = knobs["condition"]
    condition_grade = knobs["condition_grade"]
    make = knobs["make"]
    model_name = knobs["model_name"]
    year = knobs["year"]

    if knobs["listing_id"]:
        listing = Motorcycle.objects.filter(pk=knobs["listing_id"]).first()
        if listing:
            if otr is None:
                otr = listing.start_price
            make = make or listing.make
            model_name = model_name or listing.model_name
            year = year or listing.year
            condition = condition or listing.condition
            condition_grade = condition_grade or getattr(listing, "condition_grade", None)

    if otr is None:
        otr = Decimal("15000000")  # mid used-bike default for blank form

    rate_mode = knobs["rate_mode"]
    annual_rate = knobs["annual_rate"]
    if annual_rate is None:
        annual_rate = default_flat_rate() if rate_mode == "flat" else default_effective_rate()

    dp_pct = knobs["dp_pct"] if knobs["dp_pct"] is not None else default_dp_pct()
    tenor = knobs["tenor_months"] if knobs["tenor_months"] is not None else default_tenor_months()

    estimate = simulate(
        otr,
        dp_pct=dp_pct,
        tenor_months=tenor,
        rate_mode=rate_mode,
        annual_rate=annual_rate,
        condition=condition,
        condition_grade=condition_grade,
    )

    return render(
        request,
        "market/financing.html",
        {
            "estimate": estimate,
            "listing": listing,
            "vehicle": {
                "make": make,
                "model_name": model_name,
                "year": year,
                "condition": condition,
                "condition_grade": condition_grade,
            },
            "form": {
                "otr": otr,
                "dp_pct": dp_pct,
                "dp_pct_display": (dp_pct * 100).quantize(Decimal("1")),
                "tenor": tenor,
                "rate_mode": rate_mode,
                "annual_rate": annual_rate,
                "annual_rate_pct": (annual_rate * 100).quantize(Decimal("0.1")),
                "condition": condition or "",
                "condition_grade": condition_grade or "",
                "make": make or "",
                "model_name": model_name or "",
                "year": year or "",
                "listing_id": listing.pk if listing else (knobs["listing_id"] or ""),
            },
            "tenor_choices": TENOR_CHOICES,
            "rate_samples": {
                "flat": [Decimal("0.10"), Decimal("0.14"), Decimal("0.18")],
                "effective": [Decimal("0.18"), Decimal("0.24"), Decimal("0.30")],
            },
        },
    )


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
