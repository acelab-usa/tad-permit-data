# LLM Eval Harness

Scores `llm_processor.py`'s actual output against hand-labeled golden cases.
Unlike a unit test, this calls the live OpenRouter API — it's the only way
to catch quality regressions in the free-text extraction/enrichment (a
prompt edit, a model swap) that a deterministic test can't see.

## Run it

```bash
uv run python -m eval.harness                     # both suites
uv run python -m eval.harness --suite enrichment   # enrich_permit_text only
uv run python -m eval.harness --suite pdf          # extract_multiple_permits_from_text only
uv run python -m eval.harness --fail-under 0.75    # exit nonzero if a suite average drops below this
```

Requires `OPEN_ROUTER_KEY` in `.env`. Each run writes a timestamped JSON
report to `eval/results/` (gitignored) unless you pass `--no-save`.

## Suites

- **`golden/enrichment/`** — one JSON case per file: a raw permit
  description, the building systems it should surface, and a few keywords
  its summary should mention. Scored on building-systems precision/recall/F1
  (fuzzy-matched, so wording differences like "HVAC" vs "HVAC system" don't
  count against it) plus summary keyword coverage.
- **`golden/pdf_extraction/`** — one JSON case per ledger page (two are real
  pages pulled from `allen_pdfs/`, hand-labeled from the actual text).
  Scored on permit-id precision/recall/F1, plus address and valuation
  accuracy for permits that were matched.

## Adding a case

Drop a new JSON file in the relevant `golden/` subfolder — no code changes
needed. See any existing file for the shape. For a PDF-extraction case, the
cleanest way to build one is to extract real page text and hand-label the
permits found in it:

```python
from pdf_processor import iter_pdf_pages
pages = dict(iter_pdf_pages("allen_pdfs/some_file.pdf"))
print(pages[<page_number>])  # read it, then hand-write expected_permits
```

## Interpreting scores

A case is reported as PASS/FAIL at a 0.7 overall-score cutoff, but that
threshold is just for the console report — it's not a hard gate. Use
`--fail-under` on the *suite average* for CI-style gating; a single
borderline case shouldn't block a run.
