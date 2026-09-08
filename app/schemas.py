"""
schemas.py — the data shapes for this project.

This is Phase 1, build task 1: decide exactly what a "listing" and a
"verdict" look like BEFORE writing any logic. Everything else in the
project depends on these shapes being right.

Fill in ProductListing with the real fields a listing needs (title,
category, price, seller_id, description, image_url, has_battery, etc.)
and AuditResult with what a finished audit looks like (status,
risk_score, violations, cited_rule, etc.). We'll do this together.
"""

from pydantic import BaseModel


class ProductListing(BaseModel):
    """TODO: define the real fields together — this is a placeholder."""
    pass


class AuditResult(BaseModel):
    """TODO: define the real fields together — this is a placeholder."""
    pass
