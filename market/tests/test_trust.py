from django.test import SimpleTestCase

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
        )
        codes = {f.code for f in report.flags}
        self.assertIn("extreme_deal", codes)
        self.assertIn("low_mileage_rate", codes)
        self.assertIn("many_owners", codes)
        self.assertLess(report.score, 55)
        self.assertEqual(report.label, "caution")
