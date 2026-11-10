# Investigation log

What we found while reading our results, where we found it, what the number
means in plain words, one real example from our data, and why it might be.
Add new entries with `/addinvest`.

Status: **open** = not looked at yet · **explained** = we know why ·
**fixed** = changed and checked.

All numbers below are for **bge plain** (collection 3) unless another
collection is named. Source run: `reports/probe.pdf`, built 2026-11-10 21:39.

## Summary

| ID | Finding | Severity | Status |
|---|---|---|---|
| I-01 | 1 in 4 dev alerts is a word-for-word copy of a library alert, and copies flatter the score | High | open |
| I-02 | "2.6× better than luck" uses too easy a yardstick; a simple category rule gets 0.70 | High | open |
| I-03 | Chemical is half the library, so luck already hits it half the time | High | open |
| I-04 | Chemical carries the average; other dangers score lower | High | open |
| I-05 | Neighbours match on who wrote the alert (country), not only the product | High | open |
| I-06 | The score drops as dev alerts get newer | Medium | open |
| I-07 | The 0.88 weak-match cut-off flags 40% of alerts | Medium | open |
| I-08 | The "ten equal groups" in the calibration chart are not equal | Low | open |
| I-09 | B8 word table is blank in the PDF | Low | open |
| I-10 | B8 hint-word test is diluted and its word list catches non-hints | Medium | open |
| I-11 | "If supported, …" decisions print whatever the verdict | Low | open |
| I-12 | D14 says near-copies "often" share no danger, but it is 6% | Low | open |
| I-13 | Headline "1 to 616 near-copies" mixes collections | Low | open |
| I-14 | E18 says the score changes, then says time effects are hard to see | Low | open |
| I-15 | 79 library alerts are dated after dev starts | Low | explained (likely) |
| I-16 | Old split files in `data/` don't match `data/splits/` | Medium | open |
| I-17 | B9 (chemical names) has not run | Low | open |
| I-18 | Nobody has read the 20 hand-review examples yet | Medium | open |
| I-19 | Closer neighbours share law and danger more often, but exact copies lose on danger | High | explained (likely) |
| I-20 | Before the classifier: clean old split files and build one honest scorecard; the rest can wait (who does what, session plan and gates inside) | High | open |
| I-21 | The general safety law has two names (old Directive, new Regulation), so right answers get marked wrong | High | open |
| I-22 | Thin descriptions (text that only repeats the product name) score lower | Medium | open |

---

## I-01 1 in 4 dev alerts is a word-for-word copy of a library alert, and copies flatter the score
- **Status:** open · **Severity:** High
- **Where we found it:** probe.pdf B6 and C11; `reports/probe_results/B6_generic_words.csv`,
  `data/splits/pipeline_summary.json` ("group2_marked": 407)
- **What we found:** 407 of 1,658 dev alerts (25%) have the same category, product and
  description as a library alert. They score 0.88; the other 1,251 score 0.76. The
  headline 0.79 mixes both. B6 wrote its claim the wrong way round ("copies score
  lower"), so its "not supported" hides a big effect.
- **The metric in plain words:** precision@5 = of the 5 closest library alerts, the
  share that has at least one danger in common with the new alert.
- **Real example:** dev alert 12115 (SR/02420/25), "Motor vehicles. Passenger car.
  Passenger car.", danger Injuries. Its 5 neighbours all have similarity 1.0 (identical
  text) and dangers Fire, Injuries, Injuries, Fire, Injuries, so it scores 3 of 5.
- **Why it might be:** car recalls and some other alerts are written as one short
  template line, and the same product type is reported again and again. Identical
  text can carry different dangers, so even copies don't score 1.0.
- **Next check:** put the score without the 407 copies in the headline, next to the
  score with them.

## I-02 "2.6× better than luck" uses too easy a yardstick
- **Status:** open · **Severity:** High
- **Where we found it:** probe.pdf F21 and the "Read this first" page;
  `reports/probe_results/F21_compare_k5.csv` (rows `baseline`)
- **What we found:** a simple rule, "guess the most common danger of the category",
  gets vote accuracy 0.70. The search gets 0.81, so the real gain is +0.11. Macro-F1:
  search 0.43, rule 0.24.
- **The metric in plain words:** vote accuracy = the 5 neighbours vote for a danger;
  how often is the winner one of the true dangers? Macro-F1 = a score where rare
  dangers count as much as common ones.
- **Real example:** dev alert 12095 (SR/02453/25), "Jewellery. Necklace set", danger
  Chemical. The rule says "Jewellery → Chemical" (448 library jewellery alerts are
  Chemical) and is right without any search.
- **Why it might be:** within one category most alerts share the same danger, so the
  category alone already gives most of the answer.
- **Next check:** lead the report with "search vs simple rule", not "search vs luck".

## I-03 Chemical is half the library, so luck already hits it half the time
- **Status:** open · **Severity:** High
- **Where we found it:** probe.pdf C10 and D15; `reports/probe_results/C10_chance.csv`,
  `data/splits/library.jsonl`
- **What we found:** 6,078 of 11,913 library alerts (51%) are Chemical. Random luck
  for a Chemical alert is 0.52; for Electric shock it is 0.09.
- **The metric in plain words:** random luck = pick 5 library alerts with your eyes
  closed; how often does one share a danger with the new alert?
- **Real example:** dev alert 12099 (SR/02407/25), "Cosmetics. Cosmetics set" (eau de
  toilette + body lotion), danger Chemical because it contains the banned fragrance
  BMHCA. Five random library alerts: about 1 in 2 is Chemical anyway.
- **Why it might be:** cosmetics alone are 3,790 library alerts, and 3,716 of them
  are Chemical (more than half of all Chemical alerts). Inspectors test many
  cosmetics, toys and jewellery for banned substances. Not a bug, but it makes
  averages look better.
- **Next check:** report scores with and without Chemical alerts (see I-04).

## I-04 Chemical carries the average; other dangers score lower
- **Status:** open · **Severity:** High
- **Where we found it:** probe.pdf D15; `reports/probe_results/D15_by_risk_type.csv`
- **What we found:** Chemical is 794 of 1,658 dev alerts (48%) and scores 0.93. Other
  big dangers: Injuries 0.83, Electric shock 0.81, Strangulation 0.72, Choking 0.69,
  Environment 0.66, Burns 0.66, Fire 0.44.
- **The metric in plain words:** precision@5 per danger type = the same score, but
  only for the dev alerts that have that danger.
- **Real example:** dev alert 12178 (SR/02522/25), "Passenger car. Passenger car.",
  danger Fire. Its 5 identical-text neighbours have Environment, Fire, Injuries,
  Injuries, Injuries, so it scores 1 of 5.
- **Why it might be:** Chemical alerts are easy (many examples, and luck alone is 0.52).
  Fire is spread over many categories (cars, chargers, cushions), so the text doesn't
  point to it.
- **Next check:** give the headline score without Chemical, and per danger type.

## I-05 Neighbours match on who wrote the alert, not only the product
- **Status:** open · **Severity:** High
- **Where we found it:** probe.pdf E19 and A3; `reports/probe_results/E19_country.csv`,
  `A3_pca_links.csv`
- **What we found:** a neighbour comes from the same reporting country 38% of the
  time; luck gives 9% (4.4×). The category explains 94% of the main direction of
  the space (eta² 0.94).
- **The metric in plain words:** same-country share = of the 5 neighbours, how many
  were reported by the same national authority as the new alert.
- **Real example:** dev alert 12109 (SR/02440/25), "Lighting chain designed for
  interconnection…", reported by Slovakia. All 5 neighbours are Slovak lighting
  chains with the same phrasing ("designed for interconnection", "intended for
  mutual connection"). Here the dangers match too (Electric shock).
- **Why it might be:** each national authority writes in its own template and runs
  campaigns on certain products. The search learns the writing style. Real seller
  text won't have that style, so expect a lower score on real listings.
- **Next check:** score with neighbours from other countries only, and compare.

## I-06 The score drops as dev alerts get newer
- **Status:** open · **Severity:** Medium
- **Where we found it:** probe.pdf E18; `reports/probe_results/E18_by_month.csv`
- **What we found:** July 2025 scores 0.86 (324 alerts), Aug 0.80, Sep 0.74, Oct 0.78,
  Nov 0.77. The report says dev covers "about one year"; it covers 5 months
  (Jul–Nov 2025, 1,654 alerts) plus 4 stray alerts from 2026.
- **The metric in plain words:** precision@5 per month = the usual score, but only for
  dev alerts reported in that month.
- **Real example:** the July 2025 row (324 alerts, 0.86) against the September 2025
  row (266 alerts, 0.74), whose intervals don't overlap.
- **Why it might be:** July alerts sit right after the library ends, so they share
  campaigns and products with the library's last weeks. Later alerts bring new
  products.
- **Next check:** expect a lower score on test (2026). Consider adding the dev alerts
  to the library before the final test run.

## I-07 The 0.88 weak-match cut-off flags 40% of alerts
- **Status:** open · **Severity:** Medium
- **Where we found it:** probe.pdf G25; `reports/probe_results/G25_cutoff.csv`,
  `G25_calibration.csv`
- **What we found:** 664 of 1,658 dev alerts (40%) have a best match below 0.8841, so
  they would be marked low confidence. The cut-off was chosen and judged on the same
  dev data.
- **The metric in plain words:** best-match similarity = how alike the single closest
  library alert is (1 = identical text). The cut-off is the line below which we say
  "don't trust this answer much".
- **Real example:** dev alert 12101 (SR/02409/25), "Toy harmonica", danger Damage to
  hearing. Best match only 0.744 (a toy xylophone with Choking). Only 2 of 5
  neighbours share its danger.
- **Why it might be:** the rule picks "the lowest similarity from which every higher
  group scores at least the average", so by design it cuts near the middle.
- **Next check:** decide what "low confidence" should do in the product, and check
  the cut-off once on test.

## I-08 The "ten equal groups" in the calibration chart are not equal
- **Status:** open · **Severity:** Low
- **Where we found it:** probe.pdf G25; `reports/probe_results/G25_calibration.csv`
- **What we found:** groups 1–7 have 165–166 alerts each, but groups 8, 9 and 10 have
  128, 89 and 281. About 410 dev alerts have a best match of exactly 1.0, and they
  fall across groups 8–10.
- **The metric in plain words:** decile = one tenth of the alerts, sorted from weakest
  to strongest best match.
- **Real example:** dev alert 12115 (I-01) has best match 1.0; so do about 409 others,
  and they can't be split fairly into equal groups.
- **Why it might be:** ties at exactly 1.0 are split by position, not by value.
- **Next check:** put all similarity-1.0 alerts in their own group.

## I-09 B8 word table is blank in the PDF
- **Status:** open · **Severity:** Low
- **Where we found it:** probe.pdf B8, pages 20–21; `reports/probe_results/B8_hint_word_list.csv`
- **What we found:** most rows of the "Word pattern" column are empty, and the Fire
  row is shifted one column.
- **The metric in plain words:** none; this is a display bug.
- **Real example:** the CSV row `\bchemical\w*, Chemical, 83` shows up in the PDF with
  an empty pattern and only "Chemical 83".
- **Why it might be:** the backslash `\` is a special character for Typst (the PDF
  engine), so `\b…` gets eaten.
- **Next check:** show patterns as code, or escape the backslash, then check HTML and PDF.

## I-10 B8 hint-word test is diluted and its word list catches non-hints
- **Status:** open · **Severity:** Medium
- **Where we found it:** probe.pdf B8; `reports/probe_results/B8_hint_word_list.csv`
- **What we found:** only 162 of 1,658 questions changed when the words were removed,
  but the score difference is averaged over all 1,658, so any drop looks about 10×
  smaller. 17 of the 25 words changed no question at all. ("19 of 25" was said
  earlier in chat; the CSV says 17.)
- **The metric in plain words:** score difference = precision@5 before removing the
  danger words minus after. Near zero means the words don't drive the search.
- **Real example:** dev alert 13164 (SR/03459/25), "Pressure valves … for use in power
  plants and chemical installations", danger Injuries. Deleting "chemical" here
  removes no hint at all.
- **Why it might be:** danger words mostly live in the risk text, not in the product
  description, so the list rarely matches (that part is good news).
- **Next check:** re-score on the 162 changed questions only.

## I-11 "If supported, …" decisions print whatever the verdict
- **Status:** open · **Severity:** Low
- **Where we found it:** probe.pdf B4, B6, B7, E19, E20, A2; `reports/probe_results/verdicts.csv`
- **What we found:** the decision sentence is fixed per probe and starts with "If
  supported". The reader can't tell what was decided.
- **The metric in plain words:** none; this is report wording.
- **Real example:** B6 says verdict "not supported" and then "If supported, report the
  score without these alerts as well", while the effect (−0.12) is large (see I-01).
- **Why it might be:** each decision is a template sentence, not chosen by the verdict.
- **Next check:** write one decision per verdict (supported / not supported / unclear).

## I-12 D14 says near-copies "often" share no danger, but it is 6%
- **Status:** open · **Severity:** Low
- **Where we found it:** probe.pdf D14; `reports/probe_results/D14_nn_buckets.csv`
- **What we found:** of 5,585 library pairs with similarity 0.95 or more, 6.5% share no
  danger. The verdict says "supported" because the rule only tests "above zero".
  D14's text gives no number for the plain collections. A2, D15, D16, D17, E19 and
  E20 also give numbers only in charts.
- **The metric in plain words:** share with no shared danger = of two almost identical
  alerts, how often they have no danger in common.
- **Real example:** library alerts 1255 (A12/01084/22) "Passenger cars, Mercedes-Benz,
  GLE plug-in hybrid" (Fire) and 5648 (A12/00144/24) "Mercedes-Benz GLE plug-in
  hybrid (167 series)" (Injuries), similarity 0.95. Same car, different danger.
- **Why it might be:** the same product can fail in different ways; the verdict rule is
  too generous for a word like "often".
- **Next check:** rephrase as "sometimes (6%)", and print the key number in every
  "What you see".

## I-13 Headline "1 to 616 near-copies" mixes collections
- **Status:** open · **Severity:** Low
- **Where we found it:** probe.pdf "Read this first" and C11;
  `reports/probe_results/C11_best_match.csv`
- **What we found:** dev alerts with a best match of 0.95 or more: mpnet plain 616,
  mpnet + risk text 1, bge plain 609, bge + risk text 10.
- **The metric in plain words:** near-copy = a dev alert whose best library match is
  0.95 or more, so almost the same text.
- **Real example:** bge plain, the chosen collection: 609 near-copies (37% of dev).
- **Why it might be:** the risk-text collections have an extra paragraph on the library
  side, so no plain question matches them closely. Their low counts are not
  comparable.
- **Next check:** headline one number, for the chosen collection.

## I-14 E18 says the score changes, then says time effects are hard to see
- **Status:** open · **Severity:** Low
- **Where we found it:** probe.pdf E18 and "Open questions"; `reports/probe_results/verdicts.csv`
- **What we found:** the verdict is "supported" (first month 0.86, last 0.77), but the
  decision says "Dev covers almost one year only, so time effects stay hard to see".
- **The metric in plain words:** see I-06.
- **Real example:** same rows as I-06.
- **Why it might be:** the decision text was written before the result (same cause as I-11).
- **Next check:** fix together with I-06 and I-11.

## I-15 79 library alerts are dated after dev starts
- **Status:** explained (likely) · **Severity:** Low
- **Where we found it:** `data/splits/library.jsonl`, `data/splits/dev.jsonl` (field `report_date`)
- **What we found:** 79 library alerts are dated on or after 2025-07-04 (dev's first
  date), up to 2026-10-23. 4 dev alerts are dated 2026 (test period).
- **The metric in plain words:** none; this is about which alerts sit in which part.
- **Real example:** library alert 17228 (SR/02937/26), "Motorcycle", 2026-10-23, Belgium.
  Its `twin_group` is 10418, an older library alert.
- **Why it might be:** the pipeline keeps twins (the same product reported again)
  together in the part where the first one landed, so no product sits in both
  library and test. That is on purpose.
- **Next check:** confirm the 4 dev alerts from 2026 are twins of dev alerts in the same way.

## I-16 Old split files in `data/` don't match `data/splits/`
- **Status:** open · **Severity:** Medium
- **Where we found it:** `data/dev.jsonl`, `data/knowledge.jsonl`, `data/test.jsonl`
  against `data/splits/`
- **What we found:** `data/dev.jsonl` has 1,609 rows (dates 2022-01-07 to 2025-11-28);
  `data/splits/dev.jsonl` has 1,658. Same mismatch for knowledge/library (12,211 vs
  11,913) and test (3,455 vs 3,370). The probes correctly read `data/splits/`
  (`boxes/probes.py`, `_read_split`).
- **The metric in plain words:** none; this is housekeeping.
- **Real example:** the row counts above.
- **Why it might be:** files left over from an older pipeline run.
- **Next check:** search the code for anything still reading the old files, then move
  them to an `old/` folder or delete them.

## I-17 B9 (chemical names) has not run
- **Status:** open · **Severity:** Low
- **Where we found it:** probe.pdf B9; `boxes/probe_groups.py` (B9 is skipped on purpose)
- **What we found:** the probe waits for Dev to approve a list of substance names.
- **The metric in plain words:** the planned check: for a Chemical alert, do its
  neighbours name the same substance (lead, cadmium, …)?
- **Real example:** dev alert 12095 (SR/02453/25), "Necklace set": its risk text says
  "excessive concentration of cadmium (measured value up to 37 % by weight)". B9
  would check whether its neighbours also say cadmium.
- **Why it might be:** waiting on Dev, by design.
- **Next check:** write and approve the substance list, then run B9.

## I-18 Nobody has read the 20 hand-review examples yet
- **Status:** open · **Severity:** Medium
- **Where we found it:** probe.pdf F24; `reports/probe_results/hand_review_collections_1_and_3.md`
- **What we found:** 20 random dev alerts with their 5 neighbours are saved for a human
  to judge; the program doesn't judge them.
- **The metric in plain words:** none; this is a human check that the neighbours make sense.
- **Real example:** dev alert 12122, "Vintage garden furniture and gardening pots…
  manufactured about 1950-1993", danger Chemical. bge plain neighbours: Burns+Fire,
  Injuries, Injuries, Fire, Chemical, so only 1 of 5.
- **Why it might be:** the hint is "made 1950–1993" (old paint can contain lead). The
  search sees "garden furniture", not the age.
- **Next check:** Dev reads all 20 and writes one line per alert: makes sense / doesn't.

## I-19 Closer neighbours share law and danger more often, but exact copies lose on danger
- **Status:** explained (likely) · **Severity:** High
- **Where we found it:** not in probe.pdf; our own check on 2026-11-10 with all 1,658
  dev alerts × their 5 nearest library alerts (bge plain), 8,290 pairs. Inputs:
  `data/splits/`, `data/embeddings/` and the saved dev query vectors in
  `reports/probe_results/cache/`. The script (`similar_means_same.py`) is in the
  session scratchpad, not in the repo yet. Related: I-01, I-12.
- **What we found:**

  | Neighbour's similarity | Pairs | Shares a danger | Shares a law |
  |---|---|---|---|
  | below 0.80 | 1,704 | 0.59 | 0.62 |
  | 0.80–0.85 | 1,464 | 0.72 | 0.77 |
  | 0.85–0.90 | 1,462 | 0.81 | 0.80 |
  | 0.90–0.95 | 1,008 | 0.93 | 0.93 |
  | 0.95–0.99 | 695 | 0.98 | 0.96 |
  | 0.99–1.00 (copies) | 1,957 | **0.86** | 0.98 |
  | luck (random alert) | | 0.30 | 0.15 |

  Both climb as similarity goes up. At exact copies, the law stays at 0.98 but the
  danger drops from 0.98 to 0.86.
- **The metric in plain words:** take one new alert and one of its 5 closest old
  alerts. "Shares a danger" = they have at least one danger in common. "Shares a law"
  = they have at least one law in common. The table shows how often that is true,
  grouped by how alike the two texts are.
- **Real example:** dev alert 13729 (SR/03987/25), "Passenger car.", danger Fire, law
  Motor Vehicles Approval Regulation. Its 5 neighbours all have identical text and
  similarity 1.0. All 5 share the law, but only 3 share the danger: Fire+Injuries
  (11501), Fire (12737), Fire (10644). The other two are Electric shock (16587) and
  Environment (13255).
- **Why it might be:** the law follows the product (a car is always under the car
  law). The danger follows the specific defect (brakes, battery, emissions), and a
  one-line description like "Passenger car." doesn't mention the defect. So the law is
  the easy half of the answer and the danger is the hard half.
- **Next check:** re-run the table without Motor vehicles, to see whether cars alone
  cause the drop at 1.0. Then move the script into `boxes/` so it becomes a proper probe.

## I-20 Before the classifier: clean old split files and build one honest scorecard; the rest can wait
- **Status:** open · **Severity:** High
- **Where we found it:** our triage of I-01 to I-19 on 2026-11-10, before the next plan
  step: `project_plan.md` section 9, system 3, "Classifier on the embeddings
  (e.g. logistic regression, scikit-learn)". Related: I-01, I-02, I-03, I-04, I-16.
- **What we found:** only 5 entries change the classifier's score or what it learns
  from. All others (I-05 to I-15, I-17 to I-19) can wait.

  | Before the classifier | Why | What to do |
  |---|---|---|
  | I-16 old split files | `data/dev.jsonl` has 1,609 rows, `data/splits/dev.jsonl` 1,658; it could train on the wrong file | Move or delete the old files |
  | I-01 copies | 407 of 1,658 dev alerts have the same text as a library alert, which the classifier will have studied | Score with and without copies |
  | I-02 easy yardstick | The category rule already gets vote accuracy 0.70 (`F21_compare_k5.csv`, row `baseline`) | Compare against the category rule, not luck |
  | I-03 + I-04 Chemical | 794 of 1,658 dev alerts (48%) are Chemical, so saying "Chemical" often looks good | Report macro-F1 and the score without Chemical; try giving rare dangers more weight in training (`class_weight`) |

  I-01 to I-04 need one shared **scorecard** function that every system goes through
  (luck, category rule, vote, classifier, later Gemini). The data itself doesn't change.

  **Who does what** (added 2026-11-10). The rule: Dev builds what he will be asked
  about in an interview; Claude does what has no learning value.

  | Work | Who | Why |
  |---|---|---|
  | Scorecard (I-01 to I-04) | Dev, Claude as buddy (`/box` → Dev writes the spec → Claude explains → Dev builds) | Core data-science skill: "how did you make sure your score is honest?" Dev must explain it in his own words |
  | Classifier (next plan step) | Dev, Claude as buddy | The first real training in the project. Strong interview material |
  | Hand review (I-18), substance list (I-17) | Dev alone | Judgment calls only a human can make; about 30 minutes of reading (estimate) |
  | Cleanup (I-16) | Claude, Dev watching | No learning value. Dev types the git and move commands himself (`claude.md` rule) |
  | Report bugs (I-09 to I-14) | Claude | Wording and display bugs, no skill to gain. Dev checks the result |

  **Session by session** (added 2026-11-11). The encoder (bge, the model that turns
  text into 768 numbers) stays frozen (unchanged) in every session below. Everything
  we train sits on top of its numbers.

  | Session | Build | Solves | Who | Ends with (commit) |
  |---|---|---|---|---|
  | Today | Save all probe work in git (code, tests, reports, this log, `/addinvest`) | Nothing gets lost | Dev types, Claude explains | "Add probe report, investigation log, /addinvest" |
  | S1 | Move old split files; merge GPSD/GPSR into one label; check the 4 dev alerts from 2026 | I-16, I-21, I-15 | Claude, Dev watches and types git | Clean data, the same everywhere |
  | S2 | Scorecard function: score with/without copies, without Chemical, macro-F1, for risk and law | I-01, I-02, I-03, I-04 | Dev with `/box` | Scorecard + tests on a 3-row table |
  | S3 | Luck, category rule and vote through the scorecard → honest baseline table | Round 1 of the plan done | Dev | Baseline table saved |
  | Homework | Read the 20 hand-review examples | I-18 | Dev alone | One line per alert |
  | S4 | Logistic regression for risk + law, with class weights | First real training | Dev with `/box` | Classifier rows in the table |
  | S5 | PyTorch network with two outputs (risk + law) | Multi-task learning | Dev with `/box` | Network rows in the table |
  | S6+ | Gemini + RAG: product + 5 neighbours + classifier guess → danger, why, law | Round 2 of the plan; I-05, I-19 | Dev with `/box` | Gemini rows in the table |
  | Side task | Fix report wording and display bugs | I-09 to I-14 | Claude | Report rebuilt |

  **Decision gates** (stop and decide):

  | Gate | After | Question | If yes | If no |
  |---|---|---|---|---|
  | 1 | S3 | Is the honest vote still clearly above the category rule? | Go to S4 | Go to S4 anyway; note that Gemini matters more |
  | 2 | S4 | Does logistic regression beat the vote? | Note it for the README | Fine: memory beats learning here (also an interview story) |
  | 3 | S5 | Does the network beat logistic regression by more than its likely range? | Consider fine-tuning the encoder, but only after Gemini works | Skip fine-tuning; go straight to Gemini |

  **Probe triage map** (added 2026-11-11). Where the bad-news probes and the work
  items from probe.pdf live in this log:

  | Probe | Bad news in plain words | Entry | Worked on in |
  |---|---|---|---|
  | C11 | 609 dev alerts have a near-copy in the library and flatter the score | I-01, I-13 | S2 scorecard |
  | B6 | Word-for-word copies score 0.88 against 0.76 for the rest | I-01 | S2 scorecard |
  | E19 | Neighbours match the reporting country's writing style | I-05 | S6+ Gemini, real listings |
  | E18 | Newer alerts score lower (July 0.86 → September 0.74) | I-06, I-14 | Final test |
  | B4 | Thin descriptions score 0.66 against 0.81 | I-22 | Later: low-confidence flag |
  | D14 | Even near-identical alerts sometimes have different dangers | I-12, I-19 | S6+ Gemini |
  | G25 | The weak-match cut-off flags 40% of alerts | I-07, I-08 | Later: low-confidence flag |
  | C10, F21 | Scores compared only against luck | I-02 | S2/S3 |
  | D15 | Chemical carries the average; Fire weakest (0.44) | I-03, I-04 | S2 scorecard |
  | F24 | 20 hand-review examples not read | I-18 | Homework |

  Time-box: S4 and S5 get at most 2 sessions each, so the classifiers don't push
  Gemini back. Every session: read "Where we left off" → `/box` for one function →
  3-row table first, then real data → result as a table → `/addinvest` anything
  surprising → Dev commits and writes "Where we left off".
- **The metric in plain words:** a scorecard = one fixed way of marking every method,
  so no method gets an easier test. Macro-F1 = a score where each danger type counts
  equally, so being good at Chemical alone can't carry it. "Without copies" = the same
  score after removing new alerts whose text already sits in the library word for word.
- **Real example:** dev alert 12115 (SR/02420/25), text "Passenger car.", danger
  Injuries. The library holds the exact same text at least 5 times: 990 (A12/00821/22),
  10643 (SR/00999/25) and 10645 (SR/01001/25) with Injuries; 10644 (SR/01000/25) and
  12737 (SR/03058/25) with Fire. A classifier trained on the library has already seen
  this text with its answer, so a right guess here is memory, not skill. Only a
  "without copies" score shows that.
- **Why it might be:** the classifier is scored on the same dev alerts, with the same
  data, as the vote. So it inherits the same measurement traps.
- **Next check:** write the scorecard function with `/box`, run luck, category rule
  and vote through it (honest baseline table), then add the classifier as one more row.

## I-21 The general safety law has two names (old Directive, new Regulation), so right answers get marked wrong
- **Status:** open · **Severity:** High
- **Where we found it:** our label check on 2026-11-11 while planning the law
  classifier; `data/splits/library.jsonl` and `data/splits/dev.jsonl` (field
  `law_names`). The plan already warns about it: `project_plan.md` line 157 ("Treat
  them as old and new versions of the same rule"). Related: I-20.
- **What we found:**

  | Label | Library (training) | Dev (testing) |
  |---|---|---|
  | General Product Safety **Directive** (old) | 1,043 alerts, 2022-01-07 to 2025-06-06 | 5 alerts, 2025-07-11 to 2025-10-24 |
  | General Product Safety **Regulation** (new) | 145 alerts, 2023-02-17 to 2025-07-04 | 120 alerts, 2025-07-04 to 2025-11-21 |

  The old name dominates training and the new name dominates testing. It already
  hurts today: 64 of the 120 dev "Regulation" alerts have 3 or more of their 5
  neighbours saying "Directive", so the vote names the old law and is marked wrong.
  The law scores we quoted (vote 0.86, category rule 0.80) are therefore a bit too
  low; by how much is not checked yet. The switch is not a clean cut by date: the
  new name appears from 2023, and the old name still appears in October 2025.
- **The metric in plain words:** none; this is about the labels (the correct
  answers). The same law has two names, and a computer treats two names as two
  different answers.
- **Real example:** dev alert 12119 (SR/02470/25), "Step ladder" (Hand tools),
  2025-07-04, law "General Product Safety Regulation". Its nearest library alerts
  include three older ladders, 1091 (A12/00967/22), 1000 (A12/00839/22) and 1090
  (A12/00966/22), all labelled "General Product Safety Directive". The vote says
  "Directive" and is marked wrong, though it is the same law.
- **Why it might be:** the EU replaced the old Directive with the new Regulation
  (in force from 13 December 2024; date from EU law, not checked in our repo), so
  newer alerts use the new name. Guess: some alerts from 2023 and 2025 were labelled
  differently by individual countries, which is why the change is not a clean cut.
- **Next check:** merge both names into one label, "General Product Safety
  (GPSD/GPSR)", before training. Then re-score the law vote and category rule to see
  how much they go up.

## I-22 Thin descriptions (text that only repeats the product name) score lower
- **Status:** open · **Severity:** Medium
- **Where we found it:** probe.pdf B4; `reports/probe_results/B4_length.csv`. The
  "thin" flag is set by `is_thin` in `boxes/preprocessing.py` and stored as the
  `is_thin` field in `data/splits/dev.jsonl`. Related: I-01, I-19.
- **What we found:** 170 of 1,658 dev alerts are thin. They score 0.66; the other
  1,488 score 0.81. Gap 0.14 (likely range 0.09 to 0.20), so the gap is real. 122 of
  the 170 thin alerts (72%) are Motor vehicles, then Cosmetics 24, Chemical products
  14 and Electrical appliances 3.
- **The metric in plain words:** "thin" = the description adds nothing to the product
  name (e.g. product "Turntable", description "Turntable."). The score is precision@5:
  of the 5 closest old alerts, the share that has a danger in common.
- **Real example:** dev alert 12405 (SR/02742/25), "Turntable" (Electrical
  appliances), description "Turntable.", danger Environment. Its 5 neighbours are
  other one-word electrical products: headphones 5397 (Chemical, Environment), power
  supply 1051 (Environment), kettle 470 (Electric shock), hand mixer 6694 (Burns),
  toaster 410 (Burns, Fire). Only 2 of 5 share its danger.
- **Why it might be:** with only a product name, the search can only find "similar
  products", not "similar defects". Most thin alerts are car recalls, which are
  written as one line (see I-01, I-19).
- **Next check:** in the scorecard (S2), also report the score with and without thin
  alerts. Later, mark thin alerts as low confidence and let Gemini or a human decide.
