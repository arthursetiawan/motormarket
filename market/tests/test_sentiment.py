from decimal import Decimal

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from market.models import Motorcycle
from market.services.sentiment import score_listing_sentiment, seller_listing_sentiment
from ml.sentiment import assess_listing_text


class SentimentLexiconTests(SimpleTestCase):
    def test_professional_bahasa_copy_scores_high(self):
        report = assess_listing_text(
            title="Honda BeAT 2022 Jakarta",
            description=(
                "Pemilik pertama, surat lengkap BPKB STNK, pajak hidup, "
                "terawat service record, bisa survey dan nego wajar di Jakarta Selatan."
            ),
        )
        self.assertEqual(report.label, "professional")
        self.assertGreaterEqual(report.score, 70)

    def test_spammy_aggressive_copy_scores_low(self):
        report = assess_listing_text(
            title="MURAH BANGET!!! HARGA PAS!!!",
            description=(
                "NO LOWBALL jangan nawar serius aja!!! WA only 081234567890 "
                "cepat laku must sell chat wa buang waktu!!!"
            ),
        )
        self.assertEqual(report.label, "caution")
        self.assertLess(report.score, 45)
        codes = {s.code for s in report.signals}
        self.assertTrue({"negative_cue", "off_platform_contact"} & codes)


class SentimentPersistenceTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("seller_sent", password="pass12345")
        self.bike = Motorcycle.objects.create(
            title="Yamaha NMAX 2021",
            description="Kondisi bagus, terawat, siap pakai, bisa dicek di Bandung.",
            start_price=Decimal("22000000"),
            seller=self.seller,
            make="Yamaha",
            model_name="NMAX",
            year=2021,
            city="Bandung",
        )

    def test_score_persists_and_aggregates_on_seller(self):
        report = score_listing_sentiment(self.bike)
        self.bike.refresh_from_db()
        self.assertTrue(hasattr(self.bike, "sentiment"))
        self.assertEqual(self.bike.sentiment.label, report.label)
        self.assertAlmostEqual(self.bike.sentiment.score, report.score, places=1)

        agg = seller_listing_sentiment(self.seller)
        self.assertEqual(agg.count, 1)
        self.assertIsNotNone(agg.average)

        detail = self.client.get(f"/market/motorcycle/{self.bike.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "sentiment-")
