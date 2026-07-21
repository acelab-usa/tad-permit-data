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