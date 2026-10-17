"""
frontend/audit_client.py — the non-UI logic of the audit page, kept apart
from Streamlit so it can be tested with plain pytest.
"""

import json

import requests

BATCH_SIZE = 100  # listings per request; keeps each request small for big uploads


def parse_upload(uploaded_file) -> tuple[list | None, str | None]:
    """Reads the uploaded file. Returns (listings, None) or (None, error message)."""
    try:
        parsed = json.loads(uploaded_file.getvalue().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return None, f"This file is not valid JSON: {e}"
    if not isinstance(parsed, list):
        return None, "The file must contain a JSON list of listings, like [ {...}, {...} ]."
    if not parsed:
        return None, "The file contains an empty list — nothing to audit."
    return parsed, None


def run_audit(listings: list, backend_url: str, on_progress) -> dict:
    """Sends the listings to POST /listings/audit, BATCH_SIZE at a time.

    Each batch response has `rejected` (with batch-relative index) and
    `results` (in upload order, only for the listings that were let in).
    We add the batch offset so rejected indices match the ORIGINAL file, and
    zip the let-in listings with their results to recover the titles.
    """
    rejected: list[dict] = []
    results: list[dict] = []
    titles: list[str | None] = []

    for start in range(0, len(listings), BATCH_SIZE):
        batch = listings[start:start + BATCH_SIZE]
        response = requests.post(f"{backend_url}/listings/audit", json=batch, timeout=120)
        response.raise_for_status()
        body = response.json()

        blocked_here = {r["index"] for r in body["rejected"]}
        for r in body["rejected"]:
            rejected.append({**r, "index": r["index"] + start})

        let_in = [raw for i, raw in enumerate(batch) if i not in blocked_here]
        for raw, result in zip(let_in, body["results"]):
            results.append(result)
            titles.append(raw.get("title") if isinstance(raw, dict) else None)

        on_progress(min(start + BATCH_SIZE, len(listings)))

    return {"total": len(listings), "rejected": rejected, "results": results, "titles": titles}
