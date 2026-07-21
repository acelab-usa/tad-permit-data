"""Deterministic scoring for the LLM eval harness.

No LLM calls live here -- these functions just compare a golden expectation
against whatever llm_processor actually returned, so results are
reproducible given a fixed set of model outputs.
"""
import re
from typing import Optional


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _tokenize(text: str) -> set:
    return set(_normalize(text).split())


def _f1(precision: float, recall: float, nothing_to_match: bool) -> float:
    """F1 from precision/recall, careful not to reward a total mismatch.

    precision + recall == 0 happens in two very different situations: (a)
    nothing was expected and nothing was returned -- trivially perfect, or
    (b) something was expected/returned but none of it matched -- a total
    miss. Naively falling back to 1.0 whenever the denominator is zero
    conflates these and scores a complete miss as perfect.
    """
    if nothing_to_match:
        return 1.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def fuzzy_label_match(expected: str, actual: str) -> bool:
    """True if two short labels (building systems, etc.) likely refer to the
    same thing, tolerating wording differences ('HVAC' vs 'HVAC system',
    'Structural Steel' vs 'structural steel framing')."""
    e_tokens, a_tokens = _tokenize(expected), _tokenize(actual)
    if not e_tokens or not a_tokens:
        return False
    overlap = e_tokens & a_tokens
    return bool(overlap) and (len(overlap) / min(len(e_tokens), len(a_tokens))) >= 0.5


def score_building_systems(expected: list, actual: list) -> dict:
    """Precision/recall/F1 over two lists of free-text system labels, matched
    via fuzzy_label_match (order-independent, tolerant of wording)."""
    matched_expected, matched_actual = set(), set()

    for i, exp in enumerate(expected):
        for j, act in enumerate(actual):
            if j in matched_actual:
                continue
            if fuzzy_label_match(exp, act):
                matched_expected.add(i)
                matched_actual.add(j)
                break

    tp = len(matched_expected)
    precision = tp / len(actual) if actual else (1.0 if not expected else 0.0)
    recall = tp / len(expected) if expected else (1.0 if not actual else 0.0)
    f1 = _f1(precision, recall, nothing_to_match=not expected and not actual)

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "unmatched_expected": [expected[i] for i in range(len(expected)) if i not in matched_expected],
        "unmatched_actual": [actual[j] for j in range(len(actual)) if j not in matched_actual],
    }


def score_keyword_coverage(expected_keywords: list, text: str) -> dict:
    """Fraction of expected keywords/phrases that show up (case/punct
    insensitive) somewhere in a free-text summary."""
    text_norm = _normalize(text or "")
    hits = [kw for kw in expected_keywords if _normalize(kw) in text_norm]
    coverage = len(hits) / len(expected_keywords) if expected_keywords else 1.0
    return {
        "coverage": round(coverage, 3),
        "hit": hits,
        "missed": [kw for kw in expected_keywords if kw not in hits],
    }


def score_enrichment_case(case: dict, actual) -> dict:
    """`actual` is a PermitEnrichmentSchema, or None if the call failed."""
    if actual is None:
        return {
            "ok": False,
            "error": "llm_processor.enrich_permit_text returned None (API failure or schema mismatch)",
            "overall": 0.0,
        }

    systems_score = score_building_systems(case.get("expected_building_systems", []), actual.building_systems)
    summary_score = score_keyword_coverage(case.get("expected_summary_keywords", []), actual.scope_summary)
    overall = 0.7 * systems_score["f1"] + 0.3 * summary_score["coverage"]

    return {
        "ok": True,
        "overall": round(overall, 3),
        "systems": systems_score,
        "summary": summary_score,
        "actual_summary": actual.scope_summary,
        "actual_systems": actual.building_systems,
    }


def _address_similarity(expected: str, actual: Optional[str]) -> float:
    """Fraction of expected address tokens present in the actual address --
    lets `actual` include extra detail (unit, city, zip) without penalty."""
    if not expected:
        return 1.0
    if not actual:
        return 0.0
    e_tokens, a_tokens = _tokenize(expected), _tokenize(actual)
    if not e_tokens:
        return 1.0
    return len(e_tokens & a_tokens) / len(e_tokens)


def _valuation_match(expected: Optional[float], actual: Optional[float], tolerance: float = 0.01) -> bool:
    if expected is None:
        return actual is None
    if actual is None:
        return False
    if expected == 0:
        return abs(actual) <= tolerance
    return abs(actual - expected) / abs(expected) <= tolerance


def score_pdf_extraction_case(expected_permits: list, actual_permits: list) -> dict:
    """`actual_permits` is a list of SinglePermitExtract (or [] on failure).

    Matching is by permit_id. The source ledgers occasionally list the same
    permit_id twice (e.g. a corrected line item) -- both expected and actual
    are deduped to one entry per id before comparing, so that quirk doesn't
    manufacture a false precision/recall penalty.
    """
    expected_by_id = {p["permit_id"]: p for p in expected_permits}
    actual_by_id = {}
    for p in actual_permits:
        actual_by_id.setdefault(p.permit_id, p)

    expected_ids = set(expected_by_id)
    actual_ids = set(actual_by_id)
    matched_ids = expected_ids & actual_ids

    precision = len(matched_ids) / len(actual_ids) if actual_ids else (1.0 if not expected_ids else 0.0)
    recall = len(matched_ids) / len(expected_ids) if expected_ids else (1.0 if not actual_ids else 0.0)
    f1 = _f1(precision, recall, nothing_to_match=not expected_ids and not actual_ids)

    field_scores = []
    for pid in matched_ids:
        exp, act = expected_by_id[pid], actual_by_id[pid]
        field_scores.append({
            "permit_id": pid,
            "address_similarity": round(_address_similarity(exp.get("address", ""), act.address), 3),
            "valuation_match": _valuation_match(exp.get("valuation"), act.valuation),
        })

    avg_address_sim = (
        sum(f["address_similarity"] for f in field_scores) / len(field_scores) if field_scores else 1.0
    )
    valuation_accuracy = (
        sum(1 for f in field_scores if f["valuation_match"]) / len(field_scores) if field_scores else 1.0
    )
    overall = 0.5 * f1 + 0.3 * avg_address_sim + 0.2 * valuation_accuracy

    return {
        "ok": True,
        "overall": round(overall, 3),
        "permit_precision": round(precision, 3),
        "permit_recall": round(recall, 3),
        "permit_f1": round(f1, 3),
        "matched_ids": sorted(matched_ids),
        "missed_ids": sorted(expected_ids - actual_ids),
        "extra_ids": sorted(actual_ids - expected_ids),
        "avg_address_similarity": round(avg_address_sim, 3),
        "valuation_accuracy": round(valuation_accuracy, 3),
        "field_scores": field_scores,
    }
