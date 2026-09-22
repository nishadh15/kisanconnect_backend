"""
Generates realistic synthetic farmers, listings, and buyer demands
for demo/testing purposes (no external data dependency required).
"""

import random
import uuid
from app.matching_engine import Listing, BuyerDemand

COMMODITIES = ["Tomato", "Onion", "Potato", "Brinjal", "Cabbage"]
GRADES = ["C", "B", "A", "Premium"]

DISTRICT_COORDS = {
    "Bengaluru Rural": (13.25, 77.55),
    "Kolar": (13.14, 78.13),
    "Mysuru": (12.30, 76.65),
    "Tumakuru": (13.34, 77.10),
}

FIRST_NAMES = ["Ravi", "Suresh", "Lakshmi", "Ganesh", "Meena", "Anand", "Kavya", "Deepak", "Shalini", "Manjunath"]


def _jitter(lat, lon, km_radius=15):
    delta = km_radius / 111.0
    return lat + random.uniform(-delta, delta), lon + random.uniform(-delta, delta)


def generate_listings(n=40, seed=None) -> list:
    if seed is not None:
        random.seed(seed)
    listings = []
    for _ in range(n):
        district = random.choice(list(DISTRICT_COORDS.keys()))
        base_lat, base_lon = DISTRICT_COORDS[district]
        lat, lon = _jitter(base_lat, base_lon)
        listings.append(Listing(
            id=str(uuid.uuid4())[:8],
            commodity=random.choice(COMMODITIES),
            grade=random.choice(GRADES),
            quantity_kg=round(random.uniform(50, 1000), 1),
            lat=lat,
            lon=lon,
        ))
    return listings


def generate_buyer_demands(n=25, seed=None) -> list:
    if seed is not None:
        random.seed(seed + 1 if seed is not None else None)
    demands = []
    for _ in range(n):
        district = random.choice(list(DISTRICT_COORDS.keys()))
        base_lat, base_lon = DISTRICT_COORDS[district]
        lat, lon = _jitter(base_lat, base_lon)
        demands.append(BuyerDemand(
            id=str(uuid.uuid4())[:8],
            commodity=random.choice(COMMODITIES),
            min_grade=random.choice(GRADES),
            quoted_price_per_kg=round(random.uniform(12, 45), 2),
            max_radius_km=random.choice([10, 20, 30, 50]),
            min_quantity_kg=round(random.uniform(50, 400), 1),
            lat=lat,
            lon=lon,
            reliability_score=round(random.uniform(0.6, 1.0), 2),
        ))
    return demands


def farmer_name() -> str:
    return random.choice(FIRST_NAMES)
