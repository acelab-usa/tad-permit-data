# models.py
from pydantic import BaseModel, Field
from typing import List

class PermitEnrichmentSchema(BaseModel):
    scope_summary: str = Field(
        description="A concise, high-level summary of the construction work being performed, translated from raw permit text."
    )
    building_systems: List[str] = Field(
        description="A clean list of building systems, materials, or components identified in the scope (e.g., 'Structural Steel', 'HVAC', 'Drywall', 'Plumbing')."
    )