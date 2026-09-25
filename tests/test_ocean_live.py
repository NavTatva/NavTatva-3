"""Tests for real ocean data fetching and vector field generation."""
from __future__ import annotations

from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.drift import ocean_live
from app.main import app


def test_deg_to_compass():
    assert ocean_live.deg_to_compass(0) == "N"
    assert ocean_live.deg_to_compass(90) == "E"
    assert ocean_live.deg_to_compass(180) == "S"
    assert ocean_live.deg_to_compass(270) == "W"
    assert ocean_live.deg_to_compass(45) == "NE"
    assert ocean_live.deg_to_compass(350) == "N"


def test_fetch_live_ocean_point_structure(monkeypatch):
    sample_marine = {
        "hourly": {
            "ocean_current_velocity": [1.5, 2.0],
            "ocean_current_direction": [80.0, 85.0],
            "wave_height": [1.2, 1.4],
            "wave_period": [6.0, 6.2],
            "wave_direction": [70.0, 75.0],
        }
    }
    sample_wind = {
        "hourly": {
            "wind_speed_10m": [5.5, 6.0],
            "wind_direction_10m": [290.0, 295.0],
        }
    }

    def fake_get_json(url, params, timeout=12.0):
        if "marine" in url:
            return sample_marine
        return sample_wind

    monkeypatch.setattr(ocean_live, "_cached", lambda *a, **kw: None)
    monkeypatch.setattr(ocean_live, "_http_get_json", fake_get_json)

    t = datetime(2024, 3, 13, 1, 0, tzinfo=timezone.utc)
    res = ocean_live.fetch_live_ocean_point(19.05, 71.60, t)

    assert res["available"] is True
    assert res["lat"] == 19.05
    assert res["lon"] == 71.60
    assert res["current"]["speed_ms"] > 0
    assert res["current"]["direction_compass"] == "E" or "NE" in res["current"]["direction_compass"]
    assert res["wind"]["speed_ms"] == 6.0
    assert res["waves"]["height_m"] == 1.4


def test_fetch_ocean_vector_grid_structure(monkeypatch):
    def fake_get_json(url, params, timeout=12.0):
        return {"hourly": {"ocean_current_velocity": [1.0], "ocean_current_direction": [90.0], "wind_speed_10m": [5.0], "wind_direction_10m": [270.0]}}

    monkeypatch.setattr(ocean_live, "_cached", lambda *a, **kw: None)
    monkeypatch.setattr(ocean_live, "_http_get_json", fake_get_json)

    bbox = (71.0, 18.5, 72.0, 19.5)
    res = ocean_live.fetch_ocean_vector_grid(bbox, t=datetime(2024, 3, 13, 0, tzinfo=timezone.utc), grid_n=3)

    assert res["bbox"] == list(bbox)
    assert res["grid_n"] == 3
    assert len(res["vectors"]) == 9
    v0 = res["vectors"][0]
    assert "current" in v0
    assert "wind" in v0
    assert "speed_ms" in v0["current"]


def test_ocean_live_api_endpoints(monkeypatch):
    monkeypatch.setattr(ocean_live, "_http_get_json", lambda *a, **kw: {"hourly": {}})
    client = TestClient(app)

    # Test point query
    resp = client.get("/api/ocean/live?lat=19.05&lon=71.60")
    assert resp.status_code == 200
    data = resp.json()
    assert "current" in data
    assert "wind" in data
    assert "source" in data

    # Test field query
    resp2 = client.get("/api/ocean/field?west=71.0&south=18.5&east=72.0&north=19.5&grid_n=3")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert "vectors" in data2
    assert len(data2["vectors"]) == 9


def test_missing_ocean_data_is_not_invented(monkeypatch):
    monkeypatch.setattr(ocean_live, "_http_get_json", lambda *a, **kw: {"hourly": {}})
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(ocean_live, "_cached", lambda *a, **kw: None)
    point = ocean_live.fetch_live_ocean_point(19, 71, t)
    assert point["available"] is False
    assert point["current"]["speed_ms"] is None
    assert point["wind"]["speed_ms"] is None
    grid = ocean_live.fetch_ocean_vector_grid((70, 18, 72, 20), t, 3)
    assert all(v["current"]["u"] is None and v["wind"]["u"] is None for v in grid["vectors"])


def test_calm_and_north_are_valid_measurements(monkeypatch):
    monkeypatch.setattr(ocean_live, "_cached", lambda *a, **kw: None)
    monkeypatch.setattr(ocean_live, "_http_get_json", lambda *a, **kw: {"hourly": {
        "time": ["2024-01-01T00:00"], "ocean_current_velocity": [0],
        "ocean_current_direction": [0], "wind_speed_10m": [0], "wind_direction_10m": [0]}})
    res = ocean_live.fetch_live_ocean_point(19, 71, datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert res["current"]["available"]
    assert res["current"]["speed_ms"] == 0
    assert res["current"]["direction_deg"] == 0
    assert res["wind"]["speed_ms"] == 0


def test_cached_point_and_grid_use_same_field_without_network(monkeypatch, uniform_field):
    monkeypatch.setattr(ocean_live, "_cached", lambda *a, **kw: uniform_field)
    monkeypatch.setattr(ocean_live, "_http_get_json", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("network")))
    t = datetime(2024, 2, 14, 6, tzinfo=timezone.utc)
    point = ocean_live.fetch_live_ocean_point(19, 71.5, t)
    grid = ocean_live.fetch_ocean_vector_grid((71, 18.5, 72, 19.5), t, 3)
    assert point["mode"] == grid["mode"] == "cached"
    assert point["current"]["u"] == 1
    assert all(v["current"]["u"] == 1 for v in grid["vectors"])


def test_wrong_timestamp_is_not_replaced_by_last_hour(monkeypatch):
    monkeypatch.setattr(ocean_live, "_cached", lambda *a, **kw: None)
    monkeypatch.setattr(ocean_live, "_http_get_json", lambda *a, **kw: {"hourly": {
        "time": ["2024-01-01T00:00"], "ocean_current_velocity": [3.6], "ocean_current_direction": [90]}})
    res = ocean_live.fetch_live_ocean_point(19, 71, datetime(2024, 1, 2, tzinfo=timezone.utc))
    assert res["current"]["available"] is False


def test_calm_cache_preserves_availability_and_synthetic_provenance(tmp_path, uniform_field):
    from app.drift import fields
    uniform_field.data['u_current'][:] = 0
    uniform_field.data['v_current'][:] = 0
    uniform_field.currents_available = True
    path = tmp_path / 'calm.npz'
    fields.save_npz(path, uniform_field)
    restored = fields.load_npz(path)
    assert restored.has_currents is True
    assert restored.describe()['mean_current_ms'] == 0
    uniform_field.synthetic = True
    fields.save_npz(path, uniform_field)
    assert fields.load_npz(path).synthetic is True


def test_stale_cache_is_not_used_for_another_date(tmp_path, monkeypatch, uniform_field):
    from app.drift import fields
    from app import config
    monkeypatch.setattr(config, 'METOCEAN_DIR', tmp_path)
    monkeypatch.setattr(config, 'OPEN_METEO_LIVE', False)
    fields.save_npz(tmp_path / 'old.npz', uniform_field)
    result = fields.load_for_scene('old', 19, 71.5, datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert result.synthetic


def test_covering_cache_avoids_online_refetch(monkeypatch, tmp_path, uniform_field):
    from app import config
    from app.drift import fields
    monkeypatch.setattr(config, 'METOCEAN_DIR', tmp_path)
    monkeypatch.setattr(config, 'OFFLINE', False)
    monkeypatch.setattr(config, 'OPEN_METEO_LIVE', True)
    fields.save_npz(tmp_path / 'existing.npz', uniform_field)
    monkeypatch.setattr(fields, 'fetch_live', lambda *a: (_ for _ in ()).throw(AssertionError('unnecessary network')))
    field = fields.load_for_scene('existing', 19, 71.5, datetime(2024, 2, 14, 6, tzinfo=timezone.utc))
    assert not field.synthetic


def test_missing_cache_fetches_when_enabled(monkeypatch, tmp_path, uniform_field):
    from app import config
    from app.drift import fields
    monkeypatch.setattr(config, 'METOCEAN_DIR', tmp_path)
    monkeypatch.setattr(config, 'OFFLINE', False)
    monkeypatch.setattr(config, 'OPEN_METEO_LIVE', True)
    calls = []
    def fetch(*args):
        calls.append(args)
        return uniform_field
    monkeypatch.setattr(fields, 'fetch_live', fetch)
    assert fields.load_for_scene('new', 19, 71.5, datetime(2024, 2, 14, 6, tzinfo=timezone.utc)) is uniform_field
    assert len(calls) == 1


def test_incident_time_default_and_explicit_override(monkeypatch):
    from types import SimpleNamespace
    from app.api import ocean
    from app.drift import ocean_live
    from app.main import app
    monkeypatch.setattr(ocean.scenes_mod, "get", lambda _: SimpleNamespace(t_sat="2023-05-09T12:00:00Z"))
    monkeypatch.setattr(ocean_live, "fetch_live_ocean_point", lambda lat, lon, t, **kw: {"timestamp": t.isoformat()})
    client = TestClient(app)
    base = "/api/ocean/live?lat=20&lon=70&scene_id=incident"
    assert client.get(base).json()["timestamp"] == "2023-05-09T12:00:00+00:00"
    assert client.get(base, params={"lat":20,"lon":70,"scene_id":"incident","t": "2023-05-09T18:30:00+05:30"}).json()["timestamp"] == "2023-05-09T13:00:00+00:00"
    assert client.get(base, params={"lat":20,"lon":70,"scene_id":"incident","t": "bad-date"}).status_code == 400
    monkeypatch.setattr(ocean.scenes_mod, "get", lambda _: None)
    assert client.get(base).status_code == 404


def test_wave_archive_is_loaded_beside_cached_currents(monkeypatch, tmp_path, uniform_field):
    monkeypatch.setattr(ocean_live, '_cached', lambda *a, **k: uniform_field)
    monkeypatch.setattr(ocean_live.config, 'CACHE_DIR', tmp_path)
    monkeypatch.setattr(ocean_live.config, 'OFFLINE', False)
    monkeypatch.setattr(ocean_live.config, 'OPEN_METEO_LIVE', True)
    calls = []
    def fetch(url, params):
        calls.append(params)
        return {'hourly': {'time': ['2024-02-14T05:00'], 'wave_height': [1.2], 'wave_period': [5.1], 'wave_direction': [90]}}
    monkeypatch.setattr(ocean_live, '_http_get_json', fetch)
    t = datetime(2024, 2, 14, 5, 40, tzinfo=timezone.utc)
    for _ in range(2):
        result = ocean_live.fetch_live_ocean_point(19, 71, t)
        assert result['waves']['height_m'] == 1.2
        assert result['current']['speed_ms'] == 1.0
    assert len(calls) == 1
    assert calls[0]['start_date'] == '2024-02-14'
