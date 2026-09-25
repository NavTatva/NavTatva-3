"""Observation-time ocean fields, shared with drift; missing data stays missing."""
from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

from .. import config
from . import fields as fields_mod

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
WIND_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
WIND_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
KMH_TO_MS = 1000.0 / 3600.0
MS_TO_KNOTS = 1.94384


def _http_get_json(url, params, timeout=12.0):
    # Open-Meteo coordinates are comma-separated, not repeated query keys.
    params = {k: ",".join(map(str, v)) if isinstance(v, (list, tuple)) else v
              for k, v in params.items()}
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": f"NavTatva/{config.VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def deg_to_compass(degrees):
    return ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"][int(degrees / 22.5 + .5) % 16]


def _utc(t):
    t = t or datetime.now(timezone.utc)
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)


def _vector(speed=None, direction=None, wind=False):
    if speed is None or direction is None or not np.isfinite([speed, direction]).all():
        return dict(available=False, speed_ms=None, speed_knots=None, direction_deg=None,
                    direction_compass=None, u=None, v=None)
    rad = math.radians(direction)
    sign = -1 if wind else 1
    return dict(available=True, speed_ms=round(speed, 3),
                speed_knots=round(speed * MS_TO_KNOTS, 2), direction_deg=round(direction, 1),
                direction_compass=deg_to_compass(direction),
                u=round(sign * speed * math.sin(rad), 4),
                v=round(sign * speed * math.cos(rad), 4))


def _hour_value(block, variable, t):
    hourly = block.get("hourly") or {}
    times = hourly.get("time")
    values = hourly.get(variable) or []
    if times:
        target = t.strftime("%Y-%m-%dT%H:00")
        if target not in times:
            return None
        idx = times.index(target)
    else:
        idx = t.hour
    if idx >= len(values) or values[idx] is None:
        return None
    value = float(values[idx])
    return value if math.isfinite(value) else None


def _cached(lat, lon, t, scene_id=None):
    paths = sorted(config.METOCEAN_DIR.glob("*.npz"))
    if scene_id:
        preferred = config.METOCEAN_DIR / (scene_id + ".npz")
        paths = [preferred] + [p for p in paths if p != preferred]
    for path in paths:
        try:
            field = fields_mod.load_npz(path)
            if not field.synthetic and field.covers(lat, lon, t):
                return field
        except (OSError, ValueError, KeyError):
            continue
    return None


def _sample(field, lat, lon, t):
    if not field.covers(lat, lon, t):
        return {"current": _vector(), "wind": _vector()}
    data = field.sample(lat, lon, t)
    out = {}
    for name, uk, vk in (("current", "u_current", "v_current"), ("wind", "u_wind10", "v_wind10")):
        u, v = float(data[uk][0]), float(data[vk][0])
        if name == "current" and not field.has_currents:
            out[name] = _vector()
        else:
            direction = math.degrees(math.atan2(-u if name == "wind" else u,
                                                -v if name == "wind" else v)) % 360
            out[name] = _vector(math.hypot(u, v), direction, wind=name == "wind")
    return out


def _incident_waves(lat, lon, t):
    """Cache daily wave fields separately from the drift velocity cube."""
    date = t.date().isoformat()
    cache = Path(config.CACHE_DIR) / "waves" / f"{lat:.4f}_{lon:.4f}_{date}.json"
    marine = None
    try:
        marine = json.loads(cache.read_text())
    except (OSError, ValueError):
        pass
    if marine is None and not config.OFFLINE and config.OPEN_METEO_LIVE:
        marine = _http_get_json(MARINE_URL, dict(latitude=round(lat,4), longitude=round(lon,4),
            start_date=date, end_date=date, timezone="UTC",
            hourly="wave_height,wave_period,wave_direction"))
        if any(v is not None for v in (marine.get("hourly", {}).get("wave_height") or [])):
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(marine))
    return {dest: _hour_value(marine or {}, var, t) for dest, var in
            (("height_m", "wave_height"), ("period_s", "wave_period"), ("direction_deg", "wave_direction"))}


def fetch_live_ocean_point(lat, lon, t=None, scene_id=None):
    t_target = _utc(t)
    out = dict(lat=round(lat, 4), lon=round(lon, 4), timestamp=t_target.isoformat(),
               source="Open-Meteo Marine / ECMWF", mode="provider", available=False,
               current=_vector(), wind=_vector(wind=True),
               waves=dict(height_m=None, period_s=None, direction_deg=None),
               sea_surface_temperature_c=None)
    field = _cached(lat, lon, t_target, scene_id) if t is not None else None
    if field is not None:
        out.update(_sample(field, lat, lon, t_target), source=field.source, mode="cached")
        try:
            out["waves"] = _incident_waves(lat, lon, t_target)
        except (OSError, ValueError, KeyError):
            out["wave_error"] = "Wave archive request failed."
        if out["waves"]["height_m"] is not None:
            out["waves"]["source"] = "Open-Meteo Marine · DWD / Météo-France"
            out["waves"]["timestamp"] = t_target.replace(minute=0, second=0, microsecond=0).isoformat()
    else:
        date = t_target.date().isoformat()
        params = dict(latitude=round(lat, 4), longitude=round(lon, 4), timezone="UTC",
                      start_date=date, end_date=date)
        try:
            marine = _http_get_json(MARINE_URL, {**params,
                "hourly": "ocean_current_velocity,ocean_current_direction,wave_height,wave_period,wave_direction"})
            speed = _hour_value(marine, "ocean_current_velocity", t_target)
            out["current"] = _vector(None if speed is None else speed * KMH_TO_MS,
                                    _hour_value(marine, "ocean_current_direction", t_target))
            for dest, var in (("height_m", "wave_height"), ("period_s", "wave_period"),
                              ("direction_deg", "wave_direction")):
                out["waves"][dest] = _hour_value(marine, var, t_target)
        except Exception:
            out["current_error"] = "Marine provider did not return data for this location and time."
        try:
            url = WIND_FORECAST_URL if (datetime.now(timezone.utc) - t_target).days < 6 else WIND_ARCHIVE_URL
            wind = _http_get_json(url, {**params, "hourly": "wind_speed_10m,wind_direction_10m",
                                       "wind_speed_unit": "ms"})
            out["wind"] = _vector(_hour_value(wind, "wind_speed_10m", t_target),
                                 _hour_value(wind, "wind_direction_10m", t_target), wind=True)
        except Exception:
            out["wind_error"] = "Wind provider did not return data for this location and time."
    out["available"] = out["current"]["available"] or out["wind"]["available"]
    if not out["current"]["available"]:
        out["current_error"] = out.get("current_error", "No current coverage in the observation-time field; drift uses wind only.")
    return out


def fetch_ocean_vector_grid(bbox, t=None, grid_n=6, scene_id=None):
    w, s, e, n = bbox
    target = _utc(t)
    points = [(round(float(la), 4), round(float(lo), 4))
              for la in np.linspace(s, n, grid_n) for lo in np.linspace(w, e, grid_n)]
    field = _cached((s+n)/2, (w+e)/2, target, scene_id) if t is not None else None
    vectors = [dict(lat=la, lon=lo, current=_vector(), wind=_vector()) for la, lo in points]
    errors = {}
    if field is not None:
        for vector in vectors:
            vector.update(_sample(field, vector["lat"], vector["lon"], target))
    else:
        date = target.date().isoformat()
        params = dict(latitude=[p[0] for p in points], longitude=[p[1] for p in points],
                      timezone="UTC", start_date=date, end_date=date)
        wind_url = WIND_FORECAST_URL if (datetime.now(timezone.utc)-target).days < 6 else WIND_ARCHIVE_URL
        for kind, url, speed_var, dir_var, factor in (
            ("current", MARINE_URL, "ocean_current_velocity", "ocean_current_direction", KMH_TO_MS),
            ("wind", wind_url, "wind_speed_10m", "wind_direction_10m", 1)):
            try:
                payload = _http_get_json(url, {**params, "hourly": speed_var + "," + dir_var,
                    **({"wind_speed_unit": "ms"} if kind == "wind" else {})})
                blocks = payload if isinstance(payload, list) else [payload]
                for vector, block in zip(vectors, blocks):
                    speed = _hour_value(block, speed_var, target)
                    vector[kind] = _vector(None if speed is None else speed * factor,
                                          _hour_value(block, dir_var, target), wind=kind == "wind")
            except Exception:
                errors[kind] = "Provider data unavailable for this location and time."
    return dict(bbox=list(bbox), timestamp=target.isoformat(), grid_n=grid_n, vectors=vectors,
                source=field.source if field else "Open-Meteo Marine / ECMWF",
                mode="cached" if field else "provider", errors=errors)


def ensure_real_metocean_cube(
    scene_id: str,
    lat0: float,
    lon0: float,
    t_center: datetime,
    back_h: int = 72,
    fwd_h: int = 48,
    out_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Fetch and freeze a real ocean cube covering the given centre and window."""
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "_metocean_builder", config.ROOT_DIR / "scripts" / "build_metocean_cache.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        res = mod.build_box(
            scene_id=scene_id,
            lat=lat0,
            lon=lon0,
            t_center=t_center,
            half_deg=1.0,
            n=5,
            back_h=back_h,
            fwd_h=fwd_h,
            out_dir=out_dir or config.METOCEAN_DIR,
            currents="auto",
        )
        return res
    except Exception as exc:
        return {"scene_id": scene_id, "error": str(exc), "currents_available": False}
