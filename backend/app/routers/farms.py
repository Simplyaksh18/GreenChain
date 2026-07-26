"""
Farms router — Phase 2 + Phase 11 lifecycle & GIS extensions.

Endpoints:
  POST   /farms                                   FARMER — create farm
  GET    /farms                                   all roles — list farms
  GET    /farms/{farm_id}                         all roles — get farm
  DELETE /farms/{farm_id}                         FARMER — soft-delete
  PATCH  /farms/{farm_id}/archive                 FARMER — archive
  PATCH  /farms/{farm_id}/suspend                 FPO — suspend
  PATCH  /farms/{farm_id}/restore                 FPO — restore (SUSPENDED→APPROVED)
  PATCH  /farms/{farm_id}/approve                 FPO — approve (DRAFT/PENDING→APPROVED)
  PATCH  /farms/{farm_id}/boundary                FARMER/FPO/ADMIN — set GIS boundary
  GET    /farms/{farm_id}/boundary                all roles — get GIS boundary

  POST   /farms/{farm_id}/crop-cycles             FARMER — create crop cycle
  GET    /farms/{farm_id}/crop-cycles             all roles — list crop cycles
  PATCH  /farms/{farm_id}/crop-cycles/{cycle_id}  FARMER — general update
  PATCH  /farms/{farm_id}/crop-cycles/{cycle_id}/harvest  FARMER — mark harvested
  PATCH  /farms/{farm_id}/crop-cycles/{cycle_id}/close    FARMER — close cycle
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_current_farmer
from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.models.farm import Farm, CropCycle, FarmStatus, CropCycleStatus
from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.carbon_token import CarbonToken
from app.models.payout import Payout, PayoutStatus
from app.schemas.farm_schema import (
    FarmCreate, FarmResponse, FarmBoundaryUpdate, FarmBoundaryResponse,
    ArchiveFarmRequest, SuspendFarmRequest,
    CropCycleCreate, CropCycleUpdate, CropCycleResponse,
    HarvestCropCycleRequest, CloseCropCycleRequest,
    normalize_geojson_for_storage, parse_geojson_from_storage,
)

router = APIRouter(prefix="/farms", tags=["Farms"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_farm_or_404(farm_id: int, db: Session, include_deleted: bool = False) -> Farm:
    q = db.query(Farm).filter(Farm.id == farm_id)
    if not include_deleted:
        q = q.filter(Farm.is_deleted == False)  # noqa: E712
    farm = q.first()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    return farm


def _assert_farm_access(farm: Farm, current_user: User, db: Session):
    """Raise 403 if current_user may not view this farm."""
    if current_user.role == UserRole.ADMIN:
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


def _get_fpo_profile_or_403(current_user: User, db: Session) -> FPOProfile:
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FPO profile not found")
    return profile


# ── POST /farms ───────────────────────────────────────────────────────────────

@router.post("", response_model=FarmResponse, status_code=status.HTTP_201_CREATED)
def create_farm(
    payload: FarmCreate,
    current_user: User = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    if payload.fpo_id is not None:
        fpo_exists = db.query(FPOProfile).filter(FPOProfile.id == payload.fpo_id).first()
        if not fpo_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"FPO profile with id {payload.fpo_id} not found",
            )
    # Farms linked to an FPO start in PENDING_APPROVAL (awaiting FPO review).
    # Farms with no FPO are self-managed and start as DRAFT.
    initial_status = FarmStatus.PENDING_APPROVAL if payload.fpo_id else FarmStatus.DRAFT
    farm = Farm(
        farmer_id=current_user.id,
        fpo_id=payload.fpo_id,
        farm_name=payload.farm_name,
        land_area_acres=payload.land_area_acres,
        latitude=payload.latitude,
        longitude=payload.longitude,
        village=payload.village,
        district=payload.district,
        state=payload.state,
        soil_type=payload.soil_type,
        water_source=payload.water_source,
        is_approved=False,
        farm_status=initial_status,
    )
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm


# ── GET /farms ────────────────────────────────────────────────────────────────

@router.get("", response_model=List[FarmResponse])
def list_farms(
    district: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    is_approved: Optional[bool] = Query(default=None),
    farm_status: Optional[FarmStatus] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == UserRole.ADMIN:
        q = db.query(Farm).filter(Farm.is_deleted == False)  # noqa: E712
    elif current_user.role == UserRole.FARMER:
        q = db.query(Farm).filter(Farm.farmer_id == current_user.id, Farm.is_deleted == False)  # noqa: E712
    elif current_user.role == UserRole.FPO:
        profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
        if not profile:
            return []
        q = db.query(Farm).filter(Farm.fpo_id == profile.id, Farm.is_deleted == False)  # noqa: E712
    elif current_user.role == UserRole.VERIFIER:
        q = db.query(Farm).filter(Farm.is_deleted == False)  # noqa: E712
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if district is not None:
        q = q.filter(Farm.district.ilike(f"%{district}%"))
    if state is not None:
        q = q.filter(Farm.state.ilike(f"%{state}%"))
    if is_approved is not None:
        q = q.filter(Farm.is_approved.is_(is_approved))
    if farm_status is not None:
        q = q.filter(Farm.farm_status == farm_status)

    return q.offset(offset).limit(limit).all()


# ── GET /farms/{farm_id} ──────────────────────────────────────────────────────

@router.get("/{farm_id}", response_model=FarmResponse)
def get_farm(
    farm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    farm = _get_farm_or_404(farm_id, db)
    _assert_farm_access(farm, current_user, db)
    return farm


# ── PATCH /farms/{farm_id}/approve  (FPO) ─────────────────────────────────────

@router.patch("/{farm_id}/approve", response_model=FarmResponse)
def approve_farm(
    farm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FPO approves a farm. Sets farm_status=APPROVED and is_approved=True."""
    if current_user.role not in (UserRole.FPO, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only FPO or ADMIN can approve farms")

    farm = _get_farm_or_404(farm_id, db)

    if current_user.role == UserRole.FPO:
        profile = _get_fpo_profile_or_403(current_user, db)
        if farm.fpo_id != profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Farm is not linked to your FPO")

    if farm.farm_status == FarmStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Farm is already approved")
    if farm.farm_status == FarmStatus.ARCHIVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot approve an archived farm")

    now = datetime.now(timezone.utc)
    farm.farm_status = FarmStatus.APPROVED
    farm.is_approved = True
    farm.approved_at = now
    farm.approved_by = current_user.id
    db.commit()
    db.refresh(farm)
    return farm


# ── PATCH /farms/{farm_id}/archive  (FARMER) ──────────────────────────────────

@router.patch("/{farm_id}/archive", response_model=FarmResponse)
def archive_farm(
    farm_id: int,
    payload: ArchiveFarmRequest = ArchiveFarmRequest(),
    current_user: User = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    """Farmer archives their own farm. Sets farm_status=ARCHIVED."""
    farm = _get_farm_or_404(farm_id, db)
    if farm.farmer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this farm")

    if farm.farm_status == FarmStatus.ARCHIVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Farm is already archived")

    now = datetime.now(timezone.utc)
    farm.farm_status = FarmStatus.ARCHIVED
    farm.archived_at = now
    if payload.reason:
        farm.archive_reason = payload.reason
    db.commit()
    db.refresh(farm)
    return farm


# ── PATCH /farms/{farm_id}/suspend  (FPO) ─────────────────────────────────────

@router.patch("/{farm_id}/suspend", response_model=FarmResponse)
def suspend_farm(
    farm_id: int,
    payload: SuspendFarmRequest = SuspendFarmRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FPO suspends a farm. Sets farm_status=SUSPENDED and is_approved=False."""
    if current_user.role not in (UserRole.FPO, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only FPO or ADMIN can suspend farms")

    farm = _get_farm_or_404(farm_id, db)

    if current_user.role == UserRole.FPO:
        profile = _get_fpo_profile_or_403(current_user, db)
        if farm.fpo_id != profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Farm is not linked to your FPO")

    if farm.farm_status == FarmStatus.SUSPENDED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Farm is already suspended")
    if farm.farm_status == FarmStatus.ARCHIVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot suspend an archived farm")

    farm.farm_status = FarmStatus.SUSPENDED
    farm.is_approved = False
    if payload.reason:
        farm.archive_reason = payload.reason
    db.commit()
    db.refresh(farm)
    return farm


# ── PATCH /farms/{farm_id}/restore  (FPO) ─────────────────────────────────────

@router.patch("/{farm_id}/restore", response_model=FarmResponse)
def restore_farm(
    farm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FPO restores a suspended farm to APPROVED status."""
    if current_user.role not in (UserRole.FPO, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only FPO or ADMIN can restore farms")

    farm = _get_farm_or_404(farm_id, db)

    if current_user.role == UserRole.FPO:
        profile = _get_fpo_profile_or_403(current_user, db)
        if farm.fpo_id != profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Farm is not linked to your FPO")

    if farm.farm_status != FarmStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only SUSPENDED farms can be restored. Current status: {farm.farm_status.value}",
        )

    now = datetime.now(timezone.utc)
    farm.farm_status = FarmStatus.APPROVED
    farm.is_approved = True
    farm.approved_at = now
    farm.approved_by = current_user.id
    db.commit()
    db.refresh(farm)
    return farm


# ── PATCH /farms/{farm_id}/boundary  (FARMER/FPO/ADMIN) ──────────────────────

@router.patch("/{farm_id}/boundary", response_model=FarmBoundaryResponse)
def set_farm_boundary(
    farm_id: int,
    payload: FarmBoundaryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set or update GIS boundary for a farm."""
    farm = _get_farm_or_404(farm_id, db)
    _assert_farm_access(farm, current_user, db)

    # payload.farm_boundary_geojson is already a canonical JSON string
    # (FarmBoundaryUpdate._coerce_geojson normalises dict/str → str before we arrive here)
    farm.farm_boundary_geojson = payload.farm_boundary_geojson
    if payload.boundary_area_hectares is not None:
        farm.boundary_area_hectares = payload.boundary_area_hectares
    if payload.boundary_area_acres is not None:
        farm.boundary_area_acres = payload.boundary_area_acres
    db.commit()
    db.refresh(farm)
    boundary_dict = parse_geojson_from_storage(farm.farm_boundary_geojson)
    return FarmBoundaryResponse(
        farm_id=farm.id,
        farm_name=farm.farm_name,
        # Both fields carry the same parsed dict — mobile uses whichever is non-null
        farm_boundary_geojson=boundary_dict,
        boundary=boundary_dict,
        has_boundary=bool(farm.farm_boundary_geojson),
        boundary_area_hectares=farm.boundary_area_hectares,
        boundary_area_acres=farm.boundary_area_acres,
    )


# ── GET /farms/{farm_id}/boundary ─────────────────────────────────────────────

@router.get("/{farm_id}/boundary", response_model=FarmBoundaryResponse)
def get_farm_boundary(
    farm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    farm = _get_farm_or_404(farm_id, db)
    _assert_farm_access(farm, current_user, db)
    boundary_dict = parse_geojson_from_storage(farm.farm_boundary_geojson)
    return FarmBoundaryResponse(
        farm_id=farm.id,
        farm_name=farm.farm_name,
        farm_boundary_geojson=boundary_dict,
        boundary=boundary_dict,
        has_boundary=bool(farm.farm_boundary_geojson),
        boundary_area_hectares=farm.boundary_area_hectares,
        boundary_area_acres=farm.boundary_area_acres,
    )


# ── DELETE /farms/{farm_id} ───────────────────────────────────────────────────

@router.delete("/{farm_id}", status_code=status.HTTP_200_OK)
def delete_farm(
    farm_id: int,
    current_user: User = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    """
    Permanently delete a farm and all associated data.
    FARMER-only; must own the farm.

    Blocked if:
      - Carbon credits have already been minted (CarbonToken exists)
      - A payout has been issued or is in progress
      - A verified carbon report exists (data integrity protection)
    """
    farm = _get_farm_or_404(farm_id, db, include_deleted=True)
    if farm.farmer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this farm")

    # ── Safety checks ────────────────────────────────────────────────────────
    report_ids = [
        r.id for r in db.query(CarbonReport).filter(CarbonReport.farm_id == farm_id).all()
    ]

    if report_ids:
        # Block if any carbon token has been minted
        minted_token = (
            db.query(CarbonToken)
            .filter(CarbonToken.carbon_report_id.in_(report_ids))
            .first()
        )
        if minted_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Farm cannot be deleted because carbon credits have already been issued. "
                    "Contact your FPO or admin."
                ),
            )

        # Block if any payout exists for this farm's credit balances
        from app.models.farmer_credit_balance import FarmerCreditBalance
        balance_ids = [
            b.id for b in db.query(FarmerCreditBalance)
            .filter(FarmerCreditBalance.carbon_report_id.in_(report_ids))
            .all()
        ]
        if balance_ids:
            active_payout = (
                db.query(Payout)
                .filter(
                    Payout.credit_balance_id.in_(balance_ids),
                    Payout.status.in_([
                        PayoutStatus.COMPLETED,
                        PayoutStatus.INITIATED,
                        PayoutStatus.PROCESSING,
                    ]),
                )
                .first()
            )
            if active_payout:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Farm cannot be deleted because a payout has already been issued.",
                )

        # Block if any report is VERIFIED (credits about to be / already issued)
        verified_report = (
            db.query(CarbonReport)
            .filter(
                CarbonReport.farm_id == farm_id,
                CarbonReport.status == ReportStatus.VERIFIED,
            )
            .first()
        )
        if verified_report:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Farm cannot be deleted because it has a verified carbon report awaiting "
                    "credit issuance. Complete or cancel the minting process first."
                ),
            )

    # ── Permanent deletion (cascade handles all child records) ───────────────
    db.delete(farm)
    db.commit()
    return {"message": "Farm permanently deleted"}


# ── POST /farms/{farm_id}/crop-cycles ─────────────────────────────────────────

@router.post("/{farm_id}/crop-cycles", response_model=CropCycleResponse, status_code=status.HTTP_201_CREATED)
def create_crop_cycle(
    farm_id: int,
    payload: CropCycleCreate,
    current_user: User = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    farm = _get_farm_or_404(farm_id, db)
    if farm.farmer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this farm")
    cycle = CropCycle(
        farm_id=farm.id,
        crop_type=payload.crop_type,
        season=payload.season,
        start_date=payload.start_date,
        end_date=payload.end_date,
        baseline_method=payload.baseline_method,
        reduction_practice=payload.reduction_practice,
        status=CropCycleStatus.ACTIVE,
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


# ── GET /farms/{farm_id}/crop-cycles ─────────────────────────────────────────

@router.get("/{farm_id}/crop-cycles", response_model=List[CropCycleResponse])
def list_crop_cycles(
    farm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    farm = _get_farm_or_404(farm_id, db)
    _assert_farm_access(farm, current_user, db)
    return db.query(CropCycle).filter(CropCycle.farm_id == farm_id).all()


# ── PATCH /farms/{farm_id}/crop-cycles/{cycle_id} ─────────────────────────────

@router.patch("/{farm_id}/crop-cycles/{cycle_id}", response_model=CropCycleResponse)
def update_crop_cycle(
    farm_id: int,
    cycle_id: int,
    payload: CropCycleUpdate,
    current_user: User = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    """General PATCH — update mutable fields. FARMER-only; must own the farm."""
    farm = _get_farm_or_404(farm_id, db)
    if farm.farmer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this farm")

    cycle = db.query(CropCycle).filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id).first()
    if not cycle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop cycle not found")

    if cycle.status == CropCycleStatus.CLOSED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot edit a CLOSED crop cycle")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cycle, field, value)

    if cycle.end_date and cycle.start_date and cycle.end_date < cycle.start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_date must be on or after start_date")

    db.commit()
    db.refresh(cycle)
    return cycle


# ── PATCH /farms/{farm_id}/crop-cycles/{cycle_id}/harvest ─────────────────────

@router.patch("/{farm_id}/crop-cycles/{cycle_id}/harvest", response_model=CropCycleResponse)
def harvest_crop_cycle(
    farm_id: int,
    cycle_id: int,
    payload: HarvestCropCycleRequest,
    current_user: User = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    """Mark a crop cycle as HARVESTED. Records harvest date and yield."""
    farm = _get_farm_or_404(farm_id, db)
    if farm.farmer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this farm")

    cycle = db.query(CropCycle).filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id).first()
    if not cycle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop cycle not found")

    if cycle.status not in (CropCycleStatus.ACTIVE, CropCycleStatus.PLANNED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only ACTIVE or PLANNED cycles can be harvested. Current status: {cycle.status.value}",
        )

    cycle.status = CropCycleStatus.HARVESTED
    cycle.harvest_date = payload.harvest_date
    cycle.end_date = payload.end_date or payload.harvest_date
    if payload.yield_quantity is not None:
        cycle.yield_quantity = payload.yield_quantity
    if payload.yield_unit is not None:
        cycle.yield_unit = payload.yield_unit

    db.commit()
    db.refresh(cycle)
    return cycle


# ── PATCH /farms/{farm_id}/crop-cycles/{cycle_id}/close ───────────────────────

@router.patch("/{farm_id}/crop-cycles/{cycle_id}/close", response_model=CropCycleResponse)
def close_crop_cycle(
    farm_id: int,
    cycle_id: int,
    payload: CloseCropCycleRequest = CloseCropCycleRequest(),
    current_user: User = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    """Close a crop cycle — no further MRV data will be accepted."""
    farm = _get_farm_or_404(farm_id, db)
    if farm.farmer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this farm")

    cycle = db.query(CropCycle).filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id).first()
    if not cycle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop cycle not found")

    if cycle.status == CropCycleStatus.CLOSED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cycle is already closed")

    cycle.status = CropCycleStatus.CLOSED
    cycle.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cycle)
    return cycle
