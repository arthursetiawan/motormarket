from django.shortcuts import render, get_object_or_404, redirect
from .models import Motorcycle, Bid
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import MotorcycleForm
from django.core.paginator import Paginator
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def index(request):
    qs = Motorcycle.objects.all().order_by('-created_at')

    # Filters
    make = request.GET.get('make')
    year = request.GET.get('year')
    q = request.GET.get('q')
    sort = request.GET.get('sort')

    if make:
        qs = qs.filter(make__iexact=make)
    if year:
        qs = qs.filter(year=year)
    if q:
        qs = qs.filter(title__icontains=q) | qs.filter(description__icontains=q)

    if sort == 'price_asc':
        qs = qs.order_by('start_price')
    elif sort == 'price_desc':
        qs = qs.order_by('-start_price')

    paginator = Paginator(qs, 12)
    page = request.GET.get('page')
    motorcycles = paginator.get_page(page)
    return render(request, 'market/index.html', {'motorcycles': motorcycles})


def motorcycle_detail(request, pk):
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    highest_bid = motorcycle.bids.order_by('-amount').first()
    return render(request, 'market/detail.html', {'motorcycle': motorcycle, 'highest_bid': highest_bid})


@login_required
def place_bid(request, pk):
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    amount = request.POST.get('amount')
    if amount:
        try:
            amount = float(amount)
            if amount <= float(motorcycle.start_price):
                messages.error(request, 'Bid must be higher than start price')
            else:
                bid = Bid.objects.create(motorcycle=motorcycle, bidder=request.user, amount=amount)
                messages.success(request, 'Bid placed successfully')

                # Broadcast the new bid to WebSocket group for live updates
                try:
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        'auctions',
                        {
                            'type': 'auction.message',
                            'message': {
                                'type': 'new_bid',
                                'motorcycle': motorcycle.pk,
                                'amount': str(bid.amount),
                                'bidder': request.user.username,
                            }
                        }
                    )
                except Exception:
                    # Don't break the request if broadcasting fails
                    pass
        except ValueError:
            messages.error(request, 'Invalid bid amount')
    return redirect('motorcycle_detail', pk=pk)


def home(request):
    featured = Motorcycle.objects.all().order_by('-created_at')[:3]
    return render(request, 'home.html', {'featured': featured})


@login_required
def create_listing(request):
    if request.method == 'POST':
        form = MotorcycleForm(request.POST, request.FILES)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.seller = request.user
            listing.save()
            messages.success(request, 'Listing created')
            return redirect('motorcycle_detail', pk=listing.pk)
    else:
        form = MotorcycleForm()
    return render(request, 'market/create.html', {'form': form})


@login_required
def profile(request):
    user = request.user
    listings = Motorcycle.objects.filter(seller=user).order_by('-created_at')
    return render(request, 'account/profile.html', {'profile_user': user, 'listings': listings})
