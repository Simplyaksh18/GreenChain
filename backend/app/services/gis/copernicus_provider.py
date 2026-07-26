"""
CopernicusProvider — Sentinel Hub / Copernicus Data Space integration.

Docs: https://documentation.dataspace.copernicus.eu/APIs/SentinelHub.html

Stage A: Skeleton + health check.
         Real scene-search uses OGC/STAC API (catalogue.dataspace.copernicus.eu).
         Full response parsing to be completed in Phase 13.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.services.gis.base_provider import BaseSatelliteProvider

logger = logging.getLogger(__name__)

_CATALOG_URL = "https://catalogue.dataspace.copernicus.eu/stac/collections/SENTINEL-2/items"
_AUTH_URL    = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"


class CopernicusProvider(BaseSatelliteProvider):
    provider_name = "COPERNICUS"

    def is_configured(self) -> bool:
        return bool(settings.COPERNICUS_API_KEY and settings.COPERNICUS_API_SECRET)

    # ── Health check ──────────────────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "ok": False,
                "provider": self.provider_name,
                "message": "Copernicus credentials not configured",
                "configured": False,
            }
        try:
            # Probe the STAC root — lightweight, no auth required
            r = httpx.get(
                "https://catalogue.dataspace.copernicus.eu/stac",
                timeout=settings.GIS_PROVIDER_TIMEOUT,
            )
            ok = r.status_code == 200
            return {
                "ok": ok,
                "provider": self.provider_name,
                "message": "reachable" if ok else f"HTTP {r.status_code}",
                "configured": True,
            }
        except Exception as exc:
            logger.warning("Copernicus health check failed: %s", exc)
            return {
                "ok": False,
                "provider": self.provider_name,
                "message": str(exc),
                "configured": True,
            }

    # ── Scene search ──────────────────────────────────────────────────────────

    def search_scenes(
        self,
        aoi_geojson: Dict[str, Any],
        start_date: str,
        end_date: str,
        cloud_cover_max: float = 30.0,
    ) -> List[Dict[str, Any]]:
        """
        STAC search for Sentinel-2 scenes over the AOI.
        Returns list of STAC Feature dicts on success, empty list on failure.
        """
        if not self.is_configured():
            return []
        try:
            payload = {
                "bbox": _geojson_to_bbox(aoi_geojson),
                "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
                "collections": ["SENTINEL-2"],
                "query": {
                    "eo:cloud_cover": {"lte": cloud_cover_max},
                },
                "limit": 10,
            }
            r = httpx.post(
                "https://catalogue.dataspace.copernicus.eu/stac/search",
                json=payload,
                timeout=settings.GIS_PROVIDER_TIMEOUT,
            )
            r.raise_for_status()
            return r.json().get("features", [])
        except Exception as exc:
            logger.warning("Copernicus scene search failed: %s", exc)
            return []

    # ── Scene metadata ────────────────────────────────────────────────────────

    def fetch_scene_metadata(self, scene_id: str) -> Optional[Dict[str, Any]]:
        if not self.is_configured():
            return None
        try:
            r = httpx.get(
                f"https://catalogue.dataspace.copernicus.eu/stac/collections/SENTINEL-2/items/{scene_id}",
                timeout=settings.GIS_PROVIDER_TIMEOUT,
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.warning("Copernicus fetch_scene_metadata failed: %s", exc)
            return None

    # ── Spectral indices ──────────────────────────────────────────────────────

    def fetch_indices(
        self,
        scene_id: str,
        indices: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Phase 13: will call Sentinel Hub Process API to compute NDVI/NDWI.
        Phase 12 Stage A: returns placeholder dict so normalizer can handle it.
        """
        # Sentinel Hub Process API requires an evalscript + access token.
        # Token exchange via client-credentials using API key+secret is
        # implemented in Phase 13. Returning empty dict causes normalizer
        # to produce None indices (handled gracefully).
        logger.info(
            "Copernicus fetch_indices: scene_id=%s — Phase 13 integration pending",
            scene_id,
        )
        return {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _geojson_to_bbox(geojson: Dict[str, Any]) -> List[float]:
    """Extract [min_lon, min_lat, max_lon, max_lat] from a GeoJSON Polygon."""
    coords: List[List[float]] = []
    gtype = geojson.get("type", "")
    if gtype == "Polygon":
        coords = geojson["coordinates"][0]
    elif gtype == "Feature":
        coords = geojson["geometry"]["coordinates"][0]
    elif gtype == "Point":
        lon, lat = geojson["coordinates"]
        # Buffer ~0.05° (~5 km) around point
        return [lon - 0.05, lat - 0.05, lon + 0.05, lat + 0.05]
    if not coords:
        return [0, 0, 0, 0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return [min(lons), min(lats), max(lons), max(lats)]
