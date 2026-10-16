from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from market.models import DealSheet, ListingMessage, Motorcycle, PlatformFee
from market.services.contact_filter import filter_chat_message, scrub_public_text
from market.services.fees import compute_platform_fee
from market.services.unlock import buyer_has_paid_fee, simulate_pay_fee


class FeeCalcTests(SimpleTestCase):
    @override_settings(
        PLATFORM_FEE_RATE="0.03",
        PLATFORM_FEE_MIN_IDR="150000",
        PLATFORM_FEE_MAX_IDR="2500000",
    )
    def test_fee_clamped(self):
        self.assertEqual(compute_platform_fee(1_000_000), Decimal("150000"))  # below min
        self.assertEqual(compute_platform_fee(10_000_000), Decimal("300000"))
        self.assertEqual(compute_platform_fee(200_000_000), Decimal("2500000"))  # above max


class ContactFilterTests(SimpleTestCase):
    def test_scrub_phone_and_wa(self):
        result = scrub_public_text("Motor bagus WA 081234567890 atau IG @sellerx")
        self.assertTrue(result.redacted)
        self.assertNotIn("081234567890", result.text)
        self.assertIn("kontak disembunyikan", result.text)

    def test_chat_blocks_phone(self):
        result = filter_chat_message("Chat saya di 081234567890 ya")
        self.assertTrue(result.blocked)


class CommissionFlowTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("seller_c", password="x")
        self.buyer = User.objects.create_user("buyer_c", password="x")
        self.bike = Motorcycle.objects.create(
            title="2021 Honda Vario",
            description="Vario bersih single owner Jakarta Selatan ready.",
            start_price=Decimal("20000000"),
            seller=self.seller,
            make="Honda",
            model_name="Vario 160",
            year=2021,
            mileage_km=15000,
            engine_cc=160,
            city="Jakarta",
            seller_phone="081111111111",
            seller_wa="081111111111",
            stnk_status="lengkap",
            bpkb_status="ada",
        )
        self.client = Client()

    def test_listing_scrubs_contact_on_create(self):
        self.client.login(username="seller_c", password="x")
        resp = self.client.post(
            reverse("create_listing"),
            {
                "title": "Bekas WA 081222333444",
                "description": "Unit bagus hubungi WA 081222333444 sekarang juga untuk survey.",
                "start_price": "15000000",
                "make": "Honda",
                "model_name": "BeAT",
                "year": "2020",
                "mileage_km": "10000",
                "engine_cc": "110",
                "condition": "good",
                "city": "Jakarta",
                "owners_count": "1",
                "transmission": "automatic",
                "fuel_type": "petrol",
                "stnk_status": "lengkap",
                "bpkb_status": "ada",
                "pajak_mati": False,
                "seller_phone": "081999888777",
                "seller_wa": "081999888777",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        bike = Motorcycle.objects.exclude(pk=self.bike.pk).latest("id")
        self.assertNotIn("081222333444", bike.description)
        self.assertNotIn("081222333444", bike.title)
        # Private contact stored
        self.assertEqual(bike.seller_phone, "081999888777")
        # Public detail must not show phone for anonymous
        anon = Client().get(reverse("motorcycle_detail", args=[bike.pk]))
        self.assertNotContains(anon, "081999888777")

    def test_chat_and_fee_unlock(self):
        self.client.login(username="buyer_c", password="x")
        # Blocked contact message
        resp = self.client.post(
            reverse("send_listing_message", args=[self.bike.pk]),
            {"body": "WA saya 081234567890"},
            follow=True,
        )
        self.assertTrue(ListingMessage.objects.filter(was_blocked=True).exists())

        # Clean message
        resp = self.client.post(
            reverse("send_listing_message", args=[self.bike.pk]),
            {"body": "Masih ready? Bisa survey Sabtu?"},
            follow=True,
        )
        self.assertTrue(ListingMessage.objects.filter(was_blocked=False).exists())
        self.assertContains(resp, "Masih ready")

        # Contact hidden before fee
        resp = self.client.get(reverse("motorcycle_detail", args=[self.bike.pk]))
        self.assertNotContains(resp, "081111111111")
        self.assertContains(resp, "Bayar biaya platform")

        # Simulated pay
        resp = self.client.post(reverse("pay_platform_fee", args=[self.bike.pk]), follow=True)
        self.assertTrue(buyer_has_paid_fee(self.bike, self.buyer))
        self.assertContains(resp, "081111111111")
        fee = PlatformFee.objects.get(buyer=self.buyer, motorcycle=self.bike)
        self.assertEqual(fee.status, "paid")
        self.assertTrue(fee.simulated)

    def test_deal_sheet_and_close_on_platform(self):
        self.client.login(username="buyer_c", password="x")
        self.client.post(
            reverse("submit_deal_sheet", args=[self.bike.pk]),
            {
                "meetup_city": "Jakarta",
                "meetup_area": "Kelapa Gading",
                "meetup_exact": "Jl. Boulevard Raya No. 1",
                "payment_preference": "transfer",
                "notes": "Siap weekend",
            },
        )
        sheet = DealSheet.objects.get()
        self.assertEqual(sheet.meetup_exact, "Jl. Boulevard Raya No. 1")
        simulate_pay_fee(motorcycle=self.bike, buyer=self.buyer, deal_sheet=sheet)
        sheet.refresh_from_db()
        self.assertEqual(sheet.status, "unlocked")

        resp = self.client.post(
            reverse("mark_deal_closed", args=[self.bike.pk]),
            {"mode": "on_platform"},
            follow=True,
        )
        self.bike.refresh_from_db()
        self.assertEqual(self.bike.deal_status, "closed_on_platform")
        self.assertContains(resp, "Deal di NegoMotor")
