# data/ — what is what

## Raw data (never change these)
`knowledge.jsonl`, `dev.jsonl`, `test.jsonl`

The alerts as downloaded. Together they hold all 17,275 alerts (every case number
once). Their own split is NOT by date, so do not use them as library / dev / test.
They are read-only on purpose. Only two things read them:
- `boxes/preprocessing.py` (`run_pipeline`), which builds the splits below
- `boxes/twin_check.py` (the "OLD files" check)

They are not in git (see `.gitignore`). `data/fetch_rapex.py` can download the data again.

## Clean data (use these)
`splits/library.jsonl`, `splits/dev.jsonl`, `splits/test.jsonl`, `splits/pipeline_summary.json`

Made by `python -m boxes.preprocessing`: split by date (library = oldest 70%,
dev = next 10%, test = newest 20%), duplicates and twins removed, with the flags
`is_thin` and (dev/test) `same_words_in_library`. All later steps (embedding,
search, scoring) read ONLY these files.

## Rebuild
`python -m boxes.preprocessing` rebuilds `splits/` from the raw files. It gives
identical files every time.
