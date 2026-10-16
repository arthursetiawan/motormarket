from django.test import SimpleTestCase

from ml.plates import plate_matches_city, plate_region_code
from ml.trust import assess_listing


class TrustAssessmentTests(SimpleTestCase):
    def test_clean_listing_scores_high(self):
        report = assess_listing(
            make="Honda",
            model_name="BeAT",
            year=2022,
            mileage_km=18000,
            condition="good",
            city="Jakarta",
            owners_count=1,
            asking_price=14_000_000,
            predicted_price=14_500_000,
            deal_score=3.4,
            engine_cc=110,
            has_image=True,
            description="Clean single-owner BeAT used for commuting around Jakarta Selatan.",
            stnk_status="lengkap",
            bpkb_status="ada",
            pajak_mati=False,
            plate_number="B 1234 ABC",
            tax_valid_through=2026,
        )
        self.assertEqual(report.label, "high_trust")
        self.assertGreaterEqual(report.score, 80)
        self.assertEqual(report.flags, [])

    def test_extreme_deal_and_odometer_flags(self):
        report = assess_listing(
            make="Honda",
            model_name="Vario 160",
            year=2018,
            mileage_km=2000,
            condition="good",
            city="Bandung",
            owners_count=4,
            asking_price=8_000_000,
            predicted_price=16_000_000,
            deal_score=50.0,
            has_image=False,
            description="cheap",
            stnk_status="lengkap",
            bpkb_status="ada",
            pajak_mati=False,
        )
        codes = {f.code for f in report.flags}
        self.assertIn("extreme_deal", codes)
        self.assertIn("low_mileage_rate", codes)
        self.assertIn("many_owners", codes)
        self.assertLess(report.score, 55)
        self.assertEqual(report.label, "caution")

    def test_pajak_mati_and_bpkb_missing(self):
        report = assess_listing(
            make="Yamaha",
            model_name="NMAX",
            year=2021,
            mileage_km=20000,
            condition="good",
            city="Surabaya",
            owners_count=1,
            asking_price=22_000_000,
            predicted_price=23_000_000,
            deal_score=4.0,
            has_image=True,
            description="NMAX single owner Surabaya daily commute with service book.",
            stnk_status="lengkap",
            bpkb_status="hilang",
            pajak_mati=True,
            plate_number="L 99 XX",
        )
        codes = {f.code for f in report.flags}
        self.assertIn("bpkb_missing", codes)
        self.assertIn("pajak_mati", codes)
        self.assertLess(report.score, 80)

    def test_plate_city_mismatch(self):
        report = assess_listing(
            make="Honda",
            model_name="Vario 125",
            year=2020,
            mileage_km=15000,
            condition="good",
            city="Denpasar",
            owners_count=1,
            asking_price=18_000_000,
            predicted_price=18_500_000,
            deal_score=2.0,
            has_image=True,
            description="Vario for island commuting around Denpasar and Sanur.",
            stnk_status="lengkap",
            bpkb_status="ada",
            pajak_mati=False,
            plate_number="B 1111 ZZ",
        )
        codes = {f.code for f in report.flags}
        self.assertIn("plate_city_mismatch", codes)


class PlateHelperTests(SimpleTestCase):
    def test_region_codes(self):
        self.assertEqual(plate_region_code("B 1234 ABC"), "B")
        self.assertEqual(plate_region_code("DK 9876 XY"), "DK")
        self.assertEqual(plate_region_code("AB 12 CD"), "AB")

    def test_city_match(self):
        self.assertTrue(plate_matches_city("B 1 AA", "Jakarta"))
        self.assertFalse(plate_matches_city("B 1 AA", "Denpasar"))
        self.assertIsNone(plate_matches_city("", "Jakarta"))
