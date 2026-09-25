"""Online preparation is explicitly invoked; tests use tiny real-format archives."""
import csv
import io
import zipfile
from datetime import datetime, timezone, timedelta

import pytest


def test_fetch_clips_caches_and_isolates_demo_store(monkeypatch, tmp_path, app_config):
    from app.ais import ondemand, ingest
    monkeypatch.setattr(app_config, 'CACHE_DIR', tmp_path)
    when = datetime(2020, 1, 1, 12, tzinfo=timezone.utc)
    calls = []
    def download(url, path, notify):
        calls.append(url)
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('ais.csv', 'MMSI,BaseDateTime,LAT,LON,SOG,COG\n'
                       '123456789,2020-01-01T12:00:00,28,-90,10,90\n'
                       '123456790,2020-01-01T12:00:00,40,-70,10,90\n'
                       '123456791,2020-01-01T01:00:00,28,-90,10,90\n')
    monkeypatch.setattr(ondemand, 'download', download)
    args = ((-91, 27, -89, 29), when - timedelta(hours=1), when + timedelta(hours=1))
    path, info = ondemand.prepare(*args)
    assert info['status'] == 'downloaded'
    assert info['rows'] == 1
    conn = ingest.connect(path)
    assert conn.execute('SELECT source FROM positions').fetchone()[0] == 'marinecadastre'
    conn.close()
    assert ondemand.prepare(*args)[1]['status'] == 'cached'
    assert len(calls) == 1
    assert set((tmp_path / 'ais_queries').iterdir()) == {path, path.with_suffix('.json')}
    reused, metadata = ondemand.cached_window((-90.5, 27.5, -89.5, 28.5), when, when)
    assert reused == path and metadata['status'] == 'cached'
    assert ondemand.cached_window((-92, 27, -89, 29), when, when) == (None, None)
    assert ondemand.cached_window(args[0], when + timedelta(days=1), when + timedelta(days=1)) == (None, None)


def test_failed_day_does_not_publish_partial_cache(monkeypatch, tmp_path, app_config):
    from app.ais import ondemand
    monkeypatch.setattr(app_config, 'CACHE_DIR', tmp_path)
    calls = []
    def download(url, path, notify):
        calls.append(url)
        if len(calls) % 2 == 0:
            raise OSError('archive missing')
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('ais.csv', 'MMSI,BaseDateTime,LAT,LON\n')
    monkeypatch.setattr(ondemand, 'download', download)
    when = datetime(2020, 1, 1, 23, tzinfo=timezone.utc)
    for _ in range(2):
        path, info = ondemand.prepare((-91, 27, -89, 29), when, when + timedelta(hours=2))
        assert path is None and info['status'] == 'unavailable'
    assert len(calls) == 4
    assert not list((tmp_path / 'ais_queries').iterdir())


def test_unsupported_coverage_never_downloads(monkeypatch):
    from app.ais import ondemand
    monkeypatch.setattr(ondemand, 'download', lambda *a: pytest.fail('unexpected download'))
    when = datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert ondemand.prepare((49, 39, 51, 41), when, when)[1]['status'] == 'unsupported'
    assert ondemand.prepare((-91, 27, -89, 29), when, when + timedelta(days=8))[1]['status'] == 'unsupported'


def test_zstd_archive(monkeypatch, tmp_path, app_config):
    zstd = pytest.importorskip('compression.zstd')
    from app.ais import ondemand
    monkeypatch.setattr(app_config, 'CACHE_DIR', tmp_path)
    monkeypatch.setattr(ondemand, 'download', lambda url, path, notify:
        path.write_bytes(zstd.compress(b'mmsi,base_date_time,latitude,longitude\n123456789,2025-01-01T12:00:00,28,-90\n')))
    when = datetime(2025, 1, 1, 12, tzinfo=timezone.utc)
    assert ondemand.prepare((-91, 27, -89, 29), when, when)[1]['rows'] == 1


def test_unknown_schema_is_not_cached_as_empty(monkeypatch, tmp_path, app_config):
    from app.ais import ondemand
    monkeypatch.setattr(app_config, 'CACHE_DIR', tmp_path)
    def download(url, path, notify):
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('bad.csv', 'unknown,columns\n1,2\n')
    monkeypatch.setattr(ondemand, 'download', download)
    when = datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert ondemand.prepare((-91, 27, -89, 29), when, when)[1]['status'] == 'unavailable'


def test_upload_requires_real_acquisition_time(app_config):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        for time in ('', 'wrong', '2020-01-01T00:00:00', '2099-01-01T00:00:00Z'):
            response = client.post('/api/scenes/upload', files={'file': ('a.tif', b'bad')}, data={'t_sat': time})
            assert response.status_code == 422


def test_download_resumes_after_disconnect(monkeypatch, tmp_path):
    from app.ais import ondemand
    payload = b'one-chunk' + b'two-chunk'
    calls = []
    class Response:
        status = 206
        def __init__(self, offset):
            self.offset = offset
            self.headers = {'Content-Range': f'bytes {offset}-17/18', 'ETag': 'same-file'}
            self.reads = 0
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size):
            self.reads += 1
            if self.offset == 0:
                if self.reads == 1: return payload[:9]
                raise ConnectionResetError('connection dropped')
            return payload[9:] if self.reads == 1 else b''
    def open_url(request, timeout):
        calls.append(request.headers['Range'])
        return Response(int(request.headers['Range'].split('=')[1].split('-')[0]))
    monkeypatch.setattr(ondemand.urllib.request, 'urlopen', open_url)
    path = tmp_path / 'download'
    ondemand.download('https://example.invalid/ais', path, lambda text: None)
    assert path.read_bytes() == payload
    assert calls[1].startswith('bytes=9-')


def test_uploaded_scene_cannot_fall_back_to_demo_ais(monkeypatch, selftest_scene, cached_metocean):
    from app import pipeline, scenes
    from app.ais import ondemand
    selftest_scene.source = 'uploaded'
    scenes.upsert([selftest_scene])
    monkeypatch.setattr(ondemand, 'prepare', lambda *a, **kw:
        (None, {'status': 'unavailable', 'message': 'No recorded AIS available'}))
    monkeypatch.setattr(pipeline, 'run_attribution', lambda *a, **kw: pytest.fail('queried demo store'))
    result = pipeline.run(selftest_scene.id, prefer_model=False, ensemble_n=3, render_overlays=False)
    assert result['ais_fetch']['status'] == 'unavailable'
    assert result['attribution']['suspects'] == []


def test_valid_upload_registers_and_rejects_optical(app_config, tmp_path, monkeypatch):
    import numpy as np
    from fastapi.testclient import TestClient
    from app.main import app
    from app.geo.raster import write_geotiff
    from app import scenes
    monkeypatch.setattr(scenes, 'upsert', lambda scene: None)
    with TestClient(app) as client:
        for bands, expected in ((2, 200), (3, 422)):
            path = tmp_path / 'image.tif'
            write_geotiff(path, np.full((bands, 16, 16), -20, dtype=np.float32),
                          (.001, 0, -90, 0, -.001, 28), 'EPSG:4326')
            response = client.post('/api/scenes/upload',
                files={'file': ('image.tif', path.read_bytes())},
                data={'t_sat': '2020-01-01T00:00:00Z'})
            assert response.status_code == expected, response.text


def test_parallel_ranges_are_assembled_in_order(monkeypatch, tmp_path):
    import time
    from app.ais import ondemand
    payload = bytes(range(256)) * 9000
    class Response:
        status = 206
        def __init__(self, first, last):
            self.headers = {'Content-Range': f'bytes {first}-{last}/{len(payload)}', 'ETag': 'same'}
            self.body = io.BytesIO(payload[first:last+1])
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return self.body.read(size)
    def open_url(request, timeout):
        first, last = map(int, request.headers['Range'].split('=')[1].split('-'))
        return Response(first, last)
    monkeypatch.setattr(ondemand.urllib.request, 'urlopen', open_url)
    path = tmp_path / 'archive'
    path.write_bytes(payload[:100])
    ondemand._download_remaining('https://example.invalid/ais', path, 100, len(payload),
                                 'same', time.monotonic(), lambda s: None)
    assert path.read_bytes() == payload


def test_completed_ranges_survive_failure_and_are_reused(monkeypatch, tmp_path):
    import time
    from app.ais import ondemand
    payload = b'x' + b'a' * 1024**2 + b'b' * 1024**2
    checkpoint = tmp_path / 'resume'
    checkpoint.mkdir()
    import json
    metadata = dict(url='https://example.invalid/ais', etag='same', total=len(payload),
                    offset=1, chunk_size=1024**2)
    (checkpoint / 'manifest.json').write_text(json.dumps(metadata))
    (checkpoint / f'1-{1024**2}.chunk').write_bytes(payload[1:1+1024**2])
    requests = []
    class Response:
        status = 206
        def __init__(self, first, last):
            self.headers = {'Content-Range': f'bytes {first}-{last}/{len(payload)}', 'ETag': 'same'}
            self.body = io.BytesIO(payload[first:last+1])
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return self.body.read(size)
    def open_url(request, timeout):
        first, last = map(int, request.headers['Range'].split('=')[1].split('-'))
        requests.append(first)
        return Response(first, last)
    monkeypatch.setattr(ondemand.urllib.request, 'urlopen', open_url)
    path = tmp_path / 'archive'
    path.write_bytes(payload[:1])
    ondemand._download_remaining(metadata['url'], path, 1, len(payload), 'same',
                                 time.monotonic(), lambda s: None, checkpoint)
    assert requests == [1024**2 + 1]
    assert path.read_bytes() == payload
    assert not checkpoint.exists()
