"""Indonesian motorcycle catalog with approximate new MSRP in IDR.

Prices are directional market priors used to synthesize a realistic sold-listing
history. They are not live dealer quotes.
"""

from __future__ import annotations

from typing import TypedDict


class BikeSpec(TypedDict):
    make: str
    model_name: str
    engine_cc: int
    fuel_type: str
    transmission: str
    msrp_idr: int
    segment: str


CATALOG: list[BikeSpec] = [
    {"make": "Honda", "model_name": "BeAT", "engine_cc": 110, "fuel_type": "petrol", "transmission": "automatic", "msrp_idr": 18500000, "segment": "scooter"},
    {"make": "Honda", "model_name": "Vario 125", "engine_cc": 125, "fuel_type": "petrol", "transmission": "automatic", "msrp_idr": 22500000, "segment": "scooter"},
    {"make": "Honda", "model_name": "Vario 160", "engine_cc": 160, "fuel_type": "petrol", "transmission": "automatic", "msrp_idr": 27000000, "segment": "scooter"},
    {"make": "Honda", "model_name": "PCX 160", "engine_cc": 160, "fuel_type": "petrol", "transmission": "automatic", "msrp_idr": 32500000, "segment": "premium_scooter"},
    {"make": "Honda", "model_name": "ADV 160", "engine_cc": 160, "fuel_type": "petrol", "transmission": "automatic", "msrp_idr": 36500000, "segment": "adventure_scooter"},
    {"make": "Honda", "model_name": "CBR150R", "engine_cc": 150, "fuel_type": "petrol", "transmission": "manual", "msrp_idr": 38000000, "segment": "sport"},
    {"make": "Honda", "model_name": "CB150R", "engine_cc": 150, "fuel_type": "petrol", "transmission": "manual", "msrp_idr": 34000000, "segment": "naked"},
    {"make": "Yamaha", "model_name": "NMAX", "engine_cc": 155, "fuel_type": "petrol", "transmission": "automatic", "msrp_idr": 31500000, "segment": "premium_scooter"},
    {"make": "Yamaha", "model_name": "Aerox 155", "engine_cc": 155, "fuel_type": "petrol", "transmission": "automatic", "msrp_idr": 28500000, "segment": "sport_scooter"},
    {"make": "Yamaha", "model_name": "Fazzio", "engine_cc": 125, "fuel_type": "petrol", "transmission": "automatic", "msrp_idr": 22500000, "segment": "scooter"},
    {"make": "Yamaha", "model_name": "XMAX", "engine_cc": 250, "fuel_type": "petrol", "transmission": "automatic", "msrp_idr": 67000000, "segment": "maxiscooter"},
    {"make": "Yamaha", "model_name": "R15", "engine_cc": 155, "fuel_type": "petrol", "transmission": "manual", "msrp_idr": 40000000, "segment": "sport"},
    {"make": "Yamaha", "model_name": "MT-15", "engine_cc": 155, "fuel_type": "petrol", "transmission": "manual", "msrp_idr": 38000000, "segment": "naked"},
    {"make": "Kawasaki", "model_name": "Ninja 250", "engine_cc": 249, "fuel_type": "petrol", "transmission": "manual", "msrp_idr": 78000000, "segment": "sport"},
    {"make": "Kawasaki", "model_name": "Ninja ZX-25R", "engine_cc": 250, "fuel_type": "petrol", "transmission": "manual", "msrp_idr": 115000000, "segment": "supersport"},
    {"make": "Kawasaki", "model_name": "W175", "engine_cc": 177, "fuel_type": "petrol", "transmission": "manual", "msrp_idr": 35000000, "segment": "retro"},
    {"make": "Suzuki", "model_name": "Nex II", "engine_cc": 113, "fuel_type": "petrol", "transmission": "automatic", "msrp_idr": 16500000, "segment": "scooter"},
    {"make": "Suzuki", "model_name": "Address", "engine_cc": 113, "fuel_type": "petrol", "transmission": "automatic", "msrp_idr": 18500000, "segment": "scooter"},
    {"make": "Suzuki", "model_name": "GSX-R150", "engine_cc": 150, "fuel_type": "petrol", "transmission": "manual", "msrp_idr": 33000000, "segment": "sport"},
    {"make": "Vespa", "model_name": "Sprint 150", "engine_cc": 150, "fuel_type": "petrol", "transmission": "automatic", "msrp_idr": 48000000, "segment": "premium_scooter"},
    {"make": "Vespa", "model_name": "Primavera 150", "engine_cc": 150, "fuel_type": "petrol", "transmission": "automatic", "msrp_idr": 50000000, "segment": "premium_scooter"},
    {"make": "BMW", "model_name": "G 310 R", "engine_cc": 313, "fuel_type": "petrol", "transmission": "manual", "msrp_idr": 145000000, "segment": "naked"},
    {"make": "KTM", "model_name": "390 Duke", "engine_cc": 373, "fuel_type": "petrol", "transmission": "manual", "msrp_idr": 125000000, "segment": "naked"},
]

CITIES = [
    ("Jakarta", 1.08),
    ("Tangerang", 1.05),
    ("Bandung", 1.03),
    ("Surabaya", 1.04),
    ("Yogyakarta", 0.98),
    ("Semarang", 0.97),
    ("Medan", 0.96),
    ("Makassar", 0.95),
    ("Denpasar", 1.06),
    ("Bekasi", 1.02),
]

CONDITIONS = [
    ("excellent", 1.12),
    ("good", 1.00),
    ("fair", 0.86),
    ("poor", 0.70),
]

CONDITION_WEIGHTS = [0.18, 0.52, 0.24, 0.06]
CITY_WEIGHTS = [0.22, 0.10, 0.12, 0.12, 0.08, 0.07, 0.07, 0.06, 0.08, 0.08]
