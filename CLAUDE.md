# E-Commerce Agentic Audit — context for Claude Code
Read AI_Engineering_Roadmap.md The CURRENT STEP line says where we are
Read `KNOWLEDGE_TRANSFER.md` first: it has the current architecture,
repo state, decisions and roadmap. If it conflicts with this file,
this file wins. `CODING_BUDDY_BRIEFING.md` is history only (it still
describes the removed classifier and Groq). Also useful:
`master_plan.md`, `Dataset_Strategy.md`, `FIELD_DECISIONS.md`,
`Git_Github_101.md`.


## Who you're helping
Dev is a beginner in Python and FastAPI, learning AI engineering to
become job-ready. The goal is understanding and a project he can
explain and defend in interviews, not just finished code.

## How we code together
- Always use Plan Mode. Show the plan before editing files.
- One small task at a time. Flag it before jumping ahead in the
  roadmap.
- Spec first: Dev writes a plain-English spec, type hints and 3 example
  inputs and outputs. You write the code from that spec.
- For core AI pieces (prompts, schemas, tools, graph, retrieval, evals)
  Dev also writes the tests. He can say "just write it" for a task.
- After you write code, ask Dev 2 short questions about it and wait for
  his answers before moving on.
- Dev's 15-minute no-AI practice reps are his own. Do not fill them in.
- You may write directly: data scripts, test scaffolding, Docker/CI,
  docs, Streamlit.
- Never invent or guess GPSR field values. Follow `Dataset_Strategy.md`
  and `FIELD_DECISIONS.md`. Never pad data with fabricated listings.
- Verify claims against the repo before relying on them. Say plainly
  when something is unfinished or unclear.

## How to explain code
- For anything non-trivial or new, explain the REASONING before or
  alongside the code: what it does and why this approach.
- When code uses something defined elsewhere (a field, a function from
  another file), point out WHERE it's defined.
- Comment generated code enough that Dev could explain it back to
  someone else.
- If he asks "why does this work", trace it with a REAL example and
  real values, not abstract syntax rules.

## Git
Show the diff and a proposed commit message. Wait for approval before
committing or pushing. End each session on something committed, and
offer to update "Where we left off" in `KNOWLEDGE_TRANSFER.md` and
`LEARNING_LOG.md`.

## Do not
- Add a frontend framework (React, Vue, etc.). Streamlit only.
- Turn on auto-accept edits for this project.
- Put secrets in tracked files. API keys go in `.env`.