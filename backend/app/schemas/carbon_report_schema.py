from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.carbon_report import ReportStatus


class CarbonReportResponse(BaseModel):
    id: int
    farm_id: int
    crop_cycle_id: int
    baseline_methane_kg: float
    current_methane_kg: float
    methane_reduction_kg: float
    co2e_reduction_tonnes: float
    estimated_credits: int
    report_hash: str
    status: ReportStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class SubmitReportRequest(BaseModel):
    """Optional additional remarks when submitting for verification."""
    remarks: Optional[str] = None
