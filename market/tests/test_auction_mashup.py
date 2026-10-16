from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from market.models import Bid, InAppNotification, Motorcycle, Watchlist
from market.services.auction import (
    apply_soft_close,
    close_auction,
    current_high_bid,
    place_proxy_bid,
    reserve_met,
)


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    AUCTION_MIN_INCREMENT_IDR="50000",
    AUCTION_SOFT_CLOSE_MINUTES=2,
    AUCTION_SOFT_CLOSE_EXTEND_MINUTES=2,
)
class ReserveTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("seller", password="x")
        self.buyer = User.objects.create_user("buyer", password="x")
        self.bike = Motorcycle.objects.create(
            title="Vario reserve",
            description="test",
            start_price=Decimal("10000000"),
            seller=self.seller,
            has_reserve=True,
            reserve_price=Decimal("12000000"),
            ends_at=timezone.now() + timezone.timedelta(hours=2),
            is_published=True,
            known_flaws="Baret kecil",
            checklist_front=True,
            checklist_side=True,
            checklist_odometer=True,
        )

    def test_no_reserve_badge_path(self):
        self.bike.has_reserve = False
        self.bike.reserve_price = None
        self.bike.save()
        place_proxy_bid(self.bike, self.buyer, Decimal("10000000"))
        close_auction(self.bike)
        self.bike.refresh_from_db()
        self.assertEqual(self.bike.auction_status, Motorcycle.STATUS_SOLD)
        self.assertTrue(self.bike.is_sold)

    def test_reserve_not_met(self):
        place_proxy_bid(self.bike, self.buyer, Decimal("11000000"))
        self.assertFalse(reserve_met(self.bike))
        close_auction(self.bike)
        self.bike.refresh_from_db()
        self.assertEqual(self.bike.auction_status, Motorcycle.STATUS_RESERVE_NOT_MET)
        self.assertFalse(self.bike.is_sold)

    def test_reserve_met(self):
        place_proxy_bid(self.bike, self.buyer, Decimal("12500000"))
        high = current_high_bid(self.bike)
        self.assertEqual(high.amount, Decimal("12000000"))  # lifted to reserve
        self.assertTrue(reserve_met(self.bike))
        close_auction(self.bike)
        self.bike.refresh_from_db()
        self.assertEqual(self.bike.auction_status, Motorcycle.STATUS_SOLD)
        self.assertEqual(self.bike.sold_price, Decimal("12000000"))


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    AUCTION_MIN_INCREMENT_IDR="50000",
    AUCTION_SOFT_CLOSE_MINUTES=2,
    AUCTION_SOFT_CLOSE_EXTEND_MINUTES=2,
)
class SoftCloseTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("seller2", password="x")
        self.buyer = User.objects.create_user("buyer2", password="x")
        self.bike = Motorcycle.objects.create(
            title="Soft close bike",
            description="test",
            start_price=Decimal("8000000"),
            seller=self.seller,
            has_reserve=False,
            ends_at=timezone.now() + timezone.timedelta(minutes=1),
            is_published=True,
            known_flaws="Tidak ada",
            checklist_front=True,
            checklist_side=True,
            checklist_odometer=True,
        )

    def test_bid_in_window_extends_end(self):
        before = self.bike.ends_at
        place_proxy_bid(self.bike, self.buyer, Decimal("8500000"))
        self.bike.refresh_from_db()
        self.assertGreater(self.bike.ends_at, before)
        # roughly +2 minutes from now
        self.assertGreaterEqual(
            self.bike.ends_at,
            timezone.now() + timezone.timedelta(minutes=1, seconds=50),
        )

    def test_bid_outside_window_does_not_extend(self):
        self.bike.ends_at = timezone.now() + timezone.timedelta(hours=3)
        self.bike.save(update_fields=["ends_at"])
        before = self.bike.ends_at
        self.assertFalse(apply_soft_close(self.bike))
        self.bike.refresh_from_db()
        self.assertEqual(self.bike.ends_at, before)


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    AUCTION_MIN_INCREMENT_IDR="50000",
    AUCTION_SOFT_CLOSE_MINUTES=2,
    AUCTION_SOFT_CLOSE_EXTEND_MINUTES=2,
)
class ProxyBidTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("seller3", password="x")
        self.a = User.objects.create_user("alice", password="x")
        self.b = User.objects.create_user("bob", password="x")
        self.bike = Motorcycle.objects.create(
            title="Proxy bike",
            description="test",
            start_price=Decimal("10000000"),
            seller=self.seller,
            has_reserve=False,
            ends_at=timezone.now() + timezone.timedelta(hours=5),
            is_published=True,
            known_flaws="Spion goyang",
            checklist_front=True,
            checklist_side=True,
            checklist_odometer=True,
        )

    def test_proxy_auto_increments_to_stay_highest(self):
        place_proxy_bid(self.bike, self.a, Decimal("15000000"))
        high = current_high_bid(self.bike)
        self.assertEqual(high.bidder_id, self.a.id)
        self.assertEqual(high.amount, Decimal("10000000"))

        place_proxy_bid(self.bike, self.b, Decimal("12000000"))
        high = current_high_bid(self.bike)
        self.assertEqual(high.bidder_id, self.a.id)
        self.assertEqual(high.amount, Decimal("12050000"))

    def test_higher_proxy_takes_lead(self):
        place_proxy_bid(self.bike, self.a, Decimal("13000000"))
        place_proxy_bid(self.bike, self.b, Decimal("14000000"))
        high = current_high_bid(self.bike)
        self.assertEqual(high.bidder_id, self.b.id)
        self.assertEqual(high.amount, Decimal("13050000"))

    def test_outbid_notification(self):
        place_proxy_bid(self.bike, self.a, Decimal("11000000"))
        place_proxy_bid(self.bike, self.b, Decimal("16000000"))
        self.assertTrue(
            InAppNotification.objects.filter(
                user=self.a,
                kind=InAppNotification.KIND_OUTBID,
                motorcycle=self.bike,
            ).exists()
        )

    def test_seller_cannot_bid(self):
        with self.assertRaises(ValueError):
            place_proxy_bid(self.bike, self.seller, Decimal("20000000"))


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
)
class WatchlistUiSmokeTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("seller4", password="x")
        self.buyer = User.objects.create_user("buyer4", password="x")
        self.bike = Motorcycle.objects.create(
            title="Watch me",
            description="test",
            start_price=Decimal("9000000"),
            seller=self.seller,
            ends_at=timezone.now() + timezone.timedelta(hours=1),
            is_published=True,
            known_flaws="ok",
            checklist_front=True,
            checklist_side=True,
            checklist_odometer=True,
        )

    def test_watch_and_detail(self):
        self.client.login(username="buyer4", password="x")
        r = self.client.post(f"/market/motorcycle/{self.bike.pk}/watch/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Watchlist.objects.filter(user=self.buyer, motorcycle=self.bike).exists())
        r = self.client.get(f"/market/motorcycle/{self.bike.pk}/")
        self.assertContains(r, "Tanpa reserve")
        self.assertContains(r, "Kekurangan diketahui")
