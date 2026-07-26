"""
GISService — orchestrates provider selection, fallback, and normalization.

Provider priority (AUTO mode):
  1. Copernicus  — preferred (10 m Sentinel-2)
  2. Bhuvan      — Indian national archive (RESOURCESAT-2)
  3. Bhoonidhi   — NRSC archive
  4. MOCK        — only when all real providers fail AND mock fallback is enabled

Explicit provider requests:
  MOCK may be requested explicitly for admin/testing purposes.
  All other explicit providers bypass the fallback chain.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.gis.base_provider import BaseSatelliteProvider
from app.services.gis.copernicus_provider import CopernicusProvider
from app.services.gis.bhuvan_provider import BhuvanProvider
from app.services.gis.bhoonidhi_provider import BhoonidhiProvider
from app.services.gis.mock_provider import MockProvider
from app.services.gis.normalizer import (
    NormalizedScene, normalize_scenes,
)

logger = logging.getLogger(__name__)

# Singleton-per-process instances (stateless; safe to share)
_copernicus  = CopernicusProvider()
_bhuvan      = BhuvanProvider()
_bhoonidhi   = BhoonidhiProvider()
_mock        = MockProvider()

# Priority-ordered real providers
_REAL_PROVIDERS: List[BaseSatelliteProvider] = [_copernicus, _bhuvan, _bhoonidhi]
_PROVIDER_MAP: Dict[str, BaseSatelliteProvider] = {
    "COPERNICUS": _copernicus,
    "BHUVAN":     _bhuvan,
    "BHOONIDHI":  _bhoonidhi,
    "MOCK":       _mock,
}


class GISService:
    """High-level GIS operations exposed to the API layer."""

    # ── Provider status ────────────────────────────────────────────────────────

    def get_provider_status(self) -> Dict[str, Any]:
        """
        Return configuration state for all providers.
        Does NOT make network calls — config check only (fast).
        """
        mock_fallback = settings.GIS_MOCK_FALLBACK_ENABLED.lower() == "true"
        configured = [p for p in _REAL_PROVIDERS if p.is_configured()]
        active = configured[0].provider_name if configured else ("MOCK" if mock_fallback else None)

        return {
            "copernicus":     {"configured": _copernicus.is_configured()},
            "bhuvan":         {"configured": _bhuvan.is_configured()},
            "bhoonidhi":      {"configured": _bhoonidhi.is_configured()},
            "mock_fallback_enabled": mock_fallback,
            "active_provider": active,
            "mock_mode": active == "MOCK" or not configured,
        }

    def run_health_checks(self) -> Dict[str, Any]:
        """
        Run live health checks on all configured providers.
        Makes outbound HTTP calls — use only in admin contexts.
        """
        results = {}
        for p in _REAL_PROVIDERS:
            results[p.provider_name.lower()] = p.health_check()
        results["mock"] = _mock.health_check()
        return results

    # ── Scene search ──────────────────────────────────────────────────────────

    def search_scenes(
        self,
        aoi_geojson: Dict[str, Any],
        start_date: str,
        end_date: str,
        cloud_cover_max: float = 30.0,
        provider: str = "AUTO",
        farm_id: Optional[int] = None,
        crop_cycle_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Search for satellite scenes.

        provider="AUTO"  → try real providers in priority order; MOCK as last resort
        provider="MOCK"  → always use mock (for testing/admin)
        provider=<name>  → use specific provider only (no fallback)

        Returns:
          {"provider": str, "is_mock": bool, "scenes": [NormalizedScene], "count": int}
        """
        provider = provider.upper()

        if provider == "MOCK":
            raws = _mock.search_scenes(aoi_geojson, start_date, end_date, cloud_cover_max)
            return self._wrap_results("MOCK", raws, farm_id, crop_cycle_id)

        if provider != "AUTO":
            p = _PROVIDER_MAP.get(provider)
            if not p:
                raise ValueError(f"Unknown provider: {provider}")
            raws = p.search_scenes(aoi_geojson, start_date, end_date, cloud_cover_max)
            return self._wrap_results(provider, raws, farm_id, crop_cycle_id)

        # AUTO: try real providers in order
        for p in _REAL_PROVIDERS:
            if not p.is_configured():
                continue
            try:
                raws = p.search_scenes(aoi_geojson, start_date, end_date, cloud_cover_max)
                if raws:
                    logger.info("GIS AUTO: using %s (%d scenes)", p.provider_name, len(raws))
                    return self._wrap_results(p.provider_name, raws, farm_id, crop_cycle_id)
            except Exception as exc:
                logger.warning("GIS %s search failed: %s", p.provider_name, exc)

        # Fallback to MOCK
        mock_fallback = settings.GIS_MOCK_FALLBACK_ENABLED.lower() == "true"
        if mock_fallback:
            logger.info("GIS AUTO: all real providers failed/empty — using MOCK fallback")
            raws = _mock.search_scenes(aoi_geojson, start_date, end_date, cloud_cover_max)
            return self._wrap_results("MOCK", raws, farm_id, crop_cycle_id)

        return {"provider": None, "is_mock": False, "scenes": [], "count": 0,
                "error": "All configured providers returned no data"}

    # ── Indices ───────────────────────────────────────────────────────────────

    def get_indices(
        self,
        farm_id: int,
        aoi_geojson: Dict[str, Any],
        start_date: str,
        end_date: str,
        indices: Optional[List[str]] = None,
        provider: str = "AUTO",
        crop_cycle_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get NDVI/NDWI for a farm over a date range.
        For Stage A: returns scene list with pre-computed index values.
        Phase 13 will call process API per-scene.
        """
        scene_result = self.search_scenes(
            aoi_geojson=aoi_geojson,
            start_date=start_date,
            end_date=end_date,
            cloud_cover_max=50.0,
            provider=provider,
            farm_id=farm_id,
            crop_cycle_id=crop_cycle_id,
        )
        return scene_result

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _wrap_results(
        provider_name: str,
        raws: List[Dict[str, Any]],
        farm_id: Optional[int],
        crop_cycle_id: Optional[int],
    ) -> Dict[str, Any]:
        scenes = normalize_scenes(provider_name, raws, farm_id, crop_cycle_id)
        return {
            "provider": provider_name,
            "is_mock": provider_name == "MOCK",
            "scenes": [s.model_dump() for s in scenes],
            "count": len(scenes),
        }


# ── Module-level singleton ────────────────────────────────────────────────────

_service_instance: Optional[GISService] = None


def get_gis_service() -> GISService:
    global _service_instance
    if _service_instance is None:
        _service_instance = GISService()
    return _service_instance
