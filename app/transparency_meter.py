"""
Computes the real INR/kg savings a farmer captures via KisanConnect
versus a traditional mandi-chain sale, using a mandi benchmark price
(in production, sourced live from the Agmarknet/e-NAM ingestion cache)
as the counterfactual.
"""

TRADITIONAL_CHAIN_FARMER_SHARE = 0.42  # empirical avg: farmer captures ~42% of consumer price via mandi chain

# Illustrative static benchmark table (INR per kg, consumer-facing modal price).
# In production this is replaced by the live Redis-cached Agmarknet feed
# (see mandi_price_cache.py in the technical blueprint).
MANDI_BENCHMARK_PER_KG = {
    "Tomato": 32.0,
    "Onion": 28.0,
    "Potato": 24.0,
    "Brinjal": 26.0,
    "Cabbage": 20.0,
}


def compute_transparency_savings(commodity: str, net_farmer_price_per_kg: float) -> dict:
    modal_price_per_kg = MANDI_BENCHMARK_PER_KG.get(commodity)
    if modal_price_per_kg is None:
        return {"available": False, "reason": f"No benchmark data for {commodity}"}

    traditional_farmer_estimate = modal_price_per_kg * TRADITIONAL_CHAIN_FARMER_SHARE
    savings_per_kg = net_farmer_price_per_kg - traditional_farmer_estimate
    savings_pct = (savings_per_kg / traditional_farmer_estimate) * 100 if traditional_farmer_estimate else 0

    return {
        "available": True,
        "mandi_modal_price_per_kg": round(modal_price_per_kg, 2),
        "traditional_channel_farmer_estimate_per_kg": round(traditional_farmer_estimate, 2),
        "kisanconnect_net_price_per_kg": round(net_farmer_price_per_kg, 2),
        "savings_per_kg": round(savings_per_kg, 2),
        "savings_pct": round(savings_pct, 1),
    }
