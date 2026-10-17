from datetime import date
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from market.forms import CompleteKycForm, KycSignupForm
from market.models import Motorcycle, UserProfile
from market.tests.kyc_helpers import attach_complete_kyc, tiny_selfie
from market.validators import validate_nik


class NikValidationTests(TestCase):
    def test_rejects_short_and_non_digit(self):
        from django.core.exceptions import ValidationError

        for bad in ("123", "123456789012345", "123456789012345a", "abcdefghijklmnop"):
            with self.assertRaises(ValidationError):
                validate_nik(bad)

    def test_accepts_16_digits(self):
        self.assertEqual(validate_nik("3174010101010001"), "3174010101010001")
        self.assertEqual(validate_nik(" 3174-0101-0101-0001 "), "3174010101010001")


class KycSignupFormTests(TestCase):
    def _base_data(self, **overrides):
        data = {
            "email": "rider@example.com",
            "username": "rider_kyc",
            "password1": "Str0ng-Pass-Word!",
            "password2": "Str0ng-Pass-Word!",
            "ktp_number": "3174010101010001",
            "date_of_birth": "1994-02-10",
        }
        data.update(overrides)
        return data

    def test_bad_nik_rejected(self):
        form = KycSignupForm(data=self._base_data(ktp_number="12345"), files={"selfie": tiny_selfie()})
        self.assertFalse(form.is_valid())
        self.assertIn("ktp_number", form.errors)

    def test_missing_selfie_rejected(self):
        form = KycSignupForm(data=self._base_data(), files={})
        self.assertFalse(form.is_valid())
        self.assertIn("selfie", form.errors)

    def test_oversized_selfie_rejected(self):
        huge = SimpleUploadedFile(
            "big.jpg",
            b"x" * (5 * 1024 * 1024 + 10),
            content_type="image/jpeg",
        )
        form = KycSignupForm(data=self._base_data(), files={"selfie": huge})
        self.assertFalse(form.is_valid())
        self.assertIn("selfie", form.errors)

    def test_valid_signup_persists_private_profile(self):
        form = KycSignupForm(data=self._base_data(), files={"selfie": tiny_selfie()})
        self.assertTrue(form.is_valid(), form.errors)
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.test import RequestFactory

        request = RequestFactory().post("/accounts/signup/")
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        user = form.save(request)
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.ktp_number, "3174010101010001")
        self.assertEqual(profile.date_of_birth, date(1994, 2, 10))
        self.assertTrue(profile.selfie)
        self.assertTrue(profile.is_complete)
        # __str__ must not leak raw NIK
        self.assertNotIn("3174010101010001", str(profile))


class KycGateAndPrivacyTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.seller = User.objects.create_user("seller_kyc", password="x", email="s@ex.com")
        self.bidder = User.objects.create_user("bidder_kyc", password="x", email="b@ex.com")
        attach_complete_kyc(self.seller)
        self.bike = Motorcycle.objects.create(
            title="Honda BeAT KYC",
            description="Unit uji KYC gate.",
            start_price=10_000_000,
            seller=self.seller,
            make="Honda",
            model_name="BeAT",
            year=2021,
            city="Jakarta",
        )

    def test_bid_blocked_without_kyc(self):
        self.client.login(username="bidder_kyc", password="x")
        resp = self.client.post(
            reverse("place_bid", args=[self.bike.pk]),
            {"amount": "10500000"},
            follow=True,
        )
        self.assertEqual(Motorcycle.objects.get(pk=self.bike.pk).bids.count(), 0)
        self.assertContains(resp, "verifikasi")
        self.assertEqual(resp.request["PATH_INFO"], reverse("complete_kyc"))

    def test_create_listing_blocked_without_kyc(self):
        incomplete = User.objects.create_user("no_kyc", password="x", email="n@ex.com")
        self.client.login(username="no_kyc", password="x")
        resp = self.client.get(reverse("create_listing"), follow=True)
        self.assertContains(resp, "Lengkapi verifikasi")
        self.assertFalse(UserProfile.objects.filter(user=incomplete, ktp_number__regex=r"^\d{16}$").exists())

    def test_public_profile_hides_ktp_and_selfie(self):
        attach_complete_kyc(self.bidder, nik="3174090909090009")
        self.client.login(username="seller_kyc", password="x")
        resp = self.client.get(reverse("public_profile", args=["bidder_kyc"]))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "3174090909090009")
        self.assertNotContains(resp, "kyc/selfies")
        # Status block is own-profile only
        self.assertNotContains(resp, "Lengkapi KTP")

    def test_complete_kyc_form_saves(self):
        user = User.objects.create_user("finish_kyc", password="x", email="f@ex.com")
        form = CompleteKycForm(
            data={
                "ktp_number": "3201010203040005",
                "date_of_birth": "1990-01-01",
            },
            files={"selfie": tiny_selfie("me.png")},
        )
        self.assertTrue(form.is_valid(), form.errors)
        profile = form.save(user)
        self.assertTrue(profile.is_complete)


@override_settings(MEDIA_ROOT="/tmp/negomotor-kyc-media-test")
class SignupViewIntegrationTests(TestCase):
    def test_signup_page_shows_privacy_copy(self):
        resp = self.client.get(reverse("account_signup"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "verifikasi")
        self.assertContains(resp, "catatan perusahaan")
        self.assertContains(resp, "tidak ditampilkan")
