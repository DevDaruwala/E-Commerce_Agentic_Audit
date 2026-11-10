"""The text and charts of reports/probe.qmd. It only READS saved results (CSV files).

Every number in a sentence is filled in from a CSV. The fixed words below contain no results.
A probe whose CSV is missing shows a grey box: "Not run yet (session N)" or "Not available: reason".
Each probe has its own renderer; the qmd calls show("C10") and the right block appears.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from boxes.probe_charts import (FIG_SIZE, GREY, COLORS, HATCH, LABELS, LEAK_RED, VERDICT_COLORS, chance_line, dot_whisker, error_reason,
                                fmt, grey_box, grouped_bars, heatmap, hist4, howto, line_chart, load_csv,
                                not_run_box, say, scorecard, finish)

# In which session each probe group is built (shown in the "Not run yet" box).
SESSIONS = {"F0": "session 1a", "C10": "session 1b", "C11": "session 1b", "C12": "session 1b", "C13": "session 1b",
            "A1": "session 2", "A2": "session 2", "A3": "session 2",
            "D14": "session 3", "D15": "session 3", "D16": "session 3", "D17": "session 3",
            "B4": "session 4", "B5": "session 4", "B6": "session 4", "B7": "session 4", "B8": "session 4", "B9": "session 4",
            "E18": "session 5", "E19": "session 5", "E20": "session 5",
            "F21": "session 5", "F22": "session 5", "F23": "session 5", "F24": "session 5", "G25": "session 5"}
SCORECARD_PROBES = ["C10", "C11", "C12", "C13", "A1", "A2", "A3", "D14", "D15", "D16", "D17",
                    "B4", "B5", "B6", "B7", "B8", "B9", "E18", "E19", "E20", "F21", "F22", "G25"]
RENDERERS = {}          # probe id -> function that draws its block (filled in below and by the groups)


def renderer(probe: str):
    """Decorator: register the function that draws the block of one probe."""
    def register(function):
        RENDERERS[probe] = function
        return function
    return register


def show(probe: str) -> None:
    """Draw the block of one probe, or a grey box if it has no renderer or no results yet."""
    if probe in RENDERERS:
        try:
            RENDERERS[probe]()
        except Exception as problem:          # the report must always render
            plt.close("all")
            grey_box(f"Not available: this block could not be drawn ({type(problem).__name__}: {str(problem)[:80]})")
    else:
        question = QUESTIONS.get(probe, "")
        if question:
            say(f"**The question.** {question}")
        not_run_box(SESSIONS.get(probe, "a later session"))


def md_table(frame: pd.DataFrame) -> str:
    """A pandas table as a Markdown table (works in HTML and in the PDF)."""
    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    divider = "|" + "|".join("---" for _ in frame.columns) + "|"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, divider] + body)


def meaning(probe: str) -> None:
    """'What it means' and 'Decision' from verdicts.csv, written by the probe code."""
    verdicts = load_csv("verdicts")
    if verdicts is None or verdicts[verdicts["probe"] == probe].empty:
        return
    rows = verdicts[verdicts["probe"] == probe]
    parts = []
    for _, r in rows.iterrows():
        who = LABELS.get(int(r["collection_id"]), "all collections") if str(r["collection_id"]).isdigit() else "all collections"
        parts.append(f"{who}: **{r['verdict']}**")
    claim = rows.iloc[0]["claim"]
    say(f"**What it means.** The claim was: *{claim}*. Verdict: " + "; ".join(parts) + ".")
    # Prefer the decision of a collection where the probe applies (not the "not available" ones).
    applicable = rows[rows["verdict"] != "not available"]
    decision = (applicable if not applicable.empty else rows).iloc[0]["decision"]
    if isinstance(decision, str) and decision:
        say(f"**Decision.** {decision}")


def block(probe: str, question: str, how: str, needs: list, draw, see=None) -> None:
    """The standard block: question, how it was tested, figures, what you see, what it means, decision."""
    say(f"**The question.** {question}")
    say(f"**How it was tested.** {how}")
    data = {name: load_csv(name) for name in needs}
    if any(frame is None for frame in data.values()):
        reason = error_reason(probe)
        if probe == "B9":
            grey_box("Waiting for Dev (the substance list is not approved yet)")
        else:
            grey_box(f"Not available: {reason}" if reason else f"Not run yet ({SESSIONS.get(probe, 'a later session')})")
        return
    draw(data)
    if see:
        say("**What you see.** " + see(data))
    meaning(probe)


QUESTIONS = {"C10": "How well would a search do by pure luck?", "C11": "Do near-copies of library alerts make the score look better than it is?",
             "C12": "What happens if the risk text leaks into the question?", "C13": "Is any dev alert also in the library?"}


# ===========================================================================================
# Page 1: Read this first (bullets, scorecard, glossary, how to read the charts)
# ===========================================================================================
def best_collection():
    """(collection id, its row of F21 numbers) of the best collection by precision@5, or None."""
    f21 = load_csv("F21_compare_k5")
    if f21 is None:
        return None
    p = f21[(f21["metric"] == "precision_at_5") & (f21["collection_id"].astype(str).isin(["1", "2", "3", "4"]))]
    if p.empty:
        return None
    best = p.loc[p["value"].idxmax()]
    return int(best["collection_id"]), f21


def read_first_bullets() -> None:
    """The 5 plain bullets at the top. Each one says 'Not run yet' until its CSV exists."""
    lines = []
    found = best_collection()
    # 1. best collection and 2. how far above luck
    if found:
        cid, f21 = found
        def get(metric):
            return float(f21[(f21["metric"] == metric) & (f21["collection_id"].astype(str) == str(cid))]["value"].iloc[0])
        p5, lift = get("precision_at_5"), get("lift")
        lines.append(f"- **Best collection:** {LABELS[cid]}. Its five nearest neighbours share a danger with the new alert "
                     f"about {fmt(p5 * 100, 0)} times in a hundred.")
        lines.append(f"- **How far above luck:** {fmt(lift, 1)} times better than picking five random alerts "
                     f"(luck would give {fmt(p5 / lift * 100, 0)} in a hundred).")
    else:
        lines += ["- **Best collection:** not run yet (session 5).", "- **How far above luck:** not run yet (session 5)."]
    # 3. leaks
    c11, c12 = load_csv("C11_leakage"), load_csv("C12_risk_text_leak")
    leak = []
    if c11 is not None:
        row = c11[(c11["threshold"] == 0.95)]
        if not row.empty:
            leak.append(f"between {fmt(row['n_above'].min(), 0)} and {fmt(row['n_above'].max(), 0)} dev alerts have a near-copy "
                        f"(similarity 0.95 or more) in the library, depending on the collection")
    if c12 is not None:
        both = c12[c12["status"] == "ok"]
        if not both.empty:
            leak.append("putting the risk text into the question inflates the score: "
                        + "; ".join(f"{LABELS[int(r.collection_id)]} {fmt(r.precision_at_5, 2)}" for r in both.itertuples()
                                    if r.query_type.startswith("LEAK")) + " (this is not a valid score)")
    lines.append("- **Leaks found:** " + ("; ".join(leak) + "." if leak else "not run yet (session 1b)."))
    # 4. weak risk types
    d15 = load_csv("D15_by_risk_type")
    if d15 is not None and found:
        sub = d15[(d15["collection_id"] == found[0]) & (~d15["small_sample"].astype(bool))]
        weak = sub[sub["precision_at_5"] < sub["chance"] + 0.10].sort_values("precision_at_5")
        names = ", ".join(f"{r.risk_type}" for r in weak.itertuples())
        if names:
            lines.append("- **Weak risk types (best collection):** " + names + " (their score is less than a tenth above luck).")
        elif not sub.empty:
            low = sub.assign(gap=sub["precision_at_5"] - sub["chance"]).sort_values("gap").iloc[0]
            lines.append(f"- **Weak risk types (best collection):** none. Every danger type with enough alerts is clearly above luck; "
                         f"the weakest is {low['risk_type']} ({fmt(low['precision_at_5'])} against luck {fmt(low['chance'])}).")
        else:
            lines.append("- **Weak risk types (best collection):** no danger type has enough alerts to judge.")
    else:
        lines.append("- **Weak risk types:** not run yet (session 3).")
    # 5. cut-off
    g25 = load_csv("G25_cutoff")
    if g25 is not None and found:
        row = g25[g25["collection_id"] == found[0]]
        if not row.empty:
            lines.append(f"- **Weak-match cut-off:** below a similarity of {fmt(row.iloc[0]['suggested_cutoff'], 2)} "
                         "treat the answer as low confidence.")
        else:
            lines.append("- **Weak-match cut-off:** not available.")
    else:
        lines.append("- **Weak-match cut-off:** not run yet (session 5).")
    say("\n".join(lines))


def render_scorecard() -> None:
    verdicts = load_csv("verdicts")
    scorecard(verdicts, SCORECARD_PROBES)
    howto("each row is one probe, each column one collection. Green means the claim held, red means it did not, "
          "amber means we cannot tell, light grey means the probe has not run, blue-grey is a reference number with no claim.")


GLOSSARY = """
- **Alert:** one official report about one dangerous product. Each alert has a text and the dangers (risk types) the inspector found.
- **Library:** the old alerts we search in. It is never changed.
- **Dev:** a separate set of newer alerts we use to try things out. The search never sees their danger labels.
- **Test:** a final set of alerts kept locked away. This report never opens it.
- **Collection:** the library turned into lists of numbers in one particular way. We have four of them (the colours in every chart).
- **Embedding (fingerprint):** a list of numbers that stands for the meaning of a text. Similar texts get similar numbers.
- **Cosine similarity:** how alike two fingerprints are. One means identical, zero means unrelated.
- **Neighbour:** one of the library alerts whose fingerprint is closest to the new alert.
- **precision@5:** of the five closest neighbours, the share that has at least one danger in common with the new alert.
- **Chance level:** the score you would get by picking five random alerts. Every score must be read next to it.
- **Lift:** the score divided by the chance level. More than one means better than luck.
- **Interval (the whiskers):** the range in which the true value very likely lies. A short whisker means we are fairly sure.
- **Small sample:** fewer than thirty alerts. These bars are drawn hollow because they are not reliable.
- **Near-copy:** a dev alert whose best match in the library is almost the same text. It can make a score look too good.
- **Leak:** the answer sneaking into the question. A leaked score is not a real score.
- **Vote accuracy:** the five neighbours vote for a danger. The share of times the winning danger is one of the true ones.
- **Macro-F1:** a fair score over all danger types, so rare dangers count as much as common ones.
- **Anisotropy:** all fingerprints lean in one common direction, so even unrelated texts look somewhat alike.
- **PCA:** a way to squeeze the long list of numbers of each alert down to two, only to draw a picture.
- **Thin text:** a description that adds nothing to the product name.
"""

HOW_TO_READ = """
- A **taller bar** is a better score. The **thin black whisker** is the interval: if two whiskers do not overlap, the difference is probably real.
- The **grey dashed line** is the chance level. A bar must be clearly above it to mean anything.
- The number **n** on a bar is how many alerts it is based on. A **hollow bar** means a small sample.
- **Solid colours** are collections made from plain text. **Hatched colours** are collections whose library text also contains the risk text.
- Every chart has a title that states what it shows, and one line under it that tells you how to read it.
"""


def render_read_first() -> None:
    say("## The five things to know")
    try:
        read_first_bullets()
    except Exception as problem:
        say(f"*The summary could not be built yet ({type(problem).__name__}).*")
    say("## Scorecard")
    try:
        render_scorecard()
        verdicts = load_csv("verdicts")
        if verdicts is not None:
            claims = verdicts.drop_duplicates("probe").set_index("probe")["claim"]
            rows = [[p, claims[p]] for p in SCORECARD_PROBES if p in claims.index]
            say("What each row of the scorecard claims (green: the claim held; red: it did not hold; amber: cannot tell):")
            say(md_table(pd.DataFrame(rows, columns=["Row", "Claim that was tested"])))
    except Exception as problem:
        plt.close("all")
        grey_box("Scorecard not available yet")
    say("## Words used in this report")
    say(GLOSSARY)
    say("## How to read the charts")
    say(HOW_TO_READ)
    info = load_csv("run_info")
    if info is not None and not info.empty:
        used = info["n_dev_used"].astype(int)
        say(f"*Results in this report use between {int(used.min())} and {int(used.max())} dev alerts per probe "
            f"(the full dev set is the larger number). Last update: {info['written_at'].max()}.*")


# ===========================================================================================
# Section 1: foundation check
# ===========================================================================================
@renderer("F0")
def render_F0() -> None:
    say("**The question.** Before any probe: are the stored numbers really the numbers of the right alerts, and are the input files untouched?")
    say("**How it was tested.** Three library alerts per collection were embedded again with that collection's own recipe and compared "
        "with the stored numbers. The input files were fingerprinted before and after.")
    check, example, finger = load_csv("F0_vector_check"), load_csv("F0_example_neighbours"), load_csv("F0_inputs_fingerprint")
    if check is None or example is None:
        grey_box("Not run yet (session 1a)")
        return
    say(f"**What you see.** All {len(check)} re-embedded alerts match their stored numbers (the lowest similarity is "
        f"{fmt(check['cosine'].min(), 4)}, where 1 means identical). "
        + (f"All {len(finger)} input files are unchanged." if finger is not None and finger['same'].all() else "Some input files changed: stop and check."))
    first_two = example[example["collection_id"] == 1]
    say("Two example dev alerts and their five nearest library alerts (collection 1, mpnet plain):")
    shown = first_two[["dev_product", "dev_risks", "rank", "neighbour_product", "neighbour_risks", "score"]].copy()
    shown.columns = ["Dev alert", "Its dangers", "Rank", "Neighbour", "Neighbour's dangers", "Similarity"]
    say(md_table(shown))
    say("**What it means.** The stored numbers can be trusted, and the search finds alerts that look like the new one. "
        "Whether the dangers also match is what the probes below measure.")


# ===========================================================================================
# Group C: leaks and fairness
# ===========================================================================================
def overall_chance():
    """The overall chance level (C10), or None if C10 has not run."""
    table = load_csv("C10_chance")
    return None if table is None else float(table[table["risk_type"] == "ALL"]["chance_exact"].iloc[0])


@renderer("C10")
def render_C10() -> None:
    def draw(d):
        t = d["C10_chance"]
        overall = t[t["risk_type"] == "ALL"].iloc[0]
        types = t[t["risk_type"] != "ALL"].sort_values("chance_exact")
        fig, ax = plt.subplots(figsize=(FIG_SIZE[0], max(3.8, 0.3 * len(types) + 1.4)))
        y = np.arange(len(types))
        small = types["small_sample"].astype(bool).to_numpy()
        for i, r in enumerate(types.itertuples()):
            ax.barh(i, r.chance_exact, color="white" if small[i] else "#607D8B", edgecolor="#455A64", linewidth=1.2)
            ax.errorbar(r.chance_exact, i, xerr=[[max(r.chance_exact - r.low, 0)], [max(r.high - r.chance_exact, 0)]], fmt="none", ecolor="black", capsize=2, linewidth=1)
            ax.text(r.high + 0.01, i, f"n={r.n}" + (" small sample" if small[i] else ""), va="center", fontsize=7)
        ax.axvline(overall.chance_exact, color=GREY, linestyle="--", linewidth=1.5, label=f"all dev alerts ({fmt(overall.chance_exact)})")
        ax.set_yticks(y); ax.set_yticklabels(types["risk_type"], fontsize=8)
        ax.legend(fontsize=8, frameon=False, loc="lower right")
        finish(ax, f"Luck alone scores {fmt(overall.chance_exact)} overall, and common dangers are the easiest to hit",
               xlabel="score of five random neighbours (share that hit)")
        howto("each bar is the score you would get with random neighbours for alerts of that danger type. Longer bar = easier to hit by luck. "
              "The grey dashed line is the average over all dev alerts.")
    def see(d):
        t = d["C10_chance"]
        types = t[(t["risk_type"] != "ALL") & (~t["small_sample"].astype(bool))].sort_values("chance_exact")
        o = t[t["risk_type"] == "ALL"].iloc[0]
        if types.empty:
            return (f"Over all {int(o.n)} dev alerts, five random neighbours would share a danger {fmt(o.chance_exact * 100, 0)} times in a hundred. "
                    "No danger type has enough alerts yet to be listed on its own (every bar is a small sample).")
        return (f"Over all {int(o.n)} dev alerts, five random neighbours would share a danger {fmt(o.chance_exact * 100, 0)} times in a hundred. "
                f"The easiest danger to hit by luck is {types.iloc[-1].risk_type} ({fmt(types.iloc[-1].chance_exact * 100, 0)} in a hundred); "
                f"the hardest is {types.iloc[0].risk_type} ({fmt(types.iloc[0].chance_exact * 100, 0)} in a hundred). "
                f"A second way of drawing random neighbours (seed fixed) gave {fmt(o.chance_sampled * 100, 0)} in a hundred.")
    block("C10", "How well would a search do by pure luck?",
          "For every dev alert we worked out, exactly, the share of the library that shares a danger with it. That is the score of random neighbours. A random draw confirms it.",
          ["C10_chance"], draw, see)


@renderer("C11")
def render_C11() -> None:
    def draw(d):
        best, leak = d["C11_best_match"], d["C11_leakage"]
        data = {cid: best[best["collection_id"] == cid]["best_score"].to_numpy() for cid in (1, 2, 3, 4)}
        share = np.mean([(data[c] >= 0.95).mean() for c in data]) * 100
        hist4(data, [(0.90, "0.90"), (0.95, "0.95"), (0.98, "0.98")], "similarity of the best library match",
              f"About {fmt(share, 0)} in a hundred dev alerts have a near-copy (0.95 or more) in the library")
        howto("each panel is one collection. A bar to the right of the dotted lines means the dev alert has an almost identical alert in the library.")
        at = leak[leak["threshold"] == 0.95].set_index("collection_id")
        series = {c: {"value": [at.loc[c, "precision_all"], at.loc[c, "precision_without"]], "low": [at.loc[c, "all_low"], at.loc[c, "without_low"]],
                      "high": [at.loc[c, "all_high"], at.loc[c, "without_high"]], "n": [at.loc[c, "n_total"], at.loc[c, "n_without"]]} for c in (1, 2, 3, 4)}
        diff = at.loc[1, "precision_all"] - at.loc[1, "precision_without"]
        word = "lowers" if diff > 0 else "raises"
        grouped_bars(["all dev alerts", "without near-copies (0.95 or more)"], series, "precision@5",
                     f"Taking out near-copies {word} the score of {LABELS[1]} by {fmt(abs(diff), 2)}", chance=overall_chance(), ylim=(0, 1.1))
        howto("the left bars use every dev alert, the right bars leave out the alerts that have a near-copy. If the right bar is much lower, near-copies were flattering the score.")
    def see(d):
        leak = d["C11_leakage"]
        rows = []
        for t in (0.90, 0.95, 0.98):
            sub = leak[leak["threshold"] == t]
            rows.append(f"similarity {fmt(t)} or more: {fmt(sub['n_above'].min(), 0)} to {fmt(sub['n_above'].max(), 0)} alerts "
                        f"({fmt(sub['n_above_in_same_words'].min(), 0)} to {fmt(sub['n_above_in_same_words'].max(), 0)} of them are in the generic-words group)")
        return "The number of dev alerts with a near-copy, depending on the collection: " + "; ".join(rows) + "."
    block("C11", "Do near-copies of library alerts make the score look better than it is?",
          "For each dev alert we took its best library match. We counted how many are at or above three similarity lines and compared the score with and without them.",
          ["C11_best_match", "C11_leakage"], draw, see)


@renderer("C12")
def render_C12() -> None:
    def draw(d):
        t = d["C12_risk_text_leak"]
        ok = t[t["status"] == "ok"]
        fig, ax = plt.subplots(figsize=FIG_SIZE)
        cids = sorted(ok["collection_id"].unique())
        for i, cid in enumerate(cids):
            valid = ok[(ok["collection_id"] == cid) & (~ok["query_type"].str.startswith("LEAK"))].iloc[0]
            leak = ok[(ok["collection_id"] == cid) & (ok["query_type"].str.startswith("LEAK"))].iloc[0]
            ax.bar(i - 0.2, valid.precision_at_5, 0.38, color=COLORS[cid], hatch=HATCH[cid], edgecolor="white", label=f"{LABELS[cid]}: valid score" if i == 0 else None)
            ax.bar(i + 0.2, leak.precision_at_5, 0.38, color=LEAK_RED, edgecolor="white", label="LEAK, NOT A VALID SCORE" if i == 0 else None)
            for x, r in ((i - 0.2, valid), (i + 0.2, leak)):
                ax.errorbar(x, r.precision_at_5, yerr=[[r.precision_at_5 - r.low], [r.high - r.precision_at_5]], fmt="none", ecolor="black", capsize=3)
            ax.text(i + 0.2, leak.high + 0.02, "LEAK,\nNOT A VALID\nSCORE", ha="center", fontsize=7, color=LEAK_RED, fontweight="bold")
        chance_line(ax, overall_chance())
        ax.set_xticks(range(len(cids))); ax.set_xticklabels([LABELS[c] for c in cids]); ax.set_ylim(0, 1.25)
        ax.legend(fontsize=8, frameon=False, loc="upper left")
        first = ok[ok["collection_id"] == cids[0]]
        finish(ax, f"Letting the risk text into the question lifts the score from {fmt(first.iloc[0].precision_at_5)} to {fmt(first.iloc[1].precision_at_5)}, but it is not real",
               ylabel="precision@5")
        howto("the coloured bar is the honest score (no risk text in the question). The red bar is the same search with the answer leaked into the question. The red bar must never be used.")
    block("C12", "What happens if the risk text leaks into the question?",
          "Only for the two collections whose library text holds the risk text: we ran the same dev alerts once honestly and once with their own risk text added to the question.",
          ["C12_risk_text_leak"], draw,
          lambda d: "Collections 1 and 3 have no risk text on the library side, so this test does not apply to them (shown as not available in the scorecard).")


@renderer("C13")
def render_C13() -> None:
    def draw(d):
        s, lc = d["C13_self_match"], d["load_check"]
        say(f"Dev alerts found inside a collection: {fmt(s['dev_ids_found'].sum(), 0)} (out of {fmt(s['dev_ids_checked'].iloc[0], 0)} checked in each of four collections). It must be zero.")
        get = lambda m: float(lc[lc["metric"] == m]["value"].iloc[0])
        fig, ax = plt.subplots(figsize=(FIG_SIZE[0], 3))
        ax.bar(["NumPy (exact search)", "ChromaDB (database search)"], [get("precision_at_5_numpy"), get("precision_at_5_chroma")],
               color=[COLORS[1], "#7BAFD4"], edgecolor="white")
        for i, v in enumerate([get("precision_at_5_numpy"), get("precision_at_5_chroma")]):
            ax.text(i, v + 0.02, fmt(v, 3), ha="center")
        ax.set_ylim(0, 1.1)
        finish(ax, f"Both ways of searching score alike: {fmt(get('precision_at_5_numpy'), 3)} and {fmt(get('precision_at_5_chroma'), 3)}", ylabel="precision@5 (collection 1)")
        howto("the two bars should be almost the same height. NumPy checks every library alert; the database takes a faster, approximate route.")
    def see(d):
        lc = d["load_check"]
        get = lambda m: float(lc[lc["metric"] == m]["value"].iloc[0])
        return (f"The ids stored in the database equal the card lists for all four collections. On {fmt(get('alerts_checked'), 0)} dev alerts the two searches differ by "
                f"{fmt(abs(get('precision_at_5_numpy') - get('precision_at_5_chroma')), 3)}. The two searches returned exactly the same five neighbours for "
                f"{fmt(get('same_neighbour_sets_share') * 100, 0)} in a hundred alerts, because the database search is approximate and many library alerts are almost equally close.")
    block("C13", "Is any dev alert also in the library, and does the database agree with the plain search?",
          "We compared every dev id with the card list of each collection, and compared the database search with the plain NumPy search (on a copy of the database).",
          ["C13_self_match", "load_check"], draw, see)


# ===========================================================================================
# helpers for building chart series from a CSV
# ===========================================================================================
def series_of(frame: pd.DataFrame, group_col: str, groups: list, value: str, low: str = None, high: str = None, n: str = None,
              cids=(1, 2, 3, 4)) -> dict:
    """{collection id: {"value": [...], "low": [...], "high": [...], "n": [...]}} in the order of 'groups'."""
    out = {}
    for cid in cids:
        sub = frame[frame["collection_id"].astype(str) == str(cid)].set_index(group_col)
        if sub.empty:
            continue
        pick = lambda col: [sub.loc[g, col] if g in sub.index else np.nan for g in groups]
        out[cid] = {"value": pick(value), "low": pick(low) if low else pick(value), "high": pick(high) if high else pick(value),
                    "n": pick(n) if n else [None] * len(groups)}
    return out


# ===========================================================================================
# Group A: the shape of the space
# ===========================================================================================
@renderer("A1")
def render_A1() -> None:
    def draw(d):
        pairs, pct = d["A1_random_pairs"], d["A1_percentiles"].set_index("collection_id")
        data = {c: pairs[pairs["collection_id"] == c]["cosine"].to_numpy() for c in (1, 2, 3, 4)}
        vlines = {c: [(pct.loc[c, "p50"], "50th"), (pct.loc[c, "p95"], "95th"), (pct.loc[c, "p99"], "99th")] for c in (1, 2, 3, 4)}
        hist4(data, vlines, "similarity of two random library alerts",
              f"Half of all random pairs already score {fmt(pct.loc[1, 'p50'])} ({LABELS[1]}) or {fmt(pct.loc[3, 'p50'])} ({LABELS[3]})")
        howto("each panel shows 5,000 random pairs of library alerts. The dotted lines mark the 50th, 95th and 99th percentile: a match must beat the 99th line to be special.")
    def see(d):
        pct = d["A1_percentiles"]
        return "Similarity of two random alerts: " + "; ".join(
            f"{LABELS[int(r.collection_id)]} half are above {fmt(r.p50)}, one in twenty above {fmt(r.p95)}, one in a hundred above {fmt(r.p99)}" for r in pct.itertuples()) + "."
    block("A1", "What similarity do two unrelated alerts have?", "We drew five thousand random pairs of library alerts (seed fixed) and measured their similarity.",
          ["A1_random_pairs", "A1_percentiles"], draw, see)


@renderer("A2")
def render_A2() -> None:
    def draw(d):
        t = d["A2_anisotropy"]
        groups = ["average similarity of random pairs", "length of the average fingerprint"]
        series = {}
        for r in t.itertuples():
            series[int(r.collection_id)] = {"value": [r.mean_random_pair_cosine, r.mean_vector_length], "low": [r.low, r.mean_vector_length],
                                            "high": [r.high, r.mean_vector_length], "n": [None, None]}
        grouped_bars(groups, series, "value (0 = unrelated, 1 = identical)",
                     f"Random pairs already average {fmt(t.mean_random_pair_cosine.min())} to {fmt(t.mean_random_pair_cosine.max())}: the fingerprints lean one way", ylim=(0, 1))
        howto("if fingerprints were spread evenly, unrelated alerts would average close to zero. Taller bars mean a stronger common lean.")
    block("A2", "Do all fingerprints lean in one common direction?",
          "We measured the average similarity of random library pairs and the length of the average fingerprint (zero would mean no common lean).",
          ["A2_anisotropy"], draw)


@renderer("A3")
def render_A3() -> None:
    def draw(d):
        var, pts, links, fixes = d["A3_pca_variance"], d["A3_pca_points"], d["A3_pca_links"], d["A3_fixes"]
        comps = list(range(1, 11))
        series = {c: {"value": var[var["collection_id"] == c].sort_values("component")["explained_variance_ratio"].tolist()} for c in (1, 2, 3, 4)}
        grouped_bars([str(x) for x in comps], series, "share of all variation", f"The first direction alone holds {fmt(var[(var.component == 1) & (var.collection_id == 1)].explained_variance_ratio.iloc[0] * 100, 0)} in a hundred of the variation in {LABELS[1]}",
                      show_n=False)
        howto("each group of bars is one direction found by PCA. A tall first bar means one direction dominates the fingerprints.")
        p1 = pts[pts["collection_id"] == 1]
        top = p1["category"].value_counts().head(8).index
        fig, ax = plt.subplots(figsize=FIG_SIZE)
        palette = plt.get_cmap("tab10")
        for i, cat in enumerate(top):
            sub = p1[p1["category"] == cat]
            ax.scatter(sub["pc1"], sub["pc2"], s=5, color=palette(i), label=cat[:24], alpha=0.7)
        other = p1[~p1["category"].isin(top)]
        ax.scatter(other["pc1"], other["pc2"], s=5, color="#BDBDBD", label="other", alpha=0.5)
        ax.legend(fontsize=6, markerscale=2, frameon=False, ncol=2, loc="best")
        finish(ax, f"The two main directions separate some categories ({LABELS[1]})", "second direction", "first direction")
        howto("each dot is one library alert, coloured by category (the eight biggest). Colours that sit apart mean the direction follows the category.")
        fig, ax = plt.subplots(figsize=FIG_SIZE)
        scatter = ax.scatter(p1["pc1"], p1["pc2"], s=5, c=p1["text_length"], cmap="viridis", vmax=np.percentile(p1["text_length"], 95))
        fig.colorbar(scatter, ax=ax, label="length of the text (characters)")
        lk = links[(links["collection_id"] == 1) & (links["component"] == 1)].iloc[0]
        finish(ax, f"The first direction and text length go together (correlation {fmt(lk.corr_text_length)})", "second direction", "first direction")
        howto("the same dots coloured by how long the text is. A smooth colour change along an axis means that direction follows text length.")
        groups = ["none", "centred", "top 1 removed", "top 2 removed"]
        series = series_of(fixes, "variant", groups, "precision_at_5", "low", "high", None)
        grouped_bars(groups, series, "precision@5", "Does removing the common lean help? Compare each bar with the first group", chance=overall_chance(), ylim=(0, 1.1), show_n=False)
        howto("the first group is the search as it is. The other groups remove the common lean in three ways. A fix helps only if its bar is clearly higher than the first.")
    def see(d):
        f, l = d["A3_fixes"], d["A3_pca_links"]
        kept = f[f["kept"].astype(bool)]
        kept_text = ", ".join(f"{LABELS[int(r.collection_id)]} ({r.variant})" for r in kept.itertuples()) or "none"
        c1 = l[l["collection_id"] == 1].set_index("component")
        return (f"For {LABELS[1]}, the first direction is linked to text length with a correlation of {fmt(c1.loc[1, 'corr_text_length'])}; the category explains "
                f"{fmt(c1.loc[1, 'eta2_category'] * 100, 0)} in a hundred of it and the year {fmt(c1.loc[1, 'eta2_year'] * 100, 0)} in a hundred. "
                f"Fixes that improved precision@5 with an interval above zero: {kept_text}.")
    block("A3", "What do the main directions of the fingerprints follow, and does removing the common lean help?",
          "PCA on the library fingerprints (fitted on the library only). We tried centring, and removing the first one or two directions, and re-scored the dev alerts.",
          ["A3_pca_variance", "A3_pca_points", "A3_pca_links", "A3_fixes"], draw, see)


# ===========================================================================================
# Group D: does similar mean the same danger?
# ===========================================================================================
@renderer("D14")
def render_D14() -> None:
    def draw(d):
        t = d["D14_nn_buckets"]
        groups = ["below 0.80", "0.80 to 0.90", "0.90 to 0.95", "0.95 or more"]
        series = series_of(t, "bucket", groups, "share_no_shared_risk", "low", "high", "n_pairs")
        top = t[(t["collection_id"] == 1) & (t["bucket"] == "0.95 or more")].iloc[0]
        grouped_bars(groups, series, "share of pairs with no danger in common",
                     f"Even for near-copies, {fmt(top.share_no_shared_risk * 100, 0)} in a hundred pairs share no danger ({LABELS[1]})", ylim=(0, 0.6))
        howto("each library alert is paired with its single nearest library neighbour. Bars show how often the pair shares no danger, grouped by how similar they are. n is the number of pairs.")
    block("D14", "When two alerts look almost the same, do they always share a danger?",
          "For every library alert we took its nearest other library alert, grouped the pairs by similarity, and counted the pairs with no danger in common.",
          ["D14_nn_buckets"], draw,
          lambda d: "For the two collections whose library text includes the risk text, near-identical pairs are partly made alike by that text, so their numbers look better than they would for a new alert.")


def _dot_chart(probe: str, csv: str, col: str, what: str, question: str, how: str) -> None:
    def draw(d):
        t = d[csv]
        base = t[t["collection_id"] == 1]
        order = base.sort_values("n", ascending=False)[col].tolist()
        series = {c: {k: [t[(t["collection_id"] == c) & (t[col] == g)][v].iloc[0] for g in order] for k, v in
                      (("value", "precision_at_5"), ("low", "low"), ("high", "high"))} for c in (1, 2, 3, 4)}
        ns = {c: [int(t[(t["collection_id"] == c) & (t[col] == g)]["n"].iloc[0]) for g in order] for c in (1, 2, 3, 4)}
        chance = [float(base[base[col] == g]["chance"].iloc[0]) for g in order]
        big = base[~base["small_sample"].astype(bool)]
        gap = (big["precision_at_5"] - big["chance"])
        weakest = big.loc[gap.idxmin()] if not big.empty else None
        title = (f"Most {what} beat luck; the weakest is {weakest[col]} (gap {fmt(gap.min())})" if weakest is not None else f"Score per {what}")
        dot_whisker([f"{g} (n={n})" for g, n in zip(order, ns[1])], series, chance, "precision@5", title, ns=ns)
        howto("each coloured dot is a collection's score for that group, with its interval. The grey tick is the chance level for the same group. A dot far to the right of the tick is a real success. Hollow dots are small samples.")
    block(probe, question, how, [csv], draw)


@renderer("D15")
def render_D15() -> None:
    _dot_chart("D15", "D15_by_risk_type", "risk_type", "danger types", "Is the search good for every danger type, or only for the common ones?",
               "For each danger type we took the dev alerts that have it and measured precision@5, next to the luck level of those same alerts.")


@renderer("D16")
def render_D16() -> None:
    _dot_chart("D16", "D16_by_category", "category", "categories", "Is the search equally good in every category?",
               "For each of the ten biggest categories (and all others together) we measured precision@5, next to the luck level.")


@renderer("D17")
def render_D17() -> None:
    def draw(d):
        t = d["D17_multi_risk"]
        near, rnd = t[t["source"] == "neighbours"], t[t["source"] == "random"]
        groups = ["share of the alert's dangers covered", "all of its dangers covered"]
        series = {}
        for r in near.itertuples():
            series[int(r.collection_id)] = {"value": [r.coverage_share, r.fully_covered_share], "low": [r.low, r.fully_covered_share],
                                            "high": [r.high, r.fully_covered_share], "n": [r.n, r.n]}
        r1 = rnd[rnd["collection_id"] == 1].iloc[0]
        n1 = near[near["collection_id"] == 1].iloc[0]
        grouped_bars(groups, series, "share", f"Neighbours cover {fmt(n1.coverage_share * 100, 0)} in a hundred of a multi-danger alert's dangers; random ones {fmt(r1.coverage_share * 100, 0)}",
                     chance=[r1.coverage_share, r1.fully_covered_share], ylim=(0, 1.15))
        howto("only dev alerts with two or more dangers. Bars: how much of their danger list the five neighbours together cover. Grey ticks: the same for random neighbours.")
    block("D17", "For alerts with several dangers, do the neighbours together cover them?",
          "For the dev alerts with two or more dangers, we collected the dangers of the five neighbours and counted how many of the alert's own dangers were in that collection. Random neighbours give the comparison.",
          ["D17_multi_risk"], draw)


# ===========================================================================================
# Group B: what drives the matches
# ===========================================================================================
def mean_ci(values) -> tuple:
    """Mean with a simple 95% range (for display of per-alert columns saved by a probe)."""
    v = np.asarray(values, dtype=float)
    half = 1.96 * v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0.0
    return float(v.mean()), float(v.mean() - half), float(v.mean() + half)


def _two_group_block(probe, csv, names, question, how, what_a, what_b):
    def draw(d):
        t = d[csv]
        groups = t[t["group"] != "difference"]
        series = series_of(groups, "group", names, "precision_at_5", "low", "high", "n")
        diff = t[(t["collection_id"] == 1) & (t["group"] == "difference")].iloc[0]
        word = "higher" if diff.precision_at_5 > 0 else "lower"
        grouped_bars(names, series, "precision@5",
                     f"{what_b.capitalize()} alerts score {fmt(abs(diff.precision_at_5))} {word} than {what_a} ones ({LABELS[1]})", chance=overall_chance(), ylim=(0, 1.15))
        howto(f"the left group is {what_a} alerts, the right group {what_b} alerts. If the right bars are clearly taller or shorter than the left bars, this property matters. Hollow bars are small samples.")
    def see(d):
        t = d[csv]
        diffs = t[t["group"] == "difference"].set_index("collection_id")
        n_a = int(t[(t["collection_id"] == 1) & (t["group"] == names[0])]["n"].iloc[0])
        return (f"{n_a} dev alerts are {what_a}. The score gap (the second group minus the first) is " +
                "; ".join(f"{LABELS[c]} {fmt(diffs.loc[c, 'precision_at_5'], 2)} (from {fmt(diffs.loc[c, 'low'], 2)} to {fmt(diffs.loc[c, 'high'], 2)})" for c in (1, 2, 3, 4)) + ".")
    block(probe, question, how, [csv], draw, see)


@renderer("B4")
def render_B4() -> None:
    _two_group_block("B4", "B4_length", ["thin", "normal"], "Do very short descriptions score worse?",
                     "We split the dev alerts into those whose description only repeats the product name (thin) and the rest, and compared precision@5.", "thin", "normal")


@renderer("B6")
def render_B6() -> None:
    _two_group_block("B6", "B6_generic_words", ["same words", "rest"], "Do alerts with generic words (the same words as a library alert) score worse?",
                     "We split the dev alerts into those whose product and description match a library alert word for word and the rest.", "generic-words", "other")


@renderer("B5")
def render_B5() -> None:
    def draw(d):
        t, t2 = d["B5_same_category"], d["B5_text_vs_filter"]
        series = {int(r.collection_id): {"value": [r.share_same_category], "low": [r.low], "high": [r.high], "n": [r.n]} for r in t.itertuples()}
        grouped_bars(["share of the five neighbours in the same category"], series, "share", 
                     f"About {fmt(t.share_same_category.mean() * 100, 0)} in a hundred neighbours share the category; luck would give {fmt(t.chance.iloc[0] * 100, 0)}",
                     chance=float(t.chance.iloc[0]), ylim=(0, 1.15))
        howto("how often the neighbours are from the same category as the new alert. The grey dashed line is what random library alerts would give.")
        variants = ["category in the text", "product + description", "product + description + category filter"]
        series2 = {}
        for model, cid in (("all-mpnet-base-v2", 1), ("bge-base-en-v1.5", 3)):
            sub = t2[t2["model"] == model].set_index("variant")
            series2[cid] = {k: [sub.loc[v, k if k != "value" else "precision_at_5"] for v in variants] for k in ("value", "low", "high", "n")}
        best = t2.loc[t2["precision_at_5"].idxmax()]
        grouped_bars(variants, series2, "precision@5", f"On {int(t2.n.iloc[0])} dev alerts the best version is: {best.variant} ({best.model})", chance=overall_chance(), ylim=(0, 1.15), rotate=12)
        howto("three ways to use the category: inside the text, not at all, or as a filter that only allows library alerts of the same category. Mpnet and bge are shown in their plain colours.")
    block("B5", "Does the category pull the matches, and is it better inside the text or as a filter?",
          "We measured how often neighbours share the category, then on 300 dev alerts compared three versions. The last two need new fingerprints of the library without the category (cached, never saved over the real ones).",
          ["B5_same_category", "B5_text_vs_filter"], draw)
    meaning("B5b")


@renderer("B7")
def render_B7() -> None:
    def draw(d):
        t = d["B7_names"]
        groups = ["0", "1", "2", "3", "4", "5"]
        series = {}
        for c in (1, 2, 3, 4):
            sub = t[t["collection_id"] == c]
            series[c] = {"value": [float((sub["kept_of_5"] == int(g)).mean()) for g in groups], "n": [None] * 6}
        mean5 = t[t["collection_id"] == 1]["kept_of_5"].mean()
        grouped_bars(groups, series, "share of dev alerts", f"Adding the name keeps about {fmt(mean5, 1)} of the five neighbours ({LABELS[1]})", show_n=False, ylim=(0, 1))
        howto("each group is how many of the five neighbours stay the same when the product name is added to the question. Tall bars on the right mean the name changes little.")
        series2 = {}
        for c in (1, 2, 3, 4):
            sub = t[t["collection_id"] == c]
            a, b = mean_ci(sub["precision_without_name"]), mean_ci(sub["precision_with_name"])
            series2[c] = {"value": [a[0], b[0]], "low": [a[1], b[1]], "high": [a[2], b[2]], "n": [len(sub)] * 2}
        grouped_bars(["without the name", "with the name"], series2, "precision@5", "Does the name change the score?", chance=overall_chance(), ylim=(0, 1.15))
        howto("the left bars are the normal question; the right bars add the product name. The library text has no names, so this is a test of the question side only.")
    block("B7", "Do product names pull the matches?",
          "For two hundred dev alerts that have a name, we searched twice: with and without the name added to the question, and compared the neighbours and the score.",
          ["B7_names"], draw)


@renderer("B8")
def render_B8() -> None:
    def draw(d):
        t, words = d["B8_hint_words"], d["B8_hint_word_list"]
        series = {int(r.collection_id): {"value": [r.precision_before, r.precision_after], "n": [None, None]} for r in t.itertuples()}
        r1 = t[t["collection_id"] == 1].iloc[0]
        grouped_bars(["before removing hint words", "after removing hint words"], series, "precision@5",
                     f"Removing the hint words changes the score by {fmt(r1['diff'], 3)} ({LABELS[1]})", chance=overall_chance(), ylim=(0, 1.1), show_n=False)
        howto("the left bars are the normal search; the right bars are the same search after deleting a fixed list of danger words from the question. A big drop would mean the search leans on those words.")
        say("The word list that was removed (a pattern means the word and its endings):")
        shown = words.copy()
        shown.columns = ["Word pattern", "Group", "Dev questions changed"]
        say(md_table(shown))
    def see(d):
        t = d["B8_hint_words"]
        return (f"The word list changed {fmt(t.n_changed.max(), 0)} of the dev questions. The score difference (before minus after) is " +
                "; ".join(f"{LABELS[int(r.collection_id)]} {fmt(r.diff, 3)} (from {fmt(r.diff_low, 3)} to {fmt(r.diff_high, 3)})" for r in t.itertuples()) + ".")
    block("B8", "Does the search work mainly because of danger words in the text?",
          "We deleted a fixed list of danger words (and the examples from the project plan) from the dev questions and searched again.",
          ["B8_hint_words", "B8_hint_word_list"], draw, see)


@renderer("B9")
def render_B9() -> None:
    block("B9", "Do neighbours of chemical alerts share the same substance name?",
          "This probe needs a list of substance names. The list must be read and approved by Dev first, so it has not been run.", ["B9_chemical_names"], lambda d: None)


# ===========================================================================================
# Group E: time and style
# ===========================================================================================
@renderer("E18")
def render_E18() -> None:
    def draw(d):
        t = d["E18_by_month"]
        months = sorted(t["month"].unique())
        def pick(c, column):
            return [t[(t["collection_id"] == c) & (t["month"] == m)][column].iloc[0] for m in months]
        series = {c: {"value": pick(c, "precision_at_5"), "low": pick(c, "low"), "high": pick(c, "high")} for c in (1, 2, 3, 4)}
        ns = [int(t[(t["collection_id"] == 1) & (t["month"] == m)]["n"].iloc[0]) for m in months]
        ax = line_chart([f"{m}\n(n={n})" for m, n in zip(months, ns)], series, "precision@5", "month of the dev alert", "Score month by month", chance=overall_chance())
        howto("one line per collection, with a band for the 95% interval. Under each month is the number of dev alerts. Months with few alerts are not reliable.")
    def see(d):
        y = d["E18_same_year"]
        return ("How often a neighbour comes from the same year as the dev alert: " + "; ".join(
            f"{LABELS[int(r.collection_id)]} {fmt(r.share_same_year * 100, 0)} in a hundred (luck {fmt(r.chance * 100, 0)})" for r in y.itertuples()) +
            ". Almost all dev alerts come from one year, so a time effect is hard to see.")
    block("E18", "Does the score change over the months, and do neighbours come from the same year?",
          "We measured precision@5 for each month of the dev alerts, and counted how often a neighbour has the same report year as the dev alert.",
          ["E18_by_month", "E18_same_year"], draw, see)


def _same_share_block(probe, csv, what, question, how):
    def draw(d):
        t = d[csv]
        series = {int(r.collection_id): {"value": [r.share_same], "low": [r.low], "high": [r.high], "n": [r.n]} for r in t.itertuples()}
        grouped_bars([f"neighbours with the same {what}"], series, "share of neighbours",
                     f"Neighbours share the {what} {fmt(t.share_same.mean() * 100, 0)} times in a hundred; luck would give {fmt(t.chance.iloc[0] * 100, 0)}",
                     chance=float(t.chance.iloc[0]), ylim=(0, 1.15))
        howto(f"how often a neighbour has the same {what} as the new alert. The grey dashed line is the luck level. A bar far above it means the {what} (not the product) helps pull matches together.")
    block(probe, question, how, [csv], draw)


@renderer("E19")
def render_E19() -> None:
    _same_share_block("E19", "E19_country", "country", "Do neighbours come from the same country more than luck would explain?",
                      "For each dev alert we counted how many of the five neighbours were reported by the same country, and compared with random library alerts.")


@renderer("E20")
def render_E20() -> None:
    _same_share_block("E20", "E20_alert_type", "alert type", "Do neighbours have the same alert type more than luck would explain?",
                      "The alert type is the letters at the start of the case number. We counted how many neighbours share it with the dev alert.")


# ===========================================================================================
# Groups F and G: comparison and calibration
# ===========================================================================================
def _metric(frame, cid, metric):
    r = frame[(frame["collection_id"].astype(str) == str(cid)) & (frame["metric"] == metric)]
    return (np.nan, np.nan, np.nan) if r.empty else (float(r["value"].iloc[0]), float(r["low"].iloc[0]), float(r["high"].iloc[0]))


@renderer("F21")
def render_F21() -> None:
    def draw(d):
        t = d["F21_compare_k5"]
        names = ["precision@5", "vote accuracy", "macro-F1"]
        keys = ["precision_at_5", "vote_accuracy", "macro_f1"]
        series = {c: {"value": [_metric(t, c, k)[0] for k in keys], "low": [_metric(t, c, k)[1] for k in keys], "high": [_metric(t, c, k)[2] for k in keys],
                      "n": [None] * 3} for c in (1, 2, 3, 4)}
        base = [overall_chance(), _metric(t, "baseline", "vote_accuracy")[0], _metric(t, "baseline", "macro_f1")[0]]
        best = max((1, 2, 3, 4), key=lambda c: _metric(t, c, "precision_at_5")[0])
        grouped_bars(names, series, "score", f"{LABELS[best]} scores highest ({fmt(_metric(t, best, 'precision_at_5')[0])} precision@5); grey ticks are luck and the category rule",
                     chance=base, ylim=(0, 1.15), show_n=False)
        howto("for each measure, one bar per collection with its interval. The grey tick is the reference: luck for precision@5, and the simple rule 'guess the most common danger of the category' for the other two.")
        lifts = {c: {"value": [_metric(t, c, "lift")[0]], "low": [_metric(t, c, "lift")[1]], "high": [_metric(t, c, "lift")[2]], "n": [None]} for c in (1, 2, 3, 4)}
        ax = grouped_bars(["how many times better than luck"], lifts, "lift", f"The best collection is {fmt(_metric(t, best, 'lift')[0], 1)} times better than luck", chance=1.0, show_n=False)
        howto("a lift of one means no better than luck (the grey dashed line). Taller is better.")
        conf = load_csv("F21_confusion")
        if conf is not None:
            sub = conf[conf["collection_id"] == best]
            types = sorted(set(sub["true_risk"]) | set(sub["voted_risk"]))
            grid = np.zeros((len(types), len(types)))
            for r in sub.itertuples():
                grid[types.index(r.true_risk), types.index(r.voted_risk)] = r.share_of_true * 100
            heatmap(grid, types, types, f"What the vote says, for each true danger ({LABELS[best]})", cmap="Blues", xlabel="danger the neighbours voted for",
                    ylabel="true danger of the dev alert", vmin=0, vmax=100)
            howto("each row is a true danger and adds up to one hundred percent. A strong diagonal means the vote usually names the right danger. Bright squares off the diagonal show which dangers get mixed up.")
    block("F21", "Which collection is best when we use the five nearest neighbours?",
          "For each collection we measured precision@5, the lift over luck, how often the winning danger of a vote is right, and a fair score over all danger types. A simple rule (the most common danger of the category) is the yardstick.",
          ["F21_compare_k5"], draw)


@renderer("F22")
def render_F22() -> None:
    def draw(d):
        a, b = d["F21_compare_k5"], d["F22_compare_k10"]
        groups = ["precision (k=5)", "precision (k=10)", "vote accuracy (k=5)", "vote accuracy (k=10)", "macro-F1 (k=5)", "macro-F1 (k=10)"]
        pick = [(a, "precision_at_5"), (b, "precision_at_10"), (a, "vote_accuracy"), (b, "vote_accuracy"), (a, "macro_f1"), (b, "macro_f1")]
        series = {c: {"value": [_metric(f, c, m)[0] for f, m in pick], "low": [_metric(f, c, m)[1] for f, m in pick], "high": [_metric(f, c, m)[2] for f, m in pick],
                      "n": [None] * 6} for c in (1, 2, 3, 4)}
        grouped_bars(groups, series, "score", "Five neighbours or ten: which scores higher?", ylim=(0, 1.15), show_n=False, rotate=20)
        howto("pairs of groups: the first of each pair uses five neighbours, the second uses ten. If the second bar is not clearly taller, ten neighbours do not help.")
    block("F22", "Do ten neighbours do better than five?", "The same measures, once with five and once with ten neighbours.", ["F21_compare_k5", "F22_compare_k10"], draw)


@renderer("F23")
def render_F23() -> None:
    def draw(d):
        t = d["F23_points"]
        top = t["risk_type"].value_counts().head(8).index
        fig, ax = plt.subplots(figsize=FIG_SIZE)
        palette = plt.get_cmap("tab10")
        for i, name in enumerate(top):
            sub = t[t["risk_type"] == name]
            ax.scatter(sub["pc1"], sub["pc2"], s=5, color=palette(i), label=name, alpha=0.7)
        other = t[~t["risk_type"].isin(top)]
        ax.scatter(other["pc1"], other["pc2"], s=5, color="#BDBDBD", label="other", alpha=0.5)
        ax.legend(fontsize=6, markerscale=2, frameon=False, ncol=2)
        finish(ax, f"A picture of the library ({LABELS[1]}): do the dangers form groups?", "second direction", "first direction")
        howto("each dot is one library alert squeezed down to two numbers, coloured by its first danger. Groups of one colour mean similar alerts share a danger. This is for intuition only, not proof.")
    block("F23", "What does the space look like?", "The fingerprints of three thousand library alerts were squeezed to two numbers (PCA) and coloured by danger.", ["F23_points"], draw)


@renderer("F24")
def render_F24() -> None:
    def draw(d):
        t = d["F24_hand_review"]
        say("The full list of twenty dev alerts with their five neighbours is saved as `reports/probe_results/hand_review_collections_1_and_3.md`. Three example rows (collection 1):")
        shown = t[(t["collection_id"] == 1)].head(3)[["dev_text", "rank", "neighbour_text", "neighbour_risks"]].copy()
        cut = lambda text: text if len(text) <= 70 else text[:70].rstrip() + " ..."
        shown["dev_text"] = shown["dev_text"].map(cut)
        shown["neighbour_text"] = shown["neighbour_text"].map(cut)
        shown.columns = ["Dev alert", "Rank", "Neighbour", "Neighbour's dangers"]
        say(md_table(shown))
    block("F24", "Do the neighbours look right to a human?", "Twenty random dev alerts and their five neighbours (text and dangers), written to a file for you to read. The program does not judge them.",
          ["F24_hand_review"], draw)


@renderer("G25")
def render_G25() -> None:
    def draw(d):
        t, cut = d["G25_calibration"], d["G25_cutoff"].set_index("collection_id")
        fig, ax = plt.subplots(figsize=FIG_SIZE)
        for c in (1, 2, 3, 4):
            sub = t[t["collection_id"] == c].sort_values("decile")
            x = (sub["sim_low"] + sub["sim_high"]) / 2
            ax.plot(x, sub["precision_at_5"], marker="o", color=COLORS[c], label=f"{LABELS[c]}: precision@5", linestyle="-")
            ax.fill_between(x, sub["p_low"], sub["p_high"], color=COLORS[c], alpha=0.12)
            ax.plot(x, sub["vote_accuracy"], marker="s", color=COLORS[c], linestyle=":", alpha=0.8, markersize=3)
            if c in cut.index:
                ax.axvline(cut.loc[c, "suggested_cutoff"], color=COLORS[c], linestyle="-.", linewidth=1)
        chance_line(ax, overall_chance())
        ax.legend(fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
        finish(ax, "The closer the best match, the more often the neighbours are right", "score", "similarity of the best library match (middle of each tenth of the dev alerts)")
        howto("each dot is a tenth of the dev alerts, grouped from the weakest to the strongest best match. Solid lines are precision@5, dotted lines are vote accuracy. The dash-dot vertical lines are the suggested weak-match cut-offs.")
    def see(d):
        cut = d["G25_cutoff"]
        return "Suggested cut-offs (below these similarities, treat the answer as weak): " + "; ".join(f"{LABELS[int(r.collection_id)]} {fmt(r.suggested_cutoff)}" for r in cut.itertuples()) + "."
    block("G25", "How sure should we be about an answer?", "We grouped the dev alerts into ten equal groups by how close their best library match is, and measured the scores in each group.",
          ["G25_calibration", "G25_cutoff"], draw, see)


# ===========================================================================================
# Section 8: ranking and decisions
# ===========================================================================================
@renderer("RANK")
def render_RANK() -> None:
    f21, f22 = load_csv("F21_compare_k5"), load_csv("F22_compare_k10")
    if f21 is None:
        grey_box("Not run yet (session 5)")
        return
    order = sorted((1, 2, 3, 4), key=lambda c: (-_metric(f21, c, "precision_at_5")[0], -_metric(f21, c, "vote_accuracy")[0]))
    rows = []
    for rank, c in enumerate(order, start=1):
        p, lo, hi = _metric(f21, c, "precision_at_5")
        rows.append([rank, LABELS[c], f"{fmt(p)} ({fmt(lo)} to {fmt(hi)})", fmt(_metric(f21, c, "lift")[0], 1), fmt(_metric(f21, c, "vote_accuracy")[0]), fmt(_metric(f21, c, "macro_f1")[0])])
    say("## Ranking of the four collections")
    say(md_table(pd.DataFrame(rows, columns=["Rank", "Collection", "precision@5 (interval)", "Lift", "Vote accuracy", "Macro-F1"])))
    best, second = order[0], order[1]
    pb, lb, hb = _metric(f21, best, "precision_at_5")
    ps, ls, hs = _metric(f21, second, "precision_at_5")
    overlap = "their intervals overlap, so the difference may be luck" if lb <= hs else "their intervals do not overlap, so the difference is probably real"
    say(f"**Which one to use:** {LABELS[best]}. It has the highest precision@5 ({fmt(pb)}) and a lift of {fmt(_metric(f21, best, 'lift')[0], 1)} over luck. "
        f"The runner-up is {LABELS[second]} ({fmt(ps)}); {overlap}. The collections with risk text on the library side are scored honestly: their questions have no risk text.")
    say("## Decisions")
    dec = []
    g25 = load_csv("G25_cutoff")
    if g25 is not None:
        dec.append(["Weak-match cut-off", f"{fmt(g25[g25['collection_id'] == best].iloc[0]['suggested_cutoff'])}", "Below this best-match similarity, mark the answer low confidence."])
    a3 = load_csv("A3_fixes")
    if a3 is not None:
        kept = a3[(a3["collection_id"] == best) & (a3["kept"].astype(bool))]
        dec.append(["Centring the vectors", "yes (" + ", ".join(kept["variant"]) + ")" if not kept.empty else "no", "Kept only if the gain is clearly above zero and larger than one point."])
    b5 = load_csv("B5_text_vs_filter")
    if b5 is not None:
        sub = b5[b5["model"] == ("all-mpnet-base-v2" if best in (1, 2) else "bge-base-en-v1.5")]
        top = sub.loc[sub["precision_at_5"].idxmax()]
        dec.append(["Category in the text or a filter", top["variant"], f"Highest precision@5 ({fmt(top['precision_at_5'])}) on {int(top['n'])} dev alerts."])
    if f22 is not None:
        k5, k10 = _metric(f21, best, "vote_accuracy")[0], _metric(f22, best, "vote_accuracy")[0]
        dec.append(["Five or ten neighbours", "ten" if k10 > k5 + 0.01 else "five", f"Vote accuracy {fmt(k5)} with five, {fmt(k10)} with ten."])
    d15 = load_csv("D15_by_risk_type")
    if d15 is not None:
        sub = d15[(d15["collection_id"] == best) & (~d15["small_sample"].astype(bool))]
        weak = sub[sub["precision_at_5"] < sub["chance"] + 0.10]["risk_type"].tolist()
        dec.append(["Weak danger types", ", ".join(weak) if weak else "none", "A weak type scores less than a tenth above luck (only types with thirty or more alerts are judged)."])
    if dec:
        say(md_table(pd.DataFrame(dec, columns=["Decision", "Answer", "Why"])))
    say("## Open questions and next steps")
    say("- The chemical-names probe (B9) is waiting for Dev to approve the substance list.\n"
        "- The dev set covers about one year, so effects of time are hard to see.\n"
        "- The database search is approximate; the plain search is the reference.\n"
        "- The test set and the real seller listings are still untouched. Choose the collection here, then score the test set once.\n"
        "- Next: build the vote and the weak-match warning into the real system, then try the language model on the same alerts.")
