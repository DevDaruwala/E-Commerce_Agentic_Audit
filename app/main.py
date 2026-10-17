from fastapi import FastAPI, HTTPException
from app.recall_check import check_blacklist
from app.schemas import (
    AuditResult,
    BatchAuditResponse,
    ProductListing,
    RejectedListing,
)
from app.validation import validate_listing
from app.hygiene_check import check_hygiene
import uuid
import json
from typing import Any
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


@app.post("/listings/new_productlisting", response_model=ProductListing)
async def new_product_listing(listing: ProductListing) -> ProductListing:
    stored_listings.append(listing)
    return listing


@app.get("/listings/productlisting", response_model=ProductListing)
async def get_product_listing() -> ProductListing:
    if not stored_listings:
        raise HTTPException(status_code=404, detail="No listings have been submitted yet")
    return stored_listings[-1]



def run_gates(listing: ProductListing) -> AuditResult:
    """The gates for ONE already-valid listing, in severity order.
    Recall first (worst finding wins), then hygiene. A gate returns None
    when the listing passes, or a non_compliant AuditResult that ends the
    run. If both pass, we return the placeholder "compliant" verdict
    until the AI agent exists."""
    blacklist_result = check_blacklist(listing.gtin)
    if blacklist_result is not None:
        return blacklist_result

    hygiene_result = check_hygiene(listing)
    if hygiene_result is not None:
        return hygiene_result

    return AuditResult(
        audit_id=str(uuid.uuid4()),
        listing_gtin=listing.gtin,
        verdict="compliant",
        risk_type="none",
        risk_score=0.0,
        violations=[],
        pipeline_stage="hygiene_check",
        reasoning="Passed recall and hygiene checks — no AI agent wired yet.",
    )


def _peek(raw: Any, key: str) -> str | None:
    """Reads a field from an item that may be broken. Returns None if the
    item isn't a dict or the field is missing, so naming a rejected
    listing can never crash."""
    if isinstance(raw, dict) and raw.get(key) is not None:
        return str(raw[key])
    return None


@app.post("/listings/audit", response_model=BatchAuditResponse)
async def audit_batch(raw_listings: list[Any]) -> BatchAuditResponse:
    """The bouncer. Takes a list of raw listings (a bulk upload).

    The parameter is list[Any], NOT list[ProductListing]: if FastAPI
    validated the items itself, one bad listing would turn the whole
    upload into a 422. Instead each item is checked here, one by one.
    Bad shape -> rejected with the reasons. Good shape -> run_gates().
    """
    rejected: list[RejectedListing] = []
    results: list[AuditResult] = []

    for index, raw in enumerate(raw_listings):
        if not isinstance(raw, dict):
            rejected.append(RejectedListing(
                index=index,
                errors=["listing must be a JSON object"],
                original=raw,
            ))
            continue

        is_valid, errors = validate_listing(raw)  # app/validation.py
        if not is_valid:
            rejected.append(RejectedListing(
                index=index,
                title=_peek(raw, "title"),
                gtin=_peek(raw, "gtin"),
                distributor_id=_peek(raw, "distributor_id"),
                errors=errors,
                original=raw,
            ))
            continue

        results.append(run_gates(ProductListing(**raw)))

    return BatchAuditResponse(
        total=len(raw_listings),
        rejected_count=len(rejected),
        audited_count=len(results),
        rejected=rejected,
        results=results,
    )
