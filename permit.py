import database
from pydantic import BaseModel, Field
from typing import List, Optional

class PermitSchema(BaseModel):
    permit_id: str
    jurisdiction: str
    source_format: str
    filing_date: Optional[str] = None
    permit_type: Optional[str] = None
    address: str
    owner_name: Optional[str] = None
    contractor_name: Optional[str] = None
    valuation: Optional[float] = None  # Pydantic will auto-convert valid numeric strings to floats
    square_footage: Optional[float] = None
    raw_scope_of_work: Optional[str] = None
    model_scope_summary: Optional[str] = None
    materials_systems_mentioned: List[str] = Field(default_factory=list)