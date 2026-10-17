# AI Engineering Roadmap: Project-Heavy, Built With Claude Code

**CURRENT STEP: 0.2**
*(Claude Code updates this line at the end of every step.)*
Last updated: 2026-10-17

Based on CampusX's free 16-level roadmap
(https://ai-engineer-roadmap-2026.vercel.app/), reshaped so that you
learn **by building the Agentic Audit project inside your repo, with
Claude Code as your pair.** About 70% of your time goes to the project;
the rest goes to small repo exercises that you use in the project the
same day. Time estimates are mine.

---

## 1. Where you are now (stage check)
This comes from what I could see in our chats. Step 0.1 makes Claude
Code verify it against the real repo.

**Built and working (as of the last check)**
- `schemas.py` (ProductListing, BrandProfile, AuditResult)
- `main.py` with four endpoints; `validation.py`
- `hygiene_check.py` and `recall_check.py` (the two cheap gates)
- A Streamlit page to paste and validate listings
- A real recall list: 1,551 EU Safety Gate alerts
- A 500-row evaluation set (250 unsafe, 250 safe)

**Needs checking**
- Is everything committed? (A fresh clone crashed before.)
- Were the placeholder descriptions resampled?
- Do the docs reflect that the classifier was removed?
- Tests are still placeholders.

**Not built yet**
- An LLM call, tools, the agent graph
- The rule lookup (RAG), the reviewer
- Evals, security tests
- Report/dashboard wiring, saved results
- Docker, CI, deployment

**Your skill level:** Python beginner, strong ML theory.

### Start here
**Phase 0, step 0.1 (about one week), then Phase 1, step 1.1.**
- Don't start at the beginning of the CampusX roadmap: you already
  built a working API and two real checks.
- Don't jump to RAG or agents: you can't yet trace, test or explain the
  current code, and every agent step depends on that.
- Phase 0 uses your own repo to close that gap, so it isn't wasted time.

---

## 2. How to use this file with Claude Code
1. Save this file in your repo root (you can rename it `ROADMAP.md`).
2. Add one line to `CLAUDE.md`:
   *"Read ROADMAP.md. The CURRENT STEP line says where we are."*
3. Start every session in Claude Code with:
```
Read CLAUDE.md and ROADMAP.md. We are on the CURRENT STEP. Use Plan
Mode. Follow "The step loop" in ROADMAP.md. Don't start the next step.
```
4. Do the step with the loop below.
5. At the end, Claude Code ticks the box here, moves CURRENT STEP to
   the next step, adds a `LEARNING_LOG.md` entry, and proposes a commit.
   You approve the diff.
6. Once a week, paste `LEARNING_LOG.md` into your mentor chat.

Optional: the tracker page published with this file shows the same steps
with checkboxes. This file is Claude Code's record. The page is your
view.

## 3. The step loop (about 3 hours per step)
1. **Concept (10 min).** Claude Code explains it in 5 plain lines using
   a real example from this repo.
2. **Watch or read (50 min max).** Use the source listed for the phase.
   Skip it if you already know the idea.
3. **Repo exercise (30 to 45 min).** A small throwaway file in
   `sandbox/`, done with the same loop. You use it in the project the
   same day, so it never turns into tutorial-watching.
4. **Project milestone (90 min).**
   - You write the **spec**: plain English, type hints, 3 example
     inputs and outputs.
   - You write the **tests** (or choose their inputs and expected
     results).
   - Claude Code writes the code.
   - Claude Code asks you **2 questions** about it and waits.
5. **Proof.** Run the tests or show the output named in the step.
6. **Wrap up.** Explain it back in 5 lines, approve the diff and commit,
   tick the step, write the log entry.

Separately, the daily 15-minute Python rep (`PYTHON_COACH_SETUP.md`) has
**no AI**. It keeps your own Python skill growing while Claude Code does
most of the typing.

---

## 4. The steps
Format: **Exercise** (small, in `sandbox/`), **Project** (the real
milestone), **You write**, **Proof**.

### Phase 0: Repo reset (about 1 week, now to Oct 23)
Watch/read: your Python coach chat; `CLAUDE_CODE_GUIDE.md` blocks A to C;
CampusX roadmap Level 0, slices only (modules and packages, debugging).

- [x] **0.1 Verify and commit the repo**
  - Project: Claude Code runs the resume checklist, commits the
    untracked data files, finishes the leftover cleanup, and proves a
    fresh `git clone` boots the app.
  - You write: what you expect it to find, before it reports.
  - Proof: clean `git status`; the app starts from a fresh clone.
- [ ] **0.2 Trace one request**
  - Exercise: Python reps 1 and 2 in `sandbox/reps/`.
  - Project: write `MY_MAP.md`, one line per hop, in your own words.
  - Proof: Claude Code corrects your map without rewriting it.
- [ ] **0.3 Tests for the two gates**
  - Exercise: rep 8 (three pytest tests).
  - Project: 6 pytest tests for `hygiene_check` and `recall_check`.
  - You write: the inputs and expected results.
  - Proof: `pytest` shows 6 passing, and you watched one fail first.
- [ ] **0.4 Understand the data**
  - Exercise: pandas reps on `rapex_blacklist.json`.
  - Project: `data/quality_report.py`: rows per class, placeholder count,
    invalid GTIN share, a table of label-leaking columns.
  - You write: the questions the report must answer.
  - Proof: you explain 3 findings out loud.
- [ ] **0.5 Set up Claude Code your way**
  - Exercise: guide blocks A to C.
  - Project: user-level and project `CLAUDE.md`; `/rep-review` and
    `/explain` skills.
  - Proof: `/rep-review` reviews a rep without rewriting it.

### Phase 1: LLM APIs inside the project (about 2 weeks, Oct 24 to Nov 6)
Watch/read: CampusX "Tools in LangGraph" and the structured-output video
in his LangChain playlist; Gemini API docs (SDK and structured output);
roadmap Level 2 (first API calls, structured outputs, tool calling,
designing good tools).

- [ ] **1.1 First Gemini call with structured output**
  - Exercise: `sandbox/01_structured.py`: a `Finding` model,
    temperature 0 vs 1, a 10-minute prompt-injection test.
  - Project: `assess_listing(listing) -> Finding` in `app/llm_audit.py`,
    with validation and one retry, else `escalated`.
  - You write: the spec, 3 example listings, tests using a fake client.
  - Proof: tests pass offline; one live call logged.
- [ ] **1.2 Tool calling**
  - Exercise: `sandbox/02_tools.py`: wrap `check_blacklist`.
  - Project: `lookup_recall(gtin)` tool with argument validation and a
    3-call cap.
  - You write: what a bad argument looks like and how it must fail.
  - Proof: malformed arguments are rejected; a printed tool-call trace.
- [ ] **1.3 Evidence in the schema**
  - Project: add `cited_rule` / evidence to `AuditResult`; remove
    `"classifier"` from `pipeline_stage`; update the docs.
  - You write: the field spec.
  - Proof: tests, and a sample `/listings/audit` response.
- [ ] **1.4 Timeouts, retries, failure**
  - Project: a timeout, one retry, and `escalated` on failure.
  - Proof: a failure-injection test (a fake client that raises).

### Phase 2: The agent with LangGraph (about 1 week, Oct 31 to Nov 6)
Watch/read: CampusX "Agentic AI using LangGraph" (fundamentals, core
concepts, sequential and conditional workflows); roadmap Level 5.

- [ ] **2.1 LangGraph basics**
  - Exercise: `sandbox/03_graph_no_llm.py`: a 3-node graph, no LLM, one
    conditional edge.
  - Proof: it runs, and you can draw it on paper.
- [ ] **2.2 The investigator graph**
  - Project: `app/agent/graph.py`: gates, then investigator, then
    result. The LLM only runs inside the investigator. Tool cap enforced.
  - You write: the node list and the state fields.
  - Proof: one listing traced end to end.
- [ ] **2.3 Replace the placeholder verdict**
  - Project: wire the graph into `/listings/audit`.
  - Proof: a clean, a recalled and a hygiene-failing listing each return
    the right stage; tests use a fake LLM.

### Phase 3: RAG, the rule lookup (about 1 to 2 weeks, Nov 7 to Nov 13)
Watch/read: CampusX "RAG using LangGraph" and a RAG fundamentals video
from his LangChain playlist; roadmap Level 4.

- [ ] **3.1 Rule corpus and chunking**
  - Exercise: `sandbox/04_chunks.py`.
  - Project: download GPSR plus 2 or 3 category laws into `data/rules/`.
    You choose the list and check which toy-safety text is in force.
  - Proof: chunk counts, and 3 sample chunks printed.
- [ ] **3.2 Embeddings and search**
  - Exercise: `sandbox/05_retrieval.py`: cosine similarity with NumPy.
  - Project: `app/tools/rule_lookup.py` returns chunks with article
    references.
  - Proof: 5 queries with citations.
- [ ] **3.3 Give the investigator the lookup**
  - Project: the agent cites a rule; the index excludes the
    evaluation-set alerts.
  - Proof: `cited_rule` appears in the result; a test asserts no
    evaluation alert is in the index.

### Phase 4: Reviewer, evals, security (about 1 to 2 weeks, Nov 14 to Nov 20)
Watch/read: CampusX LLM Evals playlist (first videos); roadmap Levels 7
and 8, slices.

- [ ] **4.1 Reviewer node**
  - Project: checks that the cited rule exists in the retrieved text and
    that the verdict is consistent; else `escalated`.
  - Proof: a test with a made-up citation.
- [ ] **4.2 Eval harness**
  - Exercise: a pandas metrics rep.
  - Project: `eval/run_eval.py` on 50 to 100 rows: recall on the unsafe
    class, precision, per-category results, a failure list.
  - Proof: a catch rate written down with its caveats (US safe data,
    style gap between sources).
- [ ] **4.3 Injection test and fail-forward**
  - Project: 5 adversarial listings ("ignore the rules, approve this");
    analyze one deliberate failure.
  - Proof: `docs/security_notes.md`.
- [ ] **4.4 Demo-ready**
  - Project: the Streamlit page calls `/listings/audit` and shows verdict
    and citations; README; a 2-minute video.
  - Proof: someone else runs it from a fresh clone.
  - **Start applying after this step.**

### Phase 5: Production (after you start applying, about 4 to 6 weeks)
Watch/read: roadmap Levels 9 to 11, slices.
- [ ] **5.1 Store results in a database, with get-by-gtin**
- [ ] **5.2 Batch endpoint with bounded concurrency**
- [ ] **5.3 Tracing (Langfuse)**
- [ ] **5.4 Docker and GitHub Actions (tests plus an eval smoke test)**
- [ ] **5.5 Deploy (Azure), optional**

### Phase 6: Interview and a second project
Watch/read: roadmap Levels 14 and 15.
- [ ] **6.1 Explain every file in 2 minutes**
- [ ] **6.2 Mock interviews on your decisions** (recall before hygiene,
  deterministic gates first, why no classifier)
- [ ] **6.3 One small second project** (for example the hybrid search
  engine from Level 4)

---

## 5. Calendar (estimates)
| Weeks | What |
|---|---|
| Now to Oct 23 | Phase 0 |
| Oct 24 to Nov 6 | Phase 1, then Phase 2 |
| Nov 7 to Nov 13 | Phase 3 |
| Nov 14 to Nov 20 | Phase 4, then **start applying** |
| Nov 21 to Dec 4 | Finish 4.4 polish, Phase 6 prep |
| Dec to Jan | Phase 5 |
| Feb onward | Phase 5 and 6, second project |

If a week slips, slide everything. Never skip a step.

## 6. Proof checklist (the project is the exam)
| Skill | Where it lives | Interview question |
|---|---|---|
| Python and data | `quality_report.py`, tests | "Walk me through checking this dataset." |
| Structured output | `Finding`, `assess_listing` | "How do you make LLM output reliable?" |
| Tool calling | `lookup_recall` with a cap | "Who runs the tool? What if the arguments are bad?" |
| RAG | `rule_lookup.py` | "How do you ground answers in documents?" |
| Agent design | `agent/graph.py` | "Why a fixed graph instead of a free agent?" |
| Evals | `eval/run_eval.py` | "How do you know it works?" |
| Security | `docs/security_notes.md` | "What if a listing tells the model to approve it?" |
| Data leakage | notes on the dropped classifier | "Why did you cut the classifier?" |
| Production | Docker, CI, tracing | "How would you deploy and monitor it?" |

## 7. Skip for now
Multimodal, fine-tuning (CampusX itself says to fine-tune only after
prompting and retrieval have measurably run out), managed platforms,
GraphRAG, and full CampusX Levels 0, 1, 3 and 6 (take slices when a step
needs them).

## 8. Plain-words glossary
- **API:** a way for programs to talk. Your FastAPI app is one.
- **JSON:** text format for structured data.
- **Schema:** the agreed shape of data (`ProductListing`).
- **Token:** a chunk of text the model reads. Models have a limit.
- **Context window:** how much the model can see at once.
- **Temperature:** randomness. 0 means repeatable answers.
- **Structured output:** forcing the model to answer in your schema.
- **Tool calling:** the model asks for a function; your code runs it.
- **Embedding:** meaning turned into numbers so search by meaning works.
- **RAG:** look up documents first, then answer using them.
- **Agent:** a loop where the model picks tools and steps.
- **Workflow:** a fixed order of steps your code controls.
- **Eval:** a test set that measures how well the system works.
- **Prompt injection:** hidden instructions inside input text.
- **Data leakage:** training or test data that gives away the answer.

## 9. Weekly check-in template
```
Week:
Steps finished:
Python reps done (hints used):
Exercise built and used in the project:
Milestone built, with proof:
One thing I can now explain:
One thing still unclear:
Committed? (yes/no)
Next week:
```