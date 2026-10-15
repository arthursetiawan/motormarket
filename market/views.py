import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from ml.paths import IMPORTANCE_PATH, METRICS_PATH
from ml.recommend import similar_listings
from market.models import Bid, Motorcycle
from market.services.desk import listing_desk, market_board
from market.services.fleet_intel import enrich_programs, market_coverage, recommend_pack
from market.services.fleets import PROGRAMS
from market.services.pricing import listings_frame, score_listing
from market.services.trust import TRUST_COPY, listing_trust
from .forms import FleetInquiryForm, MotorcycleForm


def index(request):
    qs = Motorcycle.objects.all().order_by("-created_at")

    make = request.GET.get("make")
    year = request.GET.get("year")
    city = request.GET.get("city")
    deal = request.GET.get("deal")
    q = request.GET.get("q")
    sort = request.GET.get("sort")

    if make:
        qs = qs.filter(make__iexact=make)
    if year:
        qs = qs.filter(year=year)
    if city:
        qs = qs.filter(city__iexact=city)
    if deal:
        qs = qs.filter(prediction__deal_label=deal)
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
    prediction = getattr(motorcycle, "prediction", None)
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
        },
    )


@login_required
def place_bid(request, pk):
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    amount = request.POST.get("amount")
    if amount:
        try:
            amount = float(amount)
            if amount <= float(motorcycle.start_price):
                messages.error(request, "Bid must be higher than start price")
            else:
                bid = Bid.objects.create(motorcycle=motorcycle, bidder=request.user, amount=amount)
                messages.success(request, "Bid placed successfully")
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
            messages.error(request, "Invalid bid amount")
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


@login_required
def create_listing(request):
    if request.method == "POST":
        form = MotorcycleForm(request.POST, request.FILES)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.seller = request.user
            listing.save()
            score_listing(listing)
            messages.success(request, "Listing created and scored against the price model")
            return redirect("motorcycle_detail", pk=listing.pk)
    else:
        form = MotorcycleForm()
    return render(request, "market/create.html", {"form": form})


@login_required
def profile(request):
    listings = Motorcycle.objects.filter(seller=request.user).select_related("prediction")
    return render(request, "account/profile.html", {"profile_user": request.user, "listings": listings})


def fleets(request):
    program = request.GET.get("program")
    size_raw = request.GET.get("size")
    size = int(size_raw) if size_raw and size_raw.isdigit() else 10
    size = max(5, min(size, 200))
    city = (request.GET.get("city") or "").strip()

    if request.method == "POST":
        form = FleetInquiryForm(request.POST)
        if form.is_valid():
            inquiry = form.save()
            messages.success(
                request,
                f"Request saved for {inquiry.company_name}. A {inquiry.fleet_size}-bike {inquiry.get_use_case_display().lower()} fleet in {inquiry.city}.",
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
        pack = recommend_pack(program, size=size, preferred_city=city or None)

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
