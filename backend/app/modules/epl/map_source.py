from __future__ import annotations

from typing import Any


def attach_map_source_image_url(project_id: str, project_uuid: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Keep EPL map_source as a coordinate frame, not a raster base map.

    The main SiteMap view follows the Ashalim path: PDF/layout coordinates are
    transformed into MapLibre pseudo lon/lat and rendered as vector layers. The
    drawing page image is not used as a map substrate, so strip any stale
    rendered image URL that may exist in persisted project metadata.
    """
    map_source = payload.get("map_source") or {}
    if not isinstance(map_source, dict):
        return payload

    map_source.pop("image_url", None)
    map_source.pop("image_error", None)
    map_source.pop("image_width_px", None)
    map_source.pop("image_height_px", None)

    payload["map_source"] = map_source
    return payload
