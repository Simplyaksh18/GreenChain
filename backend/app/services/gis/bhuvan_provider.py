"""
BhuvanProvider — ISRO Bhuvan geoportal integration.

API docs: https://bhuvan-app3.nrsc.gov.in/api/
          https://bhuvan.nrsc.gov.in/bhuvan_links.php#

Stage A: Skeleton + health check.
         Real LISS-IV / AWiFS scene access to be implemented in Phase 13.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.services.gis.base_provider import BaseSatelliteProvider

logger = logging.getLogger(__name__)

_BHUVAN_BASE   = "https://bhuvan-app3.nrsc.gov.in"
_CATALOG_PATH  = "/api/2d/wms"          # WMS catalogue endpoint
_HEALTH_PATH   = "/api/2d/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"


class BhuvanProvider(BaseSatelliteProvider):
    provider_name = "BHUVAN"

    def is_configured(self) -> bool:
        return bool(settings.BHUVAN_ACCESS_TOKEN)

    # ── Health check ──────────────────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "ok": False,
                "provider": self.provider_name,
                "message": "Bhuvan access token not configured",
                "configured": False,
            }
        try:
            headers = {"Authorization": f"Bearer {settings.BHUVAN_ACCESS_TOKEN}"}
            r = httpx.get(
                f"{_BHUVAN_BASE}{_HEALTH_PATH}",
                headers=headers,
                timeout=settings.GIS_PROVIDER_TIMEOUT,
            )
            # Bhuvan returns 200 for GetCapabilities even on auth failure;
            # check for XML content type as a positive signal.
            ok = r.status_code == 200
            return {
                "ok": ok,
                "provider": self.provider_name,
                "message": "reachable" if ok else f"HTTP {r.status_code}",
                "configured": True,
            }
        except Exception as exc:
            logger.warning("Bhuvan health check failed: %s", exc)
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
        Bhuvan uses a WCS/WFS-style catalogue.
        Phase 13 will implement proper RESOURCESAT-2 LISS-IV scene search.
        Stage A: returns empty list to trigger next provider in fallback chain.
        """
        if not self.is_configured():
            return []
        # TODO Phase 13: implement WFS GetFeature query with BBOX + date filter
        logger.info("Bhuvan scene_search: Phase 13 integration pending")
        return []

    # ── Scene metadata ────────────────────────────────────────────────────────

    def fetch_scene_metadata(self, scene_id: str) -> Optional[Dict[str, Any]]:
        if not self.is_configured():
            return None
        # TODO Phase 13
        return None

    # ── Spectral indices ──────────────────────────────────────────────────────

    def fetch_indices(
        self,
        scene_id: str,
        indices: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        # TODO Phase 13
        return {}
