from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from market.models import Bid, DealSheet, Motorcycle
from market.tests.kyc_helpers import attach_complete_kyc


class BidFloorTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("seller", password="x")
        self.bidder = User.objects.create_user("bidder", password="x")
        self.other = User.objects.create_user("other", password="x")
        attach_complete_kyc(self.seller)
        attach_complete_kyc(self.bidder)
        attach_complete_kyc(self.other)
        self.bike = Motorcycle.objects.create(
            title="2021 Honda BeAT",
            description="Single owner BeAT for Jabodetabek commuting with service history.",
            start_price=Decimal("10000000"),
            seller=self.seller,
            make="Honda",
            model_name="BeAT",
            year=2021,
            mileage_km=12000,
            city="Jakarta",
            stnk_status="lengkap",
            bpkb_status="ada",
            pajak_mati=False,
            plate_number="B 2222 CD",
        )
        self.client = Client()

    def test_bid_must_beat_start_then_highest(self):
        self.client.login(username="bidder", password="x")
        url = reverse("place_bid", args=[self.bike.pk])
        # Equal to start — reject
        resp = self.client.post(url, {"amount": "10000000"}, follow=True)
        self.assertEqual(Bid.objects.count(), 0)
        self.assertContains(resp, "lebih tinggi")

        # Above start — accept
        resp = self.client.post(url, {"amount": "10500000"}, follow=True)
        self.assertEqual(Bid.objects.count(), 1)

        # Below highest — reject
        self.client.login(username="other", password="x")
        resp = self.client.post(url, {"amount": "10400000"}, follow=True)
        self.assertEqual(Bid.objects.count(), 1)
        self.assertContains(resp, "tawaran tertinggi")

        # Above highest — accept
        resp = self.client.post(url, {"amount": "11000000"}, follow=True)
        self.assertEqual(Bid.objects.count(), 2)


class SuratAndDealSheetTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("seller2", password="x")
        self.buyer = User.objects.create_user("buyer2", password="x")
        self.bike = Motorcycle.objects.create(
            title="2020 Yamaha NMAX",
            description="NMAX ready for ojol with complete papers and recent service.",
            start_price=Decimal("25000000"),
            seller=self.seller,
            make="Yamaha",
            model_name="NMAX",
            year=2020,
            mileage_km=22000,
            engine_cc=155,
            transmission="automatic",
            city="Jakarta",
            stnk_status="lengkap",
            bpkb_status="ada",
            pajak_mati=False,
            plate_number="B 3333 EF",
            tax_valid_through=2026,
        )
        self.client = Client()

    def test_surat_lengkap_and_ojol_ready(self):
        self.assertTrue(self.bike.surat_lengkap)
        self.assertTrue(self.bike.ojol_ready)
        self.assertEqual(self.bike.plate_region, "B")

    def test_detail_renders_trust_and_surat(self):
        url = reverse("motorcycle_detail", args=[self.bike.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Skor")
        self.assertContains(resp, "Surat lengkap")
        self.assertContains(resp, "NegoMotor")

    def test_deal_sheet_submission(self):
        self.client.login(username="buyer2", password="x")
        url = reverse("submit_deal_sheet", args=[self.bike.pk])
        resp = self.client.post(
            url,
            {
                "meetup_city": "Jakarta",
                "meetup_area": "Mall Kelapa Gading",
                "payment_preference": "cicilan",
                "dp_amount": "5000000",
                "notes": "Siap survey weekend",
            },
            follow=True,
        )
        self.assertEqual(DealSheet.objects.count(), 1)
        sheet = DealSheet.objects.get()
        self.assertEqual(sheet.payment_preference, "cicilan")
        self.assertEqual(sheet.meetup_city, "Jakarta")
        self.assertContains(resp, "Lembar deal")
