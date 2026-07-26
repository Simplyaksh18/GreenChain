"""
Mobile-specific schemas — Phase 8.

GET /mobile/dashboard  → role-aware response
GET /system/status     → SystemStatusResponse
Pagination             → PaginationParams, PaginatedResponse
"""
from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


# ── Pagination ──────────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel, Generic[T]):
    total: int
    limit: int
    offset: int
    items: List[T]


# ── System status ───────────────────────────────────────────────────────────────

class SystemStatusResponse(BaseModel):
    api_status: str
    database_status: str
    blockchain_mode: str
    blockchain_configured: bool
    total_routes: int
    timestamp: datetime


# ── Mobile dashboard — role-specific inner models ───────────────────────────────

class FarmerDashboardData(BaseModel):
    my_farms_count: int
    approved_farms_count: int
    active_crop_cycles: int
    total_sensor_readings: int
    avg_sensor_quality: float
    total_carbon_reports: int
    verified_reports: int
    token_count: int
    total_credits: float
    latest_mrv_confidence: Optional[float]


class FpoDashboardData(BaseModel):
    linked_farms_count: int
    approved_linked_farms: int
    farmers_count: int
    pending_reports: int
    high_risk_farms: int


class VerifierDashboardData(BaseModel):
    pending_verifications: int
    high_risk_reports: int
    approved_today: int
    rejected_today: int


class AdminDashboardData(BaseModel):
    total_farms: int
    total_users: int
    total_reports: int
    verified_reports: int
    total_tokens: int
    total_credits: float
    high_risk_reports: int


class MobileDashboardResponse(BaseModel):
    role: str
    data: Any
