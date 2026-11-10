---
description: Fill in the four-line spec for one function, with suggestions
---
Always use plain language, everyday words and short, logical sentences.
Explain any technical word the first time you use it.

The function I want to specify is: $ARGUMENTS

Do not write any code yet. Ask me these questions one at a time and
wait for my answer each time. After each question, give 2 or 3
suggestions based on PROJECT_PLAN.md and the boxes already built:

1. In: what goes in?
2. Out: what comes out?
3. What should this function do? (3 to 5 plain steps)
4. Example: take one real row. Show what goes in and what comes out.
5. Rules: the "what if" cases. For each one:
   - Ask it as a plain question, for example "What if the list is empty?"
     or "What if the same text appears twice?"
   - Only include cases where the choice would change the output.
     Skip anything that only changes speed.
   - Show them in one table with these columns:
     Question | My pick (first) | The other choice | Why, in one everyday sentence
   - If a case has a real example from our data, use it in the "Why".
   - Think about these kinds of cases: empty input, missing or bad values,
     order of the results, ties (two equally good answers), repeats.
   - End with: "Say 'all as recommended', or tell me which numbers to change."

Then show the finished spec as four lines (Name, In, Out, Example).
Wait for my OK before any code.

When I say OK, write the code with a comment on every step, so I can
explain it back, and a comment above every terminal command.