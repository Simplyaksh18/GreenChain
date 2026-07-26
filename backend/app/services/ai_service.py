"""
ai_service.py — Phase 18 AI Service Layer.

Gathers structured context from the DB (read-only), runs it through
the AI provider, and assembles the typed response schemas.

SAFETY INVARIANTS:
  * This module is READ-ONLY. It never writes to the DB.
  * It never changes report status, credit amounts, or approval state.
  * It never auto-approves or auto-rejects verifications.
  * All AI output is advisory only (accompanied by DISCLAIMER).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.schemas.ai_schema import (
    DISCLAIMER,
    AIInsight,
    FPOActionItem,
    FPOActionSummaryResponse,
    FarmerHelpResponse,
    MRVSummaryResponse,
    VerificationAssistResponse,
)
from app.services.ai_provider import get_ai_provider

logger = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────────────

def _completeness_pct(ctx: Dict[str, Any]) -> int:
    """Data completeness score (0–100) based on available MRV data points."""
    score = 0
    if ctx.get("has_carbon_report"):
        score += 25
    readings = ctx.get("sensor_reading_count", 0)
    if readings >= 14:
        score += 20
    elif readings > 0:
        score += 10
    if ctx.get("has_soc_estimate"):
        score += 15
    sat_count = ctx.get("satellite_count", 0)
    if sat_count >= 3:
        score += 15
    elif sat_count > 0:
        score += 8
    if ctx.get("drone_count", 0) > 0:
        score += 10
    evidence = ctx.get("evidence_count", 0)
    if evidence >= 3:
        score += 10
    elif evidence > 0:
        score += 5
    if ctx.get("verification_status"):
        score += 5
    return min(score, 100)


def _confidence_level(pct: int) -> str:
    if pct >= 70:
        return "HIGH"
    if pct >= 40:
        return "MEDIUM"
    return "LOW"


def _mrv_insights(ctx: Dict[str, Any]) -> List[AIInsight]:
    insights: List[AIInsight] = []
    readings      = ctx.get("sensor_reading_count", 0)
    credits       = ctx.get("estimated_credits", 0)
    has_report    = ctx.get("has_carbon_report", False)
    report_status = ctx.get("report_status", "")
    report_id     = ctx.get("latest_report_id")
    drone_count   = ctx.get("drone_count", 0)
    sat_count     = ctx.get("satellite_count", 0)
    evidence      = ctx.get("evidence_count", 0)
    soc_conf      = ctx.get("soc_confidence", 0.0)
    vr_status     = ctx.get("verification_status")
    is_minted     = ctx.get("is_minted", False)
    avg_ndvi      = ctx.get("avg_ndvi")

    if not has_report:
        insights.append(AIInsight(
            type="action",
            title="No carbon report yet",
            message=(
                "Generate a carbon report from your Farmer dashboard to calculate "
                "your emissions reduction and credit estimate."
            ),
        ))
        return insights   # no point adding more if no report

    # ── Report status insight ────────────────────────────────────────────────
    if report_status == "VERIFIED":
        insights.append(AIInsight(
            type="positive",
            title="Report Verified",
            message=(
                f"Carbon report #{report_id} has been verified. "
                f"Your {credits:.2f} credit(s) are confirmed."
                + (" Credits have been minted as tokens." if is_minted else " Ready for token minting.")
            ),
        ))
    elif report_status == "SUBMITTED":
        insights.append(AIInsight(
            type="info",
            title="Report Under Review",
            message=(
                f"Carbon report #{report_id} is submitted and awaiting verification. "
                "No action needed — verifier is reviewing."
            ),
        ))
    elif report_status == "REJECTED":
        insights.append(AIInsight(
            type="risk",
            title="Report Rejected",
            message=(
                f"Carbon report #{report_id} was rejected. "
                "Check verifier notes, upload missing evidence, and resubmit."
            ),
        ))
    elif credits == 0:
        insights.append(AIInsight(
            type="warning",
            title="Zero Credits Estimated",
            message=(
                "Carbon credits are currently zero. Emissions reduction may be below the "
                "1 tCO₂e threshold, or sensor/SOC data is incomplete. "
                "Improve data coverage before generating the next report."
            ),
        ))
    elif credits > 0:
        insights.append(AIInsight(
            type="positive",
            title="Credits Estimated",
            message=f"This report estimates {credits:.2f} carbon credit(s). Submit for verification to confirm.",
        ))

    # ── Verification ────────────────────────────────────────────────────────
    if vr_status and report_status not in ("VERIFIED",):
        insights.append(AIInsight(
            type="info",
            title="Verification Request",
            message=f"Verification request is {vr_status.lower().replace('_', ' ')}.",
        ))

    # ── Sensor coverage ─────────────────────────────────────────────────────
    if readings == 0:
        insights.append(AIInsight(
            type="risk",
            title="No Sensor Data",
            message=(
                "No sensor readings found for this farm. "
                "Without sensor data MRV cannot be independently verified."
            ),
        ))
    elif readings < 14:
        insights.append(AIInsight(
            type="warning",
            title="Incomplete Sensor Coverage",
            message=(
                f"Only {readings} sensor reading(s) recorded. "
                "At least 14 readings are recommended to cover a full crop cycle."
            ),
        ))
    else:
        insights.append(AIInsight(
            type="positive",
            title="Good Sensor Coverage",
            message=f"{readings} sensor reading(s) recorded — sufficient for MRV verification.",
        ))

    # ── Satellite / drone ────────────────────────────────────────────────────
    if sat_count == 0:
        insights.append(AIInsight(
            type="warning",
            title="No Satellite Data",
            message=(
                "No satellite observations found. "
                "Ensure your farm boundary is drawn to enable automatic satellite data collection."
            ),
        ))
    else:
        ndvi_note = f" Average NDVI: {avg_ndvi:.2f}." if avg_ndvi is not None else ""
        insights.append(AIInsight(
            type="positive",
            title="Satellite Data Available",
            message=f"{sat_count} satellite observation(s) recorded.{ndvi_note}",
        ))

    if drone_count > 0:
        insights.append(AIInsight(
            type="positive",
            title="Drone Data Present",
            message=f"{drone_count} drone observation(s) recorded — improves verification confidence.",
        ))

    # ── SOC ──────────────────────────────────────────────────────────────────
    if not ctx.get("has_soc_estimate"):
        insights.append(AIInsight(
            type="action",
            title="SOC Data Missing",
            message=(
                "No Soil Organic Carbon estimate found. "
                "Contact your FPO to request an SOC measurement."
            ),
        ))
    elif soc_conf < 0.5:
        insights.append(AIInsight(
            type="warning",
            title="Low SOC Confidence",
            message=(
                f"SOC confidence is {soc_conf * 100:.0f}% — based on estimates only. "
                "Add a lab or manual soil test to improve accuracy."
            ),
        ))

    # ── Evidence ─────────────────────────────────────────────────────────────
    if evidence == 0:
        insights.append(AIInsight(
            type="risk",
            title="No Evidence Files",
            message=(
                "No evidence files attached to this report. "
                "Upload photos, invoices, or field notes to support verification."
            ),
        ))
    elif evidence < 3:
        insights.append(AIInsight(
            type="warning",
            title="Minimal Evidence",
            message=(
                f"Only {evidence} evidence file(s) uploaded. "
                "3+ files (photos, invoices, field notes) are recommended."
            ),
        ))

    return insights


def _next_best_action(ctx: Dict[str, Any]) -> str:
    """Return a single prioritised next action for the farmer."""
    if not ctx.get("has_carbon_report"):
        return "Generate a carbon report after adding MRV data."
    if ctx.get("report_status") == "REJECTED":
        return "Review the verifier's notes, fix the issues, and resubmit your carbon report."
    if ctx.get("evidence_count", 0) == 0:
        return "Upload at least 3 evidence files (photos, invoices, field notes) for this report."
    if ctx.get("sensor_reading_count", 0) < 14:
        return "Ensure your FPO's sensors are recording regularly — aim for 14+ readings per crop cycle."
    if not ctx.get("has_soc_estimate"):
        return "Request an SOC measurement from your FPO to strengthen your credit calculation."
    if ctx.get("satellite_count", 0) == 0:
        return "Draw your farm boundary in the app so satellite observations can be collected automatically."
    if ctx.get("report_status") in ("DRAFT", "") and ctx.get("estimated_credits", 0) > 0:
        return "Submit your carbon report for verification to confirm your credits."
    if ctx.get("report_status") == "VERIFIED" and not ctx.get("is_minted"):
        return "Your report is verified — ask your FPO to mint your carbon credits."
    return "Your MRV data looks complete. Keep sensor coverage consistent through the next crop cycle."


def _verification_risk(ctx: Dict[str, Any]) -> str:
    ev   = ctx.get("evidence_file_count", 0)
    read = ctx.get("sensor_reading_count", 0)
    approved = ctx.get("farm_approved", False)

    score = 0
    if ev == 0:
        score += 3
    elif ev < 3:
        score += 1
    if read < 14:
        score += 1
    if not approved:
        score += 2

    if score >= 4:
        return "HIGH"
    if score >= 2:
        return "MEDIUM"
    return "LOW"


def _verification_checklist(ctx: Dict[str, Any]) -> List[str]:
    checklist = [
        "Verify farm boundary matches satellite imagery",
        "Confirm at least 3 evidence files are present",
        "Check sensor readings cover the full crop cycle",
        f"Review carbon report status: {ctx.get('report_status', 'unknown')}",
        "Confirm farmer identity matches registration records",
    ]
    if not ctx.get("farm_approved"):
        checklist.append("Farm has not been formally approved — verify approval status")
    if ctx.get("evidence_file_count", 0) == 0:
        checklist.append("URGENT: Request evidence files before proceeding")
    return checklist


def _fraud_flags(ctx: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    if ctx.get("evidence_file_count", 0) == 0:
        flags.append("No evidence files submitted")
    if ctx.get("sensor_reading_count", 0) == 0:
        flags.append("No sensor readings — data may be fabricated")
    if not ctx.get("farm_approved"):
        flags.append("Farm approval status is pending or rejected")
    return flags


def _suggested_questions(ctx: Dict[str, Any]) -> List[str]:
    qs = [
        "Can the farmer demonstrate the sensor installation on their field?",
        "Are the evidence photos geo-tagged and dated within the report period?",
        "Does the farm acreage match the boundary drawn on the map?",
    ]
    if ctx.get("estimated_credits", 0) > 100:
        qs.append("Credit estimate is high — request independent measurement or site visit.")
    return qs


def _recommendation(risk: str, ctx: Dict[str, Any]) -> tuple[str, str]:
    if risk == "HIGH":
        return "REJECT", (
            "Risk level is HIGH. Critical data is missing. "
            "Do not approve until evidence and sensor data are provided. "
            "Human review required."
        )
    if risk == "MEDIUM":
        return "REVIEW", (
            "Risk level is MEDIUM. Some data gaps exist. "
            "Recommend field follow-up before approving. "
            "Human judgment required."
        )
    return "APPROVE", (
        "Risk level is LOW. Data appears complete and consistent. "
        "Final approval decision rests with the human verifier."
    )


# ── Public service functions ────────────────────────────────────────────────────

def get_mrv_summary(farm_id: int, db: Session) -> MRVSummaryResponse:
    """
    Assemble MRV context for a farm and generate an AI summary.
    Read-only. Does not alter any record.
    """
    from sqlalchemy import func as sqla_func
    from app.models.farm import Farm
    from app.models.carbon_report import CarbonReport
    from app.models.sensor import SensorReading
    from app.models.soc import SOCReport
    from app.models.satellite_observation import SatelliteObservation
    from app.models.drone_observation import DroneObservation
    from app.models.evidence import EvidenceFile

    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if farm is None:
        raise ValueError(f"Farm {farm_id} not found")

    # ── Latest carbon report ─────────────────────────────────────────────────
    report = (
        db.query(CarbonReport)
        .filter(CarbonReport.farm_id == farm_id)
        .order_by(CarbonReport.created_at.desc())
        .first()
    )

    # ── Sensor readings ──────────────────────────────────────────────────────
    reading_count = db.query(SensorReading).filter(SensorReading.farm_id == farm_id).count()

    # ── SOC report ───────────────────────────────────────────────────────────
    soc = (
        db.query(SOCReport)
        .filter(SOCReport.farm_id == farm_id)
        .order_by(SOCReport.id.desc())
        .first()
    )

    # ── Satellite observations ───────────────────────────────────────────────
    sat_count = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.farm_id == farm_id)
        .count()
    )
    avg_ndvi: Optional[float] = None
    if sat_count > 0:
        avg_ndvi = db.query(
            sqla_func.avg(SatelliteObservation.ndvi)
        ).filter(SatelliteObservation.farm_id == farm_id).scalar()

    # ── Drone observations ───────────────────────────────────────────────────
    drone_count = (
        db.query(DroneObservation)
        .filter(DroneObservation.farm_id == farm_id)
        .count()
    )

    # ── Evidence files (for latest report) ───────────────────────────────────
    evidence_count = 0
    if report:
        evidence_count = (
            db.query(EvidenceFile)
            .filter(EvidenceFile.carbon_report_id == report.id)
            .count()
        )

    # ── Token minted? ────────────────────────────────────────────────────────
    is_minted = False
    if report:
        try:
            from app.models.carbon_token import CarbonToken
            is_minted = (
                db.query(CarbonToken)
                .filter(CarbonToken.carbon_report_id == report.id)
                .first()
            ) is not None
        except Exception:
            pass

    # ── Verification request ─────────────────────────────────────────────────
    verification_status: Optional[str] = None
    if report:
        try:
            from app.models.verification import VerificationRequest
            vr = (
                db.query(VerificationRequest)
                .filter(VerificationRequest.carbon_report_id == report.id)
                .order_by(VerificationRequest.id.desc())
                .first()
            )
            if vr:
                verification_status = str(vr.status)
        except Exception:
            pass

    # ── Build context dict ───────────────────────────────────────────────────
    report_status_str = str(report.status) if report else ""

    ctx: Dict[str, Any] = {
        "_operation": "mrv_summary",
        "farm_name": farm.farm_name,
        "has_carbon_report": report is not None,
        "latest_report_id": report.id if report else None,
        "report_status": report_status_str,
        "estimated_credits": (report.estimated_credits or 0) if report else 0,
        "sensor_reading_count": reading_count,
        "has_soc_estimate": soc is not None,
        "soc_confidence": float(soc.confidence_score) if soc and soc.confidence_score is not None else 0.0,
        "has_satellite_obs": sat_count > 0,
        "satellite_count": sat_count,
        "avg_ndvi": round(float(avg_ndvi), 3) if avg_ndvi is not None else None,
        "drone_count": drone_count,
        "evidence_count": evidence_count,
        "is_minted": is_minted,
        "verification_status": verification_status,
    }

    provider = get_ai_provider()
    summary  = provider.generate("Summarise the MRV status of this farm.", ctx)
    insights = _mrv_insights(ctx)
    pct      = _completeness_pct(ctx)
    level    = _confidence_level(pct)
    label    = {"HIGH": "High", "MEDIUM": "Medium", "LOW": "Low"}[level]
    nba      = _next_best_action(ctx)

    return MRVSummaryResponse(
        farm_id=farm_id,
        farm_name=farm.farm_name,
        has_carbon_report=report is not None,
        latest_report_id=report.id if report else None,
        report_status=report_status_str or None,
        summary=summary,
        insights=insights,
        data_completeness=pct,
        data_completeness_pct=pct,
        confidence_label=label,
        confidence_level=level,
        next_best_action=nba,
        ai_mode=provider.mode_name,
        disclaimer=DISCLAIMER,
    )


def get_verification_assist(verification_request_id: int, db: Session) -> VerificationAssistResponse:
    """
    Analyse a verification request and provide risk assessment.
    Read-only. Does not alter approval status.
    """
    from app.models.verification import VerificationRequest
    from app.models.carbon_report import CarbonReport
    from app.models.evidence import EvidenceFile
    from app.models.sensor import SensorReading
    from app.models.farm import Farm

    vr = db.query(VerificationRequest).filter(
        VerificationRequest.id == verification_request_id
    ).first()
    if vr is None:
        raise ValueError(f"VerificationRequest {verification_request_id} not found")

    report = db.query(CarbonReport).filter(CarbonReport.id == vr.carbon_report_id).first()
    farm   = db.query(Farm).filter(Farm.id == report.farm_id).first() if report else None
    ev_count = (
        db.query(EvidenceFile)
        .filter(EvidenceFile.carbon_report_id == vr.carbon_report_id)
        .count()
    ) if report else 0
    reading_count = (
        db.query(SensorReading)
        .filter(SensorReading.farm_id == report.farm_id)
        .count()
    ) if report else 0

    ctx: Dict[str, Any] = {
        "_operation": "verification_assist",
        "farm_name": farm.farm_name if farm else "unknown",
        "farm_approved": farm.is_approved if farm else False,
        "report_status": report.status if report else "unknown",
        "estimated_credits": (report.estimated_credits or 0) if report else 0,
        "evidence_file_count": ev_count,
        "sensor_reading_count": reading_count,
        "risk_level": "",  # filled in below
    }

    risk = _verification_risk(ctx)
    ctx["risk_level"] = risk

    provider     = get_ai_provider()
    explanation  = provider.generate("Explain the verification risk for this report.", ctx)
    checklist    = _verification_checklist(ctx)
    flags        = _fraud_flags(ctx)
    questions    = _suggested_questions(ctx)
    rec, rec_note = _recommendation(risk, ctx)

    return VerificationAssistResponse(
        verification_request_id=verification_request_id,
        risk_level=risk,
        risk_explanation=explanation,
        evidence_checklist=checklist,
        fraud_flags=flags,
        suggested_questions=questions,
        recommendation=rec,
        recommendation_note=rec_note,
        ai_mode=provider.mode_name,
        disclaimer=DISCLAIMER,
    )


def get_fpo_action_summary(fpo_id: int, db: Session) -> FPOActionSummaryResponse:
    """
    Gather FPO-level operational metrics and surface action items.
    Read-only.
    """
    from app.models.farm import Farm
    from app.models.carbon_report import CarbonReport
    from app.models.payout import Payout
    from app.models.marketplace import MarketplaceListing, ListingStatus
    from app.models.evidence import EvidenceFile

    # pending farm approvals
    pending_farms = (
        db.query(Farm)
        .filter(Farm.fpo_id == fpo_id, Farm.is_approved.is_(False))
        .count()
    )

    # reports that have credits but no token minted
    mintable = 0
    try:
        from app.models.carbon_token import CarbonToken
        reports_with_credits = (
            db.query(CarbonReport)
            .join(Farm, Farm.id == CarbonReport.farm_id)
            .filter(Farm.fpo_id == fpo_id, CarbonReport.methane_credits > 0)
            .all()
        )
        minted_report_ids = {
            t.carbon_report_id
            for t in db.query(CarbonToken).filter(
                CarbonToken.carbon_report_id.in_(
                    [r.id for r in reports_with_credits]
                )
            ).all()
        }
        mintable = sum(
            1 for r in reports_with_credits
            if r.id not in minted_report_ids
        )
    except Exception:
        pass

    # initiated payouts (pending)
    initiated_payouts = 0
    try:
        from app.models.payout import PayoutStatus
        initiated_payouts = (
            db.query(Payout)
            .filter(Payout.fpo_id == fpo_id, Payout.status == PayoutStatus.INITIATED)
            .count()
        )
    except Exception:
        pass

    # active marketplace listings
    active_listings = 0
    try:
        active_listings = (
            db.query(MarketplaceListing)
            .filter(
                MarketplaceListing.fpo_id == fpo_id,
                MarketplaceListing.listing_status == ListingStatus.ACTIVE,
            )
            .count()
        )
    except Exception:
        pass

    # farms missing evidence files
    evidence_gaps = 0
    try:
        all_reports = (
            db.query(CarbonReport)
            .join(Farm, Farm.id == CarbonReport.farm_id)
            .filter(Farm.fpo_id == fpo_id)
            .all()
        )
        for rep in all_reports:
            ev = db.query(EvidenceFile).filter(EvidenceFile.carbon_report_id == rep.id).count()
            if ev == 0:
                evidence_gaps += 1
    except Exception:
        pass

    ctx: Dict[str, Any] = {
        "_operation": "fpo_action_summary",
        "pending_farm_approvals": pending_farms,
        "mintable_report_count": mintable,
        "initiated_payout_count": initiated_payouts,
        "active_listing_count": active_listings,
        "evidence_gap_count": evidence_gaps,
    }

    provider = get_ai_provider()
    summary  = provider.generate("Summarise action items for this FPO.", ctx)

    action_items: List[FPOActionItem] = []
    if pending_farms:
        action_items.append(FPOActionItem(
            category="Farm Approvals",
            count=pending_farms,
            message=f"{pending_farms} farm(s) are waiting for your approval.",
            action="Go to Farmers → Approve Farms",
        ))
    if mintable:
        action_items.append(FPOActionItem(
            category="Token Minting",
            count=mintable,
            message=f"{mintable} carbon report(s) have credits ready to mint.",
            action="Go to Mint Credits",
        ))
    if initiated_payouts:
        action_items.append(FPOActionItem(
            category="Payouts",
            count=initiated_payouts,
            message=f"{initiated_payouts} payout(s) are awaiting payment.",
            action="Go to Payouts",
        ))
    if evidence_gaps:
        action_items.append(FPOActionItem(
            category="Evidence Gaps",
            count=evidence_gaps,
            message=f"{evidence_gaps} report(s) have no evidence files uploaded.",
            action="Remind farmers to upload evidence",
        ))

    return FPOActionSummaryResponse(
        action_items=action_items,
        summary=summary,
        ai_mode=provider.mode_name,
        disclaimer=DISCLAIMER,
    )


def get_farmer_help(
    topic: str,
    db: Session,
    farm_id: Optional[int] = None,
    report_id: Optional[int] = None,
) -> FarmerHelpResponse:
    """
    Return plain-language help for a farmer on a given topic.
    Read-only.
    """
    ctx: Dict[str, Any] = {
        "_operation": "farmer_help",
        "topic": topic,
        "estimated_credits": 0,
        "sensor_reading_count": 0,
    }

    if farm_id:
        try:
            from app.models.sensor import SensorReading
            from app.models.carbon_report import CarbonReport

            ctx["sensor_reading_count"] = (
                db.query(SensorReading)
                .filter(SensorReading.farm_id == farm_id)
                .count()
            )
            latest_report = (
                db.query(CarbonReport)
                .filter(CarbonReport.farm_id == farm_id)
                .order_by(CarbonReport.created_at.desc())
                .first()
            )
            if latest_report:
                ctx["estimated_credits"] = latest_report.estimated_credits or 0
        except Exception as exc:
            logger.warning("farmer_help: could not load farm context: %s", exc)

    provider    = get_ai_provider()
    explanation = provider.generate(f"Explain '{topic}' to a smallholder farmer.", ctx)

    insights: List[AIInsight] = []
    if topic == "why_zero_credits" and ctx.get("estimated_credits", 0) == 0:
        insights.append(AIInsight(
            type="action",
            message="Contact your FPO to check sensor connectivity and report generation.",
        ))
    elif topic == "missing_data":
        insights.append(AIInsight(
            type="action",
            message="Upload photos, invoices, or field notes as evidence in the Evidence section.",
        ))
    elif topic == "improve_mrv":
        insights.append(AIInsight(
            type="info",
            message="Low-emission practices are verified over multiple crop cycles — consistency matters.",
        ))

    return FarmerHelpResponse(
        topic=topic,
        explanation=explanation,
        insights=insights,
        ai_mode=provider.mode_name,
        disclaimer=DISCLAIMER,
    )
