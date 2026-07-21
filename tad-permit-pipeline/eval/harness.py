"""LLM eval harness.

Runs golden test cases through the *real* llm_processor functions (this
hits the live OpenRouter API -- there's no mocked/offline mode) and scores
the actual outputs against hand-labeled expectations. Use this to catch
quality regressions from prompt edits or model swaps that a unit test can't
see, since llm_processor's output is free-text and non-deterministic.

Usage:
    uv run python -m eval.harness                     # run every suite
    uv run python -m eval.harness --suite enrichment   # one suite only
    uv run python -m eval.harness --fail-under 0.75    # exit nonzero if a suite average drops below this

Add a new golden case by dropping a JSON file in eval/golden/enrichment/ or
eval/golden/pdf_extraction/ -- see the existing files for the expected shape.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import llm_processor
from eval.scoring import score_enrichment_case, score_pdf_extraction_case

GOLDEN_DIR = Path(__file__).parent / "golden"
RESULTS_DIR = Path(__file__).parent / "results"
PASS_THRESHOLD = 0.7  # per-case overall score needed to print as PASS


def _load_cases(suite: str) -> list:
    cases = []
    for path in sorted((GOLDEN_DIR / suite).glob("*.json")):
        with open(path) as f:
            case = json.load(f)
        case["_file"] = path.name
        cases.append(case)
    return cases


def run_enrichment_suite() -> list:
    results = []
    for case in _load_cases("enrichment"):
        actual = llm_processor.enrich_permit_text(case["raw_description"])
        score = score_enrichment_case(case, actual)
        results.append({"name": case.get("name", case["_file"]), **score})
    return results


def run_pdf_extraction_suite() -> list:
    results = []
    for case in _load_cases("pdf_extraction"):
        extracted = llm_processor.extract_multiple_permits_from_text(case["page_text"])
        actual_permits = extracted.permits_found if extracted else []
        score = score_pdf_extraction_case(case["expected_permits"], actual_permits)
        results.append({"name": case.get("name", case["_file"]), **score})
    return results


def _print_report(title: str, results: list) -> float:
    print(f"\n=== {title} ===")
    if not results:
        print("  (no golden cases found)")
        return 1.0

    for r in results:
        status = "PASS" if r.get("overall", 0) >= PASS_THRESHOLD else "FAIL"
        print(f"  [{status}] {r['name']:<45} overall={r.get('overall', 0):.2f}")
        if not r.get("ok", True):
            print(f"         {r.get('error')}")

    avg = sum(r.get("overall", 0) for r in results) / len(results)
    print(f"  --- suite average: {avg:.3f} across {len(results)} case(s) ---")
    return avg


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suite", choices=["enrichment", "pdf", "all"], default="all")
    parser.add_argument("--fail-under", type=float, default=None, help="Exit nonzero if any suite average falls below this.")
    parser.add_argument("--no-save", action="store_true", help="Don't write a JSON report to eval/results/.")
    args = parser.parse_args()

    if not os.getenv("OPEN_ROUTER_KEY"):
        print(
            "OPEN_ROUTER_KEY is not set -- this harness calls the live OpenRouter API and needs a real key in .env.",
            file=sys.stderr,
        )
        sys.exit(1)

    suite_averages = {}
    all_results = {}

    if args.suite in ("enrichment", "all"):
        results = run_enrichment_suite()
        all_results["enrichment"] = results
        suite_averages["enrichment"] = _print_report("Enrichment (enrich_permit_text)", results)

    if args.suite in ("pdf", "all"):
        results = run_pdf_extraction_suite()
        all_results["pdf_extraction"] = results
        suite_averages["pdf_extraction"] = _print_report(
            "PDF Ledger Extraction (extract_multiple_permits_from_text)", results
        )

    if not args.no_save:
        RESULTS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = RESULTS_DIR / f"{timestamp}.json"
        with open(out_path, "w") as f:
            json.dump({"suite_averages": suite_averages, "results": all_results}, f, indent=2, default=str)
        print(f"\nSaved report to {out_path}")

    print()

    if args.fail_under is not None:
        failing = {k: v for k, v in suite_averages.items() if v < args.fail_under}
        if failing:
            print(f"FAIL: suite average(s) below threshold {args.fail_under}: {failing}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
