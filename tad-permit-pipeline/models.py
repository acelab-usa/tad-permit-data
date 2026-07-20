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
    permit_id: str = Field(description="The unique permit tracking number found on the document.")
    filing_date: Optional[str] = Field(description="The date the permit was filed or issued (ISO format YYYY-MM-DD preferred).")
    permit_type_raw: Optional[str] = Field(description="The exact type of permit as written on the form.")
    permit_type_normalized: Optional[str] = Field(description="The normalized category (e.g., New Construction, Alteration, Demolition, Electrical).")
    address: Optional[str] = Field(description="The complete physical property address listed on the permit.")
    owner_name: Optional[str] = Field(description="The recorded property owner's name.")
    contractor_name: Optional[str] = Field(description="The named builder or corporate general contractor.")
    valuation: Optional[float] = Field(description="The estimated cost or total valuation of the project. Numeric only.")
    square_footage: Optional[float] = Field(description="The total area/square footage listed. Numeric only, Null if not found.")
    raw_scope_of_work: str = Field(description="The verbatim description or text block outlining the detailed construction scope.")
    scope_summary: str = Field(description="A concise, high-level summary of the construction work being performed.")
    building_systems: List[str] = Field(description="A list of specific building components, systems, or materials identified (e.g., HVAC, Structural Steel, Drywall).")

class MonthlyPDFPageExtractSchema(BaseModel):
    permits_found: List[SinglePermitExtract] = Field(description="A list of all individual building permits discovered within this text layout.")