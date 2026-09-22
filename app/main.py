"""
KisanConnect MVP backend.

Run locally with:
    uvicorn app.main:app --reload --port 8000

Then visit http://localhost:8000/docs for interactive API docs, or
GET /demo/seed to populate an in-memory demo scenario, then
GET /listings/{listing_id}/matches to see ranked, transparency-scored matches.
"""

import uuid
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.matching_engine import Listing, BuyerDemand, rank_matches_for_listing, batch_optimal_assignment
from app.synthetic_data import generate_listings, generate_buyer_demands, farmer_name
from app.transparency_meter import compute_transparency_savings
from app.fairness_scoring import score_quote

app = FastAPI(title="KisanConnect API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory stores (MVP only — production uses PostgreSQL, see technical blueprint Chapter 5)
LISTINGS_DB = {}
DEMANDS_DB = {}
FARMER_NAMES = {}


class ListingCreateRequest(BaseModel):
    commodity: str
    grade: str
    quantity_kg: float
    latitude: float
    longitude: float
    farmer_name: str = "Farmer"


class DemandCreateRequest(BaseModel):
    commodity: str
    min_grade: str
    quoted_price_per_kg: float
    max_radius_km: float
    min_quantity_kg: float
    latitude: float
    longitude: float
    reliability_score: float = 0.8


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/demo/seed")
def seed_demo(n_listings: int = 40, n_demands: int = 25, seed: int = 42):
    """Populate the in-memory store with a realistic synthetic scenario."""
    LISTINGS_DB.clear()
    DEMANDS_DB.clear()
    FARMER_NAMES.clear()

    for listing in generate_listings(n_listings, seed=seed):
        LISTINGS_DB[listing.id] = listing
        FARMER_NAMES[listing.id] = farmer_name()

    for demand in generate_buyer_demands(n_demands, seed=seed):
        DEMANDS_DB[demand.id] = demand

    return {"listings_created": len(LISTINGS_DB), "demands_created": len(DEMANDS_DB)}


@app.get("/listings")
def list_listings():
    return [
        {**vars(listing), "farmer_name": FARMER_NAMES.get(listing.id, "Farmer")}
        for listing in LISTINGS_DB.values()
    ]


@app.get("/demands")
def list_demands():
    return [vars(d) for d in DEMANDS_DB.values()]


@app.post("/listings")
def create_listing(payload: ListingCreateRequest):
    listing_id = str(uuid.uuid4())[:8]
    listing = Listing(
        id=listing_id,
        commodity=payload.commodity,
        grade=payload.grade,
        quantity_kg=payload.quantity_kg,
        lat=payload.latitude,
        lon=payload.longitude,
    )
    LISTINGS_DB[listing_id] = listing
    FARMER_NAMES[listing_id] = payload.farmer_name
    return {"listing_id": listing_id, "status": "ACTIVE"}


@app.post("/demands")
def create_demand(payload: DemandCreateRequest):
    demand_id = str(uuid.uuid4())[:8]
    DEMANDS_DB[demand_id] = BuyerDemand(
        id=demand_id,
        commodity=payload.commodity,
        min_grade=payload.min_grade,
        quoted_price_per_kg=payload.quoted_price_per_kg,
        max_radius_km=payload.max_radius_km,
        min_quantity_kg=payload.min_quantity_kg,
        lat=payload.latitude,
        lon=payload.longitude,
        reliability_score=payload.reliability_score,
    )
    return {"demand_id": demand_id, "status": "OPEN"}


@app.get("/listings/{listing_id}/matches")
def get_matches(listing_id: str, top_n: int = 5):
    listing = LISTINGS_DB.get(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    buyers = list(DEMANDS_DB.values())
    matches = rank_matches_for_listing(listing, buyers, top_n=top_n)

    for match in matches:
        match["transparency"] = compute_transparency_savings(
            commodity=listing.commodity,
            net_farmer_price_per_kg=match["net_price_per_kg"],
        )
        match["fairness"] = score_quote(listing.commodity, match["quoted_price_per_kg"])

    return {
        "listing_id": listing_id,
        "commodity": listing.commodity,
        "grade": listing.grade,
        "quantity_kg": listing.quantity_kg,
        "matches": matches,
    }


@app.get("/batch-assignment")
def get_batch_assignment():
    """Runs the Hungarian-algorithm optimal assignment across ALL current listings/demands."""
    listings = list(LISTINGS_DB.values())
    buyers = list(DEMANDS_DB.values())
    assignments = batch_optimal_assignment(listings, buyers)
    total_utility = sum(a["utility"] for a in assignments)
    return {
        "total_assignments": len(assignments),
        "total_system_utility": round(total_utility, 2),
        "assignments": assignments,
    }
