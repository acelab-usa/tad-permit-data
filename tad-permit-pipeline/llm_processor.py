# llm_processor.py
import os
import time

import openai
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import ValidationError
from models import PermitEnrichmentSchema, MonthlyPDFPageExtractSchema

from logging_setup import get_logger

load_dotenv()
logger = get_logger("llm_processor")

MAX_RETRIES = 3
BACKOFF_SECONDS = 2

# Errors worth retrying: transient network/server/rate-limit issues.
# Anything else (bad request, auth, invalid model) will just fail the same
# way again, so retrying wastes time and hides the real problem.
RETRYABLE_ERRORS = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.InternalServerError,
)

api_key = os.getenv("OPEN_ROUTER_KEY")
if not api_key:
    logger.warning("OPEN_ROUTER_KEY is not set -- LLM calls will fail until it's configured.")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    # The SDK raises at construction time if api_key is falsy, which would
    # crash this module on import for anyone who hasn't configured a key yet
    # (including any code that just wants to import PermitEnrichmentSchema
    # helpers without calling the API). Fall back to a placeholder so the
    # failure surfaces at call time instead, where it's caught and logged.
    api_key=api_key or "unset",
)


def _call_with_retry(request_fn, label: str):
    """Runs `request_fn()` with exponential backoff on transient API errors."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return request_fn()
        except RETRYABLE_ERRORS as e:
            if attempt < MAX_RETRIES:
                wait = BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "%s: transient error on attempt %s/%s (%s), retrying in %ss",
                    label, attempt, MAX_RETRIES, type(e).__name__, wait,
                )
                time.sleep(wait)
            else:
                logger.error("%s: giving up after %s attempts: %s", label, MAX_RETRIES, e)
        except openai.APIError as e:
            # Non-transient API error (bad request, auth, invalid model, etc) -- retrying won't help.
            logger.error("%s: non-retryable API error: %s", label, e)
            return None
    return None


def enrich_permit_text(raw_description: str) -> PermitEnrichmentSchema | None:
    """
    Sends the raw permit text to OpenRouter and extracts a structured
    summary and a list of building systems/materials.
    """
    if not raw_description or not raw_description.strip():
        return None

    def _request():
        return client.chat.completions.create(
            model="google/gemini-2.5-flash",  # High speed, low cost, excellent structured extraction
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert construction data analyst. Analyze the provided raw municipal permit description. "
                        "Return a JSON object matching this schema exactly:\n"
                        "{\n"
                        "  'scope_summary': 'A clear, readable string summarizing the project scope.',\n"
                        "  'building_systems': ['System/Material 1', 'System/Material 2']\n"
                        "}"
                    ),
                },
                {
                    "role": "user",
                    "content": f"Raw Permit Text: {raw_description}",
                },
            ],
            temperature=0.1,
        )

    response = _call_with_retry(_request, label="enrich_permit_text")
    if response is None:
        return None

    raw_json = response.choices[0].message.content
    try:
        return PermitEnrichmentSchema.model_validate_json(raw_json)
    except ValidationError as e:
        logger.error("enrich_permit_text: model returned JSON that didn't match schema: %s", e)
        return None


def extract_multiple_permits_from_text(chunk_text: str) -> MonthlyPDFPageExtractSchema | None:
    """
    Analyzes a chunk of text containing multiple permit listings and
    extracts them into a structured collection of individual permits.
    """
    if not chunk_text or not chunk_text.strip():
        return None

    def _request():
        return client.chat.completions.create(
            model="google/gemini-2.5-flash",
            response_format={"type": "json_object"},
            max_tokens=4000,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert data extraction assistant processing pages from a monthly municipal permit ledger. "
                        "Identify every single distinct permit listed in the text. "
                        "Return a JSON object containing a list named 'permits_found' matching this schema blueprint:\n"
                        "{\n"
                        "  'permits_found': [\n"
                        "    {\n"
                        "      'permit_id': 'string',\n"
                        "      'filing_date': 'YYYY-MM-DD',\n"
                        "      'permit_type_raw': 'string',\n"
                        "      'permit_type_normalized': 'string',\n"
                        "      'address': 'string',\n"
                        "      'owner_name': 'string',\n"
                        "      'contractor_name': 'string',\n"
                        "      'valuation': 0.0,\n"
                        "      'square_footage': 0.0,\n"
                        "      'raw_scope_of_work': 'verbatim description text from document',\n"
                        "      'scope_summary': '1 sentence summary',\n"
                        "      'building_systems': ['material1', 'material2']\n"
                        "    }\n"
                        "  ]\n"
                        "}"
                    ),
                },
                {
                    "role": "system",
                    "content": (
                        "You are an expert data extraction engine parsing a municipal ledger page.\n"
                        "CRITICAL BLOCK-IDENTIFICATION RULES:\n"
                        "1. Every distinct permit entry begins at the far left with a unique alpha-numeric Permit Number pattern "
                        "(e.g., '000397-2026-CO', '000808-2026-CO*', '007623-2025-CB*').\n"
                        "2. IGNORE the text color of the permit number—it may be RED or DARK BLUE depending on the work class category.\n"
                        "3. Extract all permit classifications on the page, including 'Commercial Building - Alteration', "
                        "'Certificate of Occupancy - C/O Stand Alone', 'Commercial Misc', etc.\n"
                        "4. Disregard lines containing summary metrics or 'SUBTOTALS'."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Raw Monthly Ledger Page Text:\n{chunk_text}",
                },
            ],
            temperature=0.1,
        )

    response = _call_with_retry(_request, label="extract_multiple_permits_from_text")
    if response is None:
        return None

    raw_json = response.choices[0].message.content
    try:
        return MonthlyPDFPageExtractSchema.model_validate_json(raw_json)
    except ValidationError as e:
        logger.error("extract_multiple_permits_from_text: model returned JSON that didn't match schema: %s", e)
        return None
