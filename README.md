# KisanConnect — MVP Backend

AI-powered direct farm-to-buyer matching engine for SIH problem statement SIH26033.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then:
1. `POST /demo/seed` — populates a realistic synthetic scenario (40 farmer listings, 25 buyer demands across 4 Karnataka districts).
2. `GET /listings` — see all seeded listings.
3. `GET /listings/{listing_id}/matches` — get ranked, transparency-scored, fairness-checked buyer matches for a single listing.
4. `GET /batch-assignment` — run the Hungarian-algorithm optimal many-to-many assignment across all current listings and demands.

Interactive API docs: http://localhost:8000/docs

## Project layout

```
app/
  matching_engine.py     Constraint-satisfaction + Hungarian-algorithm matching
  transparency_meter.py  Middleman Margin Transparency Meter calculation
  fairness_scoring.py    Price fairness heuristic (MVP) vs. mandi benchmark
  synthetic_data.py      Synthetic farmer/listing/demand generator for demos
  main.py                FastAPI app tying it all together
```

## Notes

This is the MVP/demo-stage implementation described in the KisanConnect
technical blueprint. Production upgrades documented separately include:
PostgreSQL persistence, Redis-cached live Agmarknet price feed, a trained
GradientBoostingRegressor fairness model, and the Twilio/Speech-to-Text
voice listing pipeline.
