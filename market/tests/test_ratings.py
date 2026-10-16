from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from market.models import Bid, ClosedDeal, Motorcycle, UserRating
from market.services.ratings import can_rate, close_deal, reputation_for, submit_rating


class DualRatingTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("penjual", password="pass12345")
        self.buyer = User.objects.create_user("pembeli", password="pass12345")
        self.outsider = User.objects.create_user("orang", password="pass12345")
        self.bike = Motorcycle.objects.create(
            title="Honda BeAT 2022",
            description="Terawat, surat lengkap, bisa survey di Jakarta Selatan.",
            start_price=Decimal("14000000"),
            seller=self.seller,
            make="Honda",
            model_name="BeAT",
            year=2022,
            city="Jakarta",
        )
        self.bid = Bid.objects.create(
            motorcycle=self.bike, bidder=self.buyer, amount=Decimal("14500000")
        )

    def test_close_deal_marks_sold_and_enables_mutual_rating(self):
        deal = close_deal(
            motorcycle=self.bike,
            seller=self.seller,
            buyer=self.buyer,
            winning_bid=self.bid,
        )
        self.bike.refresh_from_db()
        self.assertTrue(self.bike.is_sold)
        self.assertEqual(self.bike.sold_price, Decimal("14500000"))
        self.assertTrue(can_rate(self.buyer, deal))
        self.assertTrue(can_rate(self.seller, deal))
        self.assertFalse(can_rate(self.outsider, deal))

    def test_one_rating_each_direction_updates_role_stats(self):
        deal = close_deal(
            motorcycle=self.bike, seller=self.seller, buyer=self.buyer, winning_bid=self.bid
        )
        submit_rating(deal=deal, rater=self.buyer, score=5, review="Motor sesuai.")
        submit_rating(deal=deal, rater=self.seller, score=4, review="Pembayar cepat.")

        seller_rep = reputation_for(self.seller)
        buyer_rep = reputation_for(self.buyer)
        self.assertEqual(seller_rep.as_seller.count, 1)
        self.assertEqual(seller_rep.as_seller.average, 5.0)
        self.assertEqual(buyer_rep.as_buyer.count, 1)
        self.assertEqual(buyer_rep.as_buyer.average, 4.0)

        with self.assertRaises(PermissionError):
            submit_rating(deal=deal, rater=self.buyer, score=1)

        self.assertEqual(UserRating.objects.filter(deal=deal).count(), 2)

    def test_cannot_rate_before_close(self):
        self.assertFalse(
            ClosedDeal.objects.filter(motorcycle=self.bike).exists()
        )
        client = Client()
        client.login(username="pembeli", password="pass12345")
        # Fake deal id should 404
        resp = client.get(reverse("rate_deal", args=[9999]))
        self.assertEqual(resp.status_code, 404)

    def test_close_and_rate_via_http(self):
        client = Client()
        client.login(username="penjual", password="pass12345")
        resp = client.post(
            reverse("close_listing_deal", args=[self.bike.pk]),
            {"buyer": self.buyer.pk, "sale_price": "14500000"},
        )
        self.assertEqual(resp.status_code, 302)
        deal = ClosedDeal.objects.get(motorcycle=self.bike)

        client.logout()
        client.login(username="pembeli", password="pass12345")
        resp = client.post(
            reverse("rate_deal", args=[deal.pk]),
            {"score": 5, "review": "Mantap"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            UserRating.objects.filter(
                deal=deal, rater=self.buyer, ratee=self.seller, ratee_role="seller", score=5
            ).exists()
        )

        detail = client.get(reverse("motorcycle_detail", args=[self.bike.pk]))
        self.assertContains(detail, "★")
        profile = client.get(reverse("public_profile", args=["penjual"]))
        self.assertContains(profile, "Sebagai penjual")
        self.assertContains(profile, "5.0")
