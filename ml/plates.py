"""Indonesian plate wilayah codes ↔ city heuristics for trust checks."""

from __future__ import annotations

# City name (lowercase) → accepted plate prefixes (single or two-letter).
CITY_PLATE_PREFIXES: dict[str, frozenset[str]] = {
    "jakarta": frozenset({"B"}),
    "bekasi": frozenset({"B"}),
    "tangerang": frozenset({"B", "A"}),
    "bandung": frozenset({"D"}),
    "surabaya": frozenset({"L", "W", "S"}),
    "yogyakarta": frozenset({"AB"}),
    "semarang": frozenset({"H"}),
    "medan": frozenset({"BK"}),
    "makassar": frozenset({"DD"}),
    "denpasar": frozenset({"DK"}),
}


def plate_region_code(plate_number: str | None) -> str:
    """Extract leading wilayah code from a plate string (e.g. 'B 1234 ABC' → 'B')."""
    raw = (plate_number or "").strip().upper()
    if not raw:
        return ""
    parts = raw.replace("-", " ").split()
    if not parts:
        return ""
    code = parts[0]
    two_letter = {
        "DK",
        "AB",
        "AA",
        "AD",
        "AE",
        "AG",
        "BK",
        "BH",
        "BL",
        "BM",
        "BN",
        "BG",
        "BA",
        "BB",
        "BD",
        "BE",
        "DD",
        "DE",
        "DG",
        "DH",
        "DN",
        "DR",
        "DT",
        "DW",
        "EA",
        "EB",
        "ED",
        "KB",
        "KH",
        "KT",
        "KU",
        "PB",
        "PK",
    }
    if len(code) >= 2 and code[:2].isalpha() and code[:2] in two_letter:
        return code[:2]
    if code[0].isalpha():
        return code[0]
    return ""


def plate_matches_city(plate_number: str | None, city: str | None) -> bool | None:
    """Return True/False if we can judge, or None if unknown (no plate or unmapped city)."""
    region = plate_region_code(plate_number)
    if not region or not city:
        return None
    expected = CITY_PLATE_PREFIXES.get(city.strip().lower())
    if not expected:
        return None
    return region in expected
