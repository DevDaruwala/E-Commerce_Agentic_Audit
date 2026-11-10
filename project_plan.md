# Product Risk Analyst: Project Plan

*Written 2026-11-09 from the full design discussion. This file is the single
place where the idea, the two phases and the agent are written down. If it
conflicts with `CLAUDE.md`, `CLAUDE.md` wins.*

---

## 1. The aim in one line

**Given a product description, predict how the product could hurt someone,
explain why, and back it up with EU safety rules and similar past cases.
Score it against real EU Safety Gate (RAPEX) inspector reports.**

It is a **risk analyst**, not a safe/unsafe detector and not a judge.
It never says "this product is safe" or "this product is dangerous".
At most it says "worth a human look".

## 2. Why this design (short history)

- The first idea was an "AI auditor" for seller listings. The data could not
  support it: "unsafe" rows came from Safety Gate, "safe" rows from Amazon US.
  The two sources are written differently, so the label leaked
  (the model could learn "Safety Gate style vs Amazon style").
- A library of only dangerous products can never say what "good" looks like.
- So the project uses **one real source (Safety Gate)** for both inputs and
  answers. Every correct answer was written by a real inspector.

## 3. Input and output

**Input: `ProductInput`** (fields as they appear in a Safety Gate alert)

| Field | Example |
|---|---|
| category | Toys |
| product | Inflatable swim seat |
| name | Children's Swim Ring |
| model_type | QS0720 |
| description | Pink inflatable swim seat with sunshade and a fin. |
| country_of_origin | People's Republic of China |

No barcode: it would let the system look the answer up instead of reasoning.

**Output: `RiskAssessment`**

| Field | Meaning |
|---|---|
| risk_types | Fixed list (enum). Can hold more than one, most serious first |
| risk_description | The "why" |
| legal_provisions | Laws and standards. Must come from the rulebook |
| precedents | Past alerts used as evidence. Must be ones that were retrieved |
| confidence | low / medium / high |
| status | ok / escalated |

Dropped: "Measures taken by economic operators". It records what someone did
after the alert, not a property of the product, so it cannot be predicted.

## 4. High-level architecture (black boxes only)

```
Safety Gate data --> Library of past alerts   Rulebook (GPSR + EU standards)
 (weekly download)        |                          |
                          v                          v
Product description --> Find similar alerts --> Gemini decides --> Safety checks --> Result
                         (5 closest cases)     (agent can           (plain code,       |
                                                investigate)         retry once)       v
                                                                              Grade the system
                                                                          (compare with inspector)
```

Stored data: Safety Gate data, Library of past alerts, Rulebook.
The AI: Gemini. Everything else is plain code or a small embedding model.

## 5. Data

- **Source:** EU Safety Gate weekly XML export (public, updated weekly).
- **Fields we want:** category, product, name, model/type number, description,
  country of origin, risk type, risk description, legal provisions.
  Some of these may be sparsely filled. **The data check is the first task.**
- **One real example (alert INFO/00141/22):** "Inflatable children's swimming
  float", Swim Ring QUACKER FLOAT, yellow duck, risk type **Chemical** (too much
  DEHP in the plastic). The description sounds like Drowning, the real danger is
  Chemical. A good test case for voting vs Gemini.
- **Alert types differ:** alert numbers start with A12, SR, INFO and others.
  Decide in the data check whether to keep all kinds.
- **Never invent values.** Follow `Dataset_Strategy.md` and `FIELD_DECISIONS.md`.

### Splits (by time, not random)

| Part | Size | Text versions | Used for |
|---|---|---|---|
| Library (knowledge) | oldest ~70% | as it is | What the system searches in |
| Dev | middle ~10% | as is, hint-removed, marketing-style | Tuning only |
| Test | newest ~20% | as is, hint-removed, marketing-style | Final score, run once |
| Real listings | 30-50 | real seller text (+ clean-up step) | Final real-life check, run once |

Rules:
- **Dedupe across countries.** The same product reported by several countries
  must not land in both library and test. Also check near-twins by similarity.
- **Tune only on dev.** Never change anything after looking at test or
  real-listing scores.
- **Pick the real-listing alerts from the test split**, so the matching alert
  is not in the library.
- The library stays **real and untouched**, danger hints included. Never
  rewrite it.

## 6. Phase 1: Find the danger

Goal: guess how the product could hurt someone, using similar past cases.
This is the "R" (retrieval) in RAG.

1. **Get the alerts ready:** download, split by date, remove duplicates.
2. **Choose what text to embed:** start with **product type + description**,
   glued into one text. Leave out name, brand, model number and country
   (names confuse the search and can point at the exact product).
   Category may work better as a filter. Test other versions on dev.
3. **Embedding model:** start with `sentence-transformers/all-mpnet-base-v2`.
   Compare `BAAI/bge-base-en-v1.5` on the same dev set. Optional third:
   Gemini embeddings (free tier is small). **One model for everything:**
   library, dev, test, real listings and real use. Switching models means
   re-embedding the whole library. Write down the exact model name and version.
4. **Find the 5 closest past alerts** by cosine similarity (try 10 later).
5. **Check the match is really close:** compare the best score with the
   random-pair distribution (percentile of D_rand). If even the best match is
   weak, set confidence to low instead of guessing.
6. **Make the guess, two ways, built side by side:**
   - **Neighbours vote (no Gemini):** count the dangers of the 5 alerts.
     Multi-risk alerts: each danger gets a vote. Ties: take the closest neighbour.
   - **Gemini (RAG):** reads the product plus the 5 alerts and decides.
7. **Score it** against the inspector's risk type (see section 9).

Embeddings are only a lookup tool here. Voting is not RAG (no generation).
Gemini with the 5 neighbours is full RAG.

## 7. Phase 2: Explain and back it up

Goal: say why, and name the EU rules and standards it breaks, again pointing
to past cases as evidence. This is the "AG" (augmented generation) in RAG.

1. **Look up matching rules** in the rulebook (GPSR articles + list of EU
   standards and what each covers, e.g. EN 13138-3 for swim seats).
2. **Gemini writes the full answer** as structured output (`RiskAssessment`),
   from the product + 5 past alerts + matching rules.
3. **Guardrails (plain Python, no AI):**
   - Is the form valid? (Pydantic)
   - Is every rule Gemini named really in the rulebook?
   - Is every precedent it cites really one of the 5 it was given?
   - Fail: retry once. Fail again: `status = escalated` (needs a human).
4. **Reviewer (later):** a second Gemini call checks the reasoning against the
   evidence. Keep it only if the dev score goes up.
5. **FastAPI `/analyze`** endpoint and a **Streamlit** page.

In the real system, Gemini handles its part of Phase 1 and Phase 2 in **one
call**. The two phases are separate only to make them easy to understand.

Rulebook note: older alerts say "General Product Safety Directive", newer ones
"General Product Safety Regulation" (GPSR). Treat them as old and new versions
of the same rule, or Gemini will look wrong when it is right.

## 8. The Investigator agent (built after Phase 1 + 2 work and are scored)

**GenAI vs agentic:** in Phase 1 + 2 *we* decide every step and Gemini only
writes the answer. In the Investigator, Gemini decides its own next step.

**Tools it gets:** `search_library` (search past alerts again with better words),
`look_up_rule` (rulebook), `read_alert` (read one past alert in full).

**How it works:**
1. **Start from the tip:** the neighbours' vote plus the 5 past alerts.
2. **Read the description and list clues** (e.g. detachable valve, used in
   water, leg holes, rubber/polymer).
3. **Check every candidate danger with evidence**, even one with a single
   vote. Write down the reason before dropping a danger. Not "I don't think so".
4. **Draft the answer:** all supported dangers, most serious first, each with
   its rule and past case.
5. **Reviewer agent tries to break it, with evidence only:** for each danger,
   show the rule and the past case; no proof means remove it or lower
   confidence. Also asks "did you miss a danger?". Sends back **once**.
6. **Final answer, or `escalated`.**

**Rules to keep it fair and cheap:**
- **Library only, no internet,** at least when measuring scores. Safety Gate
  alerts are public, so searching the internet could find the exact answer.
- **Max about 6 tool uses per product** (free Gemini quota).
- The vote strength sets the effort: strong vote and close matches means a quick
  check; split vote or weak matches means "the tip is unreliable, investigate".
- Do not let Gemini just copy the vote: check how often it disagrees with the
  vote and whether it is right when it does.
- **Default is the one-shot GenAI path.** Use the agent for hard cases
  (split vote, weak matches). Let the dev scores decide.
- Imagined "what if" scenarios are not proof. Evidence only.

Other agent ideas, lower priority: analyst + reviewer back-and-forth, specialist
team (skip), agent that asks the user a question (demo only, cannot be scored),
weekly watcher that refreshes the library and reports score changes (MLOps bonus).

## 9. Evaluation

**Systems compared on the same dev/test alerts:**

1. Baseline table: most common danger per category (no AI)
2. Neighbours vote (embeddings, no Gemini)
3. Classifier on the embeddings (e.g. logistic regression, scikit-learn)
4. Gemini alone (no retrieval): what Gemini knows from memory
5. Gemini + RAG (library + rulebook)
6. Investigator agent (later)

**Metrics:**

| What | Metric |
|---|---|
| The lookup alone | precision@5: of the 5 neighbours, how many share the inspector's danger |
| The danger guess | accuracy and macro-F1, also per category and per risk type |
| The rules named | precision and recall against the inspector's list |
| The "why" | LLM-as-judge: do the two explanations mean the same thing |

**Generalisation tests (inspector text is not seller text):**
1. **Hint-removed run:** delete danger words ("detach", "sharp", "small parts",
   "battery") from the descriptions with a plain word list, search again. Shows
   how much the system leans on hints.
2. **Marketing-style stress test (synthetic):** rewrite descriptions in seller
   style with a **different model than the analyst**, tell it to keep facts, add
   fluff, never mention danger, check 20 by hand. Store as its own labelled
   file, report separately, never mix with real data or real scores.
3. **Real-listing set (most convincing):** 30-50 real listings matched to
   alerts in the test split. Collected by hand (open each link, confirm it is
   the same product, copy the text yourself, save alert number, link, date,
   and why it matches). Alerts with brand and model number are the best
   candidates. Expect to try 100-150 alerts. No bulk scraping.

**Seller text clean-up step (real-world use):** Gemini rewrites marketing text
as plain facts, adds nothing, then search. Experiment: Option A = clean-up of
the query into plain facts (default); Option B = rewrite the library into
seller style (keep the original inspector text attached as evidence). Judge
both on the real-listing set.

**Probes to run on the embeddings** (state the suspicion, run the test, then
fix it, read scores more carefully, or write it as a limit):
- Hint words: does the search work mainly because of them?
- Names and model numbers: do they pull matches?
- Same product, different risk: the maximum score voting can ever reach
- Near-twin leakage: how many test alerts have a near-copy in the library?
- Per risk type: is precision@5 fine overall but poor for rare dangers?
- Also: length, product type vs description alone, writing style by notifying
  country, alert type and year, multi-risk alerts, numbers and chemical names.
- Possible fixes for a leaning embedding space: centering, removing the top
  directions, whitening. Keep a fix only if precision@5 on dev improves.

**Cost control:** response cache (re-runs cost zero calls), checkpointing,
rate limiting and exponential backoff on 429 errors.

## 10. Build order: thin slice first, then thicken

Never finish one level and then start the next. Build the thinnest version of
the whole pipeline first, with placeholder boxes that return a simple fixed
answer, then make one box real at a time. Always come back up and run the whole
pipeline end to end, then measure.

| Step | What |
|---|---|
| 0 | **Data check:** download one week of XML, count how often each field is filled. If the data is not there, this plan changes |
| 1 | Data pipeline: extend `fetch_rapex.py`, time split, dedupe, save `alerts.jsonl` |
| 2 | **Round 1:** load, make_text, embed (mpnet), find 5 closest, vote, score. Baseline table and classifier baseline |
| 3 | **Round 2:** Gemini decides from the 5 alerts (structured output), compare with voting |
| 4 | **Round 3:** rulebook and guardrails, Phase 2 complete, probes |
| 5 | **Round 4:** Investigator agent, reviewer, FastAPI, Streamlit, Docker, CI, deployment |
| 6 | Real-listing set, stress test, README with honest limits |

**How to work on each box** (also in `CLAUDE.md`):
1. Write the box as four lines: name, in, out, one example.
2. Make a tiny table by hand (3 rows) and build the function on it.
3. Run it, print the result, compare with the example.
4. Connect it: the output of one function goes into the next.
5. Only then run it on the real file. Dev types the git commands himself.

## 11. Tech

| Tech | Role |
|---|---|
| EU Safety Gate (RAPEX) | All data and correct answers |
| Python, pandas | Everything, data handling |
| Pydantic | Input and output shape checks |
| sentence-transformers (all-mpnet-base-v2, later BAAI/bge-base-en-v1.5) | Text to numbers |
| NumPy | Cosine similarity |
| ChromaDB (after the plain version works) | Vector database for the precedent index |
| scikit-learn | Classifier baseline |
| Gemini API (`gemini-2.5-flash`, name in `.env` as `GEMINI_MODEL`) | The analyst |
| FastAPI, Streamlit | API and web page |
| Docker, GitHub Actions, one cloud deployment | Professional finish |

LangChain and LangGraph are not used at first. Plain Python first so every step
is understood; LangGraph may be added later for the retry loop and reviewer.

## 12. Where it sits in the real world

- Before it: seller tools that handle GPSR paperwork (labels, documents).
- After it: lab tests and Safety Gate alerts, then crawlers that find copies
  of already-reported products still on sale.
- **This project sits before the human decision:** an early warning and
  explanation tool for new products nobody has reported yet. It helps a human
  decide what to check first. Possible users: marketplace safety teams,
  inspectors, testing companies.
- Optional end feature: "screening mode" that screens 100-200 listings that
  merely *resemble* known dangerous products, and a "paste a link" reader.
  A full internet crawler stays in future work.

## 13. Known limitations (say these in interviews)

1. Every Safety Gate item is unsafe, so the system always finds a risk. It is a
   risk analyst, not a safe/unsafe detector. Output means "worth a human look".
2. Inspector descriptions sometimes hint at the danger. Real seller listings
   are harder. The hint-removed run and real-listing set measure this.
3. Similar products do not always share a risk (the duck: looks like Drowning,
   was Chemical). Voting has a ceiling.
4. Inspector writing is not marketing copy. The newest alerts also have a
   different category mix (cosmetics are now the biggest group).
5. Free-tier Gemini quota limits how often the full test set can be run.
6. Marketing-style text is synthetic and labelled as such. Real listings are
   the proof.

## 14. Open questions

- Standards catalog titles: the codes (EN 13138-3) appear in alerts, the titles
  are on the CEN website. Need a simple, legal way to get them.
- Risk type list: take the exact list from the data, including how multi-risk
  alerts are written.
- Split sizes: set from the real number of alerts per week.
- Which alert types (A12, SR, INFO, others) to keep.
- Which embedding model wins on dev (mpnet vs BAAI vs Gemini).
- Optional second dataset (e.g. US CPSC recalls) as a late generalisation test,
  with a hazard-label mapping and cross-country dedupe. Never mixed into the
  library at the start.