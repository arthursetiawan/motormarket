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
                transmission="automatic",
                stnk_status="lengkap",
                bpkb_status="ada",
                pajak_mati=False,
                plate_number=f"B {1000 + i} XX",
            )
            ListingPrediction.objects.create(
                motorcycle=bike,
                predicted_price=Decimal("13000000"),
                deal_score=7.5,
                deal_label="good_deal",
            )

        # Caution unit: missing BPKB + pajak mati + extreme deal — for exclude_caution
        caution = Motorcycle.objects.create(
            title="2019 Honda BeAT risky",
            description="Cheap BeAT incomplete papers.",
            start_price=Decimal("5000000"),
            seller=self.seller,
            make="Honda",
            model_name="BeAT",
            segment="scooter",
            year=2019,
            mileage_km=500,
            engine_cc=110,
            condition="fair",
            city="Jakarta",
            transmission="automatic",
            stnk_status="hilang",
            bpkb_status="hilang",
            pajak_mati=True,
            plate_number="DK 1 BAD",
        )
        ListingPrediction.objects.create(
            motorcycle=caution,
            predicted_price=Decimal("11000000"),
            deal_score=55.0,
            deal_label="great_deal",
        )

        # Ojol-ready Vario
        ojol = Motorcycle.objects.create(
            title="2022 Honda Vario 160",
            description="Vario 160 ready for ride-hailing with complete surat.",
            start_price=Decimal("22000000"),
            seller=self.seller,
            make="Honda",
            model_name="Vario 160",
            segment="scooter",
            year=2022,
            mileage_km=8000,
            engine_cc=160,
            condition="good",
            city="Jakarta",
            transmission="automatic",
            stnk_status="lengkap",
            bpkb_status="ada",
            pajak_mati=False,
            plate_number="B 5555 OJ",
        )
        ListingPrediction.objects.create(
            motorcycle=ojol,
            predicted_price=Decimal("23000000"),
            deal_score=4.0,
            deal_label="fair",
        )

    def test_recommend_delivery_pack(self):
        pack = recommend_pack("delivery", size=10, preferred_city="Jakarta")
        self.assertIsNotNone(pack)
        self.assertEqual(pack["program"]["slug"], "delivery")
        self.assertGreaterEqual(pack["on_book"], 4)
        self.assertTrue(pack["demand"])
        self.assertLessEqual(len(pack["units"]), 10)

    def test_exclude_caution(self):
        all_pack = recommend_pack("delivery", size=20)
        filtered = recommend_pack("delivery", size=20, exclude_caution=True)
        self.assertGreater(all_pack["on_book"], filtered["on_book"])
        caution_titles = [u["title"] for u in filtered["units"]]
        self.assertNotIn("2019 Honda BeAT risky", caution_titles)

    def test_ojol_ready_filters_small_cc(self):
        # BeAT is 110cc — excluded; Vario 160 included for ride_hailing program models
        pack = recommend_pack("ride_hailing", size=10, ojol_ready=True)
        self.assertIsNotNone(pack)
        models = {u["title"] for u in pack["units"]}
        self.assertTrue(any("Vario 160" in t for t in models))
        self.assertFalse(any("BeAT" in t for t in models))

    def test_unknown_program(self):
        self.assertIsNone(recommend_pack("spaceships", size=10))
