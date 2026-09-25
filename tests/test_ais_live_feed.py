"""Tests for real-time AIS vessel feed, active registry, and configuration endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.ais import live
from app.main import app


def test_active_vessels_retrieval_and_filtering():
    service = live.LiveService()
    assert service.get_active_vessels() == []
    service.active_vessels[123456789] = {"mmsi": 123456789, "lat": 19, "lon": 71.5,
        "updated_at": datetime.now(timezone.utc).isoformat(), "source": "aisstream_live"}
    assert len(service.get_active_vessels((71, 18.5, 72, 19.5))) == 1
    assert service.get_active_vessels((-90, 28, -89, 29)) == []


def test_live_vessels_endpoint(monkeypatch):
    monkeypatch.setattr(live, "service", live.LiveService())
    client = TestClient(app)
    resp = client.get("/api/ais/live/vessels")
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert "vessels" in data
    assert data["vessels"] == []

    # Bounded query
    resp_bounded = client.get("/api/ais/live/vessels?west=71.0&south=18.5&east=72.0&north=19.5")
    assert resp_bounded.status_code == 200
    data_bounded = resp_bounded.json()
    assert data_bounded["count"] == 0


def test_live_configure_and_clear_endpoints(tmp_path, monkeypatch):
    from app.api import ais as ais_api
    key_file = tmp_path / "aisstream.key"
    monkeypatch.setattr(live, "KEY_FILE", key_file)
    monkeypatch.setattr(ais_api.live, "KEY_FILE", key_file)

    client = TestClient(app)

    # Configure key
    resp = client.post("/api/ais/live/configure", json={"api_key": "test_live_key_12345"})
    assert resp.status_code == 200
    assert resp.json()["configured"] is True
    assert key_file.exists()
    assert key_file.read_text(encoding="utf-8").strip() == "test_live_key_12345"

    # Clear key
    resp_clear = client.post("/api/ais/live/clear")
    assert resp_clear.status_code == 200
    assert resp_clear.json()["configured"] is False
    assert not key_file.exists()
