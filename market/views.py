import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from ml.paths import IMPORTANCE_PATH, METRICS_PATH
from ml.recommend import similar_listings
from market.models import Bid, ListingPrediction, Motorcycle
from market.services.pricing import listings_frame, score_listing
from .forms import MotorcycleForm


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
    return render(request, "market/index.html", {"motorcycles": motorcycles})


def motorcycle_detail(request, pk):
    motorcycle = get_object_or_404(Motorcycle.objects.select_related("prediction", "seller"), pk=pk)
    highest_bid = motorcycle.bids.order_by("-amount").first()
    prediction = getattr(motorcycle, "prediction", None)
    if prediction is None:
        prediction = score_listing(motorcycle)

    similar = []
    frame = listings_frame(Motorcycle.objects.exclude(pk=motorcycle.pk)[:80])
    if not frame.empty:
        all_frame = listings_frame(Motorcycle.objects.all()[:120])
        try:
            idx = list(all_frame["listing_id"]).index(str(motorcycle.pk))
            neighbors = similar_listings(all_frame, idx, k=4)
            ids = [int(x) for x in neighbors["listing_id"].tolist()]
            similar = list(Motorcycle.objects.filter(pk__in=ids).select_related("prediction"))
        except (ValueError, KeyError):
            similar = []

    return render(
        request,
        "market/detail.html",
        {
            "motorcycle": motorcycle,
            "highest_bid": highest_bid,
            "prediction": prediction,
            "similar": similar,
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
    featured = Motorcycle.objects.select_related("prediction").order_by("-created_at")[:3]
    deals = (
        ListingPrediction.objects.filter(deal_label__in=["great_deal", "good_deal"])
        .select_related("motorcycle")
        .order_by("-deal_score")[:4]
    )
    stats = Motorcycle.objects.aggregate(n=Count("id"), avg_ask=Avg("start_price"))
    return render(
        request,
        "home.html",
        {"featured": featured, "deals": deals, "stats": stats},
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


def insights(request):
    metrics = {}
    importance = []
    if METRICS_PATH.exists():
        metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    if IMPORTANCE_PATH.exists():
        importance = json.loads(IMPORTANCE_PATH.read_text(encoding="utf-8"))[:8]

    qs = ListingPrediction.objects.select_related("motorcycle")
    label_counts = list(qs.values("deal_label").annotate(n=Count("id")).order_by("-n"))
    city_stats = list(
        Motorcycle.objects.values("city")
        .annotate(n=Count("id"), avg_ask=Avg("start_price"))
        .order_by("-n")[:8]
    )
    make_stats = list(
        Motorcycle.objects.values("make")
        .annotate(n=Count("id"), avg_ask=Avg("start_price"))
        .order_by("-n")[:8]
    )
    top_deals = qs.order_by("-deal_score")[:8]
    rich = qs.order_by("deal_score")[:8]
    return render(
        request,
        "market/insights.html",
        {
            "metrics": metrics,
            "importance": importance,
            "label_counts": label_counts,
            "city_stats": city_stats,
            "make_stats": make_stats,
            "top_deals": top_deals,
            "rich": rich,
        },
    )
