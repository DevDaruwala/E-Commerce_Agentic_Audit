def tidy_text(text) -> str:
    """Turn a text into one clean line (capital letters are kept).

    Spaces, tabs and line breaks all become a single space, and spaces at the
    start and end are removed. A missing value (None) becomes "".
    Use this for the text that goes into the embedding model.
    """
    if text is None:
        return ""
    # split() cuts at any run of spaces, tabs or line breaks.
    # " ".join(...) glues the pieces back together with one space.
    return " ".join(str(text).split())


def normalise_text(text) -> str:
    """tidy_text plus lower case, so "SOFT TOY", "Soft toy" and "soft  toy " match.

    Use this only to COMPARE texts (duplicates, counting products, twins between
    library and test). Do not use it for the text that goes into the embedding
    model: that text keeps its capital letters.
    """
    return tidy_text(text).lower()


# ---------------------------------------------------------------------------
# Splitting the alerts into library, dev and test (by date, twins kept together)
# ---------------------------------------------------------------------------
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
# The three old files together hold every alert. Their own split is not by date,
# so we pool them and split again.
POOL_FILES = ["knowledge.jsonl", "dev.jsonl", "test.jsonl"]
SPLITS_DIR = DATA_DIR / "splits"

LIBRARY_SHARE = 0.70  # oldest 70% of the alerts
DEV_SHARE = 0.10      # the next 10%; the newest 20% is the test set


def load_pool(data_dir: Path = DATA_DIR, files: list[str] = POOL_FILES) -> list[dict]:
    """Read the old files, join them, and check that no case number appears twice."""
    alerts = []
    for name in files:
        with open(data_dir / name, encoding="utf-8") as f:
            alerts.extend(json.loads(line) for line in f)
    case_numbers = [alert["case_number"] for alert in alerts]
    if len(set(case_numbers)) != len(case_numbers):
        raise ValueError("the same case number appears in more than one file")
    return alerts


def twin_key(alert: dict) -> tuple:
    """What makes two alerts 'the same product': product, name, brand, description.

    All four are compared after tidying and lower-casing. Name and brand are
    included on purpose: "Passenger car" alone is thousands of different cars, but
    "Passenger car + Transit-Connect + Ford" is one model that was reported again.
    """
    return tuple(normalise_text(alert.get(field)) for field in ("product", "name", "brand", "description"))


def split_by_date(alerts: list[dict]) -> dict[str, list[dict]]:
    """Sort by date, then cut into library / dev / test, keeping twins together.

    Steps:
      1. Sort the alerts by report_date (oldest first). The position in this order
         becomes the new "index" (1, 2, 3, ...), the same in every part.
      2. Give each twin group a number ("twin_group").
      3. A group goes to the part where its OLDEST alert falls, so twins never end
         up on two sides. The cut points are 70% and 80% of the sorted list.
    Returns {"library": [...], "dev": [...], "test": [...]}.
    The input alerts are not changed.
    """
    ordered = sorted(alerts, key=lambda alert: alert["report_date"])  # sort is stable
    total = len(ordered)
    library_end, dev_end = total * LIBRARY_SHARE, total * (LIBRARY_SHARE + DEV_SHARE)

    def part_of(position: int) -> str:
        if position < library_end:
            return "library"
        return "dev" if position < dev_end else "test"

    group_number: dict[tuple, int] = {}   # twin key -> group number
    group_part: dict[tuple, str] = {}     # twin key -> part of its oldest alert
    for position, alert in enumerate(ordered):
        key = twin_key(alert)
        if key not in group_number:
            group_number[key] = len(group_number) + 1
            group_part[key] = part_of(position)

    parts: dict[str, list[dict]] = {"library": [], "dev": [], "test": []}
    for position, alert in enumerate(ordered):
        key = twin_key(alert)
        row = dict(alert)
        row["index"] = position + 1
        row["twin_group"] = group_number[key]
        parts[group_part[key]].append(row)
    return parts


def check_split(parts: dict[str, list[dict]]) -> dict:
    """Print how the three parts look and check the rules. Returns the numbers.

    Stops with an error if a twin group or a case number is in two parts.
    Also reports (but does not forbid) how many alerts in dev and test have the same
    product + description as a library alert: for generic texts like "Passenger
    car" that cannot be avoided.
    """
    twins = {name: {twin_key(a) for a in rows} for name, rows in parts.items()}
    cases = {name: {a["case_number"] for a in rows} for name, rows in parts.items()}
    names = list(parts)
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            if twins[first] & twins[second]:
                raise ValueError(f"twin groups are in both {first} and {second}")
            if cases[first] & cases[second]:
                raise ValueError(f"case numbers are in both {first} and {second}")

    def short_key(alert):
        return normalise_text(alert["product"]), normalise_text(alert["description"])

    library_texts = {short_key(a) for a in parts["library"]}
    total = sum(len(rows) for rows in parts.values())
    result = {}
    print(f"{'part':<9}{'alerts':>7}{'share':>8}  {'oldest':<12}{'newest':<12}{'same product+description as library':>38}")
    for name, rows in parts.items():
        dates = [a["report_date"] for a in rows]
        same_text = sum(short_key(a) in library_texts for a in rows) if name != "library" else 0
        result[name] = {"alerts": len(rows), "oldest": min(dates), "newest": max(dates), "same_text_as_library": same_text}
        shown = f"{same_text} ({same_text / len(rows) * 100:.0f}%)" if name != "library" else "-"
        print(f"{name:<9}{len(rows):>7}{len(rows) / total * 100:>7.1f}%  {min(dates):<12}{max(dates):<12}{shown:>38}")
    # Twins pulled to an older part make the dates overlap a little: count them.
    dev_oldest, test_oldest = result["dev"]["oldest"], result["test"]["oldest"]
    result["library_newer_than_dev_oldest"] = sum(a["report_date"] > dev_oldest for a in parts["library"])
    result["dev_newer_than_test_oldest"] = sum(a["report_date"] > test_oldest for a in parts["dev"])
    print(f"library alerts newer than the oldest dev alert: {result['library_newer_than_dev_oldest']}")
    print(f"dev alerts newer than the oldest test alert   : {result['dev_newer_than_test_oldest']}")
    return result


def save_split(parts: dict[str, list[dict]], folder: Path = SPLITS_DIR) -> None:
    """Write each part to <folder>/<name>.jsonl, one alert per line."""
    folder.mkdir(parents=True, exist_ok=True)
    for name, rows in parts.items():
        with open(folder / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")


# (The command-line entry point is at the very end of this file, after run_pipeline.)


# ---------------------------------------------------------------------------
# Twins between the library and dev/test
# ---------------------------------------------------------------------------
# Group 1, "same product": all six product fields match a library alert.
FULL_FIELDS = ["category", "product", "name", "brand", "description", "country_of_origin"]
# Group 2, "same words only": only product + description match.
WORDS_FIELDS = ["product", "description"]
# An invisible character that never appears in the texts. It sits between the parts
# of a key, so ("a b", "c") and ("a", "b c") can never become the same key.
KEY_SEPARATOR = "\x1f"


def _make_key(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    """Build one text key per row from the given columns.

    Each value is cleaned with normalise_text (spaces tidied, lower case), and a
    missing value counts as an empty string. The parts are joined with
    KEY_SEPARATOR. This only builds a new Series: the columns of df are not changed.
    """
    # fillna("") turns missing values (None / NaN) into "", then each text is cleaned.
    cleaned = [df[column].fillna("").map(normalise_text) for column in columns]
    key = cleaned[0]
    for part in cleaned[1:]:
        key = key + KEY_SEPARATOR + part
    return key


def split_twins(library_df: pd.DataFrame, other_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Find twins of library alerts in a dev or test frame, and sort them in two groups.

    Group 1 "same product" (a real twin): all of FULL_FIELDS match a library alert.
        These rows are REMOVED.
    Group 2 "same words only": product + description match a library alert, but at
        least one other field differs. These rows are KEPT and marked True in the
        new column "same_words_in_library".
    Every other row is kept and marked False.

    Returns (kept_rows, counts). counts has: rows_checked, group1_removed, group2_kept.
    Neither input frame is changed: the result is a copy, and its row index is kept
    so every row can be traced back to other_df.
    """
    # Step 1: the set of keys that exist in the library (a set is fast to look up in).
    library_full_keys = set(_make_key(library_df, FULL_FIELDS))
    library_words_keys = set(_make_key(library_df, WORDS_FIELDS))

    # Step 2: for every row, does its key exist in the library?
    # to_numpy() gives plain True/False arrays that line up row by row.
    is_group1 = _make_key(other_df, FULL_FIELDS).isin(library_full_keys).to_numpy()
    words_match = _make_key(other_df, WORDS_FIELDS).isin(library_words_keys).to_numpy()

    # Step 3: Group 2 = the words match, but it is not already a real twin.
    # Group 1 is checked first, so a row is never counted in both groups.
    is_group2 = words_match & ~is_group1

    # Step 4: drop Group 1 and mark Group 2 on the rows that stay.
    kept = other_df[~is_group1].copy()
    kept["same_words_in_library"] = is_group2[~is_group1]

    counts = {
        "rows_checked": len(other_df),
        "group1_removed": int(is_group1.sum()),
        "group2_kept": int(is_group2.sum()),
    }
    return kept, counts


# ---------------------------------------------------------------------------
# Removing duplicates inside one part (library, dev or test)
# ---------------------------------------------------------------------------
def _list_key(series: pd.Series) -> pd.Series:
    """Turn a column of lists (risk_types, law_names) into one text per row.

    The items are cleaned and sorted, so ["Fire", "Burns"] and ["burns", "fire"]
    give the same text. A missing list counts as empty.
    """
    return series.map(lambda items: "|".join(sorted(normalise_text(item) for item in (items or []))))


def remove_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Remove repeated alerts from one frame, keeping the OLDEST of each repeat.

    Two alerts are duplicates when the six product fields (FULL_FIELDS) AND the
    answer (risk_types and law_names) are the same, after tidying and lower-casing.
    A repeat of the same product with a DIFFERENT answer is kept on purpose: it is
    useful evidence for the search and the vote.

    Returns (unique_rows, counts). counts has: rows_checked, duplicates_removed,
    rows_kept. The input frame is not changed; the row order and the row index of
    the kept rows stay as they were.
    """
    # Step 1: one text key per row: product fields + risk types + law names.
    key = (
        _make_key(df, FULL_FIELDS)
        + KEY_SEPARATOR + _list_key(df["risk_types"])
        + KEY_SEPARATOR + _list_key(df["law_names"])
    )

    # Step 2: look at the rows from oldest to newest. argsort(kind="stable") gives
    # the row positions in date order, and rows with the same date keep their order.
    oldest_first = np.argsort(df["report_date"].to_numpy(), kind="stable")

    # Step 3: in that order, every key seen before is a duplicate (the first stays).
    repeated_in_date_order = key.iloc[oldest_first].duplicated().to_numpy()

    # Step 4: put the answers back in the original row order.
    is_duplicate = np.empty(len(df), dtype=bool)
    is_duplicate[oldest_first] = repeated_in_date_order

    counts = {
        "rows_checked": len(df),
        "duplicates_removed": int(is_duplicate.sum()),
        "rows_kept": int((~is_duplicate).sum()),
    }
    return df[~is_duplicate].copy(), counts


# ---------------------------------------------------------------------------
# Making the text of one alert, and spotting thin descriptions
# ---------------------------------------------------------------------------
def join_parts(parts: list[tuple[str, str]]) -> str:
    """Join named text parts, in order, into one text.

    parts is a list of (name, text) pairs, for example [("product", "Plastic duck")].
    The name is only used in the error message.
    Every part except the last gets a full stop at the end (unless it already
    ends with one), then the parts are joined with a single space.
    The last part is left as it is.
    """
    cleaned = []
    for name, text in parts:
        # Clean the text (tabs and line breaks become single spaces).
        text = tidy_text(text)
        # Stop with a clear message if a part is missing or empty.
        if not text:
            raise ValueError(f"{name} is missing or empty")
        cleaned.append(text)

    pieces = []
    for text in cleaned[:-1]:
        # Add a full stop after the part, unless it already ends with one.
        if not text.endswith((".", "!", "?")):
            text = text + "."
        pieces.append(text)
    pieces.append(cleaned[-1])
    return " ".join(pieces)


def make_text(product: str, description: str) -> str:
    """The text of one alert: the product, a full stop, then the description.

    Example: "Plastic duck" + "Yellow plastic duck."
             -> "Plastic duck. Yellow plastic duck."
    Capital letters and special characters are left as they are, so this is the
    text to give to the embedding model. Stops with an error if a part is missing.
    """
    return join_parts([("product", product), ("description", description)])


def is_thin(product: str, description: str) -> bool:
    """True when the description tells us nothing more than the product already did.

    Thin = every word of the description is already a word of the product, so
    "Motorcycle" + "Motorcycle" or "Skin-lightening lotion" + "Skin lightening lotion."
    are thin, while "Plastic duck" + "Yellow plastic duck." is not (it adds "yellow").
    An empty or missing description is thin too. Capital letters, punctuation and
    word order are ignored. Never raises an error.
    """
    # normalise_text lower-cases and tidies; \w+ then picks out the words.
    product_words = set(re.findall(r"\w+", normalise_text(product)))
    description_words = set(re.findall(r"\w+", normalise_text(description)))
    # <= means "is a subset of": all description words are found in the product.
    return description_words <= product_words



def flag_thin(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Add a True/False column "is_thin" to a frame. Nothing is removed or changed.

    A row is thin when its description adds nothing to the product (see is_thin).
    The flag is only a label: later you can score "all rows" and "without thin rows"
    separately. The text that is embedded is not changed.

    Returns (frame_with_flag, counts). counts has: rows_checked, thin_flagged.
    The input frame is not changed; the result is a copy with the same row index.
    """
    flagged = df.copy()
    # fillna("") turns missing values into "", and is_thin treats "" as "adds nothing".
    flagged["is_thin"] = [
        is_thin(product, description)
        for product, description in zip(df["product"].fillna(""), df["description"].fillna(""))
    ]
    return flagged, {"rows_checked": len(df), "thin_flagged": int(flagged["is_thin"].sum())}


# ---------------------------------------------------------------------------
# The whole pipeline: all the steps above, in order, and save the result
# ---------------------------------------------------------------------------
def _to_records(df: pd.DataFrame) -> list[dict]:
    """A DataFrame as a list of dicts, with None (not NaN) for missing values."""
    return df.astype(object).where(df.notna(), None).to_dict("records")


def _json_default(value):
    """Let json.dumps write numpy numbers and booleans (pandas hands these out)."""
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"cannot write {type(value)} as JSON")


def _write_jsonl(df: pd.DataFrame, path: Path) -> None:
    """Write a frame as .jsonl, one alert per line. Missing values become null."""
    with open(path, "w", encoding="utf-8") as f:
        for record in _to_records(df):
            f.write(json.dumps(record, ensure_ascii=False, default=_json_default) + "\n")


def run_pipeline(data_dir: Path = DATA_DIR, out_dir: Path = SPLITS_DIR, save: bool = True):
    """Run every preprocessing step in order and (optionally) save the result.

    Steps:
      1. Pool: read the old files into one list of alerts.
      2. Split by date into library / dev / test (twin groups kept whole).
      3. Remove duplicates inside each part (same product + same answer, oldest kept).
      4. Remove Group 1 twins from dev and test, and mark Group 2 ("same_words_in_library").
      5. Flag thin descriptions ("is_thin") in all three parts.
      6. Safety check: no twin group or case number may be in two parts.
      7. Save library.jsonl, dev.jsonl, test.jsonl and pipeline_summary.json to out_dir.
    Returns (frames, summary): frames = {"library": df, "dev": df, "test": df}, and
    summary = the number of rows after every step.
    """
    # Steps 1 and 2: pool and split. check_split prints a table and stops on a problem.
    pool = load_pool(data_dir)
    print(f"{len(pool)} alerts in the pool\n\nAfter the split by date:")
    raw_parts = split_by_date(pool)
    check_split(raw_parts)

    frames: dict[str, pd.DataFrame] = {}
    summary: dict = {"pool": len(pool), "parts": {}}
    for name, rows in raw_parts.items():
        frame = pd.DataFrame(rows)
        # Step 3: remove duplicates inside this part.
        frame, counts = remove_duplicates(frame)
        frames[name] = frame
        summary["parts"][name] = {
            "after_split": counts["rows_checked"],
            "duplicates_removed": counts["duplicates_removed"],
        }

    # Step 4: compare dev and test with the (cleaned) library.
    for name in ("dev", "test"):
        frames[name], counts = split_twins(frames["library"], frames[name])
        summary["parts"][name]["group1_removed"] = counts["group1_removed"]
        summary["parts"][name]["group2_marked"] = counts["group2_kept"]

    # Step 5: flag thin descriptions everywhere.
    for name in frames:
        frames[name], counts = flag_thin(frames[name])
        summary["parts"][name]["thin_flagged"] = counts["thin_flagged"]
        summary["parts"][name]["rows_saved"] = len(frames[name])

    # Step 6: final safety check on the cleaned parts.
    print("\nAfter cleaning:")
    check_split({name: _to_records(frame) for name, frame in frames.items()})

    # Step 7: save.
    if save:
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, frame in frames.items():
            _write_jsonl(frame, out_dir / f"{name}.jsonl")
        with open(out_dir / "pipeline_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
            f.write("\n")
        print(f"\nsaved to {out_dir}")
    return frames, summary


if __name__ == "__main__":
    _, result = run_pipeline()
    print(f"\n{'part':<9}{'after split':>12}{'duplicates':>12}{'group 1':>9}{'group 2':>9}{'thin':>7}{'saved':>8}")
    for name, numbers in result["parts"].items():
        print(f"{name:<9}{numbers['after_split']:>12}{numbers['duplicates_removed']:>12}"
              f"{numbers.get('group1_removed', '-'):>9}{numbers.get('group2_marked', '-'):>9}"
              f"{numbers['thin_flagged']:>7}{numbers['rows_saved']:>8}")

