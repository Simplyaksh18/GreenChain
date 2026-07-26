from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from app.models.verification import VerificationStatus, RiskLevel, Recommendation


class VerificationRequestResponse(BaseModel):
    id: int
    carbon_report_id: int
    verifier_id: Optional[int]
    status: VerificationStatus
    remarks: Optional[str]
    risk_score: float
    risk_level: RiskLevel
    recommendation: Recommendation
    verified_at: Optional[datetime]
    created_at: datetime

    # ── Enriched fields (computed on read, not stored) ────────────────────────
    # Risk breakdown: each factor that contributed to the risk score
    risk_factors: List[str] = []

    # Evidence summary (re-computed from related tables)
    sensor_count: Optional[int] = None
    satellite_count: Optional[int] = None
    drone_count: Optional[int] = None
    avg_quality_score: Optional[float] = None
    num_evidence_files: Optional[int] = None

    # Report values (for calculation display)
    baseline_methane_kg: Optional[float] = None
    current_methane_kg: Optional[float] = None
    methane_reduction_kg: Optional[float] = None
    co2e_reduction_tonnes: Optional[float] = None
    estimated_credits: Optional[int] = None

    # Verifier name (looked up from users table)
    verifier_name: Optional[str] = None

    model_config = {"from_attributes": True}


class ApproveRequest(BaseModel):
    remarks: Optional[str] = None


class RejectRequest(BaseModel):
    remarks: str                    # required for rejection
