"""Pydantic schemas for dashboard endpoints — Phase 7."""
from typing import Optional
from pydantic import BaseModel


class FarmDashboardResponse(BaseModel):
    farm_id: int
    farm_name: str
    land_area_acres: float
    is_approved: bool
    total_sensor_readings: int
    avg_sensor_quality: float
    total_satellite_observations: int
    total_drone_observations: int
    total_carbon_reports: int
    verified_credits: float
    mrv_confidence_score: Optional[float]
    mrv_consistency_score: Optional[float]
    mrv_flags: list[str]


class AdminDashboardResponse(BaseModel):
    total_farms: int
    approved_farms: int
    total_farmers: int
    total_carbon_reports: int
    verified_reports: int
    pending_verification: int
    total_tokens_minted: int
    total_credits_issued: float
    high_risk_reports: int
    critical_fraud_alerts: int


class VerifierDashboardResponse(BaseModel):
    pending_verifications: int
    approved_today: int
    rejected_today: int
    avg_risk_score: float
    high_risk_count: int
    reports_with_fraud_flags: int
