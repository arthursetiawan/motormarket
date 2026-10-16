from decimal import Decimal
from unittest.mock import patch

import numpy as np
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from market.models import FleetInquiry, ListingPrediction, Motorcycle
from market.services.fleet_intel import pack_snapshot, recommend_pack
from market.services.pricing import score_listing, suggest_fair_value


class PersistTrustTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("trust_seller", password="x")
        self.bike = Motorcycle.objects.create(
            title="2022 Honda BeAT",
            description="Single-owner scooter used for commuting around Jakarta Selatan daily.",
            start_price=Decimal("14000000"),
            seller=self.seller,
            make="Honda",
            model_name="BeAT",
            segment="scooter",
            year=2022,
            mileage_km=16000,
            engine_cc=110,
            condition="good",
            city="Jakarta",
            owners_count=1,
        )

    @patch("market.services.pricing.predict_prices", return_value=np.array([14500000.0]))
    def test_score_listing_persists_trust(self, _mock):
        pred = score_listing(self.bike)
        self.assertIsNotNone(pred)
        pred.refresh_from_db()
        self.assertEqual(pred.trust_label, "high_trust")
        self.assertGreaterEqual(pred.trust_score, 80)
        self.assertIsInstance(pred.trust_flags, list)

    def test_index_trust_filter(self):
        ListingPrediction.objects.create(
            motorcycle=self.bike,
            predicted_price=Decimal("14500000"),
            deal_score=3.0,
            deal_label="fair",
            trust_score=40,
            trust_label="caution",
            trust_flags=[{"code": "extreme_deal", "severity": "alert", "message": "x"}],
            trust_completeness=1.0,
        )
        other = Motorcycle.objects.create(
            title="2021 Yamaha NMAX",
            description="Clean premium scooter with service history in Bandung.",
            start_price=Decimal("22000000"),
            seller=self.seller,
            make="Yamaha",
            model_name="NMAX",
            year=2021,
            mileage_km=12000,
            city="Bandung",
        )
        ListingPrediction.objects.create(
            motorcycle=other,
            predicted_price=Decimal("23000000"),
            deal_score=4.0,
            deal_label="fair",
            trust_score=90,
            trust_label="high_trust",
            trust_flags=[],
            trust_completeness=1.0,
        )
        res = self.client.get(reverse("index"), {"trust": "caution"})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "2022 Honda BeAT")
        self.assertNotContains(res, "2021 Yamaha NMAX")


class PackSnapshotTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("pack_seller", password="x")
        for i in range(3):
            bike = Motorcycle.objects.create(
                title=f"2021 Honda BeAT {i}",
                description="Fleet candidate scooter for delivery programs in greater Jakarta.",
                start_price=Decimal("12000000"),
                seller=self.seller,
                make="Honda",
                model_name="BeAT",
                segment="scooter",
                year=2021,
                mileage_km=10000 + i,
                city="Jakarta",
            )
            ListingPrediction.objects.create(
                motorcycle=bike,
                predicted_price=Decimal("13000000"),
                deal_score=7.0,
                deal_label="good_deal",
                trust_score=85,
                trust_label="high_trust",
            )

    def test_inquiry_stores_pack_snapshot(self):
        res = self.client.post(
            reverse("fleets"),
            {
                "company_name": "Surya Courier",
                "contact_name": "Ada",
                "email": "ada@surya.test",
                "city": "Jakarta",
                "use_case": "delivery",
                "intent": "buy",
                "fleet_size": 10,
                "notes": "",
            },
        )
        self.assertEqual(res.status_code, 302)
        inquiry = FleetInquiry.objects.get()
        self.assertEqual(inquiry.pack_snapshot.get("program_slug"), "delivery")
        self.assertEqual(inquiry.pack_snapshot.get("on_book"), 3)
        self.assertEqual(len(inquiry.pack_snapshot.get("unit_ids")), 3)
        self.assertIn("coverage_pct", inquiry.pack_snapshot)
        self.assertTrue(inquiry.pack_snapshot.get("demand_top"))

    def test_pack_snapshot_helper(self):
        pack = recommend_pack("delivery", size=10, preferred_city="Jakarta")
        snap = pack_snapshot(pack)
        self.assertEqual(snap["program_slug"], "delivery")
        self.assertNotIn("image", snap)


class SuggestAskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("seller", password="x")
        self.client = Client()
        self.client.login(username="seller", password="x")

    @patch("market.services.pricing.predict_prices", return_value=np.array([15500000.0]))
    def test_suggest_fair_value_helper(self, _mock):
        out = suggest_fair_value(
            {
                "make": "Honda",
                "model_name": "BeAT",
                "year": 2022,
                "mileage_km": 12000,
                "engine_cc": 110,
                "condition": "good",
                "city": "Jakarta",
                "owners_count": 1,
                "start_price": "14000000",
            }
        )
        self.assertEqual(out["predicted_price"], 15500000)
        self.assertEqual(out["deal_label"], "good_deal")

    @patch("market.services.pricing.predict_prices", return_value=np.array([15500000.0]))
    def test_suggest_ask_endpoint(self, _mock):
        res = self.client.get(
            reverse("suggest_ask"),
            {
                "make": "Honda",
                "model_name": "BeAT",
                "year": 2022,
                "mileage_km": 12000,
                "condition": "good",
                "city": "Jakarta",
                "start_price": "14000000",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["predicted_price"], 15500000)
