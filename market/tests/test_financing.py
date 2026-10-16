from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from market.models import Motorcycle
from market.services.financing import (
    eligible_ltv,
    parse_query,
    simulate,
)


class FinancingMathTests(SimpleTestCase):
    @override_settings(
        FINANCING_DEFAULT_FLAT_RATE="0.14",
        FINANCING_DEFAULT_EFFECTIVE_RATE="0.24",
        FINANCING_DEFAULT_DP_PCT="0.20",
        FINANCING_DEFAULT_TENOR_MONTHS=24,
        FINANCING_ADMIN_FEE_IDR="250000",
    )
    def test_flat_angsuran_and_total(self):
        # OTR 20jt, DP 20% → principal 16jt
        # Flat 14%/yr × 2yr → interest 4.48jt
        # Angsuran = (16jt + 4.48jt) / 24 = 853_333.333… → 853333
        est = simulate(
            Decimal("20000000"),
            dp_pct=Decimal("0.20"),
            tenor_months=24,
            rate_mode="flat",
            annual_rate=Decimal("0.14"),
            condition_grade="B",
        )
        self.assertEqual(est.dp_amount, Decimal("4000000"))
        self.assertEqual(est.principal, Decimal("16000000"))
        self.assertEqual(est.interest_total, Decimal("4480000"))
        self.assertEqual(est.angsuran, Decimal("853333"))
        # total = DP + angsuran*tenor + admin
        expected_total = (
            Decimal("4000000")
            + Decimal("853333") * 24
            + Decimal("250000")
        )
        self.assertEqual(est.total_bayar, expected_total)

    @override_settings(FINANCING_ADMIN_FEE_IDR="0")
    def test_effective_annuity_zero_rate(self):
        est = simulate(
            Decimal("12000000"),
            dp_pct=Decimal("0.25"),
            tenor_months=12,
            rate_mode="effective",
            annual_rate=Decimal("0"),
            admin_fee=Decimal("0"),
        )
        # Principal 9jt / 12
        self.assertEqual(est.principal, Decimal("9000000"))
        self.assertEqual(est.angsuran, Decimal("750000"))
        self.assertEqual(est.interest_total, Decimal("0"))

    @override_settings(FINANCING_ADMIN_FEE_IDR="0")
    def test_effective_positive_rate(self):
        est = simulate(
            Decimal("15000000"),
            dp_pct=Decimal("0.20"),
            tenor_months=12,
            rate_mode="effective",
            annual_rate=Decimal("0.24"),
            admin_fee=Decimal("0"),
        )
        # Principal 12jt; monthly rate 2%; payment > principal/12
        self.assertEqual(est.principal, Decimal("12000000"))
        self.assertGreater(est.angsuran, Decimal("1000000"))
        self.assertGreater(est.interest_total, Decimal("0"))
        self.assertEqual(
            est.total_bayar,
            est.dp_amount + est.angsuran * 12,
        )

    def test_eligible_ltv_grade_and_band(self):
        mid = eligible_ltv(Decimal("15000000"), condition_grade="B")
        high = eligible_ltv(Decimal("15000000"), condition_grade="A", condition="excellent")
        low = eligible_ltv(Decimal("15000000"), condition_grade="C", condition="poor")
        cheap = eligible_ltv(Decimal("5000000"), condition_grade="B")
        self.assertEqual(mid, Decimal("0.85"))
        self.assertGreater(high, mid)
        self.assertLess(low, mid)
        self.assertLess(cheap, mid)

    def test_plafon_caps_principal(self):
        # Force low LTV via grade C + poor so plafon < principal at low DP
        est = simulate(
            Decimal("20000000"),
            dp_pct=Decimal("0.10"),
            tenor_months=24,
            rate_mode="flat",
            annual_rate=Decimal("0.14"),
            condition_grade="C",
            condition="poor",
            admin_fee=Decimal("0"),
        )
        self.assertLessEqual(est.principal, est.plafon)
        self.assertFalse(est.eligible_ok)

    def test_parse_query_idr_dots_and_listing(self):
        parsed = parse_query(
            {
                "listing": "42",
                "otr": "15.000.000",
                "dp_pct": "25",
                "tenor": "36",
                "rate_mode": "flat",
                "rate": "0.14",
                "grade": "A",
            }
        )
        self.assertEqual(parsed["listing_id"], 42)
        self.assertEqual(parsed["otr"], Decimal("15000000"))
        self.assertEqual(parsed["dp_pct"], Decimal("0.25"))
        self.assertEqual(parsed["tenor_months"], 36)
        self.assertEqual(parsed["condition_grade"], "A")


class FinancingPageTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("fin_seller", password="x")
        self.bike = Motorcycle.objects.create(
            title="2020 Yamaha NMAX",
            description="NMAX bersih siap pakai",
            start_price=Decimal("18000000"),
            seller=self.seller,
            make="Yamaha",
            model_name="NMAX",
            year=2020,
            condition="good",
            condition_grade="B",
            city="Jakarta",
        )
        self.client = Client()

    def test_page_renders_blank_defaults(self):
        resp = self.client.get(reverse("financing"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Simulasi pembiayaan")
        self.assertContains(resp, "estimasi")
        self.assertContains(resp, "bukan persetujuan")

    def test_page_with_listing_query(self):
        resp = self.client.get(reverse("financing"), {"listing": self.bike.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "NMAX")
        self.assertContains(resp, "Angsuran / bulan")
        ctx = resp.context["estimate"]
        self.assertEqual(ctx.otr, Decimal("18000000"))

    def test_manual_otr_knobs(self):
        resp = self.client.get(
            reverse("financing"),
            {
                "otr": "12000000",
                "dp_pct": "0.30",
                "tenor": "12",
                "rate_mode": "flat",
                "rate": "0.12",
            },
        )
        self.assertEqual(resp.status_code, 200)
        est = resp.context["estimate"]
        self.assertEqual(est.otr, Decimal("12000000"))
        self.assertEqual(est.dp_pct, Decimal("0.30"))
        self.assertEqual(est.tenor_months, 12)
        # Principal 8.4jt × (1 + 0.12×1yr) / 12 = 9.408jt / 12 = 784000
        self.assertEqual(est.angsuran, Decimal("784000"))
