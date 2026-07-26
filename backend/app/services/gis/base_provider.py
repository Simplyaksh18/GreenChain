"""
BaseSatelliteProvider — abstract interface every provider must implement.
"""
from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional


class BaseSatelliteProvider(abc.ABC):
    """
    All satellite/GIS providers must implement this interface.
    Methods return raw dicts that the Normalizer then converts to the
    unified NormalizedScene schema.
    """

    provider_name: str = "BASE"

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """Return True if all required credentials are present."""
        ...

    @abc.abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Lightweight connectivity/auth probe.
        Returns: {"ok": bool, "message": str, "provider": str}
        Must not raise — catch all exceptions internally.
        """
        ...

    # ── Data access ───────────────────────────────────────────────────────────

    @abc.abstractmethod
    def search_scenes(
        self,
        aoi_geojson: Dict[str, Any],
        start_date: str,     # ISO date "YYYY-MM-DD"
        end_date: str,       # ISO date "YYYY-MM-DD"
        cloud_cover_max: float = 30.0,
    ) -> List[Dict[str, Any]]:
        """
        Search for available scenes over an AOI.
        Returns list of raw scene dicts (provider-specific format).
        """
        ...

    @abc.abstractmethod
    def fetch_scene_metadata(self, scene_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full metadata for a specific scene_id. Returns None if not found."""
        ...

    @abc.abstractmethod
    def fetch_indices(
        self,
        scene_id: str,
        indices: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch computed spectral indices for a scene.
        Default indices: ["NDVI", "NDWI"]
        Returns raw dict; normalizer extracts index values.
        """
        ...
