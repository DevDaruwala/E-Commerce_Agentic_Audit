"""
hygiene_check.py — checks a listing's legal-hygiene fields are actually
filled in, not just present in the right shape. validation.py checks the
data is well-formed (right types, non-empty strings); this checks it's
GPSR-complete (Responsible Person, safety warning, CE marking) before
spending an agent/LLM call on it.

Phase 1, build task 3.
"""

import uuid

from app.schemas import AuditResult, ProductListing


def _is_missing(value: str | None) -> bool:
    """A field counts as missing if it's None, empty, or whitespace-only.
    `not value` alone catches None/"" but NOT "   " — a whitespace-only
    string is truthy in Python, so it would silently pass the old check.
    """
    return not value or not value.strip()


def check_hygiene(listing: ProductListing) -> AuditResult | None:
    """
    Returns None if the listing passes (forward to the agent team),
    or a non_compliant AuditResult if it fails.
    """
    violations = []
    if _is_missing(listing.brand_profile.responsible_person_name):
        violations.append("Missing responsible person name")
    if _is_missing(listing.brand_profile.responsible_person_address):
        violations.append("Missing responsible person address")
    if _is_missing(listing.brand_profile.responsible_person_email):
        violations.append("Missing responsible person email")
    if _is_missing(listing.safety_warning_text):
        violations.append("Missing safety warning text")
    if listing.ce_marking_present is False:
        violations.append("CE marking not present")

    if not violations:
        return None

    return AuditResult(
        audit_id=str(uuid.uuid4()),
        listing_gtin=listing.gtin,
        verdict="non_compliant",
        risk_type="legal_hygiene",
        risk_score=1.0,
        violations=violations,
        pipeline_stage="hygiene_check",
        reasoning="; ".join(violations),
    )
