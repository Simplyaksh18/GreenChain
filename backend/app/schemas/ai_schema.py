"""
ai_schema.py — Phase 18 AI Layer schemas.

All AI responses carry a disclaimer field.
AI responses NEVER modify report values, credit amounts, or approval status.
"""
from typing import Literal, List, Optional
from pydantic import BaseModel, Field

DISCLAIMER = (
    "AI-generated assistance. "
    "Final decision is based on verified MRV records and human judgment."
)


class AIInsight(BaseModel):
    """A single AI-generated insight item."""
    type: Literal["info", "positive", "warning", "risk", "action"]
    title: Optional[str] = None
    message: str


# ── MRV Summary ───────────────────────────────────────────────────────────────

class MRVSummaryResponse(BaseModel):
    farm_id: int
    farm_name: str
    # Carbon report presence
    has_carbon_report: bool = False
    latest_report_id: Optional[int] = None
    report_status: Optional[str] = None
    # AI-generated text
    summary: Optional[str] = None
    insights: List[AIInsight]
    # Completeness / confidence
    data_completeness: int = Field(default=0, ge=0, le=100)
    data_completeness_pct: int = Field(default=0, ge=0, le=100)  # backward-compat alias
    confidence_label: str = "Low"                                 # "High" / "Medium" / "Low"
    confidence_level: Literal["HIGH", "MEDIUM", "LOW"] = "LOW"   # kept for AIInsightsCard
    # Actionable guidance
    next_best_action: str = ""
    ai_mode: str
    disclaimer: str = DISCLAIMER


# ── Verification Assistant ────────────────────────────────────────────────────

class VerificationAssistResponse(BaseModel):
    verification_request_id: int
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    risk_explanation: str
    evidence_checklist: List[str]
    fraud_flags: List[str]
    suggested_questions: List[str]
    recommendation: Literal["APPROVE", "REVIEW", "REJECT"]
    recommendation_note: str
    ai_mode: str
    disclaimer: str = DISCLAIMER


# ── FPO Action Summary ────────────────────────────────────────────────────────

class FPOActionItem(BaseModel):
    category: str
    count: int
    message: str
    action: Optional[str] = None


class FPOActionSummaryResponse(BaseModel):
    action_items: List[FPOActionItem]
    summary: str
    ai_mode: str
    disclaimer: str = DISCLAIMER


# ── Farmer Help ───────────────────────────────────────────────────────────────

class FarmerHelpRequest(BaseModel):
    topic: Literal[
        "explain_credits",
        "why_zero_credits",
        "missing_data",
        "improve_mrv",
        "general",
    ] = "general"
    farm_id: Optional[int] = None
    report_id: Optional[int] = None


class FarmerHelpResponse(BaseModel):
    topic: str
    explanation: str
    insights: List[AIInsight]
    ai_mode: str
    disclaimer: str = DISCLAIMER
