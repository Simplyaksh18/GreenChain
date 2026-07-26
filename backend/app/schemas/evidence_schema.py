from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator

from app.models.evidence import EvidenceType


# ── Create (JSON body — URL-based upload) ─────────────────────────────────────

class EvidenceFileCreate(BaseModel):
    farm_id: int
    crop_cycle_id: Optional[int] = None      # nullable — farm-level evidence allowed
    carbon_report_id: Optional[int] = None
    file_url: str
    file_type: str                           # legacy alias; set = evidence_type if provided
    evidence_type: Optional[str] = None      # PHOTO | VIDEO | PDF | DOCUMENT | … | OTHER
    description: Optional[str] = None
    file_name: Optional[str] = None
    file_mime_type: Optional[str] = None
    file_size: Optional[int] = None

    @field_validator("file_url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("file_url cannot be empty")
        return v

    @field_validator("file_type")
    @classmethod
    def file_type_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("file_type cannot be empty")
        return v.upper()


# ── Response ──────────────────────────────────────────────────────────────────

class EvidenceFileResponse(BaseModel):
    id: int
    farm_id: int
    crop_cycle_id: Optional[int]
    carbon_report_id: Optional[int]
    uploaded_by: int
    evidence_type: Optional[str]
    file_type: str
    file_name: Optional[str]
    file_mime_type: Optional[str]
    file_size: Optional[int]
    file_url: str
    storage_path: Optional[str]
    description: Optional[str]
    file_hash: Optional[str]
    hash_algorithm: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Hash verification ─────────────────────────────────────────────────────────

class EvidenceVerifyResponse(BaseModel):
    """Result of recomputing a file hash and comparing to the stored value."""
    evidence_id: int
    stored_hash: Optional[str]
    recomputed_hash: str
    hash_algorithm: str
    hash_match: bool
    verified_at: datetime


# ── Upload summary (returned after multipart file upload) ─────────────────────

class EvidenceUploadSummary(BaseModel):
    id: int
    farm_id: int
    crop_cycle_id: Optional[int]
    carbon_report_id: Optional[int]
    evidence_type: Optional[str]
    file_name: Optional[str]
    file_mime_type: Optional[str]
    file_size: Optional[int]
    file_hash: str
    hash_algorithm: str
    file_url: str
    description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
