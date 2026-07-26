from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.dependencies import get_current_fpo, get_current_user
from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.models.farm import Farm, CropCycle, FarmStatus
from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.carbon_token import CarbonToken
from app.models.verification import VerificationRequest, VerificationStatus
from app.models.farmer_credit_balance import FarmerCreditBalance
from app.models.payout import Payout, PayoutStatus
from app.models.evidence import EvidenceFile
from app.models.blockchain_transaction import BlockchainTransaction, ActionType
from sqlalchemy import func
from app.schemas.fpo_schema import (
    FPOProfileCreate, FPOProfileResponse,
    FPOWalletUpdateRequest, FPOWalletResponse, FPOWalletVerifyRequest, FPOWalletVerifyResponse,
    FPOListItemResponse, _mask_wallet,
)
from app.schemas.farm_schema import FarmResponse
from app.schemas.user_schema import UserResponse
from datetime import datetime, timezone

router = APIRouter(prefix="/fpo", tags=["FPO"])


# ── GET /fpo/list ─────────────────────────────────────────────────────────────
@router.get("/list", response_model=List[FPOListItemResponse])
def list_fpos(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all FPO organizations (id, name, district, state).
    Accessible to any authenticated user so farmers can select their FPO
    when registering a farm.
    """
    profiles = db.query(FPOProfile).order_by(FPOProfile.organization_name).all()
    return profiles


# ── POST /fpo/profile ──────────────────────────────────────────────────────────
@router.post("/profile", response_model=FPOProfileResponse, status_code=status.HTTP_201_CREATED)
def create_fpo_profile(
    payload: FPOProfileCreate,
    current_user: User = Depends(get_current_fpo),
    db: Session = Depends(get_db),
):
    # One profile per FPO user
    existing = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FPO profile already exists for this user",
        )
    # Unique registration number
    reg_taken = (
        db.query(FPOProfile)
        .filter(FPOProfile.registration_number == payload.registration_number)
        .first()
    )
    if reg_taken:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration number already in use",
        )
    profile = FPOProfile(
        user_id=current_user.id,
        organization_name=payload.organization_name,
        registration_number=payload.registration_number,
        district=payload.district,
        state=payload.state,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


# ── GET /fpo/profile ──────────────────────────────────────────────────────────
@router.get("/profile", response_model=FPOProfileResponse)
def get_fpo_profile(
    current_user: User = Depends(get_current_fpo),
    db: Session = Depends(get_db),
):
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found")
    return profile


# ── GET /fpo/farms ────────────────────────────────────────────────────────────
@router.get("/farms", response_model=List[FarmResponse])
def get_fpo_farms(
    current_user: User = Depends(get_current_fpo),
    db: Session = Depends(get_db),
):
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found. Create a profile first.")
    farms = db.query(Farm).filter(Farm.fpo_id == profile.id, Farm.is_deleted == False).all()  # noqa: E712
    return farms


# ── GET /fpo/farmers ──────────────────────────────────────────────────────────
@router.get("/farmers", response_model=List[UserResponse])
def get_fpo_farmers(
    current_user: User = Depends(get_current_fpo),
    db: Session = Depends(get_db),
):
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found.")
    farmer_ids = (
        db.query(Farm.farmer_id).filter(Farm.fpo_id == profile.id, Farm.is_deleted == False).distinct().all()  # noqa: E712
    )
    ids = [r[0] for r in farmer_ids]
    if not ids:
        return []
    farmers = db.query(User).filter(User.id.in_(ids)).all()
    return farmers


# ── POST /fpo/farms/{farm_id}/approve ─────────────────────────────────────────
@router.post("/farms/{farm_id}/approve", response_model=FarmResponse)
def approve_farm(
    farm_id: int,
    current_user: User = Depends(get_current_fpo),
    db: Session = Depends(get_db),
):
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found.")
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    if farm.fpo_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Farm is not linked to your FPO",
        )
    now = datetime.now(timezone.utc)
    farm.is_approved = True
    farm.farm_status = FarmStatus.APPROVED
    farm.approved_at = now
    farm.approved_by = current_user.id
    db.commit()
    db.refresh(farm)
    return farm


# ── GET /fpo/registry/summary ─────────────────────────────────────────────────
@router.get("/registry/summary")
def get_fpo_registry_summary(
    current_user: User = Depends(get_current_fpo),
    db: Session = Depends(get_db),
):
    """
    FPO Farmer Registry summary dashboard.
    Returns: total farmers, approved/pending/suspended farms,
             total acreage, active crop cycles.
    """
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found")

    farms = db.query(Farm).filter(Farm.fpo_id == profile.id, Farm.is_deleted == False).all()  # noqa: E712
    farm_ids = [f.id for f in farms]

    total_farmers = db.query(Farm.farmer_id).filter(
        Farm.fpo_id == profile.id, Farm.is_deleted == False  # noqa: E712
    ).distinct().count()

    approved_farms  = sum(1 for f in farms if f.farm_status == FarmStatus.APPROVED)
    pending_farms   = sum(1 for f in farms if f.farm_status in (FarmStatus.DRAFT, FarmStatus.PENDING_APPROVAL))
    suspended_farms = sum(1 for f in farms if f.farm_status == FarmStatus.SUSPENDED)
    total_acreage   = sum(f.land_area_acres for f in farms)

    active_cycles = 0
    if farm_ids:
        from app.models.farm import CropCycleStatus
        active_cycles = db.query(CropCycle).filter(
            CropCycle.farm_id.in_(farm_ids),
            CropCycle.status == CropCycleStatus.ACTIVE,
        ).count()

    return {
        "total_farmers": total_farmers,
        "total_farms": len(farms),
        "approved_farms": approved_farms,
        "pending_farms": pending_farms,
        "suspended_farms": suspended_farms,
        "total_acreage": round(total_acreage, 2),
        "active_crop_cycles": active_cycles,
    }


# ── GET /fpo/registry/farms ───────────────────────────────────────────────────
@router.get("/registry/farms", response_model=List[FarmResponse])
def get_fpo_farm_registry(
    farm_status_filter: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_fpo),
    db: Session = Depends(get_db),
):
    """All farms under this FPO, optionally filtered by farm_status."""
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found")

    q = db.query(Farm).filter(Farm.fpo_id == profile.id, Farm.is_deleted == False)  # noqa: E712
    if farm_status_filter:
        try:
            fs = FarmStatus(farm_status_filter.upper())
            q = q.filter(Farm.farm_status == fs)
        except ValueError:
            pass
    return q.order_by(Farm.created_at.desc()).offset(offset).limit(limit).all()


# ── GET /fpo/registry/farmers ─────────────────────────────────────────────────
@router.get("/registry/farmers")
def get_fpo_farmer_registry(
    current_user: User = Depends(get_current_fpo),
    db: Session = Depends(get_db),
):
    """
    Enriched farmer list — each farmer with their farm count, credit balance,
    and active crop cycle count. Used by FPOFarmersScreen.
    """
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found")

    farmer_ids = db.query(Farm.farmer_id).filter(
        Farm.fpo_id == profile.id, Farm.is_deleted == False  # noqa: E712
    ).distinct().all()
    ids = [r[0] for r in farmer_ids]
    if not ids:
        return []

    result = []
    for farmer_id in ids:
        farmer = db.query(User).filter(User.id == farmer_id).first()
        if not farmer:
            continue

        farms = db.query(Farm).filter(
            Farm.farmer_id == farmer_id,
            Farm.fpo_id == profile.id,
            Farm.is_deleted == False,  # noqa: E712
        ).all()

        farm_ids = [f.id for f in farms]

        from app.models.farm import CropCycleStatus
        active_cycles = db.query(CropCycle).filter(
            CropCycle.farm_id.in_(farm_ids),
            CropCycle.status == CropCycleStatus.ACTIVE,
        ).count() if farm_ids else 0

        total_available = db.query(
            __import__("sqlalchemy", fromlist=["func"]).func.sum(FarmerCreditBalance.credits_available)
        ).filter(
            FarmerCreditBalance.farmer_id == farmer_id,
            FarmerCreditBalance.fpo_id == profile.id,
        ).scalar() or 0.0

        result.append({
            "farmer_id": farmer_id,
            "name": farmer.name,
            "email": farmer.email,
            "total_farms": len(farms),
            "approved_farms": sum(1 for f in farms if f.is_approved),
            "active_crop_cycles": active_cycles,
            "total_available_credits": float(total_available),
        })

    return result


# ── GET /fpo/registry/farmers/{farmer_id} ─────────────────────────────────────
@router.get("/registry/farmers/{farmer_id}")
def get_fpo_farmer_detail(
    farmer_id: int,
    current_user: User = Depends(get_current_fpo),
    db: Session = Depends(get_db),
):
    """
    Full detail for a single farmer under this FPO.
    Includes: profile, farms, crop cycles, credit balances, verification history.
    """
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found")

    farmer = db.query(User).filter(User.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farmer not found")

    farms = db.query(Farm).filter(
        Farm.farmer_id == farmer_id,
        Farm.fpo_id == profile.id,
        Farm.is_deleted == False,  # noqa: E712
    ).all()
    if not farms:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Farmer is not linked to your FPO")

    farm_ids = [f.id for f in farms]

    # Credit balances
    balances = db.query(FarmerCreditBalance).filter(
        FarmerCreditBalance.farmer_id == farmer_id,
        FarmerCreditBalance.fpo_id == profile.id,
    ).all()

    # Verification history for this farmer's reports
    from app.models.verification import VerificationRequest, VerificationStatus
    vr_list = db.query(VerificationRequest).join(
        CarbonReport, VerificationRequest.carbon_report_id == CarbonReport.id
    ).filter(CarbonReport.farm_id.in_(farm_ids)).order_by(
        VerificationRequest.created_at.desc()
    ).limit(20).all()

    from app.schemas.farm_schema import FarmResponse
    from app.schemas.verification_schema import VerificationRequestResponse

    return {
        "farmer": {
            "id": farmer.id,
            "name": farmer.name,
            "email": farmer.email,
            "is_active": farmer.is_active,
            "is_approved": farmer.is_approved,
            "created_at": farmer.created_at,
        },
        "farms": [FarmResponse.model_validate(f) for f in farms],
        "credit_balances": [
            {
                "id": b.id,
                "carbon_report_id": b.carbon_report_id,
                "credits_earned": b.credits_earned,
                "credits_available": b.credits_available,
                "credits_distributed": b.credits_distributed,
                "status": b.status,
                "created_at": b.created_at,
            }
            for b in balances
        ],
        "verification_history": [
            {
                "id": vr.id,
                "carbon_report_id": vr.carbon_report_id,
                "status": vr.status,
                "risk_level": vr.risk_level,
                "verified_at": vr.verified_at,
                "created_at": vr.created_at,
            }
            for vr in vr_list
        ],
    }


# ── GET /fpo/mintable-reports ─────────────────────────────────────────────────
@router.get("/mintable-reports")
def get_fpo_mintable_reports(
    current_user: User = Depends(get_current_fpo),
    db: Session = Depends(get_db),
):
    """
    Returns VERIFIED carbon reports from this FPO's farms that have not yet
    been minted into a token.  Used by the FPO Mint Queue screen.
    """
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found")

    farm_ids = [
        r[0] for r in db.query(Farm.id).filter(
            Farm.fpo_id == profile.id, Farm.is_deleted == False  # noqa: E712
        ).all()
    ]
    if not farm_ids:
        return []

    reports = (
        db.query(CarbonReport)
        .filter(
            CarbonReport.farm_id.in_(farm_ids),
            CarbonReport.status == ReportStatus.VERIFIED,
        )
        .order_by(CarbonReport.created_at.desc())
        .all()
    )
    if not reports:
        return []

    report_ids = [r.id for r in reports]
    # Find already-minted report IDs
    minted_ids = {
        t.carbon_report_id
        for t in db.query(CarbonToken).filter(
            CarbonToken.carbon_report_id.in_(report_ids)
        ).all()
    }

    result = []
    for report in reports:
        if report.id in minted_ids:
            continue
        farm = db.query(Farm).filter(Farm.id == report.farm_id).first()
        farmer = db.query(User).filter(User.id == farm.farmer_id).first() if farm else None
        vr = (
            db.query(VerificationRequest)
            .filter(
                VerificationRequest.carbon_report_id == report.id,
                VerificationRequest.status == VerificationStatus.APPROVED,
            )
            .first()
        )
        result.append({
            "report_id": report.id,
            "farm_id": report.farm_id,
            "farm_name": farm.farm_name if farm else "Unknown",
            "farmer_id": farmer.id if farmer else None,
            "farmer_name": farmer.name if farmer else "Unknown",
            "estimated_credits": report.estimated_credits,
            "co2e_reduction_tonnes": report.co2e_reduction_tonnes,
            "report_status": report.status,
            "verified_at": vr.verified_at if vr else None,
            "created_at": report.created_at,
        })
    return result


# ── GET /fpo/mint-history ─────────────────────────────────────────────────────
@router.get("/mint-history")
def get_fpo_mint_history(
    current_user: User = Depends(get_current_fpo),
    db: Session = Depends(get_db),
):
    """
    Returns all tokens minted by this FPO, with farm/farmer details.
    Used by the FPO Mint History screen.
    """
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found")

    tokens = (
        db.query(CarbonToken)
        .filter(CarbonToken.fpo_id == profile.id)
        .order_by(CarbonToken.minted_at.desc())
        .all()
    )

    result = []
    for token in tokens:
        report = db.query(CarbonReport).filter(CarbonReport.id == token.carbon_report_id).first()
        farm = db.query(Farm).filter(Farm.id == report.farm_id).first() if report else None
        farmer = db.query(User).filter(User.id == token.farmer_id).first()
        # Look up the TOKEN_MINT blockchain transaction for this report
        mint_tx = (
            db.query(BlockchainTransaction)
            .filter(
                BlockchainTransaction.carbon_report_id == token.carbon_report_id,
                BlockchainTransaction.action_type == ActionType.TOKEN_MINT,
            )
            .first()
        )
        result.append({
            "db_id": token.id,
            "token_id": token.token_id,
            "report_id": token.carbon_report_id,
            "farm_id": farm.id if farm else None,
            "farm_name": farm.farm_name if farm else "Unknown",
            "farmer_id": token.farmer_id,
            "farmer_name": farmer.name if farmer else "Unknown",
            "credit_amount": token.credit_amount,
            "minted_at": token.minted_at,
            "minted_tx_hash": token.minted_tx_hash,
            "status": token.status,
            # Phase 17: real blockchain fields
            "blockchain_network": mint_tx.blockchain_network if mint_tx else None,
            "contract_address": mint_tx.contract_address if mint_tx else None,
        })
    return result


# ── PATCH /fpo/profile/wallet ─────────────────────────────────────────────────
@router.patch("/profile/wallet", response_model=FPOWalletResponse)
def update_fpo_wallet(
    payload: FPOWalletUpdateRequest,
    current_user: User = Depends(get_current_fpo),
    db: Session = Depends(get_db),
):
    """
    Update FPO wallet address and/or vault identifier. FPO only.
    wallet_address must be a valid 0x-prefixed 42-character EVM address.
    """
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found")

    if payload.wallet_address is not None:
        # Changing wallet address resets verification
        if profile.wallet_address != payload.wallet_address:
            profile.wallet_verified = False
            profile.wallet_verified_at = None
        profile.wallet_address = payload.wallet_address
    if payload.vault_identifier is not None:
        profile.vault_identifier = payload.vault_identifier
    if payload.wallet_network is not None:
        profile.wallet_network = payload.wallet_network

    db.commit()
    db.refresh(profile)
    return FPOWalletResponse.from_orm_enriched(profile)


# ── GET /fpo/profile/wallet ───────────────────────────────────────────────────
@router.get("/profile/wallet", response_model=FPOWalletResponse)
def get_fpo_wallet(
    current_user: User = Depends(get_current_fpo),
    db: Session = Depends(get_db),
):
    """Get FPO wallet address, vault identifier, and verification status. FPO only."""
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found")
    return FPOWalletResponse.from_orm_enriched(profile)


# ── POST /fpo/profile/wallet/verify ──────────────────────────────────────────
@router.post("/profile/wallet/verify", response_model=FPOWalletVerifyResponse)
def verify_fpo_wallet(
    payload: FPOWalletVerifyRequest,
    current_user: User = Depends(get_current_fpo),
    db: Session = Depends(get_db),
):
    """
    Verify the FPO custodial vault wallet address.

    Mock mode (BLOCKCHAIN_MODE != 'web3'):
      - Validates format (0x-prefixed, 42 chars)
      - Marks wallet_verified = True immediately
      - No on-chain call

    Web3 mode (BLOCKCHAIN_MODE = 'web3'):
      - Validates address checksum via Web3.py
      - Checks provider connectivity
      - Marks wallet_verified = True on success

    Verification is reset when wallet_address changes (PATCH /fpo/profile/wallet).
    """
    import os
    from app.schemas.fpo_schema import _mask_wallet

    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found")
    if not profile.wallet_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No wallet address set. Use PATCH /fpo/profile/wallet to set one first.",
        )

    # Format validation (always)
    addr = profile.wallet_address.strip()
    if not addr.startswith("0x") or len(addr) != 42:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet address format invalid. Must be 0x-prefixed 42-character EVM address.",
        )

    blockchain_mode = os.environ.get("BLOCKCHAIN_MODE", "mock").lower()

    if blockchain_mode == "web3":
        # Web3 mode: checksum + connectivity check
        try:
            from web3 import Web3
            if not Web3.is_checksum_address(Web3.to_checksum_address(addr)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Wallet address failed EIP-55 checksum validation.",
                )
            # Provider connectivity check
            from app.services.blockchain_service import get_blockchain_provider
            provider = get_blockchain_provider()
            if not provider.is_connected():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Blockchain provider not reachable. Cannot verify wallet at this time.",
                )
        except ImportError:
            pass  # web3 not installed — fall through to mock verification

    # Mark verified
    now = datetime.now(timezone.utc)
    profile.wallet_verified = True
    profile.wallet_verified_at = now
    if not profile.wallet_network:
        profile.wallet_network = "POLYGON_AMOY" if blockchain_mode == "web3" else "MOCK_POLYGON_AMOY"
    db.commit()
    db.refresh(profile)

    return FPOWalletVerifyResponse(
        verified=True,
        wallet_address=profile.wallet_address,
        wallet_address_masked=_mask_wallet(profile.wallet_address),
        wallet_network=profile.wallet_network,
        verified_at=profile.wallet_verified_at,
        message=(
            "Wallet verified via Web3 provider."
            if blockchain_mode == "web3"
            else "Wallet format verified (mock mode)."
        ),
    )


# ── GET /fpo/operations-dashboard ─────────────────────────────────────────────
@router.get("/operations-dashboard")
def get_fpo_operations_dashboard(
    current_fpo: User = Depends(get_current_fpo),
    db: Session = Depends(get_db),
):
    """
    Phase 15 — FPO Operations Dashboard.

    Returns a structured summary of the FPO's operations:
      - summary counts (farmers, farms, crop_cycles, reports, tokens, payouts)
      - action_queue: farms needing approval, reports ready to mint, payouts initiated
      - recent evidence uploads
      - risk alerts (high-risk pending verifications)
    """
    profile = db.query(FPOProfile).filter(FPOProfile.user_id == current_fpo.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FPO profile not found")

    fpo_id = profile.id

    # ── Farms ──────────────────────────────────────────────────────────────────
    all_farms = db.query(Farm).filter(Farm.fpo_id == fpo_id).all()
    farm_ids = [f.id for f in all_farms]

    farms_pending_approval = [
        {"id": f.id, "farm_name": f.farm_name, "village": f.village, "district": f.district}
        for f in all_farms
        if f.farm_status == FarmStatus.PENDING_APPROVAL
    ]

    # ── Farmers ────────────────────────────────────────────────────────────────
    farmer_ids_set = set(f.farmer_id for f in all_farms)
    total_farmers = len(farmer_ids_set)

    # ── Crop Cycles ────────────────────────────────────────────────────────────
    total_cycles = 0
    if farm_ids:
        total_cycles = (
            db.query(func.count(CropCycle.id))
            .filter(CropCycle.farm_id.in_(farm_ids))
            .scalar()
        ) or 0

    # ── Carbon Reports ─────────────────────────────────────────────────────────
    total_reports = 0
    mintable_reports = []
    if farm_ids:
        all_reports = (
            db.query(CarbonReport)
            .filter(CarbonReport.farm_id.in_(farm_ids))
            .all()
        )
        total_reports = len(all_reports)

        # Mintable = VERIFIED reports with no corresponding CarbonToken
        verified_reports = [r for r in all_reports if r.status == ReportStatus.VERIFIED]
        minted_report_ids = {
            t.carbon_report_id
            for t in db.query(CarbonToken.carbon_report_id)
            .filter(CarbonToken.carbon_report_id.in_([r.id for r in verified_reports]))
            .all()
        }
        mintable_reports = [
            {
                "report_id": r.id,
                "farm_id": r.farm_id,
                "estimated_credits": r.estimated_credits,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in verified_reports
            if r.id not in minted_report_ids
        ]

    # ── Carbon Tokens ──────────────────────────────────────────────────────────
    total_tokens = 0
    if farm_ids:
        report_ids = [r.id for r in db.query(CarbonReport.id).filter(CarbonReport.farm_id.in_(farm_ids)).all()]
        if report_ids:
            total_tokens = (
                db.query(func.count(CarbonToken.id))
                .filter(CarbonToken.carbon_report_id.in_(report_ids))
                .scalar()
            ) or 0

    # ── Payouts ────────────────────────────────────────────────────────────────
    initiated_payouts = (
        db.query(Payout)
        .filter(Payout.fpo_id == fpo_id, Payout.status == PayoutStatus.INITIATED)
        .all()
    )
    total_payouts = (
        db.query(func.count(Payout.id))
        .filter(Payout.fpo_id == fpo_id)
        .scalar()
    ) or 0

    payout_queue = [
        {
            "payout_id": p.id,
            "farmer_id": p.farmer_id,
            "amount_credits": p.amount_credits,
            "payout_amount": p.payout_amount,
            "currency": p.currency,
            "initiated_at": p.initiated_at.isoformat() if p.initiated_at else None,
        }
        for p in initiated_payouts
    ]

    # ── Recent Evidence ────────────────────────────────────────────────────────
    recent_evidence: list = []
    if farm_ids:
        cycle_rows = (
            db.query(CropCycle.id, CropCycle.farm_id)
            .filter(CropCycle.farm_id.in_(farm_ids))
            .all()
        )
        cycle_ids = [r[0] for r in cycle_rows]
        cycle_farm_map = {r[0]: r[1] for r in cycle_rows}
        if cycle_ids:
            recent_ev_rows = (
                db.query(EvidenceFile)
                .filter(EvidenceFile.crop_cycle_id.in_(cycle_ids))
                .order_by(EvidenceFile.id.desc())
                .limit(10)
                .all()
            )
            recent_evidence = [
                {
                    "id": ev.id,
                    "file_type": ev.file_type,
                    "evidence_type": ev.evidence_type,
                    "description": ev.description,
                    "crop_cycle_id": ev.crop_cycle_id,
                    "farm_id": cycle_farm_map.get(ev.crop_cycle_id),
                    "created_at": ev.created_at.isoformat() if ev.created_at else None,
                }
                for ev in recent_ev_rows
            ]

    # ── Pending Verifications (risk alerts) ────────────────────────────────────
    risk_alerts: list = []
    if farm_ids:
        pending_vrs = (
            db.query(VerificationRequest)
            .join(CarbonReport, VerificationRequest.carbon_report_id == CarbonReport.id)
            .filter(
                CarbonReport.farm_id.in_(farm_ids),
                VerificationRequest.status == VerificationStatus.PENDING,
            )
            .all()
        )
        risk_alerts = [
            {
                "verification_id": vr.id,
                "carbon_report_id": vr.carbon_report_id,
                "risk_score": vr.risk_score,
                "risk_level": vr.risk_level,
                "recommendation": vr.recommendation,
                "created_at": vr.created_at.isoformat() if vr.created_at else None,
            }
            for vr in pending_vrs
            if vr.risk_level in ("HIGH", "MEDIUM")
        ]

    return {
        "fpo_id": fpo_id,
        "fpo_name": profile.organization_name,
        "summary": {
            "total_farmers": total_farmers,
            "total_farms": len(all_farms),
            "total_crop_cycles": total_cycles,
            "total_reports": total_reports,
            "total_tokens": total_tokens,
            "total_payouts": total_payouts,
        },
        "action_queue": {
            "farms_pending_approval": farms_pending_approval,
            "mintable_reports": mintable_reports,
            "initiated_payouts": payout_queue,
        },
        "recent_evidence": recent_evidence,
        "risk_alerts": risk_alerts,
    }
