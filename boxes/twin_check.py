"""Run split_twins on dev and test and print what it finds.

Two runs:
  1. OLD files (knowledge.jsonl as library, old dev.jsonl and test.jsonl):
     Group 1 + Group 2 must equal the first check (535 test, 390 dev).
  2. NEW splits (data/splits/): twins were already kept together, so Group 1 should
     be 0 and Group 2 shows the generic texts that remain.
Run it with:  python -m boxes.twin_check
"""
import pandas as pd

from boxes.preprocessing import DATA_DIR, SPLITS_DIR, split_twins
from boxes.Product_description import load_alerts

# Numbers from the first check (product + description only, on the OLD files).
OLD_CHECK = {"dev": 390, "test": 535}


def load_frame(path) -> pd.DataFrame:
    """Read a .jsonl file into a DataFrame (load_alerts keeps every value as it is)."""
    return pd.DataFrame(load_alerts(path))


def run(title: str, library_path, other_paths: dict, expected: dict | None) -> None:
    """Run split_twins for each part (dev, test) and print the numbers."""
    print(f"\n=== {title} ===")
    library = load_frame(library_path)
    print(f"library: {len(library)} alerts")
    for name, path in other_paths.items():
        kept, counts = split_twins(library, load_frame(path))
        total = counts["group1_removed"] + counts["group2_kept"]
        print(f"\n{name}: checked {counts['rows_checked']}, "
              f"Group 1 removed {counts['group1_removed']}, Group 2 kept {counts['group2_kept']} "
              f"(Group 1 + Group 2 = {total})")
        if expected:
            verdict = "matches" if total == expected[name] else "DOES NOT MATCH"
            print(f"  first check said {expected[name]}: {verdict}")
        top = kept[kept["same_words_in_library"]]["category"].value_counts().head(5)
        print("  top 5 categories in Group 2:")
        for category, count in top.items():
            print(f"    {category}: {count}")


if __name__ == "__main__":
    run("OLD files",
        DATA_DIR / "knowledge.jsonl",
        {"dev": DATA_DIR / "dev.jsonl", "test": DATA_DIR / "test.jsonl"},
        OLD_CHECK)
    run("NEW splits",
        SPLITS_DIR / "library.jsonl",
        {"dev": SPLITS_DIR / "dev.jsonl", "test": SPLITS_DIR / "test.jsonl"},
        None)
