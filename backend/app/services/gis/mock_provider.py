"""
MockProvider — fallback / testing provider.

Policy:
- Only used when ALL real providers fail or are unconfigured.
- Returns realistic normalized data so UI remains functional during development.
- Responses include provider="MOCK" so clients can distinguish them.
- Never silently substituted for a real provider that returned data.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.services.gis.base_provider import BaseSatelliteProvider


class MockProvider(BaseSatelliteProvider):
    provider_name = "MOCK"

    def is_configured(self) -> bool:
        # Mock is always "configured" but should only be used as last resort.
        return True

    def health_check(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "provider": self.provider_name,
            "message": "Mock provider always healthy (fallback only)",
            "configured": True,
        }

    def search_scenes(
        self,
        aoi_geojson: Dict[str, Any],
        start_date: str,
        end_date: str,
        cloud_cover_max: float = 30.0,
    ) -> List[Dict[str, Any]]:
        """Generate 2–3 realistic mock scenes for the requested window."""
        scenes = []
        try:
            sd = date.fromisoformat(start_date)
            ed = date.fromisoformat(end_date)
        except ValueError:
            sd = date.today() - timedelta(days=5)
            ed = date.today()

        delta = max(1, (ed - sd).days)
        for i in range(min(3, max(1, delta // 3))):
            obs_date = sd + timedelta(days=i * (delta // 3))
            scenes.append({
                "_mock": True,
                "id": f"MOCK_SCENE_{obs_date.isoformat()}_{i}",
                "observation_date": obs_date.isoformat(),
                "cloud_cover": round(random.uniform(2.0, min(cloud_cover_max, 25.0)), 1),
                "ndvi": round(random.uniform(0.35, 0.75), 4),
                "ndwi": round(random.uniform(0.10, 0.45), 4),
                "resolution_m": 10,
                "satellite": "MOCK-SAT-2",
            })
        return scenes

    def fetch_scene_metadata(self, scene_id: str) -> Optional[Dict[str, Any]]:
        return {
            "_mock": True,
            "id": scene_id,
            "satellite": "MOCK-SAT-2",
            "resolution_m": 10,
            "cloud_cover": round(random.uniform(2.0, 20.0), 1),
        }

    def fetch_indices(
        self,
        scene_id: str,
        indices: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return {
            "_mock": True,
            "scene_id": scene_id,
            "ndvi": round(random.uniform(0.35, 0.75), 4),
            "ndwi": round(random.uniform(0.10, 0.45), 4),
        }
