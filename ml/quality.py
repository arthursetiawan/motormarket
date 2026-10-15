"""Lightweight data-quality gates (warehouse-style checks without extra deps)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass
class QualityReport:
    rows: int
    passed: bool
    failures: list[str]
    checks: dict[str, bool]


REQUIRED_COLUMNS = [
    "make",
    "model_name",
    "year",
    "mileage_km",
    "engine_cc",
    "condition",
    "city",
    "asking_price",
]


def run_quality_checks(df: pd.DataFrame, require_sold: bool = True) -> QualityReport:
    failures: list[str] = []
    checks: dict[str, bool] = {}

    def check(name: str, ok: bool, message: str) -> None:
        checks[name] = bool(ok)
        if not ok:
            failures.append(message)

    check("not_empty", len(df) > 0, "dataset is empty")
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    check("required_columns", not missing, f"missing columns: {missing}")

    if not missing:
        check("year_range", df["year"].between(2008, 2026).all(), "year outside 2008-2026")
        check("mileage_nonneg", (df["mileage_km"] >= 0).all(), "negative mileage")
        check("engine_positive", (df["engine_cc"] > 0).all(), "non-positive engine_cc")
        check("asking_positive", (df["asking_price"] > 0).all(), "non-positive asking_price")
        null_rate = df[REQUIRED_COLUMNS].isna().mean().max()
        check("null_rate", null_rate < 0.02, f"null rate too high: {null_rate:.2%}")

    if require_sold and "sold_price" in df.columns:
        sold = df["sold_price"].dropna()
        check("sold_positive", (sold > 0).all() if len(sold) else False, "sold_price not positive")
        if "asking_price" in df.columns and len(sold):
            ratio = df.loc[df["sold_price"].notna(), "sold_price"] / df.loc[df["sold_price"].notna(), "asking_price"]
            check("sold_ask_ratio", ratio.between(0.4, 1.2).mean() > 0.95, "sold/ask ratios look broken")

    return QualityReport(rows=len(df), passed=not failures, failures=failures, checks=checks)


def report_to_dict(report: QualityReport) -> dict:
    return asdict(report)
