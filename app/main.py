from fastapi import FastAPI
from app.schemas import ProductListing, AuditResult
from app.validation import validate_listing
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI()

# In-memory storage — a real database will replace this later.
# This list lives OUTSIDE any function, so it persists across requests.
stored_listings: list[ProductListing] = []


@app.on_event("startup")
async def load_raw_listings():
    with open(BASE_DIR / "raw_listings.json") as f:
        raw_data = json.load(f)
    for entry in raw_data:
        try:
            listing = ProductListing(**entry)
            stored_listings.append(listing)
        except Exception as e:
            print(f"Skipped one bad listing: {e}")
    print(f"Loaded {len(stored_listings)} listings from raw_listings.json")


@app.post("/listings/validate")
async def validate_listing_endpoint(raw_listing: dict):
    is_valid, errors = validate_listing(raw_listing)
    return {"is_valid": is_valid, "errors": errors}


@app.post("/listings/new_productlisting", response_model=ProductListing)
async def new_product_listing(listing: ProductListing) -> ProductListing:
    stored_listings.append(listing)
    return listing


@app.get("/listings/productlisting", response_model=ProductListing)
async def get_product_listing() -> ProductListing:
    return stored_listings[-1]  # the most recently added listing



@app.post("/listings/audit", response_model=AuditResult)
async def audit_listing(listing: ProductListing) -> AuditResult:
    return AuditResult(
        audit_id="temp-0001",
        listing_gtin=listing.gtin,
        verdict="compliant",
        risk_type="none",
        risk_score=0.0,
        violations=[],
        pipeline_stage="hygiene_check",
        reasoning="Placeholder — no real audit logic implemented yet."
    )