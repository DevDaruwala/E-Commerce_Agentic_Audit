import json
import re
import statistics
from collections import Counter
from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt

from boxes.preprocessing import normalise_text
from boxes.Product_description import KNOWLEDGE_PATH, clean_row, load_alerts

# "index" is unique per row, so it is ignored when looking for duplicates.
IGNORE_FOR_DUPLICATES = {"index"}

# Plots are saved here as .png files (project root / plots).
PLOTS_DIR = Path(__file__).resolve().parent.parent / "plots"


def _is_missing(value) -> bool:
    """None, empty string and empty list all count as missing."""
    return value is None or value == "" or value == []


def show_overview(cleaned_rows: list[dict], head_size: int = 5) -> None:
    """Print the shape (rows, columns) and the first rows of the cleaned rows."""
    columns = {key for row in cleaned_rows for key in row}
    print(f"Shape: ({len(cleaned_rows)} rows, {len(columns)} columns)")
    print(f"Head (first {head_size} rows):")
    for row in cleaned_rows[:head_size]:
        print(json.dumps(row, ensure_ascii=False))


def _comparable(value):
    """A value in a form that can be compared: texts are tidied and lower-cased,
    lists (risk_types, law_names) are handled item by item, None stays None."""
    if isinstance(value, str):
        return normalise_text(value)
    if isinstance(value, list):
        return [_comparable(item) for item in value]
    return value


def check_duplicates(cleaned_rows: list[dict]) -> list[dict]:
    """Print the duplicate rows, then return the rows without duplicates.

    Two rows are duplicates when every field is the same (except "index").
    Texts are compared after tidying and lower-casing, so "SOFT TOY", "Soft toy"
    and "Soft toy " (extra space) count as the same.
    The first occurrence is kept. The input list is not changed.
    """
    seen = set()
    unique_rows = []
    duplicate_rows = []
    for row in cleaned_rows:
        key = json.dumps(
            {k: _comparable(v) for k, v in row.items() if k not in IGNORE_FOR_DUPLICATES},
            sort_keys=True,
            ensure_ascii=False,
        )
        if key in seen:
            duplicate_rows.append(row)
        else:
            seen.add(key)
            unique_rows.append(row)

    print(f"Duplicate rows: {len(duplicate_rows)}")
    for row in duplicate_rows:
        print(json.dumps(row, ensure_ascii=False))
    print(f"Rows without duplicates: {len(unique_rows)}")
    return unique_rows


def check_missing_and_types(unique_rows: list[dict]) -> None:
    """Print, for each column: how many values exist / are missing, and the value types."""
    columns = list(dict.fromkeys(key for row in unique_rows for key in row))
    total = len(unique_rows)
    print(f"{'column':<20}{'exist':>8}{'missing':>9}{'missing %':>11}  types of the existing values")
    for column in columns:
        values = [row.get(column) for row in unique_rows]
        missing = sum(_is_missing(v) for v in values)
        types = Counter(type(v).__name__ for v in values if not _is_missing(v))
        types_text = ", ".join(f"{name} ({count})" for name, count in types.items())
        print(f"{column:<20}{total - missing:>8}{missing:>9}{missing / total * 100:>10.1f}%  {types_text}")


def missing_values(cleaned_rows: list[dict]) -> tuple[int, int]:
    """Count the missing values in the cleaned rows, and the columns that have any.

    Returns (missing_values, columns_with_missing) and prints both.
    A value is missing if it is None, "" or [] (see _is_missing).
    The input list is not changed.
    """
    columns = list(dict.fromkeys(key for row in cleaned_rows for key in row))
    missing_per_column = {
        column: sum(_is_missing(row.get(column)) for row in cleaned_rows)
        for column in columns
    }
    total_missing = sum(missing_per_column.values())
    columns_with_missing = sum(1 for count in missing_per_column.values() if count > 0)
    print(f"Missing values: {total_missing} of {len(cleaned_rows) * len(columns)} cells")
    print(f"Columns with missing values: {columns_with_missing} of {len(columns)}")
    return total_missing, columns_with_missing


def _print_length_stats(label: str, lengths: list[int], missing: int) -> None:
    """Print the full set of length statistics for one text column."""
    quartiles = statistics.quantiles(lengths, n=4)
    print(f"--- {label} (length in characters) ---")
    print(f"count    : {len(lengths)}  (skipped {missing} missing)")
    print(f"mean     : {statistics.mean(lengths):.1f}")
    print(f"median   : {statistics.median(lengths)}")
    print(f"mode     : {statistics.mode(lengths)}")
    print(f"std dev  : {statistics.stdev(lengths):.1f}")
    print(f"min      : {min(lengths)}")
    print(f"25%      : {quartiles[0]:.1f}")
    print(f"75%      : {quartiles[2]:.1f}")
    print(f"max      : {max(lengths)}")
    sorted_lengths = sorted(lengths)
    print(f"95th pct : {sorted_lengths[int(len(sorted_lengths) * 0.95)]}")


def analyse_text_lengths(unique_rows: list[dict]) -> None:
    """Print length statistics for description and for name."""
    for column in ("description", "name"):
        values = [row.get(column) for row in unique_rows]
        lengths = [len(v) for v in values if not _is_missing(v)]
        _print_length_stats(column, lengths, len(values) - len(lengths))


def text_length_distribution(cleaned_rows: list[dict], column: str = "description") -> dict:
    """How long are the texts of one column, and is there a long tail?

    column is "description" (default) or "risk_description".
    Length is counted in characters. Missing texts are skipped.
    Prints the numbers, saves plots/<column>_length.png (log scale, so the
    tail stays visible) and returns the numbers as a dict.
    The "long tail" check: long_tail is True when the 99th percentile is more
    than 5x the median. Rows longer than 3x the median are also counted.
    """
    lengths = sorted(
        len(row[column]) for row in cleaned_rows if not _is_missing(row.get(column))
    )
    count = len(lengths)
    median = statistics.median(lengths)
    percentile = lambda p: lengths[min(count - 1, int(count * p))]
    result = {
        "count": count,
        "min": lengths[0],
        "median": median,
        "mean": statistics.mean(lengths),
        "p90": percentile(0.90),
        "p95": percentile(0.95),
        "p99": percentile(0.99),
        "max": lengths[-1],
        "longer_than_3x_median": sum(1 for n in lengths if n > 3 * median),
    }
    result["long_tail"] = result["p99"] > 5 * median
    for key, value in result.items():
        print(f"{key:<22}: {value:.1f}" if isinstance(value, float) else f"{key:<22}: {value}")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(lengths, bins=50)
    ax.set_yscale("log")
    ax.set_title(f"{column} length (characters, log count)")
    ax.set_xlabel("characters")
    ax.set_ylabel("number of alerts (log)")
    PLOTS_DIR.mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / f"{column}_length.png", dpi=120)
    plt.close(fig)
    return result


def length_by_group(
    cleaned_rows: list[dict], group_by: str = "category", min_count: int = 30, top_n: int = 15
) -> dict:
    """Does the description length change across groups (category or product)?

    Length is counted in characters; rows with a missing description or group are
    skipped. Only groups with at least min_count rows are kept (a median of 3 rows
    means little), and only the top_n biggest of those are shown.
    Prints count / median / mean / 95th percentile per group, saves
    plots/description_length_by_<group_by>.png (boxplots, sorted by median) and
    returns {group: {"count", "median", "mean", "p95"}} for the shown groups.
    """
    lengths_by_group: dict[str, list[int]] = {}
    for row in cleaned_rows:
        group, text = row.get(group_by), row.get("description")
        if not _is_missing(group) and not _is_missing(text):
            lengths_by_group.setdefault(group, []).append(len(text))

    big_groups = [(g, v) for g, v in lengths_by_group.items() if len(v) >= min_count]
    big_groups = sorted(big_groups, key=lambda item: len(item[1]), reverse=True)[:top_n]
    big_groups.sort(key=lambda item: statistics.median(item[1]))

    result = {}
    print(f"{group_by:<42}{'count':>7}{'median':>8}{'mean':>8}{'p95':>6}")
    for group, lengths in big_groups:
        ordered = sorted(lengths)
        result[group] = {
            "count": len(lengths),
            "median": statistics.median(lengths),
            "mean": statistics.mean(lengths),
            "p95": ordered[int(len(ordered) * 0.95)],
        }
        stats = result[group]
        print(f"{group[:41]:<42}{stats['count']:>7}{stats['median']:>8.0f}{stats['mean']:>8.1f}{stats['p95']:>6}")

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.boxplot([v for _, v in big_groups], vert=False, showfliers=False)
    ax.set_yticklabels([f"{g[:30]} (n={len(v)})" for g, v in big_groups])
    ax.set_title(f"Description length by {group_by} (top {len(big_groups)} groups, sorted by median)")
    ax.set_xlabel("characters (outliers hidden)")
    fig.tight_layout()
    PLOTS_DIR.mkdir(exist_ok=True)
    fig.savefig(PLOTS_DIR / f"description_length_by_{group_by}.png", dpi=120)
    plt.close(fig)
    return result


def _plot_heatmap(matrix, row_labels, col_labels, title, filename, unit="%") -> None:
    """Draw a heatmap with the number written in every cell and save it as a .png."""
    fig, ax = plt.subplots(figsize=(13, 0.5 * len(row_labels) + 3))
    image = ax.imshow(matrix, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(col_labels)), col_labels, rotation=45, ha="right")
    ax.set_yticks(range(len(row_labels)), row_labels)
    top = max(max(row) for row in matrix) or 1
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            if value:
                color = "white" if value > top * 0.6 else "black"
                ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=7, color=color)
    ax.set_title(title)
    fig.colorbar(image, ax=ax, label=unit)
    fig.tight_layout()
    PLOTS_DIR.mkdir(exist_ok=True)
    fig.savefig(PLOTS_DIR / filename, dpi=120)
    plt.close(fig)


def risk_type_by_category(cleaned_rows: list[dict], top_n: int = 10) -> dict:
    """Which risk types go with which category?

    Rows are the top_n biggest categories, columns are the risk types. Each number
    is the % of that category's alerts that have the risk type (an alert can have
    several risk types, so a row can add up to more than 100%).
    Prints the table, saves plots/risk_type_by_category.png and returns
    {category: {risk_type: percent}}.
    """
    categories = Counter(row["category"] for row in cleaned_rows if not _is_missing(row.get("category")))
    top_categories = [name for name, _ in categories.most_common(top_n)]
    risk_totals = Counter(risk for row in cleaned_rows for risk in (row.get("risk_types") or []))
    risks = [name for name, _ in risk_totals.most_common()]

    counts = {category: Counter() for category in top_categories}
    for row in cleaned_rows:
        if row.get("category") in counts:
            counts[row["category"]].update(row.get("risk_types") or [])
    result = {
        category: {risk: counts[category][risk] / categories[category] * 100 for risk in risks}
        for category in top_categories
    }
    print(f"{'category':<42}{'alerts':>7}  top 3 risk types (% of the category's alerts)")
    for category in top_categories:
        best = sorted(result[category].items(), key=lambda item: item[1], reverse=True)[:3]
        text = ", ".join(f"{risk} {percent:.0f}%" for risk, percent in best)
        print(f"{category[:41]:<42}{categories[category]:>7}  {text}")
    matrix = [[result[category][risk] for risk in risks] for category in top_categories]
    labels = [f"{category[:32]} (n={categories[category]})" for category in top_categories]
    _plot_heatmap(matrix, labels, risks, "% of a category's alerts with each risk type", "risk_type_by_category.png")
    return result


def _law_kind(name: str) -> str:
    """Directive, Regulation, Decision or Other: read from the words in the law name."""
    for kind in ("Directive", "Regulation", "Decision"):
        if kind in name:
            return kind
    return "Other"


def law_name_types(cleaned_rows: list[dict]) -> dict:
    """What kinds of law names are there, and how many per alert?

    Counts the different law names, sorts them into Directive / Regulation /
    Decision / Other (by the word in the name), counts laws per alert, and saves
    plots/law_names.png (alerts per law). Returns the numbers as a dict.
    """
    per_law = Counter(law for row in cleaned_rows for law in (row.get("law_names") or []))
    kinds = Counter(_law_kind(law) for law in per_law)
    alerts_per_kind = Counter()
    for law, count in per_law.items():
        alerts_per_kind[_law_kind(law)] += count
    laws_per_alert = Counter(len(row.get("law_names") or []) for row in cleaned_rows)

    print(f"{len(per_law)} different law names")
    print("different law names per kind:", dict(kinds))
    print("law mentions per kind       :", dict(alerts_per_kind))
    print("laws per alert (0, 1, 2, ...):", dict(sorted(laws_per_alert.items())))
    _plot_top_counts(per_law, "Alerts per law name (top 15)", "law_names.png", 15)
    return {"per_law": per_law, "kinds": kinds, "alerts_per_kind": alerts_per_kind, "laws_per_alert": laws_per_alert}


def law_risk_category(cleaned_rows: list[dict], top_n: int = 12) -> dict:
    """Law name vs risk type vs category, in one picture.

    Rows are the top_n most common law names, columns are the risk types, and each
    number is the % of that law's alerts with the risk type. The row label also
    gives the law's most common category and its share. An alert with several laws
    counts for each of them. Returns {law: {"alerts", "top_category", "category_share", "top_risk"}}.
    """
    law_counts = Counter(law for row in cleaned_rows for law in (row.get("law_names") or []))
    top_laws = [law for law, _ in law_counts.most_common(top_n)]
    risk_totals = Counter(risk for row in cleaned_rows for risk in (row.get("risk_types") or []))
    risks = [name for name, _ in risk_totals.most_common()]

    risk_counts = {law: Counter() for law in top_laws}
    category_counts = {law: Counter() for law in top_laws}
    for row in cleaned_rows:
        for law in row.get("law_names") or []:
            if law in risk_counts:
                risk_counts[law].update(row.get("risk_types") or [])
                category_counts[law][row.get("category")] += 1

    result, labels, matrix = {}, [], []
    print(f"{'law name':<48}{'alerts':>7}  {'top category':<34}{'top risk type'}")
    for law in top_laws:
        total = law_counts[law]
        category, in_category = category_counts[law].most_common(1)[0]
        risk, in_risk = risk_counts[law].most_common(1)[0]
        result[law] = {
            "alerts": total, "top_category": category,
            "category_share": in_category / total * 100, "top_risk": risk,
        }
        print(f"{law[:47]:<48}{total:>7}  {f'{category[:22]} {in_category / total * 100:.0f}%':<34}{risk} {in_risk / total * 100:.0f}%")
        labels.append(f"{law[:36]} (n={total}; {category[:18]} {in_category / total * 100:.0f}%)")
        matrix.append([risk_counts[law][r] / total * 100 for r in risks])
    _plot_heatmap(matrix, labels, risks, "% of a law's alerts with each risk type (label: top category)", "law_risk_category.png")
    return result


def time_trend(alerts: list[dict]) -> dict:
    """Does the data change over time?

    Input: the RAW alerts (clean_row drops report_date). Counts alerts per quarter
    and per year, and shows how the category mix and the main risk types change by
    year. Saves plots/time_trend.png (3 panels) and returns the numbers as a dict.
    """
    def quarter(date: str) -> str:
        return f"{date[:4]}-Q{(int(date[5:7]) - 1) // 3 + 1}"

    per_quarter = Counter(quarter(a["report_date"]) for a in alerts)
    per_year = Counter(a["report_date"][:4] for a in alerts)
    years = sorted(per_year)
    print("alerts per year   :", dict(sorted(per_year.items())))
    print("alerts per quarter:", dict(sorted(per_quarter.items())))
    print(f"date range: {min(a['report_date'] for a in alerts)} to {max(a['report_date'] for a in alerts)}")

    top_categories = [c for c, _ in Counter(a["category"] for a in alerts).most_common(6)]
    category_share = {y: {} for y in years}
    top_risks = [r for r, _ in Counter(x for a in alerts for x in a["risk_types"]).most_common(5)]
    risk_share = {y: {} for y in years}
    print(f"\n{'% of the year':<40}" + "".join(f"{y:>8}" for y in years))
    for year in years:
        rows = [a for a in alerts if a["report_date"][:4] == year]
        for category in top_categories:
            category_share[year][category] = sum(a["category"] == category for a in rows) / len(rows) * 100
        category_share[year]["Other"] = 100 - sum(category_share[year].values())
        for risk in top_risks:
            risk_share[year][risk] = sum(risk in a["risk_types"] for a in rows) / len(rows) * 100
    for category in top_categories + ["Other"]:
        print(f"{category[:38]:<40}" + "".join(f"{category_share[y][category]:>7.1f}%" for y in years))
    print()
    for risk in top_risks:
        print(f"risk: {risk:<34}" + "".join(f"{risk_share[y][risk]:>7.1f}%" for y in years))

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    quarters = sorted(per_quarter)
    axes[0].bar(quarters, [per_quarter[q] for q in quarters])
    axes[0].set_title("Alerts per quarter (last quarter is partial)")
    axes[0].tick_params(axis="x", rotation=60)
    bottom = [0] * len(years)
    for category in top_categories + ["Other"]:
        heights = [category_share[y][category] for y in years]
        axes[1].bar(years, heights, bottom=bottom, label=category[:28])
        bottom = [b + h for b, h in zip(bottom, heights)]
    axes[1].set_title("Category mix by year (% of the year)")
    axes[1].legend(fontsize=7, loc="upper left", bbox_to_anchor=(1, 1))
    for risk in top_risks:
        axes[2].plot(years, [risk_share[y][risk] for y in years], marker="o", label=risk)
    axes[2].set_title("Top risk types by year (% of the year's alerts)")
    axes[2].legend(fontsize=8)
    fig.tight_layout()
    PLOTS_DIR.mkdir(exist_ok=True)
    fig.savefig(PLOTS_DIR / "time_trend.png", dpi=120)
    plt.close(fig)
    return {"per_year": per_year, "per_quarter": per_quarter, "category_share": category_share, "risk_share": risk_share}


def similar_descriptions_share_risk(cleaned_rows: list[dict], k: int = 5) -> dict:
    """Do alerts with similar descriptions share a risk type? (no embeddings, TF-IDF)

    Text = product + description. For every alert, find the k most similar OTHER
    alerts (cosine similarity on TF-IDF words). Two settings: all neighbours, and
    without neighbours whose text is identical (twins make the result look too good).
    A "hit" means the predicted risk type is one of the alert's true risk types.
      top1_any   : the closest neighbour shares at least one risk type
      top1_exact : the closest neighbour has exactly the same set of risk types
      vote_hit   : the most common risk among the k neighbours is a true one
                   (a tie goes to the closer neighbour)
    Baselines: always predict the most common risk type, and always predict the
    most common risk of the alert's category. Saves plots/similar_share_risk.png
    (per category) and returns the numbers as a dict.
    """
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer

    texts = [f"{row['product']}. {row['description']}" for row in cleaned_rows]
    risks = [set(row["risk_types"]) for row in cleaned_rows]
    categories = [row["category"] for row in cleaned_rows]
    n = len(texts)
    matrix = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2).fit_transform(texts)
    _, text_group = np.unique(np.array([t.lower() for t in texts]), return_inverse=True)

    def neighbours(skip_twins: bool) -> list[list[int]]:
        found = []
        for start in range(0, n, 500):
            sims = (matrix[start:start + 500] @ matrix.T).toarray()
            for offset in range(sims.shape[0]):
                row = start + offset
                sims[offset, row] = -1
                if skip_twins:
                    sims[offset, text_group == text_group[row]] = -1
            top = np.argpartition(-sims, k, axis=1)[:, :k]
            for offset in range(sims.shape[0]):
                order = top[offset][np.argsort(-sims[offset, top[offset]])]
                found.append([int(j) for j in order if sims[offset, j] >= 0])
        return found

    risk_counts = Counter(r for rs in risks for r in rs)
    most_common_risk = risk_counts.most_common(1)[0][0]
    by_category: dict[str, Counter] = {}
    for category, rs in zip(categories, risks):
        by_category.setdefault(category, Counter()).update(rs)
    category_guess = {c: counts.most_common(1)[0][0] for c, counts in by_category.items()}

    def score(found, rows=None):
        rows = range(n) if rows is None else rows
        top1_any = top1_exact = vote = used = 0
        for i in rows:
            if not found[i]:
                continue
            used += 1
            best = found[i][0]
            top1_any += bool(risks[i] & risks[best])
            top1_exact += risks[i] == risks[best]
            votes = Counter(r for j in found[i] for r in sorted(risks[j]))
            vote += votes.most_common(1)[0][0] in risks[i]
        return {"alerts": used, "top1_any": top1_any / used * 100, "top1_exact": top1_exact / used * 100, "vote_hit": vote / used * 100}

    result = {
        "baseline_most_common_risk": (most_common_risk, sum(most_common_risk in rs for rs in risks) / n * 100),
        "baseline_category_majority": sum(category_guess[c] in rs for c, rs in zip(categories, risks)) / n * 100,
    }
    for name, skip in (("all neighbours", False), ("without identical-text neighbours", True)):
        found = neighbours(skip)
        result[name] = score(found)
        if skip:
            top = [c for c, _ in Counter(categories).most_common(10)]
            result["per_category"] = {
                c: {
                    **score(found, [i for i in range(n) if categories[i] == c]),
                    "category_majority": sum(category_guess[c] in risks[i] for i in range(n) if categories[i] == c)
                    / categories.count(c) * 100,
                    "alerts_in_category": categories.count(c),
                }
                for c in top
            }
    print(f"baseline: always '{most_common_risk}' -> hit {result['baseline_most_common_risk'][1]:.1f}%")
    print(f"baseline: most common risk of the category -> hit {result['baseline_category_majority']:.1f}%")
    for name in ("all neighbours", "without identical-text neighbours"):
        r = result[name]
        print(f"{name:<34} top1_any {r['top1_any']:.1f}%  top1_exact {r['top1_exact']:.1f}%  vote_hit(k={k}) {r['vote_hit']:.1f}%")
    print(f"\n{'category (no identical-text neighbours)':<42}{'alerts':>7}{'top1_any':>10}{'vote':>7}{'category majority':>19}")
    for c, r in result["per_category"].items():
        print(f"{c[:41]:<42}{r['alerts_in_category']:>7}{r['top1_any']:>9.1f}%{r['vote_hit']:>6.1f}%{r['category_majority']:>18.1f}%")

    names = list(result["per_category"])[::-1]
    positions = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(10, 6.5))
    ax.barh(positions + 0.2, [result["per_category"][c]["vote_hit"] for c in names], 0.4, label=f"{k} similar alerts vote")
    ax.barh(positions - 0.2, [result["per_category"][c]["category_majority"] for c in names], 0.4, label="category's most common risk")
    ax.set_yticks(positions, [f"{c[:34]} (n={result['per_category'][c]['alerts_in_category']})" for c in names])
    ax.set_xlabel("% of alerts where the guess is one of the true risk types")
    ax.set_title("Similar descriptions vs a plain category guess (identical texts left out)")
    ax.legend()
    fig.tight_layout()
    PLOTS_DIR.mkdir(exist_ok=True)
    fig.savefig(PLOTS_DIR / "similar_share_risk.png", dpi=120)
    plt.close(fig)
    return result


# Words that name a danger directly, per risk type (matched at the start of a word).
HINT_WORDS = {
    "Chemical": [r"toxic", r"cadmium", r"mercury", r"formaldehyde", r"phthalate", r"chemical"],
    "Injuries": [r"injur"],
    "Choking": [r"chok", r"small part"],
    "Electric shock": [r"shock", r"live part"],
    "Fire": [r"fire\b", r"flammab", r"ignit", r"overheat"],
    "Burns": [r"burn", r"scald"],
    "Strangulation": [r"strangul", r"drawstring"],
    "Suffocation": [r"suffocat"],
    "Drowning": [r"drown"],
}


def leakage_check(cleaned_rows: list[dict]) -> dict:
    """How often does the product text already name the danger?

    Looks for danger words (HINT_WORDS) in product + description. For each risk type:
    how many alerts contain its words, and how many of those really have the risk
    ("precision"). Also: the share of all alerts where the text names one of the
    alert's own risk types. Saves plots/leakage_check.png and returns the numbers.
    """
    patterns = {
        risk: re.compile("|".join(rf"\b{word}" for word in words))
        for risk, words in HINT_WORDS.items()
    }
    result = {}
    own_hint = 0
    for row in cleaned_rows:
        text = f"{row['product']} {row['description']}".lower()
        hits = {risk for risk, pattern in patterns.items() if pattern.search(text)}
        own_hint += bool(hits & set(row["risk_types"]))
        for risk in hits:
            stats = result.setdefault(risk, {"alerts_with_word": 0, "really_has_risk": 0})
            stats["alerts_with_word"] += 1
            stats["really_has_risk"] += risk in row["risk_types"]
    print(f"{'risk type':<18}{'alerts with its words':>23}{'really have the risk':>22}{'precision':>11}")
    for risk in HINT_WORDS:
        stats = result.get(risk, {"alerts_with_word": 0, "really_has_risk": 0})
        result[risk] = stats
        share = stats["really_has_risk"] / stats["alerts_with_word"] * 100 if stats["alerts_with_word"] else 0
        print(f"{risk:<18}{stats['alerts_with_word']:>23}{stats['really_has_risk']:>22}{share:>10.0f}%")
    total = len(cleaned_rows)
    print(f"\nAlerts whose text names one of their own risk types: {own_hint} of {total} ({own_hint / total * 100:.1f}%)")
    result["own_risk_named"] = own_hint

    risks = list(HINT_WORDS)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.barh(risks[::-1], [result[r]["alerts_with_word"] for r in risks][::-1], label="text has the word")
    ax.barh(risks[::-1], [result[r]["really_has_risk"] for r in risks][::-1], label="and the alert has that risk")
    ax.set_title("Danger words in product text (how many are real hints)")
    ax.set_xlabel("alerts")
    ax.legend()
    fig.tight_layout()
    PLOTS_DIR.mkdir(exist_ok=True)
    fig.savefig(PLOTS_DIR / "leakage_check.png", dpi=120)
    plt.close(fig)
    return result


def multi_risk_alerts(cleaned_rows: list[dict], top_pairs: int = 10, top_n: int = 10) -> dict:
    """Which alerts have several risk types, and which risks go together?

    Counts risk types per alert, the most common pairs, and the share of alerts
    with 2+ risk types in the top_n categories. Saves plots/multi_risk.png and
    returns the numbers as a dict.
    """
    sizes = Counter(len(row["risk_types"]) for row in cleaned_rows)
    total = len(cleaned_rows)
    multi = sum(count for size, count in sizes.items() if size >= 2)
    print("risk types per alert:", dict(sorted(sizes.items())))
    print(f"alerts with 2+ risk types: {multi} of {total} ({multi / total * 100:.1f}%)")

    pairs = Counter()
    for row in cleaned_rows:
        for pair in combinations(sorted(set(row["risk_types"])), 2):
            pairs[pair] += 1
    print(f"\n{'pair of risk types':<40}{'alerts':>8}{'% of multi-risk alerts':>24}")
    for pair, count in pairs.most_common(top_pairs):
        print(f"{' + '.join(pair):<40}{count:>8}{count / multi * 100:>23.1f}%")

    categories = Counter(row["category"] for row in cleaned_rows)
    share = {}
    print(f"\n{'category':<42}{'alerts':>7}{'with 2+ risks':>15}")
    for category, count in categories.most_common(top_n):
        with_many = sum(1 for row in cleaned_rows if row["category"] == category and len(row["risk_types"]) >= 2)
        share[category] = with_many / count * 100
        print(f"{category[:41]:<42}{count:>7}{share[category]:>14.1f}%")

    fig, axes = plt.subplots(1, 2, figsize=(16, 5.5))
    labels, values = zip(*[(" + ".join(pair), count) for pair, count in pairs.most_common(top_pairs)][::-1])
    axes[0].barh(labels, values)
    axes[0].set_title("Most common risk-type pairs (alerts)")
    names = list(share)[::-1]
    axes[1].barh([f"{c[:34]} (n={categories[c]})" for c in names], [share[c] for c in names])
    axes[1].set_title("% of alerts with 2+ risk types")
    fig.tight_layout()
    PLOTS_DIR.mkdir(exist_ok=True)
    fig.savefig(PLOTS_DIR / "multi_risk.png", dpi=120)
    plt.close(fig)
    return {"sizes": sizes, "multi": multi, "pairs": pairs, "share_by_category": share}


def product_variety(cleaned_rows: list[dict], top_n: int = 15) -> dict:
    """How many different products are there, and how are the alerts spread over them?

    Counts the different product names (as written, and after lower-casing and
    trimming), how many appear only once, how many alerts the biggest products
    cover, and how many products sit in more than one category.
    Saves plots/product_variety.png (top products, and the coverage curve) and
    returns the numbers as a dict.
    """
    total = len(cleaned_rows)
    counts = Counter(row["product"] for row in cleaned_rows)
    merged = Counter()
    for product, count in counts.items():
        merged[product.strip().lower()] += count
    categories_per_product: dict[str, set] = {}
    for row in cleaned_rows:
        categories_per_product.setdefault(row["product"], set()).add(row["category"])

    ordered = [count for _, count in counts.most_common()]
    coverage = {top: sum(ordered[:top]) / total * 100 for top in (10, 50, 100, 500)}
    result = {
        "distinct": len(counts),
        "distinct_after_lowercase": len(merged),
        "only_once": sum(1 for c in ordered if c == 1),
        "at_most_5": sum(1 for c in ordered if c <= 5),
        "at_least_30": sum(1 for c in ordered if c >= 30),
        "at_least_100": sum(1 for c in ordered if c >= 100),
        "in_several_categories": sum(1 for cats in categories_per_product.values() if len(cats) > 1),
        "coverage": coverage,
        "top": counts.most_common(top_n),
    }
    print(f"{result['distinct']} different products as written, {result['distinct_after_lowercase']} after lower-casing")
    print(f"appear once: {result['only_once']}, at most 5 times: {result['at_most_5']}, "
          f"30+ times: {result['at_least_30']}, 100+ times: {result['at_least_100']}")
    print("share of all alerts covered by the biggest products:",
          ", ".join(f"top {top}: {share:.1f}%" for top, share in coverage.items()))
    print(f"products found in more than one category: {result['in_several_categories']}")
    print(f"\n{'top products':<40}{'alerts':>7}{'share':>8}{'cumulative':>12}")
    running = 0
    for product, count in counts.most_common(top_n):
        running += count
        print(f"{product[:39]:<40}{count:>7}{count / total * 100:>7.1f}%{running / total * 100:>11.1f}%")

    fig, axes = plt.subplots(1, 2, figsize=(16, 5.5))
    labels, values = zip(*counts.most_common(top_n)[::-1])
    axes[0].barh(labels, values)
    axes[0].set_title(f"Top {top_n} products (alerts)")
    running_share, cumulative = 0, []
    for count in ordered:
        running_share += count
        cumulative.append(running_share / total * 100)
    axes[1].plot(range(1, len(cumulative) + 1), cumulative)
    axes[1].set_xscale("log")
    axes[1].set_xlabel("number of products (biggest first, log scale)")
    axes[1].set_ylabel("% of all alerts covered")
    axes[1].set_title("How many products cover how many alerts")
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    PLOTS_DIR.mkdir(exist_ok=True)
    fig.savefig(PLOTS_DIR / "product_variety.png", dpi=120)
    plt.close(fig)
    return result


def product_vs_risk(cleaned_rows: list[dict], min_count: int = 30, top_n: int = 15) -> dict:
    """Does a product tell you its risk type?

    Only products with at least min_count alerts are used (a single alert proves
    nothing). Shows, for the top_n biggest of them, the % of their alerts with each
    risk type, and sorts all of them by how pure they are (% of the most common risk).
    Also a fair test: for each alert, guess the most common risk of the OTHER alerts
    with the same product (leave one out) and compare it with the same guess by
    category. A hit means the guess is one of the alert's true risk types.
    Saves plots/product_vs_risk.png and returns the numbers as a dict.
    """
    product_counts = Counter(row["product"] for row in cleaned_rows)
    big = [p for p, c in product_counts.items() if c >= min_count]
    risk_totals = Counter(r for row in cleaned_rows for r in row["risk_types"])
    risks = [r for r, _ in risk_totals.most_common()]

    risk_by_product = {p: Counter() for p in big}
    risk_by_category: dict[str, Counter] = {}
    for row in cleaned_rows:
        if row["product"] in risk_by_product:
            risk_by_product[row["product"]].update(row["risk_types"])
        risk_by_category.setdefault(row["category"], Counter()).update(row["risk_types"])
    category_counts = Counter(row["category"] for row in cleaned_rows)

    purity = {}
    for product in big:
        top_risk, top_count = risk_by_product[product].most_common(1)[0]
        purity[product] = {"alerts": product_counts[product], "top_risk": top_risk, "purity": top_count / product_counts[product] * 100}
    bands = {
        "90% or more": sum(1 for v in purity.values() if v["purity"] >= 90),
        "60 to 90%": sum(1 for v in purity.values() if 60 <= v["purity"] < 90),
        "under 60%": sum(1 for v in purity.values() if v["purity"] < 60),
    }
    print(f"{len(big)} products with {min_count}+ alerts, covering "
          f"{sum(product_counts[p] for p in big)} of {len(cleaned_rows)} alerts")
    print("products by how pure their most common risk is:", bands)

    product_hit = category_hit = used = 0
    for row in cleaned_rows:
        product = row["product"]
        if product not in risk_by_product:
            continue
        used += 1
        own = Counter(row["risk_types"])
        product_guess = (risk_by_product[product] - own).most_common(1)[0][0]
        category_options = (risk_by_category[row["category"]] - own).most_common(1)
        product_hit += product_guess in row["risk_types"]
        # a category with no other alert gives no guess, which counts as a miss
        category_hit += bool(category_options) and category_options[0][0] in row["risk_types"]
    result = {
        "products_used": len(big), "alerts_used": used, "bands": bands, "purity": purity,
        "product_guess_hit": product_hit / used * 100, "category_guess_hit": category_hit / used * 100,
    }
    print(f"guess from the product's other alerts: {result['product_guess_hit']:.1f}% hit")
    print(f"guess from the category's other alerts (same alerts): {result['category_guess_hit']:.1f}% hit")

    shown = [p for p, _ in product_counts.most_common() if p in risk_by_product][:top_n]
    print(f"\n{'product':<36}{'alerts':>7}  top 3 risk types (% of the product's alerts)")
    for product in shown:
        best = risk_by_product[product].most_common(3)
        text = ", ".join(f"{r} {c / product_counts[product] * 100:.0f}%" for r, c in best)
        print(f"{product[:35]:<36}{product_counts[product]:>7}  {text}")
    matrix = [[risk_by_product[p][r] / product_counts[p] * 100 for r in risks] for p in shown]
    _plot_heatmap(matrix, [f"{p[:30]} (n={product_counts[p]})" for p in shown], risks,
                  "% of a product's alerts with each risk type", "product_vs_risk.png")
    result["shown"] = shown
    result["mixed_products"] = sorted(
        ((p, v["alerts"], v["top_risk"], v["purity"]) for p, v in purity.items() if v["purity"] < 60),
        key=lambda item: -item[1],
    )
    return result


def _plot_top_counts(counts: Counter, title: str, filename: str, top_n: int = 15) -> None:
    """Draw a horizontal bar chart of the top_n most common values and save it as a .png."""
    labels, numbers = zip(*counts.most_common(top_n))
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(labels[::-1], numbers[::-1])
    ax.set_title(title)
    ax.set_xlabel("number of alerts")
    for position, number in enumerate(numbers[::-1]):
        ax.text(number, position, f" {number}", va="center")
    fig.tight_layout()
    PLOTS_DIR.mkdir(exist_ok=True)
    path = PLOTS_DIR / filename
    fig.savefig(path, dpi=120)
    print(f"Saved {path}")
    plt.show()
    plt.close(fig)


def plot_top_categories_brands_countries(unique_rows: list[dict], top_n: int = 15) -> None:
    """Plot which category, brand and country_of_origin appear in the most alerts."""
    for column in ("category", "brand", "country_of_origin"):
        counts = Counter(row[column] for row in unique_rows if not _is_missing(row.get(column)))
        print(f"{column}: {len(counts)} different values. Top 5: {counts.most_common(5)}")
        _plot_top_counts(counts, f"Top {top_n} {column}", f"top_{column}.png", top_n)


def plot_risk_types(alerts: list[dict], top_n: int = 15) -> None:
    """Plot the most common risk types. Input: the raw alerts from knowledge.jsonl.

    One alert can have several risk types, so each one is counted separately.
    """
    counts = Counter(risk for alert in alerts for risk in (alert.get("risk_types") or []))
    print(f"risk_types: {len(counts)} different values. Top 5: {counts.most_common(5)}")
    _plot_top_counts(counts, f"Top {top_n} risk types", "top_risk_types.png", top_n)


if __name__ == "__main__":
    alerts = load_alerts(KNOWLEDGE_PATH)
    cleaned_rows = clean_row(alerts)
    show_overview(cleaned_rows)
    unique_rows = check_duplicates(cleaned_rows)
    print(f"New variable unique_rows, first 5 of {len(unique_rows)}:")
    for row in unique_rows[:5]:
        print(json.dumps(row, ensure_ascii=False))
    check_missing_and_types(unique_rows)
    analyse_text_lengths(unique_rows)
    plot_top_categories_brands_countries(unique_rows)
    plot_risk_types(alerts)
