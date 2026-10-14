import json
import re
import uuid
from pathlib import Path

from app.schemas import AuditResult

BASE_DIR = Path(__file__).resolve().parent.parent        # ensure it's a Path object

with open(BASE_DIR / "data" / "rapex_blacklist.json") as f:
    blacklist_data = json.load(f)

# rapex_blacklist.json has no date field, so "most recent" can't come
# from a timestamp. File order looked like a proxy (fetch_rapex.py
# pulls weekly reports newest-first) but isn't reliable: alerts for the
# same barcode reported within the same week aren't necessarily in
# chronological order within that week's XML. Every alert_reference
# does follow a consistent PREFIX/SEQUENCE/YY format (confirmed: all
# 1,551 entries match it), and sequence numbers are assigned by the
# issuing authority in order — so (year, sequence) is a real proxy for
# recency, unlike file position.
_ALERT_REF_PATTERN = re.compile(r"^[A-Za-z0-9]+/(\d+)/(\d{2})$")


def _recency_key(item: dict) -> tuple[int, int]:
    """(year, sequence) parsed from alert_reference, for sorting alerts
    on the same barcode newest-first. Falls back to (-1, -1) — sorts
    last — if an alert_reference ever doesn't match the expected format."""
    match = _ALERT_REF_PATTERN.match(item["alert_reference"])
    if not match:
        return (-1, -1)
    sequence, year = match.groups()
    return (int(year), int(sequence))


# Group every alert by barcode instead of keeping only the last one —
# some barcodes legitimately have more than one alert on file
# (deduplicate() in fetch_rapex.py only dedupes by alert_reference, not
# barcode). Each group is sorted newest-first by _recency_key so
# matches[0] is a defensible "most recent," not just whatever happened
# to come first in the file.
blacklist_by_barcode: dict[str, list[dict]] = {}
for item in blacklist_data:
    blacklist_by_barcode.setdefault(item["barcode"], []).append(item)
for barcode, matches in blacklist_by_barcode.items():
    matches.sort(key=_recency_key, reverse=True)


def check_blacklist(gtin: str) -> AuditResult | None:
    matches = blacklist_by_barcode.get(gtin)
    if not matches:
        return None

    most_recent = matches[0]
    violation = (
        f"Product barcode matches EU Safety Gate recall "
        f"{most_recent['alert_reference']} ({most_recent['product_name']})"
    )
    reasoning = (
        f"This GTIN matches real, recorded product recall "
        f"{most_recent['alert_reference']} for \"{most_recent['product_name']}\"."
    )
    if len(matches) > 1:
        other_refs = ", ".join(m["alert_reference"] for m in matches[1:])
        note = (
            f" This barcode has {len(matches)} recorded alerts in total "
            f"(most recent shown; others: {other_refs})."
        )
        violation += note
        reasoning += note

    return AuditResult(
        audit_id=str(uuid.uuid4()),
        listing_gtin=gtin,
        verdict="non_compliant",
        risk_type="recalled_product",
        risk_score=1.0,
        violations=[violation],
        pipeline_stage="recall_check",
        reasoning=reasoning,
    )
