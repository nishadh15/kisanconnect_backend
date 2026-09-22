"""
Constraint-Satisfaction Matching Engine for KisanConnect.

Supports:
  1. Single-listing greedy top-N ranking (real-time, used for individual farmer listings)
  2. Batch many-to-many optimal assignment via the Hungarian algorithm (used for FPO bulk runs)
"""

from dataclasses import dataclass
from math import radians, sin, cos, sqrt, atan2
from typing import List, Optional
import numpy as np
from scipy.optimize import linear_sum_assignment

GRADE_RANK = {"C": 0, "B": 1, "A": 2, "Premium": 3}
BASE_LOGISTICS_RATE_PER_KG = 1.5   # INR flat handling cost per kg
PER_KM_PER_KG_RATE = 0.08          # INR per km per kg


@dataclass
class Listing:
    id: str
    commodity: str
    grade: str
    quantity_kg: float
    lat: float
    lon: float
    asking_price_per_kg: Optional[float] = None


@dataclass
class BuyerDemand:
    id: str
    commodity: str
    min_grade: str
    quoted_price_per_kg: float
    max_radius_km: float
    min_quantity_kg: float
    lat: float
    lon: float
    reliability_score: float  # 0.0 - 1.0, derived from trade history


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def logistics_cost_per_kg(distance_km: float, quantity_kg: float) -> float:
    # Flat handling cost + variable per-km cost. quantity_kg reserved for
    # future bulk-discount curves (larger lots -> lower per-kg logistics cost).
    return BASE_LOGISTICS_RATE_PER_KG + (PER_KM_PER_KG_RATE * distance_km)


def is_feasible(listing: Listing, buyer: BuyerDemand, distance_km: float) -> bool:
    same_commodity = listing.commodity.lower() == buyer.commodity.lower()
    within_radius = distance_km <= buyer.max_radius_km
    enough_quantity = listing.quantity_kg >= buyer.min_quantity_kg
    grade_ok = GRADE_RANK.get(listing.grade, -1) >= GRADE_RANK.get(buyer.min_grade, 99)
    return same_commodity and within_radius and enough_quantity and grade_ok


def compute_utility(listing: Listing, buyer: BuyerDemand) -> Optional[dict]:
    distance = haversine_km(listing.lat, listing.lon, buyer.lat, buyer.lon)
    if not is_feasible(listing, buyer, distance):
        return None
    logi_cost = logistics_cost_per_kg(distance, listing.quantity_kg)
    net_price = buyer.quoted_price_per_kg - logi_cost
    utility = net_price * (0.85 + 0.15 * buyer.reliability_score)
    return {
        "buyer_id": buyer.id,
        "distance_km": round(distance, 2),
        "logistics_cost_per_kg": round(logi_cost, 2),
        "quoted_price_per_kg": buyer.quoted_price_per_kg,
        "net_price_per_kg": round(net_price, 2),
        "utility": round(utility, 3),
    }


def rank_matches_for_listing(listing: Listing, buyers: List[BuyerDemand], top_n: int = 5) -> List[dict]:
    """Real-time single-listing matching -> returns top-N ranked candidate buyers."""
    candidates = []
    for buyer in buyers:
        result = compute_utility(listing, buyer)
        if result:
            candidates.append(result)
    candidates.sort(key=lambda c: c["utility"], reverse=True)
    return candidates[:top_n]


def batch_optimal_assignment(listings: List[Listing], buyers: List[BuyerDemand]) -> List[dict]:
    """
    Many-to-many optimal assignment across a batch of listings and buyer demands
    using the Hungarian algorithm to maximize total farmer utility system-wide.
    """
    n, m = len(listings), len(buyers)
    if n == 0 or m == 0:
        return []

    cost_matrix = np.full((n, m), fill_value=1e6)
    utility_lookup = {}
    for i, listing in enumerate(listings):
        for j, buyer in enumerate(buyers):
            result = compute_utility(listing, buyer)
            if result:
                cost_matrix[i, j] = -result["utility"]  # negate for minimization
                utility_lookup[(i, j)] = result

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    assignments = []
    for i, j in zip(row_ind, col_ind):
        if (i, j) in utility_lookup:
            assignments.append({
                "listing_id": listings[i].id,
                **utility_lookup[(i, j)],
            })
    return assignments
