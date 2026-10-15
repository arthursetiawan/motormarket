from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from market.models import ListingPrediction, Motorcycle
from market.services.fleet_intel import recommend_pack


class FleetPackTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("fleet_seller", password="x")
        for i, city in enumerate(["Jakarta", "Jakarta", "Bekasi", "Surabaya"]):
            bike = Motorcycle.objects.create(
                title=f"2021 Honda BeAT {i}",
                description="Fleet candidate scooter for delivery programs in greater Jakarta.",
                start_price=Decimal("12000000"),
                seller=self.seller,
                make="Honda",
                model_name="BeAT",
                segment="scooter",
                year=2021,
                mileage_km=12000 + i * 1000,
                engine_cc=110,
                condition="good",
                city=city,
            )
            ListingPrediction.objects.create(
                motorcycle=bike,
                predicted_price=Decimal("13000000"),
                deal_score=7.5,
                deal_label="good_deal",
            )

    def test_recommend_delivery_pack(self):
        pack = recommend_pack("delivery", size=10, preferred_city="Jakarta")
        self.assertIsNotNone(pack)
        self.assertEqual(pack["program"]["slug"], "delivery")
        self.assertEqual(pack["on_book"], 4)
        self.assertEqual(pack["sourcing_gap"], 6)
        self.assertEqual(pack["coverage_pct"], 40)
        self.assertGreater(pack["buy_total"], 0)
        self.assertTrue(pack["demand"])
        self.assertLessEqual(len(pack["units"]), 10)

    def test_unknown_program(self):
        self.assertIsNone(recommend_pack("spaceships", size=10))
