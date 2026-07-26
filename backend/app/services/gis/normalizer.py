"""
normalizer.py — Convert provider-specific scene dicts into NormalizedScene.

Every provider's raw response passes through here before being returned
to the API layer. Frontend always sees the same shape regardless of source.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ── Normalized schema ─────────────────────────────────────────────────────────

class NormalizedIndices(BaseModel):
    ndvi: Optional[float] = None
    ndwi: Optional[float] = None

    model_config = {"extra": "allow"}


class NormalizedMetadata(BaseModel):
    cloud_cover: Optional[float] = None
    source_scene_id: Optional[str] = None
    resolution_m: Optional[int] = None
    satellite: Optional[str] = None

    model_config = {"extra": "allow"}


class NormalizedScene(BaseModel):
    provider: str                          # COPERNICUS | BHUVAN | BHOONIDHI | MOCK
    is_mock: bool = False                  # True only for MOCK provider
    farm_id: Optional[int] = None
    crop_cycle_id: Optional[int] = None
    geometry: Optional[Dict[str, Any]] = None
    bbox: Optional[List[float]] = None
    observation_date: Optional[str] = None
    indices: NormalizedIndices = NormalizedIndices()
    metadata: NormalizedMetadata = NormalizedMetadata()

    model_config = {"extra": "allow"}


# ── Per-provider normalizers ──────────────────────────────────────────────────

def normalize_copernicus_scene(raw: Dict[str, Any]) -> NormalizedScene:
    """
    Normalize a Copernicus STAC Feature into NormalizedScene.
    """
    if raw.get("_mock"):
        return _normalize_mock_scene(raw)

    props  = raw.get("properties", {})
    geom   = raw.get("geometry")
    bbox   = raw.get("bbox")

    # STAC datetime field
    obs_dt = props.get("datetime") or props.get("start_datetime", "")
    obs_date = obs_dt[:10] if obs_dt else None

    cloud = props.get("eo:cloud_cover") or props.get("cloudCover")
    scene_id = raw.get("id") or props.get("title")

    return NormalizedScene(
        provider="COPERNICUS",
        is_mock=False,
        geometry=geom,
        bbox=bbox,
        observation_date=obs_date,
        indices=NormalizedIndices(ndvi=None, ndwi=None),   # Phase 13: real values
        metadata=NormalizedMetadata(
            cloud_cover=float(cloud) if cloud is not None else None,
            source_scene_id=scene_id,
            resolution_m=10,
            satellite="Sentinel-2",
        ),
    )


def normalize_bhuvan_scene(raw: Dict[str, Any]) -> NormalizedScene:
    """
    Normalize a Bhuvan WFS feature into NormalizedScene.
    Phase 13 will fill in real field mapping.
    """
    if raw.get("_mock"):
        return _normalize_mock_scene(raw)

    return NormalizedScene(
        provider="BHUVAN",
        is_mock=False,
        observation_date=raw.get("observation_date"),
        indices=NormalizedIndices(),
        metadata=NormalizedMetadata(
            cloud_cover=raw.get("cloud_cover"),
            source_scene_id=raw.get("id"),
            resolution_m=raw.get("resolution_m", 5),
            satellite="RESOURCESAT-2",
        ),
    )


def normalize_bhoonidhi_scene(raw: Dict[str, Any]) -> NormalizedScene:
    if raw.get("_mock"):
        return _normalize_mock_scene(raw)
    return NormalizedScene(
        provider="BHOONIDHI",
        is_mock=False,
        observation_date=raw.get("observation_date"),
        indices=NormalizedIndices(),
        metadata=NormalizedMetadata(
            source_scene_id=raw.get("id"),
        ),
    )


def _normalize_mock_scene(raw: Dict[str, Any]) -> NormalizedScene:
    return NormalizedScene(
        provider="MOCK",
        is_mock=True,
        observation_date=raw.get("observation_date"),
        indices=NormalizedIndices(
            ndvi=raw.get("ndvi"),
            ndwi=raw.get("ndwi"),
        ),
        metadata=NormalizedMetadata(
            cloud_cover=raw.get("cloud_cover"),
            source_scene_id=raw.get("id"),
            resolution_m=raw.get("resolution_m", 10),
            satellite=raw.get("satellite", "MOCK-SAT-2"),
        ),
    )


# ── Dispatch table ────────────────────────────────────────────────────────────

_NORMALIZERS = {
    "COPERNICUS": normalize_copernicus_scene,
    "BHUVAN":     normalize_bhuvan_scene,
    "BHOONIDHI":  normalize_bhoonidhi_scene,
    "MOCK":       _normalize_mock_scene,
}


def normalize_scene(
    provider: str,
    raw: Dict[str, Any],
    farm_id: Optional[int] = None,
    crop_cycle_id: Optional[int] = None,
) -> NormalizedScene:
    """Dispatch to the correct normalizer and attach farm context."""
    normalizer = _NORMALIZERS.get(provider, normalize_copernicus_scene)
    scene = normalizer(raw)
    scene.farm_id = farm_id
    scene.crop_cycle_id = crop_cycle_id
    return scene


def normalize_scenes(
    provider: str,
    raws: List[Dict[str, Any]],
    farm_id: Optional[int] = None,
    crop_cycle_id: Optional[int] = None,
) -> List[NormalizedScene]:
    return [normalize_scene(provider, r, farm_id, crop_cycle_id) for r in raws]
