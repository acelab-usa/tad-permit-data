from pydantic import BaseModel, Field
from datetime import date

from permit_types import PERMIT_TYPE_TAXONOMY, PermitTypeNormalized

class PermitSchemaV2(BaseModel):
    # --- Metadata & Source Details ---
    permit_id: str = Field(description="Unique identifier of the permit from the source.")
    jurisdiction: str = Field(description="The city or authority (e.g., 'chicago', 'nyc').")
    source_url: str = Field(description="Link to the source API or PDF file.")
    source_format: str = Field(description="The input format: 'API' or 'PDF'.")
    
    # --- Core Permit Info ---
    address: str
    filing_date: date | None = Field(default=None, description="The date the permit was filed/issued.")
    owner_name: str | None = Field(default=None, description="Property owner name, if available.")
    contractor_name: str | None = Field(default=None, description="Licensed contractor name, if available.")
    latitude: float | None = Field(default=None, description="Site latitude, if the source provided one (see geo.py).")
    longitude: float | None = Field(default=None, description="Site longitude, if the source provided one (see geo.py).")
    
    # --- Taxonomy & Valuation ---
    permit_type_raw: str = Field(description="The original classification given by the city.")
    permit_type_normalized: PermitTypeNormalized = Field(
        description=f"Standardized category, one of: {', '.join(PERMIT_TYPE_TAXONOMY)}. "
                    "Always derived via permit_types.normalize_permit_type(), never set directly."
    )
    square_footage: int | None = Field(default=None, description="Reported area in sq ft, null if missing.")
    valuation: float | None = Field(default=None, description="Reported cost/valuation of the job, null if missing.")
    
    # --- Scope and LLM Enrichments ---
    raw_scope_of_work: str = Field(description="The original, unedited scope text.")
    scope_summary: str = Field(description="A 1-2 sentence LLM-generated summary of the work.")
    building_systems: list[str] = Field(
        default_factory=list, 
        description="List of systems or materials mentioned (e.g. ['HVAC', 'structural steel', 'curtain wall'])."
    )