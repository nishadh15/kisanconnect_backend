"""
KisanConnect MVP backend.

Run locally with:
    uvicorn app.main:app --reload --port 8000

Then visit http://localhost:8000/docs for interactive API docs, or
GET /demo/seed to populate an in-memory demo scenario, then
GET /listings/{listing_id}/matches to see ranked, transparency-scored matches.
"""

import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.matching_engine import Listing, BuyerDemand, rank_matches_for_listing, batch_optimal_assignment, compute_utility
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
FARMER_PHONES = {}
LISTING_STATUS = {}   # listing_id -> "ACTIVE" | "MATCHED"
TRADES_DB = {}        # trade_id -> trade record, newest last


class ListingCreateRequest(BaseModel):
    commodity: str
    grade: str
    quantity_kg: float
    latitude: float
    longitude: float
    farmer_name: str = "Farmer"
    asking_price_per_kg: float | None = None
    phone_number: str | None = None


class DemandCreateRequest(BaseModel):
    commodity: str
    min_grade: str
    quoted_price_per_kg: float
    max_radius_km: float
    min_quantity_kg: float
    latitude: float
    longitude: float
    reliability_score: float = 0.8
    phone_number: str | None = None
    buyer_name: str | None = None


class TradeConfirmRequest(BaseModel):
    listing_id: str
    buyer_id: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/demo/seed")
def seed_demo(n_listings: int = 40, n_demands: int = 25, seed: int = 42):
    """Populate the in-memory store with a realistic synthetic scenario."""
    LISTINGS_DB.clear()
    DEMANDS_DB.clear()
    FARMER_NAMES.clear()
    FARMER_PHONES.clear()
    LISTING_STATUS.clear()

    for listing in generate_listings(n_listings, seed=seed):
        LISTINGS_DB[listing.id] = listing
        FARMER_NAMES[listing.id] = farmer_name()
        FARMER_PHONES[listing.id] = listing.phone_number
        LISTING_STATUS[listing.id] = "ACTIVE"

    for demand in generate_buyer_demands(n_demands, seed=seed):
        DEMANDS_DB[demand.id] = demand

    return {"listings_created": len(LISTINGS_DB), "demands_created": len(DEMANDS_DB)}


@app.get("/listings")
def list_listings():
    return [
        {**vars(listing), "farmer_name": FARMER_NAMES.get(listing.id, "Farmer"),
         "status": LISTING_STATUS.get(listing.id, "ACTIVE")}
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
        asking_price_per_kg=payload.asking_price_per_kg,
        phone_number=payload.phone_number,
    )
    LISTINGS_DB[listing_id] = listing
    FARMER_NAMES[listing_id] = payload.farmer_name
    FARMER_PHONES[listing_id] = payload.phone_number
    LISTING_STATUS[listing_id] = "ACTIVE"
    return {"listing_id": listing_id, "status": "ACTIVE"}


@app.post("/listings/bulk")
def create_listings_bulk(payloads: List[ListingCreateRequest]):
    """FPO bulk mode: create many listings in one call, return their ids in order."""
    created = []
    for payload in payloads:
        listing_id = str(uuid.uuid4())[:8]
        LISTINGS_DB[listing_id] = Listing(
            id=listing_id,
            commodity=payload.commodity,
            grade=payload.grade,
            quantity_kg=payload.quantity_kg,
            lat=payload.latitude,
            lon=payload.longitude,
            asking_price_per_kg=payload.asking_price_per_kg,
            phone_number=payload.phone_number,
        )
        FARMER_NAMES[listing_id] = payload.farmer_name
        FARMER_PHONES[listing_id] = payload.phone_number
        LISTING_STATUS[listing_id] = "ACTIVE"
        created.append({"listing_id": listing_id, "commodity": payload.commodity})
    return {"created": created}


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
        phone_number=payload.phone_number,
        buyer_name=payload.buyer_name,
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


@app.post("/trades/confirm")
def confirm_trade(payload: TradeConfirmRequest):
    """
    The real contact-exchange step: once a farmer picks a match, this confirms
    the trade and returns each side's contact details so they can actually reach
    each other — this is the step that was missing before (matching alone never
    connected two real parties).
    """
    listing = LISTINGS_DB.get(payload.listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    buyer = DEMANDS_DB.get(payload.buyer_id)
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer demand not found")

    result = compute_utility(listing, buyer)
    if result is None:
        # Buyer no longer feasible for this listing (radius/grade/quantity changed since match was shown)
        raise HTTPException(status_code=409, detail="This buyer is no longer a feasible match for this listing")

    trade_id = str(uuid.uuid4())[:8]
    trade = {
        "trade_id": trade_id,
        "listing_id": listing.id,
        "buyer_id": buyer.id,
        "commodity": listing.commodity,
        "grade": listing.grade,
        "quantity_kg": listing.quantity_kg,
        "net_price_per_kg": result["net_price_per_kg"],
        "logistics_cost_per_kg": result["logistics_cost_per_kg"],
        "distance_km": result["distance_km"],
        "farmer_name": FARMER_NAMES.get(listing.id, "Farmer"),
        "farmer_phone": FARMER_PHONES.get(listing.id) or listing.phone_number or "Not provided",
        "buyer_name": buyer.buyer_name or "Buyer",
        "buyer_phone": buyer.phone_number or "Not provided",
        "status": "CONFIRMED",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    TRADES_DB[trade_id] = trade
    LISTING_STATUS[listing.id] = "MATCHED"
    return trade


@app.get("/trades")
def list_trades():
    return list(reversed(list(TRADES_DB.values())))


@app.get("/trades/{trade_id}")
def get_trade(trade_id: str):
    trade = TRADES_DB.get(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade
