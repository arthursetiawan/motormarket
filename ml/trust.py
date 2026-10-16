"""Listing trust / anomaly signals for marketplace quality.

Rule-based and model-backed checks (not a fraud classifier). Designed to be
transparent to buyers and useful as an ops triage score.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ml.plates import plate_matches_city, plate_region_code


ANCHOR_YEAR = 2026
EXPECTED_KM_PER_YEAR = 7800
HIGH_KM_PER_YEAR = 16000
LOW_KM_PER_YEAR = 1200


@dataclass
class TrustFlag:
    code: str
    severity: str  # info | watch | alert
    message: str


@dataclass
class TrustReport:
    score: int
    label: str  # high_trust | review | caution
    flags: list[TrustFlag] = field(default_factory=list)
    completeness: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


def _age_years(year: int | None) -> float | None:
    if year is None:
        return None
    return max(float(ANCHOR_YEAR - int(year)), 0.25)


def assess_listing(
    *,
    make: str | None,
    model_name: str | None,
    year: int | None,
    mileage_km: int | None,
    condition: str | None,
    city: str | None,
    owners_count: int | None,
    asking_price: float | None,
    predicted_price: float | None = None,
    deal_score: float | None = None,
    engine_cc: int | None = None,
    has_image: bool = False,
    description: str | None = None,
    stnk_status: str | None = None,
    bpkb_status: str | None = None,
    pajak_mati: bool | None = None,
    plate_number: str | None = None,
    tax_valid_through: int | None = None,
) -> TrustReport:
    """Return a 0–100 trust score and human-readable flags."""
    flags: list[TrustFlag] = []
    score = 100.0

    required = {
        "make": make,
        "model": model_name,
        "year": year,
        "mileage": mileage_km,
        "city": city,
        "condition": condition,
        "ask": asking_price,
    }
    present = sum(1 for v in required.values() if v not in (None, "", 0))
    completeness = present / len(required)
    if completeness < 1:
        missing = [k for k, v in required.items() if v in (None, "", 0)]
        flags.append(
            TrustFlag(
                "incomplete_fields",
                "watch",
                f"Field belum lengkap: {', '.join(missing)}.",
            )
        )
        score -= 12 * (1 - completeness)

    if not has_image:
        flags.append(TrustFlag("no_photo", "watch", "Belum ada foto listing."))
        score -= 8

    if description is not None and len(description.strip()) < 40:
        flags.append(TrustFlag("thin_description", "info", "Deskripsi terlalu singkat."))
        score -= 4

    age = _age_years(year)
    if year is not None and (year < 2008 or year > ANCHOR_YEAR):
        flags.append(TrustFlag("year_out_of_range", "alert", f"Tahun {year} di luar kisaran buku."))
        score -= 25

    if age is not None and mileage_km is not None and mileage_km >= 0:
        km_per_year = mileage_km / age
        if km_per_year >= HIGH_KM_PER_YEAR:
            flags.append(
                TrustFlag(
                    "high_mileage_rate",
                    "watch",
                    f"Sekitar {int(km_per_year):,} km/tahun — tinggi untuk matic Indonesia tipikal.",
                )
            )
            score -= 10
        elif age >= 1.5 and km_per_year <= LOW_KM_PER_YEAR:
            flags.append(
                TrustFlag(
                    "low_mileage_rate",
                    "watch",
                    f"Sekitar {int(km_per_year):,} km/tahun — sangat rendah; verifikasi odometer (waspada odo tipu).",
                )
            )
            score -= 12

    if owners_count is not None and owners_count >= 4:
        flags.append(TrustFlag("many_owners", "watch", f"{owners_count} pemilik tercatat."))
        score -= 8

    if asking_price is not None and asking_price <= 0:
        flags.append(TrustFlag("invalid_ask", "alert", "Harga awal tidak positif."))
        score -= 30

    if deal_score is not None:
        if deal_score >= 22:
            flags.append(
                TrustFlag(
                    "extreme_deal",
                    "alert",
                    f"Harga ~{deal_score:.0f}% di bawah estimasi wajar — cek fisik & surat sebelum tawar.",
                )
            )
            score -= 18
        elif deal_score <= -22:
            flags.append(
                TrustFlag(
                    "extreme_premium",
                    "watch",
                    f"Harga ~{abs(deal_score):.0f}% di atas estimasi wajar.",
                )
            )
            score -= 8

    if (
        predicted_price
        and asking_price
        and condition == "poor"
        and asking_price >= predicted_price * 0.95
    ):
        flags.append(
            TrustFlag(
                "condition_price_mismatch",
                "watch",
                "Kondisi kurang tapi harga dekat estimasi untuk unit baik.",
            )
        )
        score -= 10

    # --- Surat / documents (Indonesia) ---
    stnk = (stnk_status or "unknown").lower()
    bpkb = (bpkb_status or "unknown").lower()

    if stnk == "hilang":
        flags.append(TrustFlag("stnk_missing", "alert", "STNK hilang — risiko tinggi untuk jual-beli."))
        score -= 15
    elif stnk == "atas_nama_lain":
        flags.append(
            TrustFlag(
                "stnk_other_name",
                "watch",
                "STNK atas nama lain — pastikan kwitansi & proses balik nama.",
            )
        )
        score -= 8
    elif stnk == "unknown":
        flags.append(TrustFlag("stnk_unknown", "info", "Status STNK belum diisi penjual."))
        score -= 3

    if bpkb == "hilang":
        flags.append(TrustFlag("bpkb_missing", "alert", "BPKB hilang — waspada unit bermasalah / bodong."))
        score -= 20
    elif bpkb == "di_leasing":
        flags.append(
            TrustFlag(
                "bpkb_at_leasing",
                "watch",
                "BPKB masih di leasing — pelunasan / roya diperlukan sebelum serah terima penuh.",
            )
        )
        score -= 6
    elif bpkb == "unknown":
        flags.append(TrustFlag("bpkb_unknown", "info", "Status BPKB belum diisi penjual."))
        score -= 3

    if pajak_mati is True:
        flags.append(
            TrustFlag(
                "pajak_mati",
                "alert",
                "Pajak/STNK mati — tidak cocok ojol sampai diperpanjang.",
            )
        )
        score -= 12
    elif tax_valid_through is not None and tax_valid_through < ANCHOR_YEAR:
        flags.append(
            TrustFlag(
                "pajak_mati",
                "alert",
                f"Pajak berlaku sampai {tax_valid_through} — sudah lewat tahun buku.",
            )
        )
        score -= 12

    match = plate_matches_city(plate_number, city)
    if match is False:
        region = plate_region_code(plate_number)
        flags.append(
            TrustFlag(
                "plate_city_mismatch",
                "watch",
                f"Plat {region or '?'} tidak cocok dengan kota listing ({city}).",
            )
        )
        score -= 8

    if engine_cc is not None and engine_cc > 0 and asking_price and predicted_price:
        # Soft check already covered by deal_score; keep score floor clean.
        pass

    score_i = int(max(0, min(100, round(score))))
    if score_i >= 80 and not any(f.severity == "alert" for f in flags):
        label = "high_trust"
    elif score_i >= 55:
        label = "review"
    else:
        label = "caution"

    return TrustReport(score=score_i, label=label, flags=flags, completeness=round(completeness, 2))
