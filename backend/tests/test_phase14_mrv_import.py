"""
Phase 14 — MRV Import Tests

Tests cover:
  1.  Sensor CSV valid import (Phase 14 schema: date column)
  2.  Sensor CSV invalid rows reported correctly
  3.  Sensor CSV duplicate rows skipped
  4.  Satellite CSV import (Phase 14 schema)
  5.  Satellite CSV source=SENTINEL_2 classified correctly
  6.  Drone CSV import (Phase 14 schema)
  7.  Farm boundary GeoJSON import — updates boundary columns
  8.  Satellite GeoJSON import — inserts observations
  9.  FPO can import for linked farm
  10. FPO cannot import for unlinked farm
  11. Verifier cannot import
  12. Import creates SENSOR_EXPORT evidence hash record
  13. Imported satellite source is NOT simulated (SATELLITE_IMPORTED / SENTINEL_2)
  14. Imported sensor readings are present for carbon report generation
  15. Evidence multipart upload creates binary hash
  16. Evidence multipart upload blocked for verifier
"""
from __future__ import annotations

import io
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    _make_farm, _make_cycle, _make_user,
    _make_fpo_profile, TestingSessionLocal,
)
from app.models.user import UserRole
from app.models.evidence import EvidenceFile
from app.models.sensor import SensorReading, SensorSourceType
from app.models.satellite_observation import SatelliteObservation, SatelliteSource
from app.models.drone_observation import DroneObservation, DroneSource


# ── Helpers ───────────────────────────────────────────────────────────────────

def _auth(client, email, password="password123"):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _sensor_csv_v2(rows=None):
    """Phase 14 sensor CSV (uses 'date' column)."""
    lines = ["date,temperature_c,soil_moisture,water_depth_cm,humidity,rainfall_mm"]
    if rows is None:
        rows = [
            ("2025-06-01", 31.2, 42.5, 8.0, 70, 2.4),
            ("2025-06-02", 30.0, 44.0, 7.5, 68, 0.0),
        ]
    for r in rows:
        lines.append(",".join(str(v) for v in r))
    return "\n".join(lines).encode()


def _satellite_csv_v2(rows=None):
    """Phase 14 satellite CSV (uses 'date' column, no veg_health/flood_risk required)."""
    lines = ["date,ndvi,ndwi,cloud_cover_percent,source"]
    if rows is None:
        rows = [
            ("2025-06-01", 0.62, 0.18, 12.5, "SENTINEL_2"),
            ("2025-06-02", 0.55, 0.22, 5.0, "SATELLITE_IMPORTED"),
        ]
    for r in rows:
        lines.append(",".join(str(v) for v in r))
    return "\n".join(lines).encode()


def _drone_csv_v2(rows=None):
    """Phase 14 drone CSV (uses 'date' column)."""
    lines = ["date,vegetation_cover_percent,standing_water_percent,anomaly_score"]
    if rows is None:
        rows = [
            ("2025-06-01", 72.0, 15.0, 3.5),
            ("2025-06-02", 68.0, 20.0, 5.0),
        ]
    for r in rows:
        lines.append(",".join(str(v) for v in r))
    return "\n".join(lines).encode()


def _boundary_geojson(lat=18.5, lon=73.8, size=0.002):  # ~0.05 ha — well within 10× of 5-acre farm
    """Tiny square polygon around a point."""
    ring = [
        [lon,      lat],
        [lon+size, lat],
        [lon+size, lat+size],
        [lon,      lat+size],
        [lon,      lat],   # closed
    ]
    return json.dumps({
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": {}}],
    }).encode()


def _satellite_geojson(dates=None):
    if dates is None:
        dates = ["2025-06-01", "2025-06-02"]
    features = []
    for d in dates:
        features.append({
            "type": "Feature",
            "geometry": None,
            "properties": {
                "date": d,
                "ndvi": 0.55,
                "ndwi": 0.12,
                "cloud_cover_percent": 8.0,
                "source": "SENTINEL_2",
            },
        })
    return json.dumps({"type": "FeatureCollection", "features": features}).encode()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def setup_import(db, client, farmer_user, fpo_user, fpo_profile):
    """Returns (farmer_token, fpo_token, farm, cycle)."""
    farm = _make_farm(db, farmer_user, fpo_profile=fpo_profile, approved=True, farm_name="Import Farm")
    cycle = _make_cycle(db, farm)
    farmer_tok = _auth(client, farmer_user.email)
    fpo_tok    = _auth(client, fpo_user.email)
    return farmer_tok, fpo_tok, farm, cycle


@pytest.fixture
def unlinked_farm_fpo(db, farmer2_user, fpo_user, fpo_profile):
    """FPO2 cannot import for this farm (belongs to farmer2, no FPO link)."""
    fpo2 = _make_user(db, "FPO2", "fpo2unlinked@test.com", UserRole.FPO)
    _make_fpo_profile(db, fpo2, org="AnotherFPO", reg="REG999")
    farm = _make_farm(db, farmer2_user, farm_name="Unlinked Farm")
    cycle = _make_cycle(db, farm)
    tok = _auth(client=TestClient(__import__("app.main", fromlist=["app"]).app), email=fpo_user.email)
    return fpo_profile, farm, cycle, tok


# ── 1. Sensor CSV valid import ────────────────────────────────────────────────

class TestSensorCsvImport:
    def test_sensor_csv_valid_import(self, client, setup_import, db):
        farmer_tok, _, farm, cycle = setup_import
        content = _sensor_csv_v2()
        r = client.post(
            "/mrv/import/sensor-csv",
            data={"farm_id": farm.id, "crop_cycle_id": cycle.id},
            files={"file": ("sensor.csv", io.BytesIO(content), "text/csv")},
            headers=_headers(farmer_tok),
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["rows_inserted"] == 2
        assert j["rows_received"] == 2
        assert j["invalid_rows"] == 0
        assert j["duplicates_skipped"] == 0

        readings = db.query(SensorReading).filter(
            SensorReading.farm_id == farm.id,
            SensorReading.source_type == SensorSourceType.IMPORTED,
        ).all()
        assert len(readings) == 2

    def test_sensor_csv_invalid_rows_reported(self, client, setup_import):
        farmer_tok, _, farm, cycle = setup_import
        # Row with bad temperature + future date
        bad = _sensor_csv_v2([
            ("2025-06-01", 31.2, 42.5, 8.0, 70, 2.4),   # valid
            ("2099-01-01", 31.2, 42.5, 8.0, 70, 2.4),   # future date — rejected
            ("2025-06-03", "NOTANUMBER", 42.5, 8.0, 70, 2.4),  # bad value — rejected
        ])
        r = client.post(
            "/mrv/import/sensor-csv",
            data={"farm_id": farm.id, "crop_cycle_id": cycle.id},
            files={"file": ("sensor.csv", io.BytesIO(bad), "text/csv")},
            headers=_headers(farmer_tok),
        )
        assert r.status_code in (200, 422), r.text
        if r.status_code == 200:
            j = r.json()
            assert j["rows_inserted"] == 1
            assert j["invalid_rows"] >= 1

    def test_sensor_csv_duplicates_skipped(self, client, setup_import, db):
        farmer_tok, _, farm, cycle = setup_import
        content = _sensor_csv_v2()
        # First import
        client.post(
            "/mrv/import/sensor-csv",
            data={"farm_id": farm.id, "crop_cycle_id": cycle.id},
            files={"file": ("sensor.csv", io.BytesIO(content), "text/csv")},
            headers=_headers(farmer_tok),
        )
        # Second import — same rows → duplicates
        r = client.post(
            "/mrv/import/sensor-csv",
            data={"farm_id": farm.id, "crop_cycle_id": cycle.id},
            files={"file": ("sensor.csv", io.BytesIO(content), "text/csv")},
            headers=_headers(farmer_tok),
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["duplicates_skipped"] == 2
        assert j["rows_inserted"] == 0


# ── 4. Satellite CSV import ───────────────────────────────────────────────────

class TestSatelliteCsvImport:
    def test_satellite_csv_valid_import(self, client, setup_import, db):
        farmer_tok, _, farm, cycle = setup_import
        content = _satellite_csv_v2()
        r = client.post(
            "/mrv/import/satellite-csv",
            data={"farm_id": farm.id, "crop_cycle_id": cycle.id},
            files={"file": ("sat.csv", io.BytesIO(content), "text/csv")},
            headers=_headers(farmer_tok),
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["rows_inserted"] == 2

    def test_satellite_source_sentinel2_classified(self, client, setup_import, db):
        """source=SENTINEL_2 → stored as SatelliteSource.SENTINEL_2, not SIMULATED."""
        farmer_tok, _, farm, cycle = setup_import
        sentinel_csv = _satellite_csv_v2([("2025-07-01", 0.60, 0.15, 5.0, "SENTINEL_2")])
        r = client.post(
            "/mrv/import/satellite-csv",
            data={"farm_id": farm.id, "crop_cycle_id": cycle.id},
            files={"file": ("sat.csv", io.BytesIO(sentinel_csv), "text/csv")},
            headers=_headers(farmer_tok),
        )
        assert r.status_code == 200, r.text
        obs = db.query(SatelliteObservation).filter(
            SatelliteObservation.farm_id == farm.id,
        ).order_by(SatelliteObservation.id.desc()).first()
        assert obs is not None
        assert obs.source == SatelliteSource.SENTINEL_2


# ── 6. Drone CSV import ───────────────────────────────────────────────────────

class TestDroneCsvImport:
    def test_drone_csv_valid_import(self, client, setup_import, db):
        farmer_tok, _, farm, cycle = setup_import
        content = _drone_csv_v2()
        r = client.post(
            "/mrv/import/drone-csv",
            data={"farm_id": farm.id, "crop_cycle_id": cycle.id},
            files={"file": ("drone.csv", io.BytesIO(content), "text/csv")},
            headers=_headers(farmer_tok),
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["rows_inserted"] == 2
        obs = db.query(DroneObservation).filter(
            DroneObservation.farm_id == farm.id,
            DroneObservation.source == DroneSource.DRONE_IMPORTED,
        ).all()
        assert len(obs) == 2


# ── 7. Farm boundary GeoJSON ──────────────────────────────────────────────────

class TestFarmBoundaryGeojson:
    def test_boundary_geojson_updates_farm(self, client, setup_import, db):
        farmer_tok, _, farm, _ = setup_import
        content = _boundary_geojson()
        r = client.post(
            "/mrv/import/farm-boundary-geojson",
            data={"farm_id": farm.id},
            files={"file": ("boundary.geojson", io.BytesIO(content), "application/json")},
            headers=_headers(farmer_tok),
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["success"] is True
        assert j["boundary_area_hectares"] > 0
        assert j["boundary_area_acres"] > 0

        db.expire_all()
        from app.models.farm import Farm as FarmModel
        updated = db.query(FarmModel).filter(FarmModel.id == farm.id).first()
        assert updated.farm_boundary_geojson is not None
        assert updated.boundary_area_hectares > 0

    def test_boundary_geojson_unclosed_ring_rejected(self, client, setup_import):
        farmer_tok, _, farm, _ = setup_import
        bad = json.dumps({
            "type": "Polygon",
            "coordinates": [[[73.8, 18.5], [73.81, 18.5], [73.81, 18.51]]],  # not closed
        }).encode()
        r = client.post(
            "/mrv/import/farm-boundary-geojson",
            data={"farm_id": farm.id},
            files={"file": ("b.geojson", io.BytesIO(bad), "application/json")},
            headers=_headers(farmer_tok),
        )
        assert r.status_code == 422

    def test_boundary_creates_evidence_record(self, client, setup_import, db):
        farmer_tok, _, farm, _ = setup_import
        content = _boundary_geojson()
        client.post(
            "/mrv/import/farm-boundary-geojson",
            data={"farm_id": farm.id},
            files={"file": ("boundary.geojson", io.BytesIO(content), "application/json")},
            headers=_headers(farmer_tok),
        )
        ev = db.query(EvidenceFile).filter(
            EvidenceFile.farm_id == farm.id,
            EvidenceFile.evidence_type == "GIS_BOUNDARY",
        ).first()
        assert ev is not None
        assert ev.file_hash is not None and len(ev.file_hash) == 64


# ── 8. Satellite GeoJSON import ───────────────────────────────────────────────

class TestSatelliteGeojsonImport:
    def test_satellite_geojson_valid_import(self, client, setup_import, db):
        farmer_tok, _, farm, cycle = setup_import
        content = _satellite_geojson()
        r = client.post(
            "/mrv/import/satellite-geojson",
            data={"farm_id": farm.id, "crop_cycle_id": cycle.id},
            files={"file": ("sat.geojson", io.BytesIO(content), "application/json")},
            headers=_headers(farmer_tok),
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["rows_inserted"] == 2

    def test_satellite_geojson_non_collection_rejected(self, client, setup_import):
        farmer_tok, _, farm, cycle = setup_import
        bad = json.dumps({"type": "Polygon", "coordinates": []}).encode()
        r = client.post(
            "/mrv/import/satellite-geojson",
            data={"farm_id": farm.id, "crop_cycle_id": cycle.id},
            files={"file": ("sat.geojson", io.BytesIO(bad), "application/json")},
            headers=_headers(farmer_tok),
        )
        assert r.status_code == 422


# ── 9. FPO can import for linked farm ─────────────────────────────────────────

class TestFpoImportAccess:
    def test_fpo_can_import_linked_farm(self, client, setup_import):
        _, fpo_tok, farm, cycle = setup_import
        content = _sensor_csv_v2()
        r = client.post(
            "/mrv/import/sensor-csv",
            data={"farm_id": farm.id, "crop_cycle_id": cycle.id},
            files={"file": ("sensor.csv", io.BytesIO(content), "text/csv")},
            headers=_headers(fpo_tok),
        )
        assert r.status_code == 200, r.text
        assert r.json()["rows_inserted"] == 2

    def test_fpo_cannot_import_unlinked_farm(self, client, db, farmer2_user, fpo_user, fpo_profile):
        """FPO for farm A cannot import into farm B (different farmer, no FPO link)."""
        farm_b = _make_farm(db, farmer2_user, farm_name="Unlinked Farm B")
        cycle_b = _make_cycle(db, farm_b)
        fpo_tok = _auth(client, fpo_user.email)
        content = _sensor_csv_v2()
        r = client.post(
            "/mrv/import/sensor-csv",
            data={"farm_id": farm_b.id, "crop_cycle_id": cycle_b.id},
            files={"file": ("sensor.csv", io.BytesIO(content), "text/csv")},
            headers=_headers(fpo_tok),
        )
        assert r.status_code == 403


# ── 11. Verifier cannot import ────────────────────────────────────────────────

class TestVerifierImportBlocked:
    def test_verifier_cannot_import_sensor(self, client, setup_import, verifier_user):
        _, _, farm, cycle = setup_import
        ver_tok = _auth(client, verifier_user.email)
        content = _sensor_csv_v2()
        r = client.post(
            "/mrv/import/sensor-csv",
            data={"farm_id": farm.id, "crop_cycle_id": cycle.id},
            files={"file": ("sensor.csv", io.BytesIO(content), "text/csv")},
            headers=_headers(ver_tok),
        )
        assert r.status_code == 403


# ── 12. Import creates evidence hash record ───────────────────────────────────

class TestImportEvidenceRecord:
    def test_sensor_import_creates_evidence_record(self, client, setup_import, db):
        farmer_tok, _, farm, cycle = setup_import
        content = _sensor_csv_v2()
        client.post(
            "/mrv/import/sensor-csv",
            data={"farm_id": farm.id, "crop_cycle_id": cycle.id},
            files={"file": ("sensor.csv", io.BytesIO(content), "text/csv")},
            headers=_headers(farmer_tok),
        )
        ev = db.query(EvidenceFile).filter(
            EvidenceFile.farm_id == farm.id,
            EvidenceFile.evidence_type == "SENSOR_EXPORT",
        ).first()
        assert ev is not None
        assert ev.file_hash is not None
        assert len(ev.file_hash) == 64
        assert ev.hash_algorithm == "SHA256"

    def test_satellite_import_evidence_not_simulated_source(self, client, setup_import, db):
        """After satellite import, observations have non-SIMULATED source."""
        farmer_tok, _, farm, cycle = setup_import
        content = _satellite_csv_v2()
        client.post(
            "/mrv/import/satellite-csv",
            data={"farm_id": farm.id, "crop_cycle_id": cycle.id},
            files={"file": ("sat.csv", io.BytesIO(content), "text/csv")},
            headers=_headers(farmer_tok),
        )
        obs = db.query(SatelliteObservation).filter(
            SatelliteObservation.farm_id == farm.id,
        ).all()
        sources = {o.source for o in obs}
        # None should be SATELLITE_SIMULATED
        assert SatelliteSource.SATELLITE_SIMULATED not in sources

    def test_imported_sensor_readings_present_for_carbon_report(self, client, setup_import, db):
        """After import, sensor readings exist with IMPORTED source and can be queried."""
        farmer_tok, _, farm, cycle = setup_import
        content = _sensor_csv_v2()
        client.post(
            "/mrv/import/sensor-csv",
            data={"farm_id": farm.id, "crop_cycle_id": cycle.id},
            files={"file": ("sensor.csv", io.BytesIO(content), "text/csv")},
            headers=_headers(farmer_tok),
        )
        readings = db.query(SensorReading).filter(
            SensorReading.crop_cycle_id == cycle.id,
            SensorReading.source_type == SensorSourceType.IMPORTED,
        ).all()
        assert len(readings) == 2
        # All readings have valid methane fields (either set in CSV or defaulted)
        for r in readings:
            assert r.estimated_methane is not None
            assert r.data_quality_score is not None


# ── 15. Evidence multipart upload ─────────────────────────────────────────────

class TestEvidenceMultipartUpload:
    def test_farmer_cannot_upload_photo(self, client, setup_import, db):
        """FARMER role is blocked from /evidence/upload (view-only)."""
        farmer_tok, _, farm, cycle = setup_import
        photo_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        r = client.post(
            "/evidence/upload",
            data={"farm_id": farm.id, "crop_cycle_id": cycle.id, "evidence_type": "PHOTO"},
            files={"file": ("field.jpg", io.BytesIO(photo_bytes), "image/jpeg")},
            headers=_headers(farmer_tok),
        )
        assert r.status_code == 403, r.text
        assert "Farmers cannot upload" in r.json()["detail"]

    def test_fpo_can_upload_evidence_for_linked_farm(self, client, setup_import, db):
        """FPO uploads multipart evidence — returns 201 with hash fields."""
        _, fpo_tok, farm, cycle = setup_import
        photo_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # minimal JPEG header
        r = client.post(
            "/evidence/upload",
            data={
                "farm_id": farm.id,
                "crop_cycle_id": cycle.id,
                "evidence_type": "PHOTO",
                "description": "FPO field photo",
            },
            files={"file": ("field.jpg", io.BytesIO(photo_bytes), "image/jpeg")},
            headers=_headers(fpo_tok),
        )
        assert r.status_code == 201, r.text
        j = r.json()
        assert j["file_hash"] is not None
        assert len(j["file_hash"]) == 64
        assert j["hash_algorithm"] == "SHA256"
        assert j["evidence_type"] == "PHOTO"
        assert j["file_name"] == "field.jpg"
        assert j["file_size"] == len(photo_bytes)

    def test_fpo_can_upload_document_for_linked_farm(self, client, setup_import, db):
        _, fpo_tok, farm, cycle = setup_import
        r = client.post(
            "/evidence/upload",
            data={
                "farm_id": farm.id,
                "evidence_type": "DOCUMENT",
                "description": "FPO field report",
            },
            files={"file": ("report.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
            headers=_headers(fpo_tok),
        )
        assert r.status_code == 201, r.text

    def test_verifier_cannot_upload_evidence(self, client, setup_import, verifier_user):
        _, _, farm, cycle = setup_import
        ver_tok = _auth(client, verifier_user.email)
        r = client.post(
            "/evidence/upload",
            data={"farm_id": farm.id, "evidence_type": "PHOTO"},
            files={"file": ("x.jpg", io.BytesIO(b"fake"), "image/jpeg")},
            headers=_headers(ver_tok),
        )
        assert r.status_code == 403
