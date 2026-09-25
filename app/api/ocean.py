"""Endpoints for real-time ocean data, surface currents, winds, and vector fields."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .. import config, scenes as scenes_mod
from ..drift import ocean_live

router = APIRouter(tags=["ocean"])


class OceanRefreshRequest(BaseModel):
    scene_id: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    t: Optional[str] = None


@router.get("/api/ocean/live")
def get_live_ocean(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
    t: Optional[str] = Query(None, description="ISO timestamp UTC, defaults to scene observation time, or now without a scene"),
    scene_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Fetch current sea conditions (surface currents, 10m wind, waves) from Copernicus Marine & ERA5."""
    target_dt: Optional[datetime] = None
    if scene_id:
        scene = scenes_mod.get(scene_id)
        if scene is None:
            raise HTTPException(404, "Unknown scene")
        t = t or scene.t_sat
    if t:
        try:
            target_dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
            target_dt = target_dt.replace(tzinfo=timezone.utc) if target_dt.tzinfo is None else target_dt.astimezone(timezone.utc)
        except ValueError:
            raise HTTPException(400, "Invalid ISO timestamp")

    return ocean_live.fetch_live_ocean_point(lat, lon, target_dt, scene_id=scene_id)


@router.get("/api/ocean/field")
def get_ocean_field(
    scene_id: Optional[str] = Query(None, description="Scene identifier to determine bounding box"),
    west: Optional[float] = Query(None),
    south: Optional[float] = Query(None),
    east: Optional[float] = Query(None),
    north: Optional[float] = Query(None),
    grid_n: int = Query(6, ge=3, le=12, description="Grid points per axis"),
    t: Optional[str] = Query(None, description="ISO timestamp UTC"),
) -> Dict[str, Any]:
    """Fetch a spatial grid of current and wind vectors over a scene or bounding box."""
    bbox = None
    target_dt = None

    if scene_id:
        scene = scenes_mod.get(scene_id)
        if scene:
            bbox = tuple(scene.bounds)
            if not t and scene.t_sat:
                t = scene.t_sat

    if bbox is None:
        if None in (west, south, east, north):
            # Default to active default scene or global default
            default_scenes = scenes_mod.all_scenes()
            if default_scenes:
                bbox = tuple(default_scenes[0].bounds)
            else:
                bbox = (71.0, 18.5, 72.0, 19.5)
        else:
            bbox = (float(west), float(south), float(east), float(north))

    if t:
        try:
            target_dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
            target_dt = target_dt.replace(tzinfo=timezone.utc) if target_dt.tzinfo is None else target_dt.astimezone(timezone.utc)
        except ValueError:
            raise HTTPException(400, "Invalid ISO timestamp")

    return ocean_live.fetch_ocean_vector_grid(bbox, target_dt, grid_n=grid_n, scene_id=scene_id)


@router.post("/api/ocean/refresh")
def refresh_ocean_cube(req: OceanRefreshRequest) -> Dict[str, Any]:
    """Trigger a live fetch and cache update of real metocean cube for a scene."""
    scene = scenes_mod.get(req.scene_id)
    lat = req.lat
    lon = req.lon
    t_center = None

    if scene:
        lon = lon if lon is not None else scene.centroid[0]
        lat = lat if lat is not None else scene.centroid[1]
        t_center = datetime.fromisoformat(scene.t_sat.replace("Z", "+00:00"))

    if req.t:
        try:
            t_center = datetime.fromisoformat(req.t.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(400, "Invalid ISO timestamp")

    if lat is None or lon is None:
        raise HTTPException(400, "lat and lon or valid scene_id required")

    t_center = t_center or datetime.now(timezone.utc)
    res = ocean_live.ensure_real_metocean_cube(req.scene_id, lat, lon, t_center)
    return res
