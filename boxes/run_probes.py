"""Run the probes group by group on the dev set, render the report after every group, and write reports/RUN_LOG.md.

Run it from the project folder:  python -m boxes.run_probes            (full dev set, groups C A D B E F G)
Options: --n 50 (a sample of dev alerts)  --groups C A  --out DIR  --no-render
A single probe that fails is written as "not available" with its reason and the run goes on.
Only a HardStop (a check that must pass) ends the run.
"""
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd

from boxes.probe_groups import GROUP_PROBES, HardStop
from boxes.probes import (PROBE_DIR, ProbeContext, fingerprint_inputs, save_fingerprint, save_probe_csv, write_foundation_check)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ORDER = ["C", "A", "D", "B", "E", "F", "G"]
GROUP_NAMES = {"F0": "Foundation check", "C": "Group C: leaks and fairness", "A": "Group A: shape of the space",
               "D": "Group D: similar means same danger", "B": "Group B: what drives the matches",
               "E": "Group E: time and style", "F": "Group F: comparison", "G": "Group G: calibration"}


def save_error(probe: str, reason: str, out_dir: Path) -> None:
    """Add (or replace) one row in errors.csv: this probe was 'not available' and why."""
    path = out_dir / "errors.csv"
    new = pd.DataFrame([{"probe": probe, "reason": reason[:300]}])
    if path.exists():
        old = pd.read_csv(path)
        new = pd.concat([old[old["probe"] != probe], new], ignore_index=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    new.to_csv(path, index=False)


def clear_error(probe: str, out_dir: Path) -> None:
    path = out_dir / "errors.csv"
    if path.exists():
        old = pd.read_csv(path)
        old[old["probe"] != probe].to_csv(path, index=False)


def render(out_dir: Path, log: list) -> None:
    """Render reports/probe.qmd to HTML and to PDF (typst) with a fresh Python kernel. A failure is logged, never raised."""
    env = dict(os.environ)
    if out_dir != PROBE_DIR:
        env["PROBE_RESULTS_DIR"] = str(out_dir)
    for fmt, target in (("html", ROOT / "reports" / "probe.html"), ("typst", ROOT / "reports" / "probe.pdf")):
        started = time.time()
        result = subprocess.run([str(ROOT / "tools" / "quarto.sh"), "render", "reports/probe.qmd", "--to", fmt, "--no-execute-daemon"],
                                cwd=ROOT, env=env, capture_output=True, text=True)
        fresh = target.exists() and target.stat().st_mtime >= started - 1
        status = "ok" if result.returncode == 0 and fresh else "FAILED"
        detail = "" if status == "ok" else (result.stderr or result.stdout)[-300:].replace("\n", " ")
        log.append({"time": datetime.now().strftime("%H:%M:%S"), "format": fmt, "status": status, "detail": detail})
        print(f"   render {fmt}: {status}", flush=True)


def write_run_log(path: Path, info: dict) -> None:
    """reports/RUN_LOG.md: what ran, what failed or was skipped, and how long each group took."""
    lines = ["# Run log: embedding probes", "",
             f"- Started: {info['start']}", f"- Finished: {info['end'] or 'NOT FINISHED (the run stopped early)'}",
             f"- Dev alerts used: {info['n_dev']} ({'the full dev set' if info['full'] else 'a sample'})",
             f"- Seed: 0. Test split opened: no. Commits or pushes: none.", ""]
    if info.get("stop"):
        lines += [f"## RUN STOPPED: {info['stop']}", ""]
    lines += ["## Checks that had to pass", ""]
    lines += [f"- {text}" for text in info["checks"]]
    lines += ["", "## Time per group", "", "| Group | Seconds | Probes |", "|---|---|---|"]
    lines += [f"| {GROUP_NAMES.get(t['group'], t['group'])} | {t['seconds']} | {t['probes']} |" for t in info["timings"]]
    lines += ["", "## Probes", "", "| Probe | Status | Note |", "|---|---|---|"]
    lines += [f"| {p['probe']} | {p['status']} | {p['note']} |" for p in info["probes"]]
    lines += ["", "## Renders", "", "| Time | Format | Status | Detail |", "|---|---|---|---|"]
    lines += [f"| {r['time']} | {r['format']} | {r['status']} | {r['detail']} |" for r in info["renders"][-6:]]
    pdf_ok = any(r["format"] == "typst" and r["status"] == "ok" for r in info["renders"][-2:])
    lines += ["", f"PDF: {'reports/probe.pdf was written.' if pdf_ok else 'The PDF FAILED. reports/probe.html is the report to read.'}", "",
              "## Notes", ""] + [f"- {n}" for n in info["notes"]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect_checks(out_dir: Path) -> list:
    """Read back the three checks that must pass, from the CSVs the probes wrote."""
    checks = []
    vc = out_dir / "F0_vector_check.csv"
    if vc.exists():
        v = pd.read_csv(vc)
        checks.append(f"Stored-vector check: {len(v)} re-embedded library alerts, lowest cosine {v['cosine'].min():.5f} (must be above 0.999): PASSED")
    sm = out_dir / "C13_self_match.csv"
    if sm.exists():
        s = pd.read_csv(sm)
        checks.append(f"Self-match: {int(s['dev_ids_found'].sum())} dev alerts found in any collection (must be 0): PASSED")
    lc = out_dir / "load_check.csv"
    if lc.exists():
        l = pd.read_csv(lc).set_index(["metric", "collection_id"])["value"]
        a, b = float(l[("precision_at_5_numpy", 1)]), float(l[("precision_at_5_chroma", 1)])
        checks.append(f"NumPy against ChromaDB (collection 1, {int(l[('alerts_checked', 1)])} dev alerts): {a:.4f} against {b:.4f}, difference {abs(a - b):.4f} "
                      f"(allowed 0.02, because the database search is approximate); identical neighbour lists for {float(l[('same_neighbour_sets_share', 1)]) * 100:.0f}% of alerts: PASSED")
    fp = out_dir / "F0_inputs_fingerprint.csv"
    if fp.exists():
        f = pd.read_csv(fp)
        checks.append(f"Input files (library, dev, saved embeddings) unchanged: {'YES' if f['same'].all() else 'NO, SOMETHING CHANGED'} ({len(f)} files, md5 at the start and the end)")
    return checks or ["No check has run yet."]


def main(argv: list) -> int:
    groups = [a for a in argv if a in DEFAULT_ORDER] or DEFAULT_ORDER
    n_dev = int(argv[argv.index("--n") + 1]) if "--n" in argv else None
    out_dir = Path(argv[argv.index("--out") + 1]) if "--out" in argv else PROBE_DIR
    do_render = "--no-render" not in argv
    start_time = datetime.now()
    info = {"start": start_time.strftime("%Y-%m-%d %H:%M:%S"), "end": None, "n_dev": 0, "full": n_dev is None, "timings": [], "probes": [],
            "renders": [], "checks": [], "notes": [], "stop": None}
    log_path = ROOT / "reports" / "RUN_LOG.md" if out_dir == PROBE_DIR else out_dir / "RUN_LOG.md"
    inputs_start = fingerprint_inputs()
    print(f"loading the dev alerts, the library and the chance level ...", flush=True)
    ctx = ProbeContext(n_dev=n_dev, out_dir=out_dir)
    info["n_dev"] = ctx.n_dev
    info["notes"] += ["Probes live in boxes/probe_groups.py; the report text and charts in boxes/probe_report.py and boxes/probe_charts.py.",
                      "B9 (chemical names) was skipped on purpose: the substance list is waiting for Dev to read and approve it."]
    try:
        # Foundation first: it re-embeds stored vectors and stops the whole run if they do not match.
        steps = [("F0", [("F0", lambda c: write_foundation_check(c))])] + [(g, GROUP_PROBES[g]) for g in groups]
        for group, probes in steps:
            started = time.time()
            print(f"== {GROUP_NAMES.get(group, group)}", flush=True)
            for name, function in probes:
                t0 = time.time()
                try:
                    function(ctx)
                    clear_error(name, out_dir)
                    status, note = ("skipped", "waiting for Dev (substance list not approved)") if name == "B9" else ("ran", f"{time.time() - t0:.0f} s")
                except HardStop:
                    raise
                except Exception as problem:
                    if group == "F0":
                        raise HardStop(f"foundation check failed: {problem}")
                    reason = f"{type(problem).__name__}: {problem}"
                    save_error(name, reason, out_dir)
                    status, note = "FAILED (not available)", reason[:160]
                    traceback.print_exc(limit=3)
                info["probes"].append({"probe": name, "status": status, "note": note})
                print(f"   {name}: {status} {note}", flush=True)
            info["timings"].append({"group": group, "seconds": f"{time.time() - started:.0f}", "probes": ", ".join(n for n, _ in probes)})
            info["checks"] = collect_checks(out_dir)
            if do_render:
                render(out_dir, info["renders"])
            write_run_log(log_path, info)
    except HardStop as stop:
        info["stop"] = str(stop)
        info["checks"] = collect_checks(out_dir)
        write_run_log(log_path, info)
        print(f"HARD STOP: {stop}", flush=True)
        return 2
    save_fingerprint(inputs_start, fingerprint_inputs(), out_dir)
    info["checks"] = collect_checks(out_dir)
    info["end"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if do_render:
        render(out_dir, info["renders"])
    write_run_log(log_path, info)
    print("run finished", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
