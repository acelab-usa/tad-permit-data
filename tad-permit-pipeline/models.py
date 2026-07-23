# models.py
from pydantic import BaseModel, Field
from typing import List, Optional

class PermitEnrichmentSchema(BaseModel):
    scope_summary: str = Field(
        description="A concise, high-level summary of the construction work being performed, translated from raw permit text."
    )
    building_systems: List[str] = Field(
        description="A clean list of building systems, materials, or components identified in the scope (e.g., 'Structural Steel', 'HVAC', 'Drywall', 'Plumbing')."
    )

class SinglePermitExtract(BaseModel):
    permit_id: str = Field(description="The unique permit tracking or application number.")
    filing_date: Optional[str] = Field(default=None, description="The date filed or issued (YYYY-MM-DD).")
    permit_type_raw: Optional[str] = Field(default=None, description="The exact type of permit as written.")
    address: Optional[str] = Field(default=None, description="The full property address.")
    owner_name: Optional[str] = Field(default=None, description="The property owner's name.")
    contractor_name: Optional[str] = Field(default=None, description="The builder or general contractor.")
    valuation: Optional[float] = Field(default=None, description="Estimated cost/valuation. Numeric only.")
    square_footage: Optional[float] = Field(default=None, description="Total area listed. Numeric only.")
    
    # Optional to prevent LLM issues
    raw_scope_of_work: Optional[str] = Field(default="", description="The verbatim description layout outlining the construction scope.")
    scope_summary: Optional[str] = Field(default="", description="A concise, high-level summary generated from the raw scope.")
    building_systems: List[str] = Field(default_factory=list, description="List of structural systems/materials identified.")

class MonthlyPDFPageExtractSchema(BaseModel):
    permits_found: List[SinglePermitExtract] = Field(description="A list of all individual building permits discovered within this text layout.")

class ProposedFieldMapping(BaseModel):
    """LLM-proposed draft of a sources.field_mapping.FieldMapping, from a raw
    Socrata dataset's column metadata + a sample record. See
    onboard_jurisdiction.py -- this is a draft for a human to review, not
    something auto-applied to sources/registry.py."""
    permit_id_field: Optional[str] = Field(
        default=None, description="Raw field holding the unique permit/case number."
    )
    address_fields: List[str] = Field(
        default_factory=list,
        description="Raw field(s) that together form the site's street address, in the order they should be joined. Empty if no usable address field exists.",
    )
    address_separator: str = Field(
        default=" ",
        description="Separator to join address_fields with -- ' ' for plain street parts, ', ' if the fields are already city/state/zip-like.",
    )
    date_fields: List[str] = Field(
        default_factory=list,
        description="Raw field(s) representing the permit's filing/issue date, in priority order (first non-blank wins).",
    )
    owner_name_fields: List[str] = Field(
        default_factory=list,
        description="Raw field(s) for the property owner's name. Leave empty if no such field exists, or if it looks redacted/too incomplete to trust (e.g. only a first name with no last name).",
    )
    contractor_name_fields: List[str] = Field(
        default_factory=list, description="Raw field(s) for the contractor/licensee/business name, if any."
    )
    permit_type_fields: List[str] = Field(
        default_factory=list,
        description="Raw field(s) carrying a construction-type signal (e.g. permit type, work class), in priority order. Only include a secondary field if it plausibly adds real signal, not just because it exists.",
    )
    valuation_field: Optional[str] = Field(
        default=None, description="Raw numeric field for the permit's reported cost/valuation."
    )
    square_footage_field: Optional[str] = Field(
        default=None, description="Raw numeric field for reported square footage/floor area, if any."
    )
    scope_fields: List[str] = Field(
        default_factory=list,
        description="Raw field(s) with a free-text description of the work being done, in priority order.",
    )
    point_fields: List[str] = Field(
        default_factory=list,
        description="Raw field name(s) holding a NESTED point/geometry object (e.g. a Socrata 'location' column with its own latitude/longitude or GeoJSON coordinates) -- NOT plain top-level latitude/longitude columns, which are already detected automatically and don't need to be listed.",
    )
    unmapped_notes: Optional[str] = Field(
        default=None,
        description="Brief notes on anything left unmapped and why, or any ambiguity worth a human's attention -- e.g. 'no clear owner field' or 'two candidate date fields, picked the more common one'.",
    )