from decimal import Decimal
from unittest.mock import patch

import numpy as np
import pandas as pd
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from market.models import ListingPrediction, Motorcycle
from market.services.anomaly import listing_anomaly
from market.services.pricing import score_listing
from ml.anomaly import MarketIndex, assess_market_anomaly


def _peer_frame(n=12, ask=13_000_000, year=2021, km=15_000):
    rows = []
    for i in range(n):
        rows.append(
            {
                "listing_id": f"p-{i}",
                "make": "Honda",
                "model_name": "BeAT",
                "segment": "scooter",
                "year": year,
                "mileage_km": km + i * 200,
                "asking_price": ask + i * 100_000,
                "sold_price": ask + i * 80_000,
                "engine_cc": 110,
            }
        )
    return pd.DataFrame(rows)


class MarketAnomalyUnitTests(TestCase):
    def test_deep_discount_and_sparse_comps(self):
        sold = _peer_frame(n=2)
        index = MarketIndex(live=pd.DataFrame(), sold=sold)
        peer = index.peer_for(make="Honda", model_name="BeAT", segment="scooter")
        report = assess_market_anomaly(
            make="Honda",
            model_name="BeAT",
            segment="scooter",
            year=2021,
            mileage_km=2000,
            engine_cc=110,
            asking_price=4_000_000,
            predicted_price=13_000_000,
            deal_score=55.0,
            peer=peer,
        )
        codes = {f.code for f in report.flags}
        self.assertIn("sparse_comps", codes)
        self.assertIn("fair_value_deep_discount", codes)
        self.assertEqual(report.label, "waspada_tinggi")

    def test_price_outside_peer_iqr(self):
        sold = _peer_frame(n=20, ask=14_000_000)
        index = MarketIndex(live=sold, sold=sold)
        peer = index.peer_for(make="Honda", model_name="BeAT", segment="scooter")
        report = assess_market_anomaly(
            make="Honda",
            model_name="BeAT",
            segment="scooter",
            year=2021,
            mileage_km=16000,
            engine_cc=110,
            asking_price=3_500_000,
            predicted_price=14_000_000,
            deal_score=10.0,
            peer=peer,
        )
        codes = {f.code for f in report.flags}
        self.assertTrue({"price_below_peer_band", "ask_vs_peer_median"} & codes)
        self.assertIn(report.label, {"waspada", "waspada_tinggi"})

    def test_catalog_msrp_ceiling(self):
        report = assess_market_anomaly(
            make="Honda",
            model_name="BeAT",
            segment="scooter",
            year=2022,
            mileage_km=10000,
            engine_cc=110,
            asking_price=25_000_000,  # above BeAT MSRP ~18.5M
            predicted_price=14_000_000,
            deal_score=-40.0,
            peer=None,
        )
        codes = {f.code for f in report.flags}
        self.assertIn("ask_above_msrp", codes)


class AnomalyPersistenceTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("anomaly_seller", password="x")
        for i in range(8):
            Motorcycle.objects.create(
                title=f"2021 Honda BeAT peer {i}",
                description="Normal peer scooter listing used for market band tests in Jakarta.",
                start_price=Decimal(str(12_500_000 + i * 150_000)),
                seller=self.seller,
                make="Honda",
                model_name="BeAT",
                segment="scooter",
                year=2021,
                mileage_km=14000 + i * 300,
                engine_cc=110,
                condition="good",
                city="Jakarta",
            )
        self.outlier = Motorcycle.objects.create(
            title="2021 Honda BeAT outlier",
            description="Suspiciously cheap BeAT with very low km for its age in Jakarta.",
            start_price=Decimal("4500000"),
            seller=self.seller,
            make="Honda",
            model_name="BeAT",
            segment="scooter",
            year=2021,
            mileage_km=900,
            engine_cc=110,
            condition="good",
            city="Jakarta",
        )

    @patch("market.services.pricing.predict_prices", return_value=np.array([13000000.0]))
    def test_score_listing_persists_anomaly(self, _mock):
        pred = score_listing(self.outlier)
        self.assertIsNotNone(pred)
        pred.refresh_from_db()
        self.assertIn(pred.anomaly_label, {"waspada", "waspada_tinggi"})
        self.assertIsInstance(pred.anomaly_flags, list)
        self.assertGreater(pred.anomaly_peer_n, 0)
        self.assertTrue(any(f.get("severity") == "alert" for f in pred.anomaly_flags))

    def test_index_anomaly_filter(self):
        ListingPrediction.objects.create(
            motorcycle=self.outlier,
            predicted_price=Decimal("13000000"),
            deal_score=40.0,
            deal_label="great_deal",
            trust_score=40,
            trust_label="caution",
            anomaly_score=35,
            anomaly_label="waspada_tinggi",
            anomaly_flags=[{"code": "price_below_peer_band", "severity": "alert", "message": "x"}],
            anomaly_confidence=0.7,
            anomaly_peer_n=8,
            anomaly_peer_source="model_live",
        )
        res = self.client.get(reverse("index"), {"anomaly": "waspada_tinggi"})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "2021 Honda BeAT outlier")
        self.assertContains(res, "Waspada tinggi")

    def test_listing_anomaly_helper(self):
        report = listing_anomaly(self.outlier, predicted_price=13_000_000, deal_score=50.0)
        self.assertIn(report.label, {"waspada", "waspada_tinggi"})
