"""
MRV Import Router — Phase 11 / Phase 14

Phase 11 endpoints (backward-compatible):
  POST /mrv/import/sensor-csv      — sensor readings CSV
  POST /mrv/import/satellite-csv   — satellite observation CSV
  POST /mrv/import/drone-csv       — drone observation CSV

Phase 14 additions:
  POST /mrv/import/farm-boundary-geojson  — GeoJSON polygon → farm boundary
  POST /mrv/import/satellite-geojson      — GeoJSON FeatureCollection → satellite obs

Phase 14 CSV schema changes (backward-compatible):
  sensor-csv:     accepts 'date' OR 'reading_time'; optional columns have defaults
  satellite-csv:  accepts 'date' OR 'observation_date'; auto-detects SENTINEL_2 source;
                  vegetation_health/flood_risk are OPTIONAL (derived from NDVI if absent)
  drone-csv:      accepts 'date' OR 'observation_date'

All imports:
  - Create an EvidenceFile record (SENSOR_EXPORT / SATELLITE_EXPORT / DRONE_EXPORT / GIS_BOUNDARY)
  - Compute SHA-256 of import file bytes
  - Duplicate detection (same farm/cycle + timestamp/date)

Security constraints:
  - Do NOT alter methane logic, SOC logic, payout logic, or token minting.
  - All imports are ADDITIVE only.
  - Verifiers cannot import.
"""
import csv
import hashlib
import io
import json
import math
from datetime import datetime, timezone, date as date_type
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.drone_observation import DroneObservation, DroneSource
from app.models.evidence import EvidenceFile, EvidenceType
from app.models.farm import Farm, CropCycle
from app.models.fpo import FPOProfile
from app.models.satellite_observation import (
    SatelliteObservation, SatelliteSource, VegetationHealth, FloodRisk,
)
from app.models.sensor import SensorReading, SensorSourceType
from app.models.user import User, UserRole

router = APIRouter(prefix="/mrv/import", tags=["MRV Import"])

_TODAY = date_type.today  # callable — evaluated at request time

# ── Shared helpers ────────────────────────────────────────────────────────────

def _assert_import_access(farm: Farm, current_user: User, db: Session) -> None:
    """FARMER (own), FPO (linked), ADMIN. VERIFIER blocked."""
    if current_user.role == UserRole.VERIFIER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verifiers cannot import MRV data")
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


def _get_farm(farm_id: int, db: Session) -> Farm:
    farm = db.query(Farm).filter(Farm.id == farm_id, Farm.is_deleted == False).first()  # noqa: E712
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    return farm


def _get_cycle(crop_cycle_id: int, farm_id: int, db: Session) -> CropCycle:
    cycle = db.query(CropCycle).filter(
        CropCycle.id == crop_cycle_id,
        CropCycle.farm_id == farm_id,
    ).first()
    if not cycle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop cycle not found")
    return cycle


def _get_farm_and_cycle(farm_id: int, crop_cycle_id: int, db: Session):
    return _get_farm(farm_id, db), _get_cycle(crop_cycle_id, farm_id, db)


def _parse_csv(content: bytes) -> List[dict]:
    text = content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))
    return [row for row in reader]


def _check_required_columns(rows: List[dict], required: List[str], source: str) -> None:
    if not rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file is empty")
    missing = [c for c in required if c not in rows[0]]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required columns in {source} CSV: {missing}",
        )


def _safe_float(val: Optional[str], col: str, row_num: int, default: Optional[float] = None) -> float:
    if val is None or val.strip() == "":
        if default is not None:
            return default
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Row {row_num}: missing value for '{col}'",
        )
    try:
        return float(val.strip())
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Row {row_num}: invalid numeric value for '{col}': {repr(val)}",
        )


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _create_import_evidence(
    db: Session,
    farm_id: int,
    crop_cycle_id: Optional[int],
    uploaded_by: int,
    evidence_type: str,
    file_name: str,
    file_hash: str,
    description: str,
) -> EvidenceFile:
    """Create an EvidenceFile record for an import operation."""
    ev = EvidenceFile(
        farm_id=farm_id,
        crop_cycle_id=crop_cycle_id,
        uploaded_by=uploaded_by,
        evidence_type=evidence_type,
        file_type=evidence_type,
        file_name=file_name,
        file_url=f"/imports/{evidence_type.lower()}/{farm_id}/{file_name}",
        file_hash=file_hash,
        hash_algorithm="SHA256",
        description=description,
    )
    db.add(ev)
    return ev


def _derive_veg_health(ndvi: float) -> VegetationHealth:
    if ndvi >= 0.5:
        return VegetationHealth.EXCELLENT
    if ndvi >= 0.3:
        return VegetationHealth.GOOD
    if ndvi >= 0.1:
        return VegetationHealth.FAIR
    return VegetationHealth.POOR


def _derive_flood_risk(ndwi: float) -> FloodRisk:
    if ndwi >= 0.3:
        return FloodRisk.HIGH
    if ndwi >= 0.1:
        return FloodRisk.MEDIUM
    if ndwi >= 0.0:
        return FloodRisk.LOW
    return FloodRisk.NONE


# ── POST /mrv/import/sensor-csv ──────────────────────────────────────────────

# Phase 14 schema: 'date' is the primary column name; 'reading_time' accepted for backward compat.
SENSOR_REQUIRED_COLS_V2 = ["date", "temperature_c", "soil_moisture", "water_depth_cm"]
SENSOR_REQUIRED_COLS_V1 = ["reading_time", "soil_moisture", "water_depth_cm", "temperature_c"]


@router.post("/sensor-csv")
async def import_sensor_csv(
    farm_id: int = Form(...),
    crop_cycle_id: int = Form(...),
    file: UploadFile = File(..., description="CSV file with sensor readings"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Import sensor readings from CSV.

    Phase 14 required columns: date, temperature_c, soil_moisture, water_depth_cm
    Optional: humidity, rainfall_mm, estimated_methane, data_quality_score,
              source_device_id, latitude, longitude

    Also accepts Phase 11 schema (reading_time instead of date, all 8 columns required).
    Duplicate detection: same farm+cycle+reading_time.
    Creates an SENSOR_EXPORT evidence record on success.
    """
    farm, cycle = _get_farm_and_cycle(farm_id, crop_cycle_id, db)
    _assert_import_access(farm, current_user, db)

    content = await file.read()
    rows = _parse_csv(content)

    # Detect schema version
    if rows and "date" in rows[0]:
        _check_required_columns(rows, SENSOR_REQUIRED_COLS_V2, "sensor")
        date_col = "date"
    else:
        _check_required_columns(rows, SENSOR_REQUIRED_COLS_V1, "sensor")
        date_col = "reading_time"

    # Normalize to naive-UTC for comparison (SQLite strips timezone on round-trip)
    def _naive_utc(dt: datetime) -> datetime:
        if dt is None:
            return dt
        if dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt

    existing_times = {
        _naive_utc(r.reading_time) for r in
        db.query(SensorReading.reading_time)
        .filter(SensorReading.crop_cycle_id == crop_cycle_id)
        .all()
    }

    inserted = 0
    skipped_duplicates = 0
    invalid_rows = 0
    errors: List[str] = []
    new_readings: List[SensorReading] = []

    for i, row in enumerate(rows, start=2):
        try:
            ts_str = row[date_col].strip()
            try:
                ts = datetime.fromisoformat(ts_str)
            except ValueError:
                # Try date-only
                try:
                    d = date_type.fromisoformat(ts_str)
                    ts = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
                except ValueError:
                    errors.append(f"Row {i}: invalid date format: {repr(ts_str)}")
                    invalid_rows += 1
                    continue

            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            # Future-date guard
            if ts.date() > _TODAY():
                errors.append(f"Row {i}: future date rejected: {ts_str}")
                invalid_rows += 1
                continue

            ts_naive = _naive_utc(ts)
            if ts_naive in existing_times:
                skipped_duplicates += 1
                continue

            temperature_c   = _safe_float(row.get("temperature_c"), "temperature_c", i)
            soil_moisture   = _safe_float(row.get("soil_moisture"), "soil_moisture", i)
            water_depth_cm  = _safe_float(row.get("water_depth_cm"), "water_depth_cm", i)
            humidity        = _safe_float(row.get("humidity"), "humidity", i, default=60.0)
            rainfall_mm     = _safe_float(row.get("rainfall_mm"), "rainfall_mm", i, default=0.0)
            est_methane     = _safe_float(row.get("estimated_methane"), "estimated_methane", i, default=0.5)
            quality         = _safe_float(row.get("data_quality_score"), "data_quality_score", i, default=75.0)

            # Reasonable range validation
            if not (-10 <= temperature_c <= 60):
                errors.append(f"Row {i}: temperature_c out of range: {temperature_c}")
                invalid_rows += 1
                continue
            if not (0 <= soil_moisture <= 100):
                errors.append(f"Row {i}: soil_moisture out of range: {soil_moisture}")
                invalid_rows += 1
                continue
            if not (0 <= water_depth_cm <= 100):
                errors.append(f"Row {i}: water_depth_cm out of range: {water_depth_cm}")
                invalid_rows += 1
                continue

            reading = SensorReading(
                farm_id=farm_id,
                crop_cycle_id=crop_cycle_id,
                reading_time=ts,
                soil_moisture=soil_moisture,
                water_depth_cm=water_depth_cm,
                temperature_c=temperature_c,
                humidity=humidity,
                rainfall_mm=rainfall_mm,
                estimated_methane=est_methane,
                data_quality_score=quality,
                source_type=SensorSourceType.IMPORTED,
            )
            new_readings.append(reading)
            existing_times.add(ts_naive)
            inserted += 1

        except HTTPException:
            raise
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")
            invalid_rows += 1

    if new_readings:
        db.bulk_save_objects(new_readings)

    # Create evidence record
    if inserted > 0:
        _create_import_evidence(
            db=db,
            farm_id=farm_id,
            crop_cycle_id=crop_cycle_id,
            uploaded_by=current_user.id,
            evidence_type=EvidenceType.SENSOR_EXPORT.value,
            file_name=file.filename or "sensor_import.csv",
            file_hash=_hash_bytes(content),
            description=f"Sensor CSV import: {inserted} readings inserted",
        )

    db.commit()

    return {
        "success": True,
        "rows_received": len(rows),
        "rows_inserted": inserted,
        "duplicates_skipped": skipped_duplicates,
        "invalid_rows": invalid_rows,
        "errors": errors[:20],
    }


# ── POST /mrv/import/satellite-csv ───────────────────────────────────────────

SATELLITE_REQUIRED_COLS_V2 = ["date", "ndvi", "ndwi", "cloud_cover_percent"]
SATELLITE_REQUIRED_COLS_V1 = [
    "observation_date", "ndvi", "ndwi", "vegetation_health",
    "flood_risk", "cloud_cover_percent",
]

VALID_VEG_HEALTH = {e.value for e in VegetationHealth}
VALID_FLOOD_RISK = {e.value for e in FloodRisk}
_SENTINEL2_ALIASES = {"sentinel_2", "sentinel2", "s2", "sentinel-2"}


def _map_satellite_source(raw: Optional[str]) -> SatelliteSource:
    """Map CSV source column to SatelliteSource enum."""
    if raw is None or raw.strip() == "":
        return SatelliteSource.SATELLITE_IMPORTED
    low = raw.strip().lower().replace(" ", "_")
    if low in _SENTINEL2_ALIASES:
        return SatelliteSource.SENTINEL_2
    if "landsat" in low:
        return SatelliteSource.LANDSAT_8
    return SatelliteSource.SATELLITE_IMPORTED


@router.post("/satellite-csv")
async def import_satellite_csv(
    farm_id: int = Form(...),
    crop_cycle_id: int = Form(...),
    file: UploadFile = File(..., description="CSV file with satellite observations"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Import satellite observations from CSV.

    Phase 14 required: date, ndvi, ndwi, cloud_cover_percent
    Optional: source, scene_id, satellite, resolution_m, vegetation_health, flood_risk

    source='SENTINEL_2' → stored with SatelliteSource.SENTINEL_2 (NOT classified as simulated).
    vegetation_health and flood_risk are auto-derived from NDVI/NDWI if not provided.

    Backward-compatible with Phase 11 schema (observation_date column).
    Creates a SATELLITE_EXPORT evidence record on success.
    """
    farm, cycle = _get_farm_and_cycle(farm_id, crop_cycle_id, db)
    _assert_import_access(farm, current_user, db)

    content = await file.read()
    rows = _parse_csv(content)

    if rows and "date" in rows[0]:
        _check_required_columns(rows, SATELLITE_REQUIRED_COLS_V2, "satellite")
        date_col = "date"
        v1_mode = False
    else:
        _check_required_columns(rows, SATELLITE_REQUIRED_COLS_V1, "satellite")
        date_col = "observation_date"
        v1_mode = True

    existing_dates = {
        r.observation_date for r in
        db.query(SatelliteObservation.observation_date)
        .filter(
            SatelliteObservation.crop_cycle_id == crop_cycle_id,
            SatelliteObservation.source.in_([
                SatelliteSource.SATELLITE_IMPORTED.value,
                SatelliteSource.SENTINEL_2.value,
                SatelliteSource.LANDSAT_8.value,
            ]),
        )
        .all()
    }

    inserted = 0
    skipped_duplicates = 0
    invalid_rows = 0
    errors: List[str] = []
    new_obs: List[SatelliteObservation] = []

    for i, row in enumerate(rows, start=2):
        try:
            date_str = row[date_col].strip()
            try:
                obs_date = date_type.fromisoformat(date_str)
            except ValueError:
                errors.append(f"Row {i}: invalid date: {repr(date_str)}")
                invalid_rows += 1
                continue

            if obs_date > _TODAY():
                errors.append(f"Row {i}: future date rejected: {date_str}")
                invalid_rows += 1
                continue

            if obs_date in existing_dates:
                skipped_duplicates += 1
                continue

            ndvi  = _safe_float(row.get("ndvi"), "ndvi", i)
            ndwi  = _safe_float(row.get("ndwi"), "ndwi", i)
            cloud = _safe_float(row.get("cloud_cover_percent"), "cloud_cover_percent", i)

            if not (-1 <= ndvi <= 1):
                errors.append(f"Row {i}: ndvi out of range [-1,1]: {ndvi}")
                invalid_rows += 1
                continue
            if not (-1 <= ndwi <= 1):
                errors.append(f"Row {i}: ndwi out of range [-1,1]: {ndwi}")
                invalid_rows += 1
                continue
            if not (0 <= cloud <= 100):
                errors.append(f"Row {i}: cloud_cover_percent out of range [0,100]: {cloud}")
                invalid_rows += 1
                continue

            # vegetation_health — required in v1, optional/derived in v2
            veg_raw = row.get("vegetation_health", "").strip().upper()
            if v1_mode:
                if veg_raw not in VALID_VEG_HEALTH:
                    errors.append(f"Row {i}: invalid vegetation_health: {repr(veg_raw)}")
                    invalid_rows += 1
                    continue
                veg_health = VegetationHealth(veg_raw)
            else:
                veg_health = VegetationHealth(veg_raw) if veg_raw in VALID_VEG_HEALTH else _derive_veg_health(ndvi)

            # flood_risk — required in v1, optional/derived in v2
            flood_raw = row.get("flood_risk", "").strip().upper()
            if v1_mode:
                if flood_raw not in VALID_FLOOD_RISK:
                    errors.append(f"Row {i}: invalid flood_risk: {repr(flood_raw)}")
                    invalid_rows += 1
                    continue
                flood_risk = FloodRisk(flood_raw)
            else:
                flood_risk = FloodRisk(flood_raw) if flood_raw in VALID_FLOOD_RISK else _derive_flood_risk(ndwi)

            source = _map_satellite_source(row.get("source"))

            obs = SatelliteObservation(
                farm_id=farm_id,
                crop_cycle_id=crop_cycle_id,
                observation_date=obs_date,
                ndvi=ndvi,
                ndwi=ndwi,
                vegetation_health=veg_health,
                flood_risk=flood_risk,
                cloud_cover_percent=cloud,
                source=source,
            )
            new_obs.append(obs)
            existing_dates.add(obs_date)
            inserted += 1

        except HTTPException:
            raise
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")
            invalid_rows += 1

    if new_obs:
        db.bulk_save_objects(new_obs)

    if inserted > 0:
        _create_import_evidence(
            db=db,
            farm_id=farm_id,
            crop_cycle_id=crop_cycle_id,
            uploaded_by=current_user.id,
            evidence_type=EvidenceType.SATELLITE_EXPORT.value,
            file_name=file.filename or "satellite_import.csv",
            file_hash=_hash_bytes(content),
            description=f"Satellite CSV import: {inserted} observations inserted",
        )

    db.commit()

    return {
        "success": True,
        "rows_received": len(rows),
        "rows_inserted": inserted,
        "duplicates_skipped": skipped_duplicates,
        "invalid_rows": invalid_rows,
        "errors": errors[:20],
    }


# ── POST /mrv/import/drone-csv ────────────────────────────────────────────────

DRONE_REQUIRED_COLS_V2 = ["date", "vegetation_cover_percent", "standing_water_percent", "anomaly_score"]
DRONE_REQUIRED_COLS_V1 = ["observation_date", "vegetation_cover_percent", "standing_water_percent", "anomaly_score"]


@router.post("/drone-csv")
async def import_drone_csv(
    farm_id: int = Form(...),
    crop_cycle_id: int = Form(...),
    file: UploadFile = File(..., description="CSV file with drone observations"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Import drone observations from CSV.

    Phase 14 required: date, vegetation_cover_percent, standing_water_percent, anomaly_score
    Optional: image_reference, drone_provider, flight_id

    Backward-compatible with Phase 11 schema (observation_date instead of date).
    Creates a DRONE_EXPORT evidence record on success.
    """
    farm, cycle = _get_farm_and_cycle(farm_id, crop_cycle_id, db)
    _assert_import_access(farm, current_user, db)

    content = await file.read()
    rows = _parse_csv(content)

    if rows and "date" in rows[0]:
        _check_required_columns(rows, DRONE_REQUIRED_COLS_V2, "drone")
        date_col = "date"
    else:
        _check_required_columns(rows, DRONE_REQUIRED_COLS_V1, "drone")
        date_col = "observation_date"

    existing_dates = {
        r.observation_date for r in
        db.query(DroneObservation.observation_date)
        .filter(
            DroneObservation.crop_cycle_id == crop_cycle_id,
            DroneObservation.source == DroneSource.DRONE_IMPORTED,
        )
        .all()
    }

    inserted = 0
    skipped_duplicates = 0
    invalid_rows = 0
    errors: List[str] = []
    new_obs: List[DroneObservation] = []

    for i, row in enumerate(rows, start=2):
        try:
            date_str = row[date_col].strip()
            try:
                obs_date = date_type.fromisoformat(date_str)
            except ValueError:
                errors.append(f"Row {i}: invalid date: {repr(date_str)}")
                invalid_rows += 1
                continue

            if obs_date > _TODAY():
                errors.append(f"Row {i}: future date rejected: {date_str}")
                invalid_rows += 1
                continue

            if obs_date in existing_dates:
                skipped_duplicates += 1
                continue

            veg   = _safe_float(row.get("vegetation_cover_percent"), "vegetation_cover_percent", i)
            water = _safe_float(row.get("standing_water_percent"), "standing_water_percent", i)
            anom  = _safe_float(row.get("anomaly_score"), "anomaly_score", i)

            if not (0 <= veg <= 100):
                errors.append(f"Row {i}: vegetation_cover_percent out of range: {veg}")
                invalid_rows += 1
                continue
            if not (0 <= water <= 100):
                errors.append(f"Row {i}: standing_water_percent out of range: {water}")
                invalid_rows += 1
                continue
            if not (0 <= anom <= 100):
                errors.append(f"Row {i}: anomaly_score out of range: {anom}")
                invalid_rows += 1
                continue

            obs = DroneObservation(
                farm_id=farm_id,
                crop_cycle_id=crop_cycle_id,
                observation_date=obs_date,
                vegetation_cover_percent=veg,
                standing_water_percent=water,
                anomaly_score=anom,
                image_reference=row.get("image_reference", "").strip() or None,
                source=DroneSource.DRONE_IMPORTED,
            )
            new_obs.append(obs)
            existing_dates.add(obs_date)
            inserted += 1

        except HTTPException:
            raise
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")
            invalid_rows += 1

    if new_obs:
        db.bulk_save_objects(new_obs)

    if inserted > 0:
        _create_import_evidence(
            db=db,
            farm_id=farm_id,
            crop_cycle_id=crop_cycle_id,
            uploaded_by=current_user.id,
            evidence_type=EvidenceType.DRONE_EXPORT.value,
            file_name=file.filename or "drone_import.csv",
            file_hash=_hash_bytes(content),
            description=f"Drone CSV import: {inserted} observations inserted",
        )

    db.commit()

    return {
        "success": True,
        "rows_received": len(rows),
        "rows_inserted": inserted,
        "duplicates_skipped": skipped_duplicates,
        "invalid_rows": invalid_rows,
        "errors": errors[:20],
    }


# ── POST /mrv/import/farm-boundary-geojson ────────────────────────────────────

def _geojson_area_m2(coordinates: list) -> float:
    """
    Approximate area in m² of a GeoJSON polygon ring using the spherical excess formula.
    Only the outer ring (index 0) is used.
    """
    ring = coordinates[0]
    if len(ring) < 4:
        return 0.0
    R = 6_371_000.0  # Earth radius in metres
    n = len(ring)
    area = 0.0
    for i in range(n - 1):
        lon1, lat1 = math.radians(ring[i][0]),   math.radians(ring[i][1])
        lon2, lat2 = math.radians(ring[i+1][0]), math.radians(ring[i+1][1])
        area += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
    return abs(area * R * R / 2)


def _extract_polygon_coords(geojson: dict) -> list:
    """
    Return coordinate ring list from a GeoJSON Polygon or a FeatureCollection with
    a single Polygon feature.  Raises HTTPException if neither is valid.
    """
    gtype = geojson.get("type")

    if gtype == "Polygon":
        return geojson["coordinates"]

    if gtype == "Feature":
        geom = geojson.get("geometry", {})
        if geom.get("type") == "Polygon":
            return geom["coordinates"]

    if gtype == "FeatureCollection":
        features = geojson.get("features", [])
        polys = [f for f in features if f.get("geometry", {}).get("type") == "Polygon"]
        if len(polys) == 1:
            return polys[0]["geometry"]["coordinates"]
        if len(polys) > 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="FeatureCollection contains multiple polygons; expected exactly one.",
            )

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Unsupported GeoJSON type: '{gtype}'. Expected Polygon or FeatureCollection with one Polygon.",
    )


@router.post("/farm-boundary-geojson")
async def import_farm_boundary_geojson(
    farm_id: int = Form(...),
    file: UploadFile = File(..., description="GeoJSON Polygon or FeatureCollection"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Import / update a farm's GIS boundary from a GeoJSON file.

    Accepts: GeoJSON Polygon or FeatureCollection with a single Polygon feature.
    Validates: closed ring, valid coordinate ranges, sensible area.
    Updates: farm_boundary_geojson, boundary_area_hectares, boundary_area_acres.
    Creates: GIS_BOUNDARY evidence record.
    """
    farm = _get_farm(farm_id, db)
    _assert_import_access(farm, current_user, db)

    content = await file.read()
    try:
        geojson = json.loads(content.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid JSON: {e}",
        )

    coords = _extract_polygon_coords(geojson)
    outer_ring = coords[0]

    # Validate ring closure
    if outer_ring[0] != outer_ring[-1]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Polygon ring is not closed (first and last coordinate must be equal).",
        )

    # Validate coordinate ranges
    for pt in outer_ring:
        lon, lat = pt[0], pt[1]
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Coordinate out of range: [{lon}, {lat}]",
            )

    area_m2 = _geojson_area_m2(coords)
    area_ha = area_m2 / 10_000
    area_ac = area_ha * 2.47105

    # Sanity check: boundary shouldn't exceed 10× registered area
    max_ha = farm.land_area_acres * 0.404686 * 10
    if area_ha > max_ha:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Boundary area ({area_ha:.1f} ha) exceeds 10× the registered farm area "
                f"({farm.land_area_acres:.1f} acres = {farm.land_area_acres * 0.404686:.1f} ha). "
                "Please check the GeoJSON."
            ),
        )

    # Update farm boundary
    farm.farm_boundary_geojson  = content.decode("utf-8")
    farm.boundary_area_hectares = round(area_ha, 4)
    farm.boundary_area_acres    = round(area_ac, 4)
    db.add(farm)

    file_hash = _hash_bytes(content)
    _create_import_evidence(
        db=db,
        farm_id=farm_id,
        crop_cycle_id=None,
        uploaded_by=current_user.id,
        evidence_type=EvidenceType.GIS_BOUNDARY.value,
        file_name=file.filename or "boundary.geojson",
        file_hash=file_hash,
        description=f"Farm boundary imported: {area_ha:.2f} ha / {area_ac:.2f} ac",
    )

    db.commit()

    return {
        "success": True,
        "farm_id": farm_id,
        "boundary_area_hectares": round(area_ha, 4),
        "boundary_area_acres": round(area_ac, 4),
        "file_hash": file_hash,
        "message": "Farm boundary updated successfully.",
    }


# ── POST /mrv/import/satellite-geojson ───────────────────────────────────────

@router.post("/satellite-geojson")
async def import_satellite_geojson(
    farm_id: int = Form(...),
    crop_cycle_id: int = Form(...),
    file: UploadFile = File(..., description="GeoJSON FeatureCollection with satellite scene properties"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Import satellite observations from a GeoJSON FeatureCollection.

    Each Feature must have properties:
      date (YYYY-MM-DD), ndvi, ndwi, cloud_cover_percent
    Optional properties:
      source, scene_id, vegetation_health, flood_risk

    Creates a SATELLITE_EXPORT evidence record on success.
    """
    farm, cycle = _get_farm_and_cycle(farm_id, crop_cycle_id, db)
    _assert_import_access(farm, current_user, db)

    content = await file.read()
    try:
        geojson = json.loads(content.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid JSON: {e}",
        )

    if geojson.get("type") != "FeatureCollection":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Expected a GeoJSON FeatureCollection.",
        )

    features = geojson.get("features", [])
    if not features:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="FeatureCollection contains no features.",
        )

    existing_dates = {
        r.observation_date for r in
        db.query(SatelliteObservation.observation_date)
        .filter(
            SatelliteObservation.crop_cycle_id == crop_cycle_id,
            SatelliteObservation.source.in_([
                SatelliteSource.SATELLITE_IMPORTED.value,
                SatelliteSource.SENTINEL_2.value,
            ]),
        )
        .all()
    }

    inserted = 0
    skipped_duplicates = 0
    invalid_rows = 0
    errors: List[str] = []
    new_obs: List[SatelliteObservation] = []

    for i, feature in enumerate(features, start=1):
        props = feature.get("properties") or {}
        try:
            date_str = str(props.get("date", "")).strip()
            if not date_str:
                errors.append(f"Feature {i}: missing 'date' property")
                invalid_rows += 1
                continue
            try:
                obs_date = date_type.fromisoformat(date_str)
            except ValueError:
                errors.append(f"Feature {i}: invalid date: {repr(date_str)}")
                invalid_rows += 1
                continue

            if obs_date > _TODAY():
                errors.append(f"Feature {i}: future date rejected: {date_str}")
                invalid_rows += 1
                continue

            if obs_date in existing_dates:
                skipped_duplicates += 1
                continue

            try:
                ndvi  = float(props["ndvi"])
                ndwi  = float(props["ndwi"])
                cloud = float(props["cloud_cover_percent"])
            except (KeyError, TypeError, ValueError) as e:
                errors.append(f"Feature {i}: missing or invalid ndvi/ndwi/cloud_cover_percent: {e}")
                invalid_rows += 1
                continue

            if not (-1 <= ndvi <= 1) or not (-1 <= ndwi <= 1) or not (0 <= cloud <= 100):
                errors.append(f"Feature {i}: values out of range ndvi={ndvi} ndwi={ndwi} cloud={cloud}")
                invalid_rows += 1
                continue

            veg_raw   = str(props.get("vegetation_health", "")).strip().upper()
            flood_raw = str(props.get("flood_risk", "")).strip().upper()
            veg_health  = VegetationHealth(veg_raw) if veg_raw in VALID_VEG_HEALTH else _derive_veg_health(ndvi)
            flood_risk  = FloodRisk(flood_raw)      if flood_raw in VALID_FLOOD_RISK else _derive_flood_risk(ndwi)
            source = _map_satellite_source(props.get("source"))

            obs = SatelliteObservation(
                farm_id=farm_id,
                crop_cycle_id=crop_cycle_id,
                observation_date=obs_date,
                ndvi=ndvi,
                ndwi=ndwi,
                vegetation_health=veg_health,
                flood_risk=flood_risk,
                cloud_cover_percent=cloud,
                source=source,
            )
            new_obs.append(obs)
            existing_dates.add(obs_date)
            inserted += 1

        except Exception as exc:
            errors.append(f"Feature {i}: {exc}")
            invalid_rows += 1

    if new_obs:
        db.bulk_save_objects(new_obs)

    if inserted > 0:
        _create_import_evidence(
            db=db,
            farm_id=farm_id,
            crop_cycle_id=crop_cycle_id,
            uploaded_by=current_user.id,
            evidence_type=EvidenceType.SATELLITE_EXPORT.value,
            file_name=file.filename or "satellite_scenes.geojson",
            file_hash=_hash_bytes(content),
            description=f"Satellite GeoJSON import: {inserted} scenes inserted",
        )

    db.commit()

    return {
        "success": True,
        "features_received": len(features),
        "rows_inserted": inserted,
        "duplicates_skipped": skipped_duplicates,
        "invalid_rows": invalid_rows,
        "errors": errors[:20],
    }
