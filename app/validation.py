"""
validation.py — checks a listing is complete and well-formed BEFORE it
reaches the classifier or the LLM. This is what saves you from wasting
compute on garbage input.

Phase 1, build task 2: write this, then test it by hand against 3
deliberately broken listings (missing field, wrong type, empty string)
before touching the classifier at all.
"""

from app.schemas import ProductListing


def validate_listing(listing: ProductListing) -> tuple[bool, list[str]]:
    """
    Returns (is_valid, list_of_error_messages).

    TODO: implement real checks once ProductListing has real fields.
    """
    raise NotImplementedError
