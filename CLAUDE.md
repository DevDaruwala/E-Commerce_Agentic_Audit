# E-Commerce Agentic Audit — context for Claude Code

Read `CODING_BUDDY_BRIEFING.md` in this repo first — it has the full
project context, architecture, dataset strategy, and phase plan.
Also relevant: `master_plan.md`, `Dataset_Strategy.md`,
`Git_Github_101.md`.

## Who you're helping
A beginner in Python, OOP, and FastAPI, explicitly prioritizing real
understanding over speed. This project exists to build practical
skill, not just to produce finished code.

## How to work with me
- Always use Plan Mode — show me your plan before editing files. I
  want to understand every change, not just accept it.
- One file/task at a time, matching the Phase 1 build order in
  `CODING_BUDDY_BRIEFING.md` Section 6 — don't jump ahead in the
  phase plan without flagging it first.
- Never invent or guess GPSR compliance field values — follow
  `Dataset_Strategy.md` exactly (real fields from real sources,
  synthetic fields clearly treated as synthetic).

## How to explain code
- For anything non-trivial or new to me, explain the REASONING before
  or alongside the code — not just what it does, but why this
  approach.
- When code references something defined elsewhere (a field in
  another class, a function from another file), point out WHERE it's
  defined — don't assume I'll trace it myself.
- Comment generated code heavily enough that I could explain it back
  to someone else afterward.
- If I ask "why does this work," trace it with a REAL example and
  real values — not just abstract syntax rules.

## What I build vs. what you build
Per CODING_BUDDY_BRIEFING.md's ownership split:
- Stage 1 core files (main.py, schemas.py, validation.py,
  hygiene_check.py, fixed llm_audit) — I write these myself. Review,
  suggest fixes, explain bugs — don't write full implementations
  unless I explicitly ask.
- Dataset preprocessing scripts — you can write these directly.
- Stage 2 (LangGraph, RAG, MCP, agents) — I write these myself.
- Stage 3 (Docker, CI/CD, Azure, Streamlit polish, pytest scaffolding)
  — you can write these directly; I'll review and ask questions.

## Git
Show me the diff and a proposed commit message, but let me approve
before you commit or push — don't do it silently.

## Do not
- Add a frontend framework (React, Vue, etc.) — Streamlit only.
- Turn on auto-accept edits mode for this project.