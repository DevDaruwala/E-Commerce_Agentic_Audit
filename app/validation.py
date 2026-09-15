"""
validation.py — checks a listing is complete and well-formed BEFORE it
reaches the classifier or the LLM. This is what saves you from wasting
compute on garbage input.

Phase 1, build task 2: write this, then test it by hand against 3
deliberately broken listings (missing field, wrong type, empty string)
before touching the classifier at all.
"""

from pydantic import ValidationError

from app.schemas import ProductListing


def validate_listing(raw_listing: dict) -> tuple[bool, list[str]]:
    """
    Attempts to build a ProductListing from raw, untrusted input.
    Returns (is_valid, list_of_error_messages).
    """
    try:
        ProductListing(**raw_listing)
        return True, []
    except ValidationError as e:
        messages = [
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in e.errors()
        ]
        return False, messages
