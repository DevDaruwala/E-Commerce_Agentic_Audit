# Build Log

Automatic progress log, appended to by a git post-commit hook on every
commit. One entry per commit: date/time, commit message, and a one-line
summary of files changed. Local to this machine only (.git/hooks/ isn't
tracked by git, so this file's *contents* accumulate here but the
mechanism generating them doesn't travel with clones).

## 2026-09-11 22:22:55

**Commit:** test: verify post-commit hook appends to BUILD_LOG.md

**Files changed:** No files changed

---

## 2026-09-15 14:15:37

**Commit:** new plan changes and hygiene_check

**Files changed:** 19 files changed, 2545 insertions(+), 23 deletions(-)

---

## 2026-09-19 00:34:19

**Commit:** Add recall_check.py, update schemas/hygiene_check, real RAPEX data + classifier dataset

**Files changed:** 5 files changed, 55 insertions(+), 5 deletions(-)

---

## 2026-09-19 00:58:52

**Commit:** Bug fixed, None and empy in hygine

**Files changed:** 2 files changed, 8 insertions(+), 6 deletions(-)

---

## 2026-10-14 15:06:28

**Commit:** Commit the data files main.py depends on; add pyarrow

- data/rapex_blacklist.json, fetch_rapex.py, build_eval_dataset.py,
  agent_eval_set.csv were previously untracked, so app.recall_check's
  import of rapex_blacklist.json broke a fresh clone before main.py
  ever reached startup
- requirements.txt: add pyarrow (needed by build_eval_dataset.py's
  McAuley parquet reads)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

**Files changed:** 5 files changed, 10379 insertions(+)

---

## 2026-10-14 15:14:12

**Commit:** hygiene_check.py: whitespace-only = missing; recall_check.py: cite alert + fix "most recent"

- hygiene_check.py: add _is_missing() so "   " counts as missing, not
  just None/"" (verified live against all 3 variants)
- recall_check.py: drop unused numpy import; cite the matched
  alert_reference + product_name instead of a generic message; group
  alerts by barcode and sort by (year, sequence) parsed from
  alert_reference instead of trusting file order for "most recent" —
  file order was confirmed unreliable (a 12-alert barcode had a higher
  sequence number NOT first in the file)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

**Files changed:** 2 files changed, 81 insertions(+), 21 deletions(-)

---

## 2026-10-14 15:15:44

**Commit:** Remove the ML classifier from the design entirely (not deferred)

Training data had source-style leakage, so the classifier slot is cut
from the pipeline: recall_check -> hygiene_check -> Audit agent team
(Investigator+tools -> Reviewer) -> Report writer -> AuditResult, no
risk-tier split.

- system-design.html: remove Step 2/low-high-risk boxes from both
  diagrams, redraw Step 1 straight into the Audit agent team, Report
  writer -> "Gemini (prompted)" (QLoRA cut, not deferred)
- CODING_BUDDY_BRIEFING.md, master_plan.md, Dataset_Strategy.md,
  README.md: same pipeline rewrite in prose/ASCII diagrams; "how we
  got here" sections get a one-line "Superseded" note, not a rewrite
- Dataset_Strategy.md: three-tier structure -> two tiers; new
  "Evaluation rules" section for agent_eval_set.csv (strip source_id/
  is_unsafe before the agent sees a row; known price/country/
  description-length leakage; weeks 52-104 must never feed the
  agent's future retrieval index)
- FIELD_DECISIONS.md: drop "classifier signal" framing, reframe for
  the agent
- app/classifier/ deleted (train.py, predict.py were both still
  raise NotImplementedError stubs; nothing imports app.classifier
  anywhere, confirmed by grep)
- requirements.txt: drop scikit-learn, joblib (both orphaned by the
  deletion above)
- Comment-only touch-ups in llm_audit.py, validation.py,
  sandbox_pandas.py (path), data/generator.py — no logic changes
- Groq -> Gemini as primary reasoning model throughout; MASTER_PLAN.md/
  GIT_GITHUB_101.md filename-casing fixed to the real master_plan.md/
  Git_Github_101.md
- SESSION_LOG.md: one new dated line recording this decision

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

**Files changed:** 16 files changed, 264 insertions(+), 297 deletions(-)

---

## 2026-10-17 19:40:09

**Commit:** Switch dependency and env template from Groq to Gemini

requirements.txt: groq -> google-genai.
.env.example: GROQ_API_KEY -> GEMINI_API_KEY.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>

**Files changed:** 4 files changed, 129 insertions(+), 7 deletions(-)

---

