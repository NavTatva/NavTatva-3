"""Live service integration without credentials or an external connection."""
import asyncio
import json
from datetime import datetime, timezone, timedelta


def test_key_never_in_status_or_provider_errors(monkeypatch, tmp_path):
    from app.ais import live
    monkeypatch.setattr(live, 'KEY_FILE', tmp_path / 'key')
    monkeypatch.setenv('AISSTREAM_API_KEY', 'private-example-key')
    service = live.LiveService()
    service.state = 'rejected'
    result = service.status()
    assert result['configured']
    assert 'private-example-key' not in json.dumps(result)


def test_live_window_requires_matching_time_and_place(monkeypatch, tmp_path):
    from app.ais import live
    from app.ais.recorder import Recorder
    monkeypatch.setattr(live, 'db_path', lambda: tmp_path / 'live.sqlite')
    recorder = Recorder(path=live.db_path())
    recorder.on_position({'Latitude': 28, 'Longitude': -90, 'UserID': 123456789, 'Sog': 4},
                         {'time_utc': '2025-01-01 12:00:00 +0000 UTC'})
    recorder.flush()
    recorder.conn.close()
    t = datetime(2025, 1, 1, 12, tzinfo=timezone.utc)
    assert live.recorded_window((-91, 27, -89, 29), t, t)[1]['rows'] == 1
    assert live.recorded_window((49, 39, 51, 41), t, t) == (None, None)
    assert live.recorded_window((-91, 27, -89, 29), t + timedelta(days=1), t + timedelta(days=2)) == (None, None)


def test_recorder_service_subscribes_and_flushes_on_shutdown(monkeypatch, tmp_path):
    from app.ais import live, ingest
    import websockets.asyncio.client
    monkeypatch.setenv('TIDETRACE_LIVE_AIS', '1')
    monkeypatch.setattr(live, 'read_key', lambda: 'test-key')
    monkeypatch.setattr(live, 'db_path', lambda: tmp_path / 'live.sqlite')
    monkeypatch.setattr(live, 'subscription_boxes', lambda: [[[27, -91], [29, -89]]])
    messages = [
        {'MessageType': 'SubscriptionConfirmation', 'Message': {'CompressionEnabled': True}},
        {'MessageType': 'StandardClassBPositionReport', 'MetaData': {'MMSI': 123456789},
         'Message': {'StandardClassBPositionReport': {'Latitude': 28, 'Longitude': -90, 'Valid': True}}},
    ]
    sent = []
    class Socket:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def send(self, message): sent.append(json.loads(message))
        async def recv(self):
            if messages: return json.dumps(messages.pop(0)).encode()
            await asyncio.Future()
    monkeypatch.setattr(websockets.asyncio.client, 'connect', lambda *a, **kw: Socket())
    async def check():
        service = live.LiveService()
        await service.start()
        for _ in range(100):
            if service.last_message: break
            await asyncio.sleep(.01)
        assert service.state == 'connected'
        await service.stop()
        assert service.task is None
    asyncio.run(check())
    assert sent[0]['APIKey'] == 'test-key'
    assert sent[0]['BoundingBoxes'] == [[[27, -91], [29, -89]]]
    conn = ingest.connect(live.db_path())
    assert conn.execute('SELECT source FROM positions').fetchone()[0] == 'aisstream_live'
    conn.close()


def test_upload_uses_live_store_before_historical(monkeypatch, selftest_scene, cached_metocean, tmp_path):
    from app import pipeline, scenes
    from app.ais import live, ondemand, ingest
    selftest_scene.source = 'uploaded'
    scenes.upsert([selftest_scene])
    path = tmp_path / 'live.sqlite'
    ingest.connect(path).close()
    monkeypatch.setattr(live, 'recorded_window', lambda *a:
        (path, {'status': 'live_recorded', 'message': 'Locally recorded live AIS'}))
    monkeypatch.setattr(ondemand, 'prepare', lambda *a, **kw: (_ for _ in ()).throw(AssertionError('unexpected historical fetch')))
    actual = pipeline.run_attribution
    def attribute(*a, **kw):
        assert kw['ais_path'] == path
        return actual(*a, **kw)
    monkeypatch.setattr(pipeline, 'run_attribution', attribute)
    result = pipeline.run(selftest_scene.id, prefer_model=False, ensemble_n=3, render_overlays=False)
    assert result['ais_fetch']['status'] == 'live_recorded'


def test_online_real_preset_fetches_recorded_ais(monkeypatch, selftest_scene, cached_metocean):
    from app import config, pipeline, scenes
    from app.ais import live, ondemand
    selftest_scene.ais_mode = "real"
    scenes.upsert([selftest_scene])
    monkeypatch.setattr(config, "OFFLINE", False)
    monkeypatch.setattr(live, "recorded_window", lambda *a: (None, None))
    calls = []
    def prepare(*args, **kwargs):
        calls.append(args)
        return None, {"status": "unavailable", "message": "Provider unavailable"}
    monkeypatch.setattr(ondemand, "prepare", prepare)
    result = pipeline.run(selftest_scene.id, prefer_model=False, ensemble_n=3, render_overlays=False)
    assert len(calls) == 1
    assert result["ais_fetch"]["status"] == "unavailable"
    assert result["attribution"]["suspects"] == []
