"""
BhoonidhiProvider — NRSC Bhoonidhi geoportal integration.

API docs: https://bhoonidhi.nrsc.gov.in/bhoonidhi/index.html

Stage A: Skeleton + health check.
         Full scene access to be implemented in Phase 13.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.services.gis.base_provider import BaseSatelliteProvider

logger = logging.getLogger(__name__)

_BHOONIDHI_BASE   = "https://bhoonidhi.nrsc.gov.in"
_HEALTH_PATH      = "/bhoonidhi/home"


class BhoonidhiProvider(BaseSatelliteProvider):
    provider_name = "BHOONIDHI"

    def is_configured(self) -> bool:
        return bool(settings.BHOONIDHI_API_KEY or (
            settings.BHOONIDHI_USERNAME and settings.BHOONIDHI_PASSWORD
        ))

    # ── Health check ──────────────────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "ok": False,
                "provider": self.provider_name,
                "message": "Bhoonidhi credentials not configured",
                "configured": False,
            }
        try:
            r = httpx.get(
                f"{_BHOONIDHI_BASE}{_HEALTH_PATH}",
                timeout=settings.GIS_PROVIDER_TIMEOUT,
                follow_redirects=True,
            )
            ok = r.status_code in (200, 302)
            return {
                "ok": ok,
                "provider": self.provider_name,
                "message": "reachable" if ok else f"HTTP {r.status_code}",
                "configured": True,
            }
        except Exception as exc:
            logger.warning("Bhoonidhi health check failed: %s", exc)
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
        # TODO Phase 13: Bhoonidhi uses a JSON API with login token
        if not self.is_configured():
            return []
        logger.info("Bhoonidhi scene_search: Phase 13 integration pending")
        return []

    # ── Scene metadata ────────────────────────────────────────────────────────

    def fetch_scene_metadata(self, scene_id: str) -> Optional[Dict[str, Any]]:
        if not self.is_configured():
            return None
        return None

    # ── Spectral indices ──────────────────────────────────────────────────────

    def fetch_indices(
        self,
        scene_id: str,
        indices: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return {}
