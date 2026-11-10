"""Chart helpers for reports/probe.qmd.

This file only READS saved results (reports/probe_results/*.csv). It never recomputes a probe,
never imports a probe function or an embedding model, and never touches the test split.
Colours are the same for the same collection in every chart, always in the order 1 to 4.
"""
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import Markdown, display

# Where the saved results are. The environment variable lets a test point somewhere else.
PROBE_DIR = Path(os.environ.get("PROBE_RESULTS_DIR", Path(__file__).resolve().parent.parent / "reports" / "probe_results"))

# One colour per collection (same in every chart). Collections 2 and 4 ("+ risk text") are hatched.
COLORS = {1: "#0072B2", 2: "#56B4E9", 3: "#009E73", 4: "#CC79A7"}
HATCH = {1: "", 2: "//", 3: "", 4: "//"}
LABELS = {1: "mpnet plain", 2: "mpnet + risk text", 3: "bge plain", 4: "bge + risk text"}
LEAK_RED = "#B22222"
GREY = "#9E9E9E"
VERDICT_COLORS = {"supported": "#2E7D32", "not supported": "#C62828", "unclear": "#F9A825",
                  "baseline": "#90A4AE", "not run": "#E0E0E0", "not available": "#BDBDBD"}

FIG_SIZE = (8, 4)
plt.rcParams.update({"font.size": 11, "axes.titlesize": 12, "axes.titleweight": "bold",
                     "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 110})


# ------------------------------------------------------------------ reading and writing text
def load_csv(name: str):
    """Read reports/probe_results/<name>.csv, or return None if it is not there (probe not run yet)."""
    path = PROBE_DIR / f"{name}.csv"
    return pd.read_csv(path) if path.exists() else None


def fmt(value, digits: int = 2) -> str:
    """A number as text for a sentence. Missing numbers show as 'n/a'."""
    try:
        if value is None or np.isnan(float(value)):
            return "n/a"
    except (TypeError, ValueError):
        return str(value)
    return f"{float(value):.{digits}f}"


def say(text: str) -> None:
    """Print a piece of Markdown text into the report."""
    display(Markdown(text))


def howto(text: str) -> None:
    """The one-line 'How to read this chart' under a figure."""
    say(f"*How to read this chart: {text}*")


# ------------------------------------------------------------------ grey boxes
def grey_box(message: str) -> None:
    """A grey box with a message (used for 'Not run yet' and 'Not available')."""
    fig, ax = plt.subplots(figsize=(FIG_SIZE[0], 0.9))
    ax.set_facecolor("#EEEEEE")
    ax.set_xticks([]); ax.set_yticks([])
    for side in ax.spines.values():
        side.set_visible(True); side.set_color("#BDBDBD")
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=12, color="#555555", transform=ax.transAxes)
    plt.show()


def not_run_box(session: str) -> None:
    grey_box(f"Not run yet ({session})")


def error_reason(probe: str):
    """The reason a probe was 'not available', from errors.csv, or None."""
    errors = load_csv("errors")
    if errors is None:
        return None
    hit = errors[errors["probe"] == probe]
    return None if hit.empty else str(hit.iloc[-1]["reason"])


# ------------------------------------------------------------------ the finishing touch on every figure
def finish(ax, title: str, ylabel: str = "", xlabel: str = "") -> None:
    """Title that states the finding, axis labels in words, then show the figure."""
    ax.set_title(title, loc="left")
    if ylabel:
        ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(xlabel)
    ax.figure.tight_layout()
    plt.show()


def chance_line(ax, value, horizontal: bool = True, label: str = "chance level") -> None:
    """A grey dashed line at the chance level."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return
    (ax.axhline if horizontal else ax.axvline)(value, color=GREY, linestyle="--", linewidth=1.5, label=label, zorder=0)


# ------------------------------------------------------------------ chart types
def grouped_bars(groups: list, series: dict, ylabel: str, title: str, chance=None, ylim=None,
                 show_n: bool = True, rotate: int = 0):
    """Bars grouped by 'groups' (x axis), one bar per collection, with 95% intervals and n.

    series: {collection_id: {"value": [...], "low": [...], "high": [...], "n": [...]}} (lists as long as groups)
    chance: one number, or a list as long as groups (drawn as grey dashed marks).
    An n below 30 is drawn hollow and labelled 'small sample'.
    """
    fig, ax = plt.subplots(figsize=FIG_SIZE)
    ids = list(series)
    width = 0.8 / max(len(ids), 1)
    x = np.arange(len(groups))
    for j, cid in enumerate(ids):
        s = series[cid]
        values = np.array(s["value"], dtype=float)
        low = np.array(s.get("low", values), dtype=float)
        high = np.array(s.get("high", values), dtype=float)
        ns = s.get("n", [None] * len(groups))
        positions = x + (j - (len(ids) - 1) / 2) * width
        for i in range(len(groups)):
            small = ns[i] is not None and not np.isnan(float(ns[i])) and float(ns[i]) < 30
            ax.bar(positions[i], values[i], width * 0.95, color="white" if small else COLORS[cid],
                   edgecolor=COLORS[cid], hatch=HATCH[cid], linewidth=1.2,
                   label=LABELS[cid] if i == 0 else None)
            if show_n and ns[i] is not None and not np.isnan(float(ns[i])):
                ax.text(positions[i], high[i] if not np.isnan(high[i]) else values[i], f"n={int(ns[i])}" + ("\nsmall sample" if small else ""),
                        ha="center", va="bottom", fontsize=7)
        ax.errorbar(positions, values, yerr=[np.maximum(values - low, 0), np.maximum(high - values, 0)],
                    fmt="none", ecolor="black", capsize=3, linewidth=1)
    if chance is not None:
        if np.ndim(chance) == 0:
            chance_line(ax, float(chance), True)
        else:
            for i, c in enumerate(chance):
                ax.hlines(c, x[i] - 0.45, x[i] + 0.45, color=GREY, linestyle="--", linewidth=1.5,
                          label="chance level" if i == 0 else None, zorder=0)
    ax.set_xticks(x)
    ax.set_xticklabels(groups, rotation=rotate, ha="right" if rotate else "center")
    if ylim:
        ax.set_ylim(*ylim)
    # With tilted axis labels the legend must sit lower, so it does not cover them.
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.40 if rotate else -0.12), ncol=5, frameon=False)
    finish(ax, title, ylabel)
    return ax


def dot_whisker(labels: list, series: dict, chance: list, xlabel: str, title: str, ns: dict | None = None):
    """Horizontal dots with 95% interval whiskers, one row per label, a chance marker beside each dot."""
    fig, ax = plt.subplots(figsize=(FIG_SIZE[0], max(3.5, 0.42 * len(labels) + 1.5)))
    ids = list(series)
    y = np.arange(len(labels))
    step = 0.7 / max(len(ids), 1)
    for j, cid in enumerate(ids):
        s = series[cid]
        values, low, high = (np.array(s[k], dtype=float) for k in ("value", "low", "high"))
        pos = y + (j - (len(ids) - 1) / 2) * step
        small = np.array([(n is not None and n < 30) for n in (ns[cid] if ns else [None] * len(labels))])
        ax.errorbar(values, pos, xerr=[np.maximum(values - low, 0), np.maximum(high - values, 0)], fmt="none",
                    ecolor=COLORS[cid], capsize=2, linewidth=1)
        ax.scatter(values[~small], pos[~small], color=COLORS[cid], s=28, label=LABELS[cid], zorder=3)
        ax.scatter(values[small], pos[small], facecolors="white", edgecolors=COLORS[cid], s=28, zorder=3)
    ax.scatter(chance, y, marker="|", color=GREY, s=160, linewidths=2, label="chance level", zorder=2)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.legend(fontsize=8, loc="lower right", frameon=False)
    finish(ax, title, xlabel=xlabel)
    return ax


def hist4(data: dict, vlines: list, xlabel: str, title: str, bins: int = 40):
    """One histogram panel per collection (2 x 2), the same colours, with labelled vertical lines."""
    fig, axes = plt.subplots(2, 2, figsize=(FIG_SIZE[0], 5.2), sharex=True)
    for cid, ax in zip((1, 2, 3, 4), axes.ravel()):
        if cid in data:
            ax.hist(data[cid], bins=bins, color=COLORS[cid], hatch=HATCH[cid], edgecolor="white", alpha=0.9)
        for value, text in vlines.get(cid, vlines) if isinstance(vlines, dict) else vlines:
            ax.axvline(value, color="black", linestyle=":", linewidth=1)
            ax.text(value, ax.get_ylim()[1] * 0.95, text, rotation=90, va="top", ha="right", fontsize=7)
        ax.set_title(LABELS[cid], fontsize=10, loc="left")
    fig.supxlabel(xlabel)
    fig.suptitle(title, x=0.01, ha="left", fontweight="bold", fontsize=12)
    fig.tight_layout()
    plt.show()


def heatmap(matrix, rows: list, cols: list, title: str, cmap: str = "Blues", fmt_str: str = "{:.0f}",
            xlabel: str = "", ylabel: str = "", vmin=None, vmax=None, figsize=None):
    """A table of numbers as colours, with the number written in every cell."""
    matrix = np.asarray(matrix, dtype=float)
    fig, ax = plt.subplots(figsize=figsize or (FIG_SIZE[0], max(3.5, 0.35 * len(rows) + 1.5)))
    image = ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=vmin, vmax=vmax)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(rows, fontsize=8)
    top = np.nanmax(matrix) if matrix.size else 1
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            if not np.isnan(matrix[i, j]) and matrix[i, j] != 0:
                ax.text(j, i, fmt_str.format(matrix[i, j]), ha="center", va="center", fontsize=6,
                        color="white" if matrix[i, j] > 0.6 * top else "black")
    fig.colorbar(image, ax=ax, fraction=0.04)
    finish(ax, title, ylabel, xlabel)


def scorecard(verdicts: pd.DataFrame, probes: list):
    """Heatmap: probes (rows) x collections (columns), coloured by verdict."""
    names = list(VERDICT_COLORS)
    grid = np.full((len(probes), 4), names.index("not run"), dtype=float)
    for i, probe in enumerate(probes):
        rows = verdicts[verdicts["probe"] == probe] if verdicts is not None else pd.DataFrame()
        for _, r in rows.iterrows():
            cid = r["collection_id"]
            if str(cid).isdigit():
                grid[i, int(cid) - 1] = names.index(r["verdict"]) if r["verdict"] in names else names.index("not run")
            else:  # a verdict that holds for all four collections
                grid[i, :] = names.index(r["verdict"]) if r["verdict"] in names else names.index("not run")
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    fig, ax = plt.subplots(figsize=(FIG_SIZE[0], 0.17 * len(probes) + 1.1))
    ax.imshow(grid, cmap=ListedColormap([VERDICT_COLORS[n] for n in names]), vmin=-0.5, vmax=len(names) - 0.5, aspect="auto")
    ax.set_xticks(range(4)); ax.set_xticklabels([LABELS[c] for c in (1, 2, 3, 4)], fontsize=8)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(probes))); ax.set_yticklabels(probes, fontsize=8)
    ax.set_xticks(np.arange(-0.5, 4), minor=True); ax.set_yticks(np.arange(-0.5, len(probes)), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.5); ax.tick_params(which="minor", length=0)
    ax.legend(handles=[Patch(color=VERDICT_COLORS[n], label=n) for n in names], fontsize=7, loc="upper left",
              bbox_to_anchor=(1.01, 1), frameon=False)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.figure.tight_layout()
    ax.set_title("Scorecard: one square per probe and collection", loc="left", pad=22)
    plt.show()


def line_chart(x: list, series: dict, ylabel: str, xlabel: str, title: str, chance=None, vline=None,
               vline_label: str = "", rotate: int = 0):
    """Lines with 95% interval bands, one per collection, optional chance line and vertical line."""
    fig, ax = plt.subplots(figsize=FIG_SIZE)
    for cid, s in series.items():
        v, lo, hi = (np.array(s[k], dtype=float) for k in ("value", "low", "high"))
        ax.plot(x, v, marker="o", color=COLORS[cid], label=LABELS[cid], linestyle="-" if not HATCH[cid] else "--")
        ax.fill_between(x, lo, hi, color=COLORS[cid], alpha=0.15)
    if chance is not None:
        chance_line(ax, chance, True)
    if vline is not None:
        ax.axvline(vline, color="black", linestyle=":", linewidth=1.2)
        ax.text(vline, ax.get_ylim()[0], " " + vline_label, rotation=90, va="bottom", fontsize=8)
    ax.legend(fontsize=8, frameon=False)
    if rotate:
        plt.setp(ax.get_xticklabels(), rotation=rotate, ha="right")
    finish(ax, title, ylabel, xlabel)
    return ax
