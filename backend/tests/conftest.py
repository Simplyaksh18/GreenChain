"""
Shared fixtures for the GreenChain test suite (Phase 1–5).
Uses SQLite (StaticPool) — no PostgreSQL required.
"""
import os
os.environ["ENV_FILE"] = ".env.test"
os.environ["DATABASE_URL"] = "sqlite:///./test_greenchain.db"

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.models.farm import Farm, CropCycle
from app.models.sensor import SensorReading, SensorSourceType
from app.models.evidence import EvidenceFile
from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.verification import VerificationRequest, VerificationStatus, RiskLevel, Recommendation
from app.models.blockchain_transaction import BlockchainTransaction
from app.models.carbon_token import CarbonToken, TokenStatus
from app.models.satellite_observation import SatelliteObservation
from app.models.drone_observation import DroneObservation
from app.models.farmer_profile import FarmerProfile
from app.models.farmer_credit_balance import FarmerCreditBalance
from app.models.payout import Payout
from app.models.soc import SOCMeasurement, SOCReport
from app.models.marketplace import RetirementCertificate, MarketplaceOrder, MarketplaceListing
from app.models.razorpay_payment import RazorpayPayment
from app.security import hash_password

# ── Engine ────────────────────────────────────────────────────────────────────
SQLITE_URL = "sqlite:///./test_greenchain.db"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


# ── Table management ──────────────────────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def reset_blockchain_provider():
    """Reset the blockchain provider singleton between tests (Phase 6)."""
    from app.services.blockchain_provider import reset_provider
    reset_provider()
    yield
    reset_provider()


@pytest.fixture(autouse=True)
def clean_tables():
    """Wipe all rows between tests — FK-safe deletion order."""
    yield
    db = TestingSessionLocal()
    try:
        # Phase 12.5 SOC tables first (FK order)
        db.query(SOCReport).delete()
        db.query(SOCMeasurement).delete()
        # Phase 17 — Razorpay payments (before payouts; no FK but references payout ids)
        db.query(RazorpayPayment).delete()
        # Phase 16 tables first (FK → marketplace orders/listings → credit balances)
        db.query(RetirementCertificate).delete()
        db.query(MarketplaceOrder).delete()
        db.query(MarketplaceListing).delete()
        # Phase 9 tables first (FK order)
        db.query(Payout).delete()
        db.query(FarmerCreditBalance).delete()
        db.query(FarmerProfile).delete()
        # Phase 5–8 tables
        db.query(CarbonToken).delete()
        db.query(BlockchainTransaction).delete()
        db.query(SatelliteObservation).delete()
        db.query(DroneObservation).delete()
        db.query(VerificationRequest).delete()
        # EvidenceFile has FK → carbon_reports; must be deleted before CarbonReport
        db.query(EvidenceFile).delete()
        db.query(CarbonReport).delete()
        db.query(SensorReading).delete()
        db.query(CropCycle).delete()
        db.query(Farm).delete()
        db.query(FPOProfile).delete()
        db.query(User).delete()
        db.commit()
    finally:
        db.close()


# ── Core fixtures ─────────────────────────────────────────────────────────────
@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


# ── User factory ──────────────────────────────────────────────────────────────
def _make_user(db, name, email, role, is_approved=True, is_active=True):
    user = User(
        name=name,
        email=email,
        password_hash=hash_password("password123"),
        role=role,
        is_active=is_active,
        is_approved=is_approved,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def farmer_user(db):
    return _make_user(db, "Alice Farmer", "farmer@test.com", UserRole.FARMER)


@pytest.fixture
def farmer2_user(db):
    return _make_user(db, "Bob Farmer2", "farmer2@test.com", UserRole.FARMER)


@pytest.fixture
def fpo_user(db):
    return _make_user(db, "Carol FPO", "fpo@test.com", UserRole.FPO, is_approved=True)


@pytest.fixture
def fpo2_user(db):
    return _make_user(db, "Dave FPO2", "fpo2@test.com", UserRole.FPO, is_approved=True)


@pytest.fixture
def verifier_user(db):
    return _make_user(db, "Eve Verify", "verifier@test.com", UserRole.VERIFIER, is_approved=True)


@pytest.fixture
def admin_user(db):
    return _make_user(db, "Frank Admin", "admin@test.com", UserRole.ADMIN, is_approved=True)


@pytest.fixture
def inactive_user(db):
    return _make_user(db, "Inactive", "inactive@test.com", UserRole.FARMER, is_active=False)


# ── FPO profile factory ───────────────────────────────────────────────────────
def _make_fpo_profile(db, user, org="GreenFPO", reg="REG001", district="Pune", state="MH"):
    profile = FPOProfile(
        user_id=user.id,
        organization_name=org,
        registration_number=reg,
        district=district,
        state=state,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@pytest.fixture
def fpo_profile(db, fpo_user):
    return _make_fpo_profile(db, fpo_user)


@pytest.fixture
def fpo2_profile(db, fpo2_user):
    return _make_fpo_profile(db, fpo2_user, org="BlueFPO", reg="REG002")


# ── Farm factory ──────────────────────────────────────────────────────────────
FARM_DEFAULTS = dict(
    farm_name="Test Farm",
    land_area_acres=5.0,
    latitude=18.5,
    longitude=73.8,
    village="Vadgaon",
    district="Pune",
    state="Maharashtra",
    soil_type="Clay",
    water_source="River",
)


def _make_farm(db, farmer, fpo_profile=None, approved=False, **overrides):
    from app.models.farm import FarmStatus
    data = {**FARM_DEFAULTS, **overrides}
    farm = Farm(
        farmer_id=farmer.id,
        fpo_id=fpo_profile.id if fpo_profile else None,
        is_approved=approved,
        farm_status=FarmStatus.APPROVED if approved else FarmStatus.DRAFT,
        **data,
    )
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm


@pytest.fixture
def farm(db, farmer_user, fpo_profile):
    """Default test farm — approved so verification tests work end-to-end."""
    return _make_farm(db, farmer_user, fpo_profile=fpo_profile, approved=True)


@pytest.fixture
def unapproved_farm(db, farmer_user):
    """Explicitly unapproved farm for testing approval-gate scenarios."""
    return _make_farm(db, farmer_user, approved=False, farm_name="Unapproved Farm")


@pytest.fixture
def approved_farm(db, farmer_user, fpo_profile):
    return _make_farm(db, farmer_user, fpo_profile=fpo_profile, approved=True, farm_name="Approved Farm")


@pytest.fixture
def farm_with_fpo(db, farmer_user, fpo_profile):
    return _make_farm(db, farmer_user, fpo_profile=fpo_profile, farm_name="FPO Farm")


@pytest.fixture
def farm2(db, farmer2_user):
    return _make_farm(db, farmer2_user, farm_name="Farmer2 Farm")


# ── CropCycle factory ─────────────────────────────────────────────────────────
def _make_cycle(db, farm, crop_type="Paddy"):
    from datetime import date
    cycle = CropCycle(
        farm_id=farm.id,
        crop_type=crop_type,
        season="Kharif",
        start_date=date(2024, 6, 1),
        baseline_method="AWD",
        reduction_practice="SRI",
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


@pytest.fixture
def crop_cycle(db, farm):
    return _make_cycle(db, farm)


@pytest.fixture
def crop_cycle2(db, farm2):
    return _make_cycle(db, farm2)


# ── SensorReading factory ─────────────────────────────────────────────────────
def _make_readings(db, farm, cycle, count=14, high_quality=True):
    """Create `count` synthetic readings, spread daily from 2024-06-01."""
    from app.services.emission_estimator import estimate_methane
    base_dt = datetime(2024, 6, 1, 6, 0, 0, tzinfo=timezone.utc)
    readings = []
    for i in range(count):
        sm  = 60.0 + (i % 5)          # soil_moisture  60–64
        wd  = 5.0  + (i % 3) * 0.5   # water_depth    5–6
        tc  = 30.0 + (i % 4)          # temperature   30–33
        hm  = 70.0
        rf  = 5.0 if i % 3 == 0 else 0.0
        dq  = 85.0 if high_quality else 55.0
        est = estimate_methane(sm, wd, tc, "Paddy").estimated_methane
        r = SensorReading(
            farm_id=farm.id,
            crop_cycle_id=cycle.id,
            reading_time=base_dt + timedelta(days=i),
            soil_moisture=sm,
            water_depth_cm=wd,
            temperature_c=tc,
            humidity=hm,
            rainfall_mm=rf,
            estimated_methane=est,
            data_quality_score=dq,
            source_type=SensorSourceType.SIMULATED,
        )
        readings.append(r)
    db.bulk_save_objects(readings)
    db.commit()
    return db.query(SensorReading).filter(SensorReading.crop_cycle_id == cycle.id).all()


@pytest.fixture
def sensor_readings(db, farm, crop_cycle):
    return _make_readings(db, farm, crop_cycle, count=14)


@pytest.fixture
def sensor_readings_7(db, farm, crop_cycle):
    return _make_readings(db, farm, crop_cycle, count=7)


@pytest.fixture
def sensor_readings_low_quality(db, farm, crop_cycle):
    return _make_readings(db, farm, crop_cycle, count=14, high_quality=False)


# ── CarbonReport factory ──────────────────────────────────────────────────────
def _make_carbon_report(db, farm, cycle, status=ReportStatus.DRAFT):
    from app.services.carbon_calculator import calculate_carbon_report
    from app.models.sensor import SensorReading
    readings = db.query(SensorReading).filter(SensorReading.crop_cycle_id == cycle.id).all()
    if len(readings) < 7:
        raise ValueError("Need at least 7 readings to create report fixture")
    calc = calculate_carbon_report(readings, farm.id, cycle.id)
    report = CarbonReport(
        farm_id=farm.id,
        crop_cycle_id=cycle.id,
        baseline_methane_kg=calc.baseline_methane_kg,
        current_methane_kg=calc.current_methane_kg,
        methane_reduction_kg=calc.methane_reduction_kg,
        co2e_reduction_tonnes=calc.co2e_reduction_tonnes,
        estimated_credits=calc.estimated_credits,
        report_hash=calc.report_hash,
        status=status,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@pytest.fixture
def carbon_report_draft(db, farm, crop_cycle, sensor_readings):
    return _make_carbon_report(db, farm, crop_cycle, status=ReportStatus.DRAFT)


@pytest.fixture
def carbon_report_submitted(db, farm, crop_cycle, sensor_readings):
    report = _make_carbon_report(db, farm, crop_cycle, status=ReportStatus.SUBMITTED)
    # also create the VR
    vr = VerificationRequest(
        carbon_report_id=report.id,
        status=VerificationStatus.PENDING,
        risk_score=30.0,
        risk_level=RiskLevel.LOW,
        recommendation=Recommendation.APPROVE,
    )
    db.add(vr)
    db.commit()
    return report


# ── Token helper ──────────────────────────────────────────────────────────────
def _login(client, email, password="password123"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def farmer_token(client, farmer_user):
    return _login(client, farmer_user.email)


@pytest.fixture
def farmer2_token(client, farmer2_user):
    return _login(client, farmer2_user.email)


# ── Buyer fixture (Phase 22B) ─────────────────────────────────────────────────
# The marketplace now blocks self-purchase (a farm's own farmer or the seller
# FPO's user account cannot buy from their own listing). Marketplace tests
# should use this unrelated authenticated user as the buyer instead of
# reusing farmer_user.
@pytest.fixture
def buyer_user(db):
    return _make_user(db, "Bea Buyer", "buyer@test.com", UserRole.FARMER)


@pytest.fixture
def buyer_token(client, buyer_user):
    return _login(client, buyer_user.email)


@pytest.fixture
def fpo_token(client, fpo_user):
    return _login(client, fpo_user.email)


@pytest.fixture
def fpo2_token(client, fpo2_user):
    return _login(client, fpo2_user.email)


@pytest.fixture
def verifier_token(client, verifier_user):
    return _login(client, verifier_user.email)


@pytest.fixture
def admin_token(client, admin_user):
    return _login(client, admin_user.email)


# ── Phase 5: verified report + minted token fixtures ─────────────────────────

def _make_verified_report(db, farm, cycle):
    """Create a VERIFIED carbon report with a linked VerificationRequest."""
    from app.services.carbon_calculator import calculate_carbon_report
    readings = db.query(SensorReading).filter(SensorReading.crop_cycle_id == cycle.id).all()
    if len(readings) < 7:
        raise ValueError("Need at least 7 readings for verified report fixture")
    calc = calculate_carbon_report(readings, farm.id, cycle.id)
    report = CarbonReport(
        farm_id=farm.id,
        crop_cycle_id=cycle.id,
        baseline_methane_kg=calc.baseline_methane_kg,
        current_methane_kg=calc.current_methane_kg,
        methane_reduction_kg=calc.methane_reduction_kg,
        co2e_reduction_tonnes=calc.co2e_reduction_tonnes,
        estimated_credits=calc.estimated_credits,
        report_hash=calc.report_hash,
        status=ReportStatus.VERIFIED,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    vr = VerificationRequest(
        carbon_report_id=report.id,
        status=VerificationStatus.APPROVED,
        risk_score=10.0,
        risk_level=RiskLevel.LOW,
        recommendation=Recommendation.APPROVE,
    )
    db.add(vr)
    db.commit()
    return report


@pytest.fixture
def verified_report(db, farm, crop_cycle, sensor_readings):
    return _make_verified_report(db, farm, crop_cycle)


@pytest.fixture
def minted_token(db, verified_report, farmer_user):
    """Create a MINTED CarbonToken for the verified_report."""
    from app.services.token_service import mint_carbon_token
    return mint_carbon_token(verified_report, farmer_user.id, db)


@pytest.fixture
def zero_credit_verified_report(db, farm, crop_cycle, sensor_readings):
    """A VERIFIED report whose estimated_credits is forced to 0."""
    report = _make_verified_report(db, farm, crop_cycle)
    report.estimated_credits = 0
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


# ── Phase 7: Satellite / Drone observation factories ──────────────────────────

def _make_satellite_observations(db, farm, crop_cycle=None, count=5):
    """Create `count` synthetic satellite observations."""
    from datetime import date, timedelta
    from app.models.satellite_observation import (
        SatelliteObservation, SatelliteSource, VegetationHealth, FloodRisk,
    )
    base_date = date(2024, 6, 1)
    obs_list = []
    for i in range(count):
        ndvi = 0.45 + (i % 3) * 0.08
        ndwi = 0.20 + (i % 4) * 0.05
        obs = SatelliteObservation(
            farm_id=farm.id,
            crop_cycle_id=crop_cycle.id if crop_cycle else None,
            observation_date=base_date + timedelta(days=i * 5),
            ndvi=round(ndvi, 4),
            ndwi=round(ndwi, 4),
            vegetation_health=VegetationHealth.GOOD,
            flood_risk=FloodRisk.NONE,
            cloud_cover_percent=10.0,
            source=SatelliteSource.SATELLITE_SIMULATED,
        )
        obs_list.append(obs)
    db.bulk_save_objects(obs_list)
    db.commit()
    return (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.farm_id == farm.id)
        .all()
    )


def _make_drone_observations(db, farm, crop_cycle=None, count=3):
    """Create `count` synthetic drone observations."""
    from datetime import date, timedelta
    from app.models.drone_observation import DroneObservation
    base_date = date(2024, 6, 1)
    obs_list = []
    for i in range(count):
        obs = DroneObservation(
            farm_id=farm.id,
            crop_cycle_id=crop_cycle.id if crop_cycle else None,
            observation_date=base_date + timedelta(days=i * 7),
            vegetation_cover_percent=70.0 + i,
            standing_water_percent=15.0,
            anomaly_score=10.0,
            image_reference=f"drone_farm{farm.id}_obs{i+1}.jpg",
        )
        obs_list.append(obs)
    db.bulk_save_objects(obs_list)
    db.commit()
    return (
        db.query(DroneObservation)
        .filter(DroneObservation.farm_id == farm.id)
        .all()
    )


@pytest.fixture
def satellite_observations(db, farm, crop_cycle):
    return _make_satellite_observations(db, farm, crop_cycle, count=5)


@pytest.fixture
def drone_observations(db, farm, crop_cycle):
    return _make_drone_observations(db, farm, crop_cycle, count=3)
