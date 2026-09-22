"""
Price Fairness Scoring.

MVP version: scores a buyer's quoted price against the static mandi
benchmark. In the state-scale build this is replaced by the trained
GradientBoostingRegressor described in the technical blueprint
(price_fairness_model.py), which predicts an expected fair price from
historical Agmarknet spreads conditioned on commodity/grade/zone/season.
"""

from app.transparency_meter import MANDI_BENCHMARK_PER_KG

LOW_BALL_THRESHOLD = 0.75


def score_quote(commodity: str, quoted_price_per_kg: float) -> dict:
    expected_price = MANDI_BENCHMARK_PER_KG.get(commodity)
    if expected_price is None:
        return {"available": False, "reason": f"No benchmark for {commodity}"}

    fairness_score = round(min(quoted_price_per_kg / expected_price, 1.5), 3)
    return {
        "available": True,
        "expected_fair_price_per_kg": expected_price,
        "quoted_price_per_kg": quoted_price_per_kg,
        "fairness_score": fairness_score,
        "flag_low_ball": fairness_score < LOW_BALL_THRESHOLD,
    }
