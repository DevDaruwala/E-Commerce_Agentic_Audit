"""
report.py — turns pipeline output into files the user can act on.

Right now: the rejection report. When the bouncer blocks listings from a
bulk upload, the user needs (1) a file they can fix and re-upload and
(2) a table they can read.
"""

import csv
import io

from typing import Optional

from app.schemas import AuditResult, RejectedListing


def build_rejection_report(rejected: list[RejectedListing]) -> dict:
    """Builds the two outputs from the blocked listings.

    Returns:
      {"correction_file": [...],  # JSON-ready: fix these and re-upload as-is
       "table_csv": "..."}        # human-readable CSV text

    The correction file holds each ORIGINAL listing plus an "_errors" key.
    ProductListing ignores unknown keys, so a leftover "_errors" does not
    break the re-upload. An item that was not a JSON object cannot take
    an extra key, so it is wrapped as {"_original": ..., "_errors": [...]}.
    """
    correction_file = []
    for r in rejected:
        if isinstance(r.original, dict):
            correction_file.append({**r.original, "_errors": r.errors})
        else:
            correction_file.append({"_original": r.original, "_errors": r.errors})

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["index", "title", "gtin", "distributor_id", "errors"])
    for r in rejected:
        writer.writerow([r.index, r.title, r.gtin, r.distributor_id, " | ".join(r.errors)])

    return {"correction_file": correction_file, "table_csv": buffer.getvalue()}


def build_audit_report(results: list[AuditResult], titles: list[Optional[str]]) -> dict:
    """Builds the audit report for the listings that were let in and audited.

    `titles[i]` is the title of `results[i]`. AuditResult itself has no
    title (it only carries listing_gtin), so the caller passes them in.

    Returns:
      {"json": [...],   # one dict per audited listing, violations as a list
       "csv": "..."}    # same rows as CSV text, violations joined with " | "
    """
    rows = [
        {
            "title": title,
            "gtin": r.listing_gtin,
            "verdict": r.verdict,
            "pipeline_stage": r.pipeline_stage,
            "risk_type": r.risk_type,
            "risk_score": r.risk_score,
            "violations": r.violations,
            "reasoning": r.reasoning,
            "audit_id": r.audit_id,
        }
        for r, title in zip(results, titles)
    ]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    columns = ["title", "gtin", "verdict", "pipeline_stage", "risk_type",
               "risk_score", "violations", "reasoning", "audit_id"]
    writer.writerow(columns)
    for row in rows:
        writer.writerow([" | ".join(row[c]) if c == "violations" else row[c] for c in columns])

    return {"json": rows, "csv": buffer.getvalue()}
