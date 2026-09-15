# Git & GitHub 101 — just what you need for now

This is not a full Git course. It's the small slice you actually need
to work on this project without getting stuck, plus what to do when
something looks scary (it usually isn't).

---

## The 5 commands you'll use 90% of the time

```
git status          # "what's going on right now?" — run this constantly, it's always safe
git add <file>       # "stage this file" — or `git add .` for everything you changed
git commit -m "..."   # "save a snapshot" with a short message saying what changed
git push              # "send my commits to GitHub"
git pull              # "get any commits from GitHub that I don't have yet"
```

If you only remember one habit: **run `git status` before and after almost everything.** It never changes anything, it just tells you what's going on. There's no way to break your project by running it too much.

---

## The daily workflow (the loop)

Every time you sit down to work:

1. `git pull` — get any changes first, especially if you ever edit on GitHub's website too.
2. Do your work — write code, save files.
3. `git status` — see what changed.
4. `git add .` — stage everything you want to save.
5. `git commit -m "short description of what you did"` — save the snapshot.
6. `git push` — send it to GitHub.

Do this **often** — after finishing one small working piece, not once a week after 10 hours of changes. Small commits are easier to understand later and much easier to undo if something breaks.

---

## Writing a decent commit message

Bad: `git commit -m "fixes"`
Good: `git commit -m "Add validation for missing required fields"`

Rule of thumb: finish the sentence *"This commit will..."* — that's your message.

---

## .gitignore — what it's for

Some files should **never** be pushed to GitHub:
- Your virtual environment folder (it's huge and machine-specific — everyone recreates their own)
- `.env` (has your real API keys — never share these)
- `__pycache__/`, `*.pyc` (Python's own junk files)
- `*.pkl` (trained models — these are generated, not source code)

Your project's `.gitignore` already handles all of this. If you ever create a new venv with a different name, add its folder name to `.gitignore` too — otherwise it can accidentally get committed.

**Check before you commit anything new:** if `git status` shows a huge folder (like a venv) as "untracked," stop and ask whether it should really be tracked before you `git add .`.

---

## When Git yells at you — the 3 messages you'll actually see

**"Updates were rejected... (fetch first)"**
Means: GitHub has a commit your laptop doesn't have (often because you edited something on the GitHub website directly). Fix: `git pull` then `git push` again.

**"You have divergent branches and need to specify how to reconcile them"**
Means: your laptop and GitHub each have commits the other doesn't. Fix (as a beginner, always pick merge):
```
git config pull.rebase false
git pull
git push
```

**Merge conflict markers appear in a file** (you'll see `<<<<<<<`, `=======`, `>>>>>>>`)
Means: you and GitHub changed the *same lines* of the *same file*, and Git can't guess which version you want. Open the file, manually keep the part you want, delete the `<<<<<<<`/`=======`/`>>>>>>>` marker lines, then:
```
git add <the file>
git commit
git push
```
If this ever happens and feels confusing, paste me the file and I'll walk you through resolving it.

---

## Undoing mistakes (safely)

- **Changed a file but haven't committed yet, want to throw it away:**
  `git restore <file>`
- **Committed something but haven't pushed yet, want to undo the last commit (keep the changes):**
  `git reset --soft HEAD~1`
- **Already pushed a bad commit — don't rewrite history others might have.** Instead:
  `git revert <commit-hash>` — this makes a *new* commit that undoes the old one, safely.

If you're ever unsure which of these applies, stop and ask me before running it — undoing things wrong is the one way Git can genuinely cause a mess.

---

## Golden rules

1. **Commit often**, in small pieces — one working thing at a time, not everything at the end of the day.
2. **Never commit `.env` or real API keys.** If you ever do by accident, tell me immediately — the fix is more than just deleting the file (the key is still in the history).
3. **Pull before you push**, especially if you ever touch the GitHub website directly.
4. **Don't edit on GitHub's website and your laptop in the same session** — pick one, or always pull right after using the other.
5. **Write commit messages for future-you**, not present-you. "fixed stuff" tells you nothing in 3 weeks.

---

## What you don't need yet (so don't worry about it)

- **Branches** — working on a copy of the code separate from `main`. Useful once you're doing bigger experimental changes (like Phase 2's agent work). We'll introduce this when it actually helps.
- **Rebasing** — an alternative to merging. Skip it for now; merge is fine.
- **Tags/releases** — marking specific versions. Not needed until much later, if at all, for this project.

When any of these become actually useful for what we're building, I'll explain them at that point — not before.