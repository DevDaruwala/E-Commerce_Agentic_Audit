---
description: Add one finding to the investigation log (reports/INVESTIGATION.md)
---
Always use plain language, everyday words and short, logical sentences.
Explain any technical word the first time you use it.

The finding to add is: $ARGUMENTS
If that is empty, use the finding we were just talking about.

Typing /addinvest is my approval to write to reports/INVESTIGATION.md only.
No Plan Mode needed for this one file. Do not touch any other file. No commits.

Steps:
1. Read reports/INVESTIGATION.md.
2. Look for an entry about the same thing. If one exists, update that entry
   (add the new facts) instead of making a new one, and say so.
3. Check every number against the repo (the CSVs in reports/probe_results/,
   the files in data/splits/, the code in boxes/). Never invent a number.
   If a number can't be checked, write "not checked yet" next to it.
4. Find one real example from our data: an actual alert (index + case number,
   e.g. "dev alert 12095 (SR/02453/25), Necklace set") or an actual row from a
   saved results file. Never a made-up example.
5. Give it the next free ID (I-19, I-20, ...).
6. Write the entry with exactly these parts, same style as the entries above:
   - Title line: "## I-NN <the finding in one plain sentence>"
   - **Status:** open / explained / fixed · **Severity:** High / Medium / Low
   - **Where we found it:** report section and the file(s)
   - **What we found:** the facts, with numbers
   - **The metric in plain words:** what the number means, as if to someone
     with no tech background ("none" if there is no metric)
   - **Real example:** the example from step 4
   - **Why it might be:** our best guess at the cause; say "guess" if unproven
   - **Next check:** one concrete thing to do next
7. Add a row to the Summary table at the top (ID | Finding | Severity | Status).
8. In the reply, show the new or updated entry as a table (part | text),
   then say "Say OK, or tell me what to change."
