"""
build_eval_dataset.py — blends real RAPEX/Safety Gate alerts (unsafe)
with real McAuley-Lab/Amazon-Reviews-2023 listings (safe) into one flat
CSV: a FIXED 50 unsafe + 50 safe per category, across 5 categories
(500 rows total), not a proportional split of real-world alert volume.
A proportional split was tried first and rejected — Cosmetics
dominates real Safety Gate data, so it starved Baby/Childcare and
Clothing down to single digits even though real data for those two
categories was never actually scarce (confirmed by direct count:
145-679 real alerts per category available in the fetch window, all
well over the 50 needed).

This is the agent's EVALUATION set, not training data — there is no
classifier in this design anymore (cut from scope; see
Dataset_Strategy.md's "Evaluation rules" section for what the
evaluation harness must strip before the agent sees a row).

Every unsafe row's alert_reference is cross-checked against
rapex_blacklist.json before sampling AND re-verified after, so none of
the ~1,551 blacklist-reserved alerts (weeks 0-51, the most recent
year) ever leak into this evaluation set recall_check.py would
otherwise reject outright.

risk_type and risk_description are deliberately never extracted here —
confirmed leakage fields, they would hand the agent the answer instead
of making it reason from category/description/price patterns.

Columns with no real source on one or both sides (product_specs,
safety_warning_text, and sometimes price/description/country_of_origin)
are backfilled with synthetic values through ONE shared function per
column, applied identically to every row regardless of is_unsafe — the
code never branches on the label when generating a synthetic value.
country_of_origin backfill is bootstrap-sampled from the real countries
seen in the RAPEX data itself, rather than an invented list, so the
synthetic distribution matches a real one.

The "datasets" library's load_dataset() no longer supports this
repo (it uses a legacy loading script, and modern `datasets` versions
hard-refuse those) — so this reads the Parquet/JSONL files directly
over HTTPS instead of adding that dependency.

Continued from fetch_rapex.py.
"""

import csv
import json
import random
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_rapex import (  # noqa: E402
    INDEX_URL,
    extract_field,
    fetch_xml,
    get_report_urls,
    parse_alerts,
)

RANDOM_SEED = 42
PER_CATEGORY_TARGET = 50  # fixed per category, per class -> 5 * 50 * 2 = 500 rows total
CATEGORIES = ["Cosmetics", "Toys", "Electronics", "Baby/Childcare", "Clothing"]

# weeks[52:104] of the report index = roughly 12-24 months old — the
# year immediately before the one fetch_rapex.py already pulled, so
# this evaluation set doesn't overlap with the live blacklist (and
# per Dataset_Strategy.md, these weeks must never feed the agent's
# future similar-recalls retrieval index either).
# Confirmed by direct count (see build log) that this window alone
# already has 145-1804 real alerts per category, comfortably over the
# 50/category target -- no need to reach back further.
OLDER_BUCKET_START = 52
OLDER_BUCKET_END = 104

OUTPUT_PATH = Path(__file__).resolve().parent / "agent_eval_set.csv"
BLACKLIST_PATH = Path(__file__).resolve().parent / "rapex_blacklist.json"
COLUMNS = [
    "title", "category", "price", "description", "product_specs",
    "safety_warning_text", "country_of_origin", "is_unsafe", "source_id",
]

# McAuley-Lab/Amazon-Reviews-2023 file paths, verified against the
# dataset's real file listing (not guessed). Cosmetics/Toys/Electronics
# have pre-converted Parquet shards; Baby/Childcare and Clothing don't,
# so those two are streamed from the raw JSONL instead.
MCAULEY_PARQUET_FILES = {
    "Cosmetics": "raw_meta_All_Beauty/full-00000-of-00001.parquet",
    "Toys": "raw_meta_Toys_and_Games/full-00000-of-00005.parquet",
    "Electronics": "raw_meta_Electronics/full-00000-of-00010.parquet",
}
MCAULEY_JSONL_FILES = {
    "Baby/Childcare": "meta_Baby_Products.jsonl",
    "Clothing": "meta_Clothing_Shoes_and_Jewelry.jsonl",
}
MCAULEY_PARQUET_BASE = "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main"
MCAULEY_JSONL_BASE = f"{MCAULEY_PARQUET_BASE}/raw/meta_categories"

PRICE_RANGES = {
    "Cosmetics": (5, 40),
    "Toys": (8, 60),
    "Electronics": (15, 300),
    "Baby/Childcare": (10, 150),
    "Clothing": (8, 80),
}
PRODUCT_SPECS_POOL = {
    "Cosmetics": ["Net weight: 50ml", "Net weight: 100ml", "pH balanced formula", "Suitable for all skin types"],
    "Toys": ["Recommended age: 3+ years", "Recommended age: 6+ years", "Material: ABS plastic", "Batteries required: 2x AA (included)"],
    "Electronics": ["Voltage: 100-240V", "Battery capacity: 2000mAh", "Connectivity: Bluetooth 5.0", "Material: ABS plastic / aluminum"],
    "Baby/Childcare": ["Recommended age: 0-12 months", "Machine washable", "BPA-free materials"],
    "Clothing": ["Material: 100% cotton", "Machine washable", "Available in multiple sizes"],
}
SAFETY_WARNING_POOL = {
    "Cosmetics": ["For external use only. Discontinue use if irritation occurs.", "Keep out of reach of children.", "Avoid contact with eyes."],
    "Toys": ["Choking hazard — small parts. Not for children under 3 years.", "Adult supervision recommended.", "Keep packaging away from children."],
    "Electronics": ["Risk of electric shock — do not open casing.", "Keep away from water and moisture.", "Use only the supplied charger."],
    "Baby/Childcare": ["Never leave child unattended.", "Check regularly for wear and damage.", "Follow assembly instructions carefully."],
    "Clothing": ["Keep away from open flame.", "Follow care label instructions.", "Drawstrings may pose a hazard for young children."],
}


def parse_price(value) -> float | None:
    """McAuley stores price as a string, sometimes literally 'None'."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "none":
        return None
    try:
        return round(float(text), 2)
    except ValueError:
        return None


MIN_DESCRIPTION_LENGTH = 20  # chars, after joining + stripping — see below


def _has_real_description(desc) -> bool:
    """True if `desc` is a non-empty sequence that joins into at least
    MIN_DESCRIPTION_LENGTH chars of real text. Used to filter OUT
    McAuley rows that would otherwise need backfill()'s "No detailed
    description available" placeholder — fixing this at the sampling
    stage (don't pick the row at all) instead of patching it after the
    fact. A bare non-blank check isn't enough: real McAuley rows exist
    with descriptions like "1" or "Stickers" that are technically
    non-blank but useless as evidence text, so a length floor is
    needed too (confirmed by direct count: 20 chars excludes exactly
    the junk one-word rows without meaningfully shrinking the pool)."""
    if desc is None:
        return False
    try:
        items = list(desc)
    except TypeError:
        return False
    joined = " ".join(str(s).strip() for s in items).strip()
    return len(joined) >= MIN_DESCRIPTION_LENGTH


def sample_up_to(pool: list, target: int, rng: random.Random) -> list:
    """Seeded random sample of up to `target` items from `pool`. No
    cross-category backfill: if a category's real pool falls short, the
    shortfall is just reported honestly (by the caller), never padded
    from another category's leftovers -- that would break the "exactly
    N per category" requirement."""
    indices = list(range(len(pool)))
    rng.shuffle(indices)
    take = min(target, len(pool))
    return [pool[i] for i in indices[:take]]


def load_blacklist_refs() -> set[str]:
    """alert_reference values already reserved for rapex_blacklist.json
    (weeks 0-51) -- must never also appear in this evaluation set, or
    recall_check.py's Step 0 would reject the row before the agent
    ever sees it."""
    blacklist = json.loads(BLACKLIST_PATH.read_text())
    return {b["alert_reference"] for b in blacklist if b.get("alert_reference")}


def fetch_older_bucket_alerts() -> list[dict]:
    index_xml = fetch_xml(INDEX_URL)
    all_urls = get_report_urls(index_xml, OLDER_BUCKET_END)
    older_urls = all_urls[OLDER_BUCKET_START:OLDER_BUCKET_END]
    print(f"Fetching {len(older_urls)} older weekly reports (~12-24 months old)...")

    alerts = []
    for i, url in enumerate(older_urls, start=1):
        detail_xml = fetch_xml(url)
        alerts.extend(parse_alerts(detail_xml))
        if i % 10 == 0 or i == len(older_urls):
            print(f"  ...{i}/{len(older_urls)} reports fetched")
        time.sleep(0.15)
    return alerts


def build_unsafe_rows(targets: dict[str, int], rng: random.Random) -> tuple[list[dict], list[str], dict[str, int]]:
    raw_alerts = fetch_older_bucket_alerts()
    blacklist_refs = load_blacklist_refs()

    clean_alerts = [a for a in raw_alerts if a.get("alert_reference") not in blacklist_refs]
    excluded = len(raw_alerts) - len(clean_alerts)
    print(f"  excluded {excluded} alert(s) already reserved for rapex_blacklist.json")

    by_category: dict[str, list[dict]] = {}
    for alert in clean_alerts:
        by_category.setdefault(alert["category"], []).append(alert)

    sampled = []
    shortfalls = {}
    for cat in targets:
        pool = by_category.get(cat, [])
        picked = sample_up_to(pool, targets[cat], rng)
        sampled.extend(picked)
        shortfalls[cat] = targets[cat] - len(picked)
        flag = " <-- SHORTFALL" if shortfalls[cat] > 0 else ""
        print(f"  {cat:20s} available={len(pool):5d}  sampled={len(picked):3d}/{targets[cat]}{flag}")

    rows = [
        {
            "title": a["product_name"],
            "category": a["category"],
            "price": None,  # RAPEX never has price
            "description": a.get("description") or None,
            "product_specs": None,  # no source has this
            "safety_warning_text": None,  # no source has this
            "country_of_origin": a.get("country_of_origin") or None,
            "is_unsafe": 1,
            "source_id": a.get("alert_reference"),
        }
        for a in sampled
    ]
    real_countries = [a["country_of_origin"] for a in clean_alerts if a.get("country_of_origin")]
    return rows, real_countries, shortfalls


def verify_no_blacklist_overlap(unsafe_rows: list[dict]) -> int:
    """Independent re-check (not just trusting the pre-filter): are any
    final unsafe rows' alert_reference also in rapex_blacklist.json?"""
    blacklist_refs = load_blacklist_refs()
    overlap = [r["source_id"] for r in unsafe_rows if r["source_id"] in blacklist_refs]
    if overlap:
        print(f"  ERROR: {len(overlap)} unsafe row(s) overlap with rapex_blacklist.json: {overlap}")
    else:
        print(f"  Confirmed: 0 overlap between {len(unsafe_rows)} unsafe rows and rapex_blacklist.json")
    return len(overlap)


def read_mcauley_parquet(category: str, n_needed: int, rng: random.Random) -> list[dict]:
    url = f"{MCAULEY_PARQUET_BASE}/{MCAULEY_PARQUET_FILES[category]}"
    df = pd.read_parquet(url, columns=["title", "price", "description", "parent_asin"])
    df = df[df["title"].str.strip().astype(bool)]
    # Only sample from rows that already have a real description, so we
    # never need backfill()'s placeholder for a safe row.
    df = df[df["description"].apply(_has_real_description)]
    take = min(n_needed, len(df))
    sample_df = df.sample(n=take, random_state=rng.randint(0, 2**31 - 1))
    return [
        {
            "title": r["title"],
            "price_raw": r["price"],
            "description_raw": list(r["description"]) if r["description"] is not None else [],
            "source_id": r["parent_asin"],
        }
        for _, r in sample_df.iterrows()
    ]


def read_mcauley_jsonl(category: str, n_needed: int, rng: random.Random) -> list[dict]:
    url = f"{MCAULEY_JSONL_BASE}/{MCAULEY_JSONL_FILES[category]}"
    # Filtering on title AND a real description yields fewer qualifying
    # rows per byte read than the old title-only filter, so the oversample
    # window needs to be wider (10x instead of 5x) to still find n_needed.
    oversample_limit = n_needed * 10
    collected = []
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            title = (row.get("title") or "").strip()
            if not title:
                continue
            description_raw = row.get("description") or []
            if not _has_real_description(description_raw):
                continue
            collected.append({
                "title": title,
                "price_raw": row.get("price"),
                "description_raw": description_raw,
                "source_id": row.get("parent_asin"),
            })
            if len(collected) >= oversample_limit:
                break
    take = min(n_needed, len(collected))
    return rng.sample(collected, take)


def build_safe_rows(targets: dict[str, int], rng: random.Random) -> list[dict]:
    rows = []
    for category, target in targets.items():
        if target <= 0:
            continue
        print(f"  fetching {target} McAuley '{category}' listings...")
        if category in MCAULEY_PARQUET_FILES:
            raw = read_mcauley_parquet(category, target, rng)
        else:
            raw = read_mcauley_jsonl(category, target, rng)

        for r in raw:
            rows.append({
                "title": r["title"],
                "category": category,
                "price": parse_price(r["price_raw"]),
                "description": " ".join(r["description_raw"]).strip() or None,
                "product_specs": None,  # no source has this
                "safety_warning_text": None,  # no source has this
                "country_of_origin": None,  # no source has this
                "is_unsafe": 0,
                "source_id": r["source_id"],
            })
    return rows


def backfill(rows: list[dict], real_countries: list[str], rng: random.Random) -> dict[str, int]:
    """One shared, label-blind generator per column — never branches on
    is_unsafe, so the synthetic values themselves carry no label signal."""
    counts = {"price": 0, "description": 0, "product_specs": 0, "safety_warning_text": 0, "country_of_origin": 0}
    for row in rows:
        category = row["category"]
        if row["price"] is None:
            low, high = PRICE_RANGES[category]
            row["price"] = round(rng.uniform(low, high), 2)
            counts["price"] += 1
        if not row["description"]:
            row["description"] = f"No detailed description available for this {category.lower()} product."
            counts["description"] += 1
        if row["product_specs"] is None:
            row["product_specs"] = rng.choice(PRODUCT_SPECS_POOL[category])
            counts["product_specs"] += 1
        if row["safety_warning_text"] is None:
            row["safety_warning_text"] = rng.choice(SAFETY_WARNING_POOL[category])
            counts["safety_warning_text"] += 1
        if not row["country_of_origin"]:
            row["country_of_origin"] = rng.choice(real_countries)
            counts["country_of_origin"] += 1
    return counts


def category_distribution(rows: list[dict]) -> dict[str, int]:
    tally: dict[str, int] = {}
    for row in rows:
        tally[row["category"]] = tally.get(row["category"], 0) + 1
    return dict(sorted(tally.items(), key=lambda x: -x[1]))


if __name__ == "__main__":
    rng = random.Random(RANDOM_SEED)
    targets = {cat: PER_CATEGORY_TARGET for cat in CATEGORIES}

    print("=== Unsafe rows (RAPEX, older bucket, blacklist-filtered) ===")
    unsafe_rows, real_countries, shortfalls = build_unsafe_rows(targets, rng)

    print("\n=== Safe rows (McAuley) ===")
    safe_rows = build_safe_rows(targets, rng)

    print("\n=== Blacklist cross-check ===")
    overlap_count = verify_no_blacklist_overlap(unsafe_rows)

    all_rows = unsafe_rows + safe_rows
    backfill_counts = backfill(all_rows, real_countries, rng)
    rng.shuffle(all_rows)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for row in all_rows:
            writer.writerow({k: row[k] for k in COLUMNS})

    print(f"\nWrote {OUTPUT_PATH}")
    print(f"\nTotal rows: {len(all_rows)}  (unsafe: {len(unsafe_rows)}, safe: {len(safe_rows)})")
    unsafe_dist = category_distribution(unsafe_rows)
    safe_dist = category_distribution(safe_rows)
    print("Unsafe category distribution:", unsafe_dist)
    print("Safe category distribution:  ", safe_dist)

    all_full = all(
        unsafe_dist.get(cat) == PER_CATEGORY_TARGET and safe_dist.get(cat) == PER_CATEGORY_TARGET
        for cat in CATEGORIES
    )
    print(f"\nAll 5 categories at {PER_CATEGORY_TARGET}/{PER_CATEGORY_TARGET} (unsafe/safe): {all_full}")
    if any(shortfalls.values()):
        print("Unsafe shortfalls by category:", {k: v for k, v in shortfalls.items() if v})
    print(f"Blacklist overlap in final dataset: {overlap_count} (expect 0)")

    print("\nSynthetic backfill count per column (out of", len(all_rows), "rows):")
    for column, count in backfill_counts.items():
        print(f"  {column}: {count}")
