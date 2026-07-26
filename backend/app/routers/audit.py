"""
Audit Router — Phase 13 Evidence & Audit Trail.

Endpoints:
  GET /audit/farms/{farm_id}/full-report
      Full auditable JSON package for a farm: farm info, crop cycles,
      carbon reports, SOC reports, evidence, verification history,
      blockchain transactions, tokens, payouts, and methodology notes.

  GET /audit/reports/{report_id}/package
      Report-level audit package: one carbon report + all related records.

Access rules:
  ADMIN and VERIFIER can audit any farm.
  FARMER can audit their own farms.
  FPO can audit farms linked to their profile.

SECURITY:
  - No raw secrets, Razorpay keys, or blockchain private keys in output.
  - Transaction hashes truncated to prevent leakage of full chain state.
  - Payout idempotency keys shortened (last 8 chars only).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.models.farm import Farm, CropCycle
from app.models.carbon_report import CarbonReport
from app.models.evidence import EvidenceFile
from app.models.verification import VerificationRequest
from app.models.blockchain_transaction import BlockchainTransaction
from app.models.carbon_token import CarbonToken
from app.models.payout import Payout
from app.models.sensor import SensorReading
from app.models.satellite_observation import SatelliteObservation
from app.models.soc import SOCReport

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["Audit"])

_METHANE_METHODOLOGY = {
    "standard": "IPCC 2006 Tier 1 — Enteric Fermentation & Manure Management",
    "gwp_factor": 27.2,
    "formula": "co2e = (baseline_methane_kg - current_methane_kg) × 27.2 / 1000",
    "credits_formula": "floor(co2e_tonnes) if co2e_tonnes >= 1.0 else 0",
    "baseline_source": "Sensor-derived average methane emission for crop cycle",
    "sensor_inputs": [
        "soil_moisture", "water_depth_cm", "temperature_c",
        "humidity", "rainfall_mm", "data_quality_score",
    ],
    "emission_estimator": "LinearEmissionEstimator v1",
}

_SOC_METHODOLOGY = {
    "standard": "IPCC Tier 1 / Ghimire et al. 2012 NDVI-SOC proxy",
    "bulk_density": 1.3,
    "soil_depth_cm": 30,
    "soil_mass_t_per_ha": 3900,
    "co2e_conversion": "soc_tonnes × 44/12",
    "soc_gain_formula": "Δ%SOC = α × max(0, mean(NDVI) − 0.30) × (days/120) × crop_factor × practice_factor",
    "alpha": 0.12,
    "provider_confidence_hierarchy": "LAB(0.95) > COPERNICUS(0.85) > BHUVAN/MANUAL(0.80) > SIMULATED(0.45) > ESTIMATED(0.25)",
    "credits_note": "SOC credits are INFORMATIONAL ONLY. They are NOT mintable or payable.",
}


def _truncate_hash(h: str | None, prefix: int = 8, suffix: int = 6) -> str | None:
    if not h:
        return None
    h = h.strip()
    if len(h) <= prefix + suffix + 3:
        return h
    return f"{h[:prefix]}...{h[-suffix:]}"


def _shorten_key(k: str | None, suffix: int = 8) -> str | None:
    """Show only the last N chars of an idempotency key (safe to log/display)."""
    if not k:
        return None
    return f"...{k[-suffix:]}"


def _assert_farm_access(farm: Farm, user: User, db: Session) -> None:
    if user.role in (UserRole.ADMIN, UserRole.VERIFIER):
        return
    if user.role == UserRole.FARMER:
        if farm.farmer_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return
    if user.role == UserRole.FPO:
        profile = db.query(FPOProfile).filter(FPOProfile.user_id == user.id).first()
        if not profile or farm.fpo_id != profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _serialise_evidence(ev: EvidenceFile) -> dict:
    return {
        "id": ev.id,
        "file_type": ev.file_type,
        "description": ev.description,
        "file_hash": ev.file_hash,
        "hash_algorithm": ev.hash_algorithm or "SHA256",
        "carbon_report_id": ev.carbon_report_id,
        "crop_cycle_id": ev.crop_cycle_id,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
        # file_url intentionally omitted from audit export for privacy
    }


def _serialise_verification(vr: VerificationRequest, verifier_name: str | None) -> dict:
    return {
        "id": vr.id,
        "status": vr.status,
        "risk_score": vr.risk_score,
        "risk_level": vr.risk_level,
        "recommendation": vr.recommendation,
        "remarks": vr.remarks,
        "verifier_name": verifier_name,
        "verified_at": vr.verified_at.isoformat() if vr.verified_at else None,
        "created_at": vr.created_at.isoformat() if vr.created_at else None,
    }


def _serialise_blockchain(tx: BlockchainTransaction) -> dict:
    return {
        "id": tx.id,
        "action_type": tx.action_type,
        "tx_hash": _truncate_hash(tx.tx_hash),
        "blockchain_network": tx.blockchain_network,
        "contract_address": _truncate_hash(tx.contract_address, prefix=6, suffix=4),
        "created_at": tx.created_at.isoformat() if tx.created_at else None,
    }


def _serialise_token(token: CarbonToken | None) -> dict | None:
    if not token:
        return None
    return {
        "id": token.id,
        "token_id": token.token_id,
        "token_standard": token.token_standard,
        "credit_amount": token.credit_amount,
        "status": token.status,
        "minted_tx_hash": _truncate_hash(token.minted_tx_hash),
        "minted_at": token.minted_at.isoformat() if token.minted_at else None,
    }


def _serialise_payout(p: Payout) -> dict:
    return {
        "id": p.id,
        "amount_credits": p.amount_credits,
        "price_per_credit": p.price_per_credit,
        "payout_amount": p.payout_amount,
        "currency": p.currency,
        "status": p.status,
        "payout_method": p.payout_method,
        "provider_reference_id": p.provider_reference_id,
        "idempotency_key_suffix": _shorten_key(p.idempotency_key),
        "initiated_at": p.initiated_at.isoformat() if p.initiated_at else None,
        "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        "remarks": p.remarks,
    }


def _build_report_package(
    report: CarbonReport,
    db: Session,
) -> dict:
    """Build the audit package for one carbon report."""
    cycle = db.query(CropCycle).filter(CropCycle.id == report.crop_cycle_id).first()

    # Sensor stats for methane diagnostics
    sensor_count = db.query(func.count(SensorReading.id)).filter(
        SensorReading.crop_cycle_id == report.crop_cycle_id
    ).scalar() or 0
    avg_quality = float(db.query(func.avg(SensorReading.data_quality_score)).filter(
        SensorReading.crop_cycle_id == report.crop_cycle_id
    ).scalar() or 0.0)
    sat_count = db.query(func.count(SatelliteObservation.id)).filter(
        SatelliteObservation.crop_cycle_id == report.crop_cycle_id
    ).scalar() or 0

    verifications = (
        db.query(VerificationRequest)
        .filter(VerificationRequest.carbon_report_id == report.id)
        .order_by(VerificationRequest.created_at)
        .all()
    )
    verifier_names: dict[int, str | None] = {}
    for vr in verifications:
        if vr.verifier_id and vr.verifier_id not in verifier_names:
            v = db.query(User).filter(User.id == vr.verifier_id).first()
            verifier_names[vr.verifier_id] = v.name if v else None

    blockchain_txns = (
        db.query(BlockchainTransaction)
        .filter(BlockchainTransaction.carbon_report_id == report.id)
        .order_by(BlockchainTransaction.created_at)
        .all()
    )
    token = db.query(CarbonToken).filter(CarbonToken.carbon_report_id == report.id).first()
    evidence = (
        db.query(EvidenceFile)
        .filter(EvidenceFile.crop_cycle_id == report.crop_cycle_id)
        .all()
    )
    soc_report = (
        db.query(SOCReport)
        .filter(SOCReport.crop_cycle_id == report.crop_cycle_id)
        .first()
    )

    return {
        "carbon_report": {
            "id": report.id,
            "status": report.status,
            "report_hash": _truncate_hash(report.report_hash),
            "created_at": report.created_at.isoformat() if report.created_at else None,
        },
        "methane_diagnostics": {
            "baseline_methane_kg": round(report.baseline_methane_kg, 4),
            "current_methane_kg": round(report.current_methane_kg, 4),
            "methane_reduction_kg": round(report.methane_reduction_kg, 4),
            "co2e_reduction_tonnes": round(report.co2e_reduction_tonnes, 6),
            "gwp_factor_used": 27.2,
            "formula": "(baseline - current) × 27.2 / 1000 = tCO₂e",
            "estimated_credits": report.estimated_credits,
            "input_sensor_count": sensor_count,
            "sensor_quality_average": round(avg_quality, 2) if sensor_count else None,
            "satellite_observation_count": sat_count,
        },
        "soc_report": {
            "id": soc_report.id if soc_report else None,
            "baseline_soc": soc_report.baseline_soc if soc_report else None,
            "current_soc": soc_report.current_soc if soc_report else None,
            "soc_gain": soc_report.soc_gain if soc_report else None,
            "soc_co2e": soc_report.soc_co2e if soc_report else None,
            "soc_credits": soc_report.soc_credits if soc_report else None,
            "is_informational_only": True,
            "note": "SOC credits are informational only — NOT mintable.",
        } if soc_report else None,
        "crop_cycle": {
            "id": cycle.id if cycle else None,
            "crop_type": cycle.crop_type if cycle else None,
            "season": cycle.season if cycle else None,
            "start_date": str(cycle.start_date) if cycle and cycle.start_date else None,
            "end_date": str(cycle.end_date) if cycle and cycle.end_date else None,
            "baseline_method": cycle.baseline_method if cycle else None,
            "reduction_practice": cycle.reduction_practice if cycle else None,
            "status": cycle.status if cycle else None,
        } if cycle else None,
        "evidence": [_serialise_evidence(e) for e in evidence],
        "verification_history": [
            _serialise_verification(vr, verifier_names.get(vr.verifier_id))
            for vr in verifications
        ],
        "blockchain_transactions": [_serialise_blockchain(tx) for tx in blockchain_txns],
        "token": _serialise_token(token),
    }


# ── GET /audit/farms/{farm_id}/full-report ────────────────────────────────────

@router.get("/farms/{farm_id}/full-report")
def farm_full_audit(
    farm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Full auditable JSON package for a farm.
    Includes: farm info, crop cycles, all carbon reports, SOC reports,
    evidence, verification history, blockchain transactions, tokens,
    payouts, and methodology notes.

    Hash values are truncated. No secrets are included.
    """
    farm = db.query(Farm).filter(Farm.id == farm_id, Farm.is_deleted == False).first()  # noqa: E712
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    _assert_farm_access(farm, current_user, db)

    cycles = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id)
        .order_by(CropCycle.start_date)
        .all()
    )
    reports = (
        db.query(CarbonReport)
        .filter(CarbonReport.farm_id == farm_id)
        .order_by(CarbonReport.created_at)
        .all()
    )

    # Payouts — linked to credit balances for this farm's farmer
    payouts = (
        db.query(Payout)
        .filter(Payout.farmer_id == farm.farmer_id)
        .order_by(Payout.initiated_at)
        .all()
    )

    # All evidence for the farm
    evidence = (
        db.query(EvidenceFile)
        .filter(EvidenceFile.farm_id == farm_id)
        .order_by(EvidenceFile.created_at)
        .all()
    )

    # All SOC reports for the farm's cycles
    cycle_ids = [c.id for c in cycles]
    soc_reports = (
        db.query(SOCReport)
        .filter(SOCReport.farm_id == farm_id)
        .all()
    ) if cycle_ids else []

    # Build per-report packages
    report_packages = [_build_report_package(r, db) for r in reports]

    fpo_profile = (
        db.query(FPOProfile).filter(FPOProfile.id == farm.fpo_id).first()
        if farm.fpo_id else None
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "farm": {
            "id": farm.id,
            "farm_name": farm.farm_name,
            "village": farm.village,
            "district": farm.district,
            "state": farm.state,
            "land_area_acres": farm.land_area_acres,
            "soil_type": farm.soil_type,
            "water_source": farm.water_source,
            "farm_status": farm.farm_status,
            "fpo_name": fpo_profile.organization_name if fpo_profile else None,
            "boundary_area_hectares": farm.boundary_area_hectares,
        },
        "crop_cycles": [
            {
                "id": c.id,
                "crop_type": c.crop_type,
                "season": c.season,
                "start_date": str(c.start_date) if c.start_date else None,
                "end_date": str(c.end_date) if c.end_date else None,
                "baseline_method": c.baseline_method,
                "reduction_practice": c.reduction_practice,
                "status": c.status,
            }
            for c in cycles
        ],
        "carbon_reports": report_packages,
        "soc_reports": [
            {
                "id": sr.id,
                "crop_cycle_id": sr.crop_cycle_id,
                "baseline_soc": sr.baseline_soc,
                "current_soc": sr.current_soc,
                "soc_gain": sr.soc_gain,
                "soc_co2e": sr.soc_co2e,
                "soc_credits": sr.soc_credits,
                "confidence_score": sr.confidence_score,
                "is_informational_only": True,
                "note": "SOC credits are informational only — NOT mintable.",
                "created_at": sr.created_at.isoformat() if sr.created_at else None,
            }
            for sr in soc_reports
        ],
        "evidence": [_serialise_evidence(e) for e in evidence],
        "payouts": [_serialise_payout(p) for p in payouts],
        "methodology": {
            "methane": _METHANE_METHODOLOGY,
            "soc": _SOC_METHODOLOGY,
        },
    }


# ── GET /audit/reports/{report_id}/package ────────────────────────────────────

@router.get("/reports/{report_id}/package")
def report_audit_package(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Report-level audit package: one carbon report + all related records.
    """
    report = db.query(CarbonReport).filter(CarbonReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carbon report not found")

    farm = db.query(Farm).filter(Farm.id == report.farm_id).first()
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    _assert_farm_access(farm, current_user, db)

    package = _build_report_package(report, db)
    package["generated_at"] = datetime.now(timezone.utc).isoformat()
    package["farm_id"] = farm.id
    package["farm_name"] = farm.farm_name
    package["methodology"] = {
        "methane": _METHANE_METHODOLOGY,
        "soc": _SOC_METHODOLOGY,
    }
    return package
