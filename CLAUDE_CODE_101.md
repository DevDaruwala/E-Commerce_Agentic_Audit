# Claude Code 101 — for this project

Claude Code is Anthropic's coding agent, built into VS Code as an
extension. Important mental model: **it's a different "brain" from
this chat** — it doesn't remember our conversation. That's exactly
why we're also creating a `CLAUDE.md` file (see below) — it's how we
hand it the context it needs automatically, every session.

---

## Getting it running

1. **Check the extension is installed:** `Ctrl+Shift+X` (Linux) or
   `Cmd+Shift+X` (Mac) → search "Claude Code" → confirm the publisher
   says **Anthropic** with a verified checkmark (not a community
   clone — several exist and can mishandle your credentials).
2. **Open your project folder** in VS Code (`E-Commerce_Agentic_Audit`).
3. **Open the panel:** click the ✱ (Spark) icon in the sidebar — it
   only appears once a file is open. First launch opens a browser
   sign-in — log in with your Claude account (your Pro plan covers
   Claude Code usage).
4. Alternatively, open the integrated terminal (`` Ctrl+` ``) and type
   `claude` — this is the CLI version. Both share the same
   conversation history; you can jump between them with `claude
   --resume`.

**Which should you use day-to-day?** The panel — better for reviewing
diffs visually, which matters a lot given your "understand every
change" rule. Drop into the terminal version only for things the CLI
does that the panel can't yet (like adding new MCP servers).

## The most important habit for you specifically: Plan Mode

Since your whole approach is "understand, don't vibe-code," always
let Claude Code show you its **plan** before it edits anything, and
actually read it. Don't auto-accept edits by default — review the
diff it proposes, ask it to explain any part you don't follow, *then*
accept. This is the single biggest lever for making Claude Code a
teaching tool instead of a code-vending machine.

## Permissions — it won't just do things silently

By default, Claude Code **asks before** running commands or editing
files. Don't turn on "auto-accept edits" mode for this project —
keep the guardrail on so every change stays something you approved
and understood.

## Git — no special setup needed, but stay deliberate

Claude Code can run `git` commands for you (it already sees your repo
since it's just a folder with `.git` in it) — but per your own
`GIT_GITHUB_101.md` rules: **ask it to show you the diff and propose
a commit message, and you decide whether to approve the commit** —
don't let it commit and push silently. This keeps you the one who
understands what's in every commit, which is the whole point of the
discipline you set for yourself earlier.

## Slash commands worth knowing now (not all of them)

- `/mcp` — see/manage MCP tool servers (relevant once you're in Phase 2)
- `/ide` — reconnect to VS Code if the connection drops
- `/resume` — pick up a past conversation
- `/config` — extension settings, e.g. turning auto-accept on/off

Skip the rest of the slash commands for now — same time-boxing rule
as everything else in this project.

## The file that actually matters most: `CLAUDE.md`

Claude Code automatically reads a file named exactly `CLAUDE.md` in
your project root, every session, without you pasting anything. This
is how it learns the project context and how you want to work,
without you re-explaining it each time. See the one provided
alongside this guide — drop it straight into your project root.

**Keep `CLAUDE.md` short.** It's read every single session, so it's
not the place to paste your whole `MASTER_PLAN.md` — just enough to
point Claude Code at the right files and set expectations, which is
exactly what the provided one does.
