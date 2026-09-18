"""
hygiene_check.py — checks a listing's legal-hygiene fields are actually
filled in, not just present in the right shape. validation.py checks the
data is well-formed (right types, non-empty strings); this checks it's
GPSR-complete (Responsible Person, safety warning, CE marking) before
spending a classifier or LLM call on it.

Phase 1, build task 3.
"""

import uuid

from app.schemas import AuditResult, ProductListing


def check_hygiene(listing: ProductListing) -> AuditResult | None:
    """
    Returns None if the listing passes (forward to the classifier),
    or a non_compliant AuditResult if it fails.
    """
    violations = []
    if not listing.brand_profile.responsible_person_name:
        violations.append("Missing responsible person name")
    if not listing.brand_profile.responsible_person_address:
        violations.append("Missing responsible person address")
    if not listing.brand_profile.responsible_person_email:
        violations.append("Missing responsible person email")
    if not listing.safety_warning_text:
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
