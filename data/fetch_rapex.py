"""
fetch_rapex.py — pulls real EU Safety Gate (formerly RAPEX) weekly alert
reports and produces two files from them:

- rapex_blacklist.json      — barcode-bearing alerts only, for the future
                               recall_check.py Step 0 blacklist match.
- rapex_training_alerts.json — all alerts in the 5 target categories, for
                               the agent evaluation set's "unsafe" rows
                               (built by build_eval_dataset.py).

Category mapping was verified against a real 1-year sample before being
hardcoded here (see CATEGORY_MAP) — not guessed. See Dataset_Strategy.md
for why these 5 categories were chosen.
"""

import json
import re
import time
import urllib.request
from pathlib import Path

INDEX_URL = "https://ec.europa.eu/safety-gate-alerts/api/download/weeklyReport/list/xml/en"
WEEKS_TO_FETCH = 52  # ~last 1 year, most recent first

# Real Safety Gate category strings -> our 5 project buckets.
# Verified by sampling 52 weekly reports (3,832 alerts) and reading the
# actual <category> values back, not assumed from the category name alone.
CATEGORY_MAP = {
    "Toys": "Toys",
    "Electrical appliances and equipment": "Electronics",
    "Cosmetics": "Cosmetics",
    "Childcare articles and children's equipment": "Baby/Childcare",
    "Clothing, textiles and fashion items": "Clothing",
}

OUTPUT_DIR = Path(__file__).resolve().parent
BLACKLIST_PATH = OUTPUT_DIR / "rapex_blacklist.json"
TRAINING_PATH = OUTPUT_DIR / "rapex_training_alerts.json"

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_xml(url: str) -> str:
    req = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def get_report_urls(index_xml: str, limit: int) -> list[str]:
    """Weekly reports are listed newest-first in the index; each <URL>
    entry points to that week's own detail XML (not the alerts directly)."""
    urls = re.findall(r"<URL>(.*?)</URL>", index_xml)
    return [u.replace("&amp;", "&") for u in urls[:limit]]


def extract_field(block: str, tag: str) -> str | None:
    """Real entries wrap text in CDATA; nil/empty fields have neither a
    CDATA body nor plain text, so both patterns are tried in order."""
    match = re.search(rf"<{tag}><!\[CDATA\[(.*?)\]\]></{tag}>", block, re.S)
    if match:
        text = match.group(1).strip()
        return text or None
    match = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S)
    return match.group(1).strip() or None if match else None


def parse_alerts(detail_xml: str) -> list[dict]:
    """Pulls every <notifications> block out of one weekly report's XML
    and keeps only the fields this script needs."""
    alerts = []
    for block in re.findall(r"<notifications.*?</notifications>", detail_xml, re.S):
        category = extract_field(block, "category")
        if category not in CATEGORY_MAP:
            continue
        name = extract_field(block, "name")
        product = extract_field(block, "product")
        alerts.append({
            "product_name": name or product,
            "category": CATEGORY_MAP[category],
            "description": extract_field(block, "description"),
            "risk_type": extract_field(block, "riskType"),
            "risk_description": extract_field(block, "danger"),
            "country_of_origin": extract_field(block, "countryOfOrigin"),
            "alert_reference": extract_field(block, "caseNumber"),
            "barcode": extract_field(block, "barcode"),
        })
    return alerts


def deduplicate(entries: list[dict]) -> list[dict]:
    """Keeps the first occurrence of each alert_reference — the same
    real alert can appear in more than one weekly report if an
    authority updates or re-references it later."""
    seen = set()
    deduped = []
    for entry in entries:
        ref = entry["alert_reference"]
        if ref in seen:
            continue
        seen.add(ref)
        deduped.append(entry)
    return deduped


def build_datasets() -> tuple[list[dict], list[dict]]:
    index_xml = fetch_xml(INDEX_URL)
    report_urls = get_report_urls(index_xml, WEEKS_TO_FETCH)
    print(f"Fetching {len(report_urls)} weekly reports...")

    training_alerts = []
    for i, url in enumerate(report_urls, start=1):
        detail_xml = fetch_xml(url)
        training_alerts.extend(parse_alerts(detail_xml))
        if i % 10 == 0 or i == len(report_urls):
            print(f"  ...{i}/{len(report_urls)} reports fetched")
        time.sleep(0.15)  # be polite to the EU Commission's server

    blacklist = [
        {
            "barcode": a["barcode"],
            "product_name": a["product_name"],
            "category": a["category"],
            "alert_reference": a["alert_reference"],
        }
        for a in training_alerts
        if a["barcode"]
    ]

    # training_alerts.json doesn't need the barcode field (that's the
    # blacklist's job) — drop it here to match the spec.
    training_alerts = [
        {k: v for k, v in a.items() if k != "barcode"} for a in training_alerts
    ]

    return blacklist, training_alerts


def report_counts(label: str, entries: list[dict]) -> None:
    print(f"\n{label}: {len(entries)} entries")
    tally: dict[str, int] = {}
    for e in entries:
        tally[e["category"]] = tally.get(e["category"], 0) + 1
    for category, count in sorted(tally.items(), key=lambda x: -x[1]):
        print(f"  {category}: {count}")


if __name__ == "__main__":
    blacklist, training_alerts = build_datasets()

    blacklist_before, training_before = len(blacklist), len(training_alerts)
    blacklist = deduplicate(blacklist)
    training_alerts = deduplicate(training_alerts)

    with open(BLACKLIST_PATH, "w") as f:
        json.dump(blacklist, f, indent=2, ensure_ascii=False)
    with open(TRAINING_PATH, "w") as f:
        json.dump(training_alerts, f, indent=2, ensure_ascii=False)

    print(f"\nRemoved {blacklist_before - len(blacklist)} duplicate(s) from blacklist")
    print(f"Removed {training_before - len(training_alerts)} duplicate(s) from training_alerts")

    report_counts("rapex_blacklist.json", blacklist)
    report_counts("rapex_training_alerts.json", training_alerts)
    print(f"\nWrote {BLACKLIST_PATH}")
    print(f"Wrote {TRAINING_PATH}")
