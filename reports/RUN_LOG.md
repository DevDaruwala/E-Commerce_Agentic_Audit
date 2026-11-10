# Run log: embedding probes

- Started: 2026-11-10 21:35:11
- Finished: 2026-11-10 21:39:38
- Dev alerts used: 1658 (the full dev set)
- Seed: 0. Test split opened: no. Commits or pushes: none.

## Checks that had to pass

- Stored-vector check: 12 re-embedded library alerts, lowest cosine 1.00000 (must be above 0.999): PASSED
- Self-match: 0 dev alerts found in any collection (must be 0): PASSED
- NumPy against ChromaDB (collection 1, 100 dev alerts): 0.7580 against 0.7540, difference 0.0040 (allowed 0.02, because the database search is approximate); identical neighbour lists for 68% of alerts: PASSED
- Input files (library, dev, saved embeddings) unchanged: YES (10 files, md5 at the start and the end)

## Time per group

| Group | Seconds | Probes |
|---|---|---|
| Foundation check | 12 | F0 |
| Group C: leaks and fairness | 4 | C10, C11, C12, C13 |
| Group A: shape of the space | 30 | A1, A2, A3 |
| Group D: similar means same danger | 37 | D14, D15, D16, D17 |
| Group B: what drives the matches | 11 | B4, B5, B6, B7, B8, B9 |
| Group E: time and style | 1 | E18, E19, E20 |
| Group F: comparison | 5 | F21, F22, F23, F24 |
| Group G: calibration | 0 | G25 |

## Probes

| Probe | Status | Note |
|---|---|---|
| F0 | ran | 12 s |
| C10 | ran | 0 s |
| C11 | ran | 0 s |
| C12 | ran | 3 s |
| C13 | ran | 1 s |
| A1 | ran | 0 s |
| A2 | ran | 0 s |
| A3 | ran | 29 s |
| D14 | ran | 36 s |
| D15 | ran | 0 s |
| D16 | ran | 0 s |
| D17 | ran | 0 s |
| B4 | ran | 0 s |
| B5 | ran | 2 s |
| B6 | ran | 0 s |
| B7 | ran | 2 s |
| B8 | ran | 7 s |
| B9 | skipped | waiting for Dev (substance list not approved) |
| E18 | ran | 0 s |
| E19 | ran | 0 s |
| E20 | ran | 0 s |
| F21 | ran | 1 s |
| F22 | ran | 2 s |
| F23 | ran | 2 s |
| F24 | ran | 0 s |
| G25 | ran | 0 s |

## Renders

| Time | Format | Status | Detail |
|---|---|---|---|
| 21:39:07 | html | ok |  |
| 21:39:16 | typst | ok |  |
| 21:39:29 | html | ok |  |
| 21:39:38 | typst | ok |  |
| 21:39:50 | html | ok |  |
| 21:40:00 | typst | ok |  |

PDF: reports/probe.pdf was written.

## Notes

- Probes live in boxes/probe_groups.py; the report text and charts in boxes/probe_report.py and boxes/probe_charts.py.
- B9 (chemical names) was skipped on purpose: the substance list is waiting for Dev to read and approve it.

## Corrections made during this session (all fixed before the final run above)

- **D17 was wrong in the first full run.** The dangers of all dev alerts were paired with the neighbour rows of only the multi-danger alerts. Found by checking against a plain independent calculation; fixed (`dangers_covered`) and tested.
- **A re-run added duplicate rows to `verdicts.csv`** (collection ids compared as text on one side and numbers on the other). Fixed in `_merge_csv`, with a test.
- **A3 "kept" was too generous.** A gain of 0.004 was marked kept; it now needs a clearly supported gain (above zero and larger than one point), the same rule as every other verdict.
- Three helper functions were deleted by accident during the D17 fix; the tests caught it and they were restored.
- ChromaDB's search is approximate, so the NumPy and ChromaDB neighbour lists are identical for only about two thirds of the alerts; the scores differ by 0.002 (allowed 0.02).
- Every headline number (precision@5, chance, vote accuracy, one danger type, thin against normal text, same country, near-copy count) was re-computed with plain loops and matched the files exactly.
