"""
Evidence Router — Phase 4 / Phase 13 / Phase 14 / Phase 15.

Phase 13:  SHA-256 hash computed on upload (URL + metadata payload)
           GET /evidence/{id}/verify     — recompute and compare hash
           GET /evidence/report/{id}     — evidence linked to a carbon report

Phase 14:  POST /evidence/upload         — multipart binary upload
           Evidence types: PHOTO VIDEO PDF DOCUMENT SENSOR_EXPORT
                           SATELLITE_EXPORT DRONE_EXPORT GIS_BOUNDARY OTHER
           Actual SHA-256 over file bytes when binary upload is used.
           Files stored in uploads/evidence/{farm_id}/

Phase 15:  POST /evidence/google-drive/import
           Import a single file from Google Drive as evidence.
           Requires GOOGLE_DRIVE_ENABLED=true.
           Access token is NEVER stored or logged.

SECURITY:
  - File bytes are hashed (SHA-256) on write; hash stored for integrity checks.
  - Full storage_path is never returned in responses (file_url only).
  - Verifiers can view but not upload.
  - Google access tokens are never stored, logged, or exposed in responses.
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.carbon_report import CarbonReport
from app.models.evidence import EvidenceFile, EvidenceType
from app.models.farm import Farm, CropCycle
from app.models.fpo import FPOProfile
from app.models.user import User, UserRole
from app.schemas.evidence_schema import (
    EvidenceFileCreate,
    EvidenceFileResponse,
    EvidenceUploadSummary,
    EvidenceVerifyResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evidence", tags=["Evidence"])

# Uploads root — resolved via the SINGLE source of truth in app.config
# (respects UPLOAD_DIR; falls back to <backend>/uploads/evidence for local dev).
# Kept as a callable so tests can monkey-patch UPLOAD_DIR before each request.
from app.config import resolve_evidence_upload_dir


def _uploads_root() -> str:
    return str(resolve_evidence_upload_dir())


# ── Helpers ────────────────────────────────────────────────────────────────────

def _compute_metadata_hash(
    file_url: str,
    farm_id: int,
    crop_cycle_id: Optional[int],
    file_type: str,
    description: Optional[str],
    carbon_report_id: Optional[int],
) -> str:
    """SHA-256 over canonical evidence metadata (URL-based evidence, no bytes)."""
    parts = [
        file_url,
        str(farm_id),
        str(crop_cycle_id) if crop_cycle_id is not None else "",
        file_type,
        description or "",
        str(carbon_report_id) if carbon_report_id is not None else "",
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _compute_bytes_hash(data: bytes) -> str:
    """SHA-256 over actual file bytes (multipart upload)."""
    return hashlib.sha256(data).hexdigest()


def _get_farm_or_404(farm_id: int, db: Session) -> Farm:
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    return farm


def _get_cycle_or_404(cycle_id: int, db: Session) -> CropCycle:
    cycle = db.query(CropCycle).filter(CropCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop cycle not found")
    return cycle


def _assert_upload_access(farm: Farm, current_user: User, db: Session) -> None:
    """
    Upload / import access rules:
      ADMIN   — full access to all farms
      FPO     — only their linked farms
      FARMER  — BLOCKED (403). Farmers view evidence; FPO uploads on their behalf.
      VERIFIER— BLOCKED (403). View-only role.
    """
    if current_user.role == UserRole.ADMIN:
        return
    if current_user.role == UserRole.FPO:
        profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
        if not profile or farm.fpo_id != profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return
    # FARMER and VERIFIER are both blocked from uploading
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Farmers cannot upload evidence. Evidence is uploaded by FPO on behalf of the farm.",
    )


def _assert_view_access(farm: Farm, current_user: User, db: Session) -> None:
    """FARMER (own), FPO (linked), VERIFIER (all), ADMIN (all)."""
    if current_user.role in (UserRole.ADMIN, UserRole.VERIFIER):
        return
    if current_user.role == UserRole.FARMER:
        if farm.farmer_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return
    if current_user.role == UserRole.FPO:
        profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
        if not profile or farm.fpo_id != profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _safe_evidence_type(raw: Optional[str]) -> str:
    if raw is None:
        return EvidenceType.OTHER.value
    upper = raw.strip().upper()
    valid = {e.value for e in EvidenceType}
    return upper if upper in valid else EvidenceType.OTHER.value


# ── POST /evidence/upload  (multipart binary) ──────────────────────────────────

@router.post(
    "/upload",
    response_model=EvidenceUploadSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file (multipart) — Phase 14",
)
async def upload_evidence_file(
    farm_id: int = Form(...),
    crop_cycle_id: Optional[int] = Form(None),
    carbon_report_id: Optional[int] = Form(None),
    evidence_type: str = Form("OTHER"),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Multipart evidence upload — Phase 14.

    Stores the file on disk, computes SHA-256 of actual bytes, returns evidence record.
    Access: FARMER (own farm), FPO (linked farm), ADMIN.
    """
    farm = _get_farm_or_404(farm_id, db)
    _assert_upload_access(farm, current_user, db)

    if crop_cycle_id is not None:
        cycle = _get_cycle_or_404(crop_cycle_id, db)
        if cycle.farm_id != farm.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Crop cycle does not belong to the specified farm",
            )

    # Read file bytes and compute hash
    data = await file.read()
    file_hash = _compute_bytes_hash(data)
    original_name = file.filename or "upload"
    mime = file.content_type or "application/octet-stream"

    # Persist to disk
    farm_dir = os.path.join(_uploads_root(), str(farm_id))
    os.makedirs(farm_dir, exist_ok=True)
    ts = int(datetime.now(timezone.utc).timestamp())
    safe_name = f"{ts}_{original_name}"
    abs_path = os.path.join(farm_dir, safe_name)
    with open(abs_path, "wb") as fh:
        fh.write(data)

    # Relative URL served by StaticFiles mount
    relative_url = f"/uploads/evidence/{farm_id}/{safe_name}"
    ev_type = _safe_evidence_type(evidence_type)

    ev = EvidenceFile(
        farm_id=farm_id,
        crop_cycle_id=crop_cycle_id,
        carbon_report_id=carbon_report_id,
        uploaded_by=current_user.id,
        evidence_type=ev_type,
        file_type=ev_type,           # keep legacy field in sync
        file_name=original_name,
        file_mime_type=mime,
        file_size=len(data),
        storage_path=abs_path,
        file_url=relative_url,
        description=description,
        file_hash=file_hash,
        hash_algorithm="SHA256",
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    logger.info(
        "evidence.upload.multipart | id=%s farm=%s type=%s size=%s hash=%s…",
        ev.id, farm_id, ev_type, len(data), file_hash[:12],
    )
    return ev


# ── POST /evidence  (JSON body — URL-based, Phase 4–13 compat) ─────────────────

@router.post("", response_model=EvidenceFileResponse, status_code=status.HTTP_201_CREATED)
def upload_evidence(
    payload: EvidenceFileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Register URL-based evidence (no binary upload).
    SHA-256 is computed over the URL + metadata payload.
    crop_cycle_id is now optional — farm-level evidence is supported.
    """
    farm = _get_farm_or_404(payload.farm_id, db)

    if payload.crop_cycle_id is not None:
        cycle = _get_cycle_or_404(payload.crop_cycle_id, db)
        if cycle.farm_id != farm.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Crop cycle does not belong to the specified farm",
            )

    _assert_upload_access(farm, current_user, db)

    ev_type = _safe_evidence_type(payload.evidence_type or payload.file_type)
    file_hash = _compute_metadata_hash(
        file_url=payload.file_url,
        farm_id=payload.farm_id,
        crop_cycle_id=payload.crop_cycle_id,
        file_type=payload.file_type,
        description=payload.description,
        carbon_report_id=payload.carbon_report_id,
    )

    ev = EvidenceFile(
        farm_id=farm.id,
        crop_cycle_id=payload.crop_cycle_id,
        carbon_report_id=payload.carbon_report_id,
        uploaded_by=current_user.id,
        evidence_type=ev_type,
        file_type=payload.file_type,
        file_name=payload.file_name,
        file_mime_type=payload.file_mime_type,
        file_size=payload.file_size,
        file_url=payload.file_url,
        description=payload.description,
        file_hash=file_hash,
        hash_algorithm="SHA256",
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    logger.info(
        "evidence.upload.url | id=%s farm_id=%s type=%s",
        ev.id, ev.farm_id, ev_type,
    )
    return ev


# ── GET /evidence/farm/{farm_id} ──────────────────────────────────────────────

@router.get("/farm/{farm_id}", response_model=List[EvidenceFileResponse])
def get_evidence_by_farm(
    farm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    farm = _get_farm_or_404(farm_id, db)
    _assert_view_access(farm, current_user, db)
    return db.query(EvidenceFile).filter(EvidenceFile.farm_id == farm_id).all()


# ── GET /evidence/crop-cycle/{crop_cycle_id} ──────────────────────────────────

@router.get("/crop-cycle/{crop_cycle_id}", response_model=List[EvidenceFileResponse])
def get_evidence_by_crop_cycle(
    crop_cycle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cycle = _get_cycle_or_404(crop_cycle_id, db)
    farm = _get_farm_or_404(cycle.farm_id, db)
    _assert_view_access(farm, current_user, db)
    return db.query(EvidenceFile).filter(EvidenceFile.crop_cycle_id == crop_cycle_id).all()


# ── GET /evidence/report/{report_id} ─────────────────────────────────────────

@router.get("/report/{report_id}", response_model=List[EvidenceFileResponse])
def get_evidence_by_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.query(CarbonReport).filter(CarbonReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carbon report not found")
    farm = _get_farm_or_404(report.farm_id, db)
    _assert_view_access(farm, current_user, db)
    return (
        db.query(EvidenceFile)
        .filter(EvidenceFile.carbon_report_id == report_id)
        .all()
    )


# ── GET /evidence/{evidence_id}/verify ────────────────────────────────────────

@router.get("/{evidence_id}/verify", response_model=EvidenceVerifyResponse)
def verify_evidence_hash(
    evidence_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Recompute the hash and compare to the stored value.
    For binary-uploaded files: recompute from disk bytes if storage_path exists.
    For URL-based evidence: recompute from metadata.
    """
    ev = db.query(EvidenceFile).filter(EvidenceFile.id == evidence_id).first()
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")

    farm = _get_farm_or_404(ev.farm_id, db)
    _assert_view_access(farm, current_user, db)

    # Try binary hash first (file on disk)
    if ev.storage_path and os.path.exists(ev.storage_path):
        with open(ev.storage_path, "rb") as fh:
            recomputed = _compute_bytes_hash(fh.read())
    else:
        # Fall back to metadata hash
        recomputed = _compute_metadata_hash(
            file_url=ev.file_url,
            farm_id=ev.farm_id,
            crop_cycle_id=ev.crop_cycle_id,
            file_type=ev.file_type,
            description=ev.description,
            carbon_report_id=ev.carbon_report_id,
        )

    return EvidenceVerifyResponse(
        evidence_id=ev.id,
        stored_hash=ev.file_hash,
        recomputed_hash=recomputed,
        hash_algorithm=ev.hash_algorithm or "SHA256",
        hash_match=(ev.file_hash == recomputed),
        verified_at=datetime.now(timezone.utc),
    )


# ── POST /evidence/google-drive/import  (Phase 15) ────────────────────────────

_DRIVE_ALLOWED_MIMES = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "application/pdf",
    "video/mp4", "video/quicktime", "video/x-msvideo",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}

_DRIVE_FILE_METADATA_URL = "https://www.googleapis.com/drive/v3/files/{file_id}?fields=name,mimeType,size"
_DRIVE_FILE_DOWNLOAD_URL = "https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"


@router.post(
    "/google-drive/import",
    response_model=EvidenceUploadSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Import a file from Google Drive as evidence — Phase 15",
)
async def import_from_google_drive(
    farm_id: int = Form(...),
    file_id: str = Form(..., description="Google Drive file ID"),
    google_access_token: str = Form(..., description="Google OAuth access token (never stored)"),
    crop_cycle_id: Optional[int] = Form(None),
    carbon_report_id: Optional[int] = Form(None),
    evidence_type: str = Form("OTHER"),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Import a file from Google Drive into GreenChain evidence storage.

    The Google access token is used ONCE to fetch the file from Drive.
    It is NEVER stored, logged, or returned in any response.

    Requires GOOGLE_DRIVE_ENABLED=true in config.
    Access: FARMER (own farm), FPO (linked farm), ADMIN. VERIFIER blocked.
    """
    if settings.GOOGLE_DRIVE_ENABLED.lower() != "true":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Drive import is not enabled on this server.",
        )

    farm = _get_farm_or_404(farm_id, db)
    _assert_upload_access(farm, current_user, db)

    if crop_cycle_id is not None:
        cycle = _get_cycle_or_404(crop_cycle_id, db)
        if cycle.farm_id != farm.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Crop cycle does not belong to the specified farm",
            )

    headers = {"Authorization": f"Bearer {google_access_token}"}

    # Step 1: Fetch file metadata from Drive (name, mimeType, size)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            meta_resp = await client.get(
                _DRIVE_FILE_METADATA_URL.format(file_id=file_id),
                headers=headers,
            )
            if meta_resp.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google access token is invalid or expired.",
                )
            if meta_resp.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Google Drive file not found. Check the file ID and sharing permissions.",
                )
            if meta_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Could not fetch file metadata from Google Drive.",
                )
            meta = meta_resp.json()
    except httpx.RequestError as exc:
        logger.error("drive.import.meta_request_error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not reach Google Drive API.",
        )

    file_name = meta.get("name", "drive_import")
    mime_type = meta.get("mimeType", "application/octet-stream")

    if mime_type not in _DRIVE_ALLOWED_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{mime_type}' is not supported. Allowed: images, PDF, video, CSV, Excel.",
        )

    # Step 2: Download file bytes from Drive
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            dl_resp = await client.get(
                _DRIVE_FILE_DOWNLOAD_URL.format(file_id=file_id),
                headers=headers,
                follow_redirects=True,
            )
            if dl_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Could not download file content from Google Drive.",
                )
            data = dl_resp.content
    except httpx.RequestError as exc:
        logger.error("drive.import.download_request_error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not download file from Google Drive.",
        )

    # Google access token is done — never stored, never logged
    del google_access_token

    # Step 3: Hash and persist to disk
    file_hash = _compute_bytes_hash(data)

    farm_dir = os.path.join(_uploads_root(), str(farm_id))
    os.makedirs(farm_dir, exist_ok=True)
    ts = int(datetime.now(timezone.utc).timestamp())
    safe_name = f"{ts}_drive_{file_name}"
    abs_path = os.path.join(farm_dir, safe_name)
    with open(abs_path, "wb") as fh:
        fh.write(data)

    relative_url = f"/uploads/evidence/{farm_id}/{safe_name}"
    ev_type = _safe_evidence_type(evidence_type)

    ev = EvidenceFile(
        farm_id=farm_id,
        crop_cycle_id=crop_cycle_id,
        carbon_report_id=carbon_report_id,
        uploaded_by=current_user.id,
        evidence_type=ev_type,
        file_type=ev_type,
        file_name=file_name,
        file_mime_type=mime_type,
        file_size=len(data),
        storage_path=abs_path,
        file_url=relative_url,
        description=description,
        file_hash=file_hash,
        hash_algorithm="SHA256",
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    logger.info(
        "evidence.drive.import | id=%s farm=%s type=%s size=%s hash=%s…",
        ev.id, farm_id, ev_type, len(data), file_hash[:12],
    )
    return ev
