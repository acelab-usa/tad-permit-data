"""Shared permit-type taxonomy and normalization.

Every jurisdiction adapter (and the PDF ledger pipeline) maps its own raw
type/category strings down to this one fixed taxonomy via
`normalize_permit_type()`, instead of each source inventing its own values
or passing its raw category straight through. That's what makes
`permit_type_normalized` actually filterable/searchable across
jurisdictions in the dashboard -- a value that means something different
per source defeats the point of the column.

This is a keyword-based v1, not a lookup table per source: it's built from
the actual raw values seen in Chicago, NYC, Austin, LA, and the Allen PDF
ledgers, and it deliberately falls back to "Other" rather than guessing --
a wrong bucket is worse for search/filtering than an honest "Other". Extend
`_KEYWORD_RULES`/`_EXACT_MATCH_OVERRIDES` as new raw values turn up that
don't match anything yet -- e.g. LA's other `Bldg-*` permit_type values
(Alter/Repair, Demolition, etc.) are still unconfirmed and would need their
own entries once seen in real ingested data, same as `bldg-new` was added
here from one real sample record rather than guessed.
"""
from typing import Literal, get_args

PermitTypeNormalized = Literal[
    "New Construction",
    "Alteration",
    "Demolition",
    "Electrical",
    "Plumbing",
    "Mechanical",
    "Roofing",
    "Certificate of Occupancy",
    "Sign",
    "Fire/Life Safety",
    "Other",
]

PERMIT_TYPE_TAXONOMY: tuple = get_args(PermitTypeNormalized)

# A few source vocabularies use short, ambiguous-as-a-substring codes for an
# otherwise-unambiguous category (e.g. Austin's work_class is literally
# "New"; LA's permit_type is literally "Bldg-New"). Checked as a whole-value
# equality match against each raw value individually -- never as a
# substring -- so it can't false-positive the way a bare "new" substring
# match would (e.g. inside "renew").
_EXACT_MATCH_OVERRIDES = {
    "new": "New Construction",
    "bldg-new": "New Construction",
}

# Ordered so more specific phrases are checked before more general ones
# (e.g. "certificate of occupancy" before "alteration" could ever apply).
_KEYWORD_RULES = (
    ("Certificate of Occupancy", ("certificate of occupancy", "c/o ")),
    ("Demolition", ("demolition", "wrecking", "wreck/demo", "demo")),
    ("New Construction", ("new construction", "new building")),
    ("Fire/Life Safety", ("fire alarm", "fire sprinkler", "fire suppression", "life safety")),
    ("Electrical", ("electric",)),
    ("Plumbing", ("plumbing",)),
    ("Mechanical", ("mechanical", "hvac", "boiler")),
    ("Roofing", ("roof",)),
    ("Sign", ("signs", "signage")),
    (
        "Alteration",
        (
            "alteration", "renovation", "remodel", "addition",
            "build-out", "buildout", "tenant build", "tenant finish", "finish out",
        ),
    ),
)


def normalize_permit_type(*raw_values: str) -> str:
    """Maps one or more raw type/category strings to the shared taxonomy.

    Takes multiple raw fields (e.g. a city's permit type plus its work
    class) because the right signal is sometimes split across columns --
    pass every raw field that might carry a construction-type signal, not
    just whichever one this codebase happens to also store as
    `permit_type_raw`.

    This is meant for short categorical fields (a permit type, a work
    class), not free-text scope-of-work descriptions -- the keyword list
    assumes that context and would false-positive more often on prose.
    """
    for value in raw_values:
        if value and str(value).strip().lower() in _EXACT_MATCH_OVERRIDES:
            return _EXACT_MATCH_OVERRIDES[str(value).strip().lower()]

    haystack = " ".join(str(v) for v in raw_values if v).lower()
    if not haystack.strip():
        return "Other"

    for category, keywords in _KEYWORD_RULES:
        if any(kw in haystack for kw in keywords):
            return category

    return "Other"
