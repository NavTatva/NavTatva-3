"""Explicit online AIS preparation. Cache only complete, geographically clipped queries.

Daily national archives are temporary (one at a time); the app never downloads
an entire year. Missing days are failures, not evidence of an empty sea.
"""
from __future__ import annotations

import csv
import hashlib
from http.client import HTTPException
import io
import json
import shutil
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from datetime import timedelta
from pathlib import Path

from .. import config, scenes
from . import ingest

_LOCK = threading.Lock()
MAX_BYTES = 2 * 1024**3


def archive_url(day):
    if day.year >= 2025 or (day.year >= 2023 and sys.version_info >= (3, 14)):
        return f"https://noaaocm.blob.core.windows.net/ais/csv2/csv{day.year}/ais-{day:%Y-%m-%d}.csv.zst"
    return f"https://coast.noaa.gov/htdata/CMSP/AISDataHandler/{day.year}/AIS_{day:%Y_%m_%d}.zip"


def download(url, path, notify):
    started = time.monotonic()
    done = 0
    if shutil.disk_usage(path.parent).free < 3 * 1024**3:
        raise ValueError('AIS preparation needs at least 3 GiB of free temporary disk space.')
    # Bounded byte-range requests tolerate connections that drop during large
    # national files. If the server ignores ranges, restart instead of appending.
    total = None
    etag = None
    failures = 0
    while total is None or done < total:
        if time.monotonic() - started > 900:
            raise ValueError('AIS download exceeded its 15-minute time limit.')
        before = done
        try:
            headers = {'Range': f'bytes={done}-{done + 4 * 1024**2 - 1}'}
            if etag:
                headers['If-Range'] = etag
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
                ranged = response.status == 206
                if ranged:
                    content_range = response.headers.get('Content-Range', '')
                    first = int(content_range.split(' ')[1].split('-')[0])
                    if first != done:
                        raise ValueError('AIS server returned an unexpected byte range.')
                    total = int(content_range.split('/')[-1])
                else:
                    done = 0
                    total = int(response.headers.get('Content-Length') or 0) or None
                if total and total > MAX_BYTES:
                    raise ValueError('Daily AIS archive exceeds the 2 GiB download limit.')
                etag = response.headers.get('ETag') or etag
                with path.open('ab' if ranged and done else 'wb') as output:
                    while block := response.read(256 * 1024):
                        done += len(block)
                        if done > MAX_BYTES or time.monotonic() - started > 900:
                            raise ValueError('AIS download exceeded its size or 15-minute time limit.')
                        if shutil.disk_usage(path.parent).free < 1024**3:
                            raise ValueError('Less than 1 GiB free disk space remains.')
                        output.write(block)
                notify(f'Downloading AIS · {done // 1024**2} MB')
                if total is None:
                    break
                if done <= before:
                    raise OSError('AIS server returned no new archive bytes.')
                failures = 0
                if ranged and total and total - done > 8 * 1024**2:
                    try:
                        checkpoint = Path(config.CACHE_DIR) / 'ais_downloads' / hashlib.sha256(url.encode()).hexdigest()[:24]
                        _download_remaining(url, path, done, total, etag, started, notify, checkpoint)
                    except Exception as exc:
                        raise ValueError('Parallel AIS download incomplete; retry the analysis.') from exc
                    return
        except (OSError, EOFError, HTTPException):
            failures += 1
            if failures >= 3 or time.monotonic() - started > 900:
                raise
            notify(f'Retrying interrupted AIS download · {done // 1024**2} MB received')
    if total and done != total:
        raise ValueError('Incomplete AIS download; retry the analysis.')


def _download_remaining(url, path, offset, total, etag, started, notify, checkpoint=None):
    """Fetch bounded disjoint ranges concurrently; publish only a complete file."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    chunk_size = 1024 ** 2
    if checkpoint is not None:
        checkpoint = Path(checkpoint)
        expected = dict(url=url, etag=etag, total=total, offset=offset, chunk_size=chunk_size)
        manifest = checkpoint / 'manifest.json'
        try:
            previous = json.loads(manifest.read_text())
        except (OSError, ValueError):
            previous = None
        # An ETag binds all saved ranges to exactly one provider object.
        if previous != expected or not etag:
            if checkpoint.exists():
                shutil.rmtree(checkpoint)
        checkpoint.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(expected))
    stop = threading.Event()
    def fetch(first, last):
        saved = checkpoint / f'{first}-{last}.chunk' if checkpoint is not None else None
        if saved is not None and saved.exists() and saved.stat().st_size == last-first+1:
            return first, saved.read_bytes()
        error = None
        for attempt in range(3):
            if stop.is_set() or time.monotonic() - started > 900:
                raise ValueError('AIS download exceeded its 15-minute time limit.')
            headers = {'Range': f'bytes={first}-{last}'}
            if etag:
                headers['If-Range'] = etag
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
                    expected = f'bytes {first}-{last}/{total}'
                    if response.status != 206 or response.headers.get('Content-Range') != expected:
                        raise ValueError('AIS archive changed or server returned an unexpected byte range.')
                    if etag and response.headers.get('ETag') != etag:
                        raise ValueError('AIS archive changed during download.')
                    data = bytearray()
                    while len(data) < last - first + 1:
                        if stop.is_set() or time.monotonic() - started > 900:
                            raise ValueError('AIS download exceeded its 15-minute time limit.')
                        block = response.read(min(64 * 1024, last - first + 1 - len(data)))
                        if not block:
                            raise EOFError('Incomplete AIS byte range')
                        data.extend(block)
                    if saved is not None:
                        temporary = saved.with_suffix('.part')
                        temporary.write_bytes(data)
                        temporary.replace(saved)
                    return first, data
            except (OSError, EOFError, HTTPException) as exc:
                error = exc
        raise error
    done = offset
    try:
        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = {pool.submit(fetch, first, min(first + chunk_size - 1, total - 1))
                       for first in range(offset, total, chunk_size)}
            try:
                with path.open('r+b') as output:
                    for future in as_completed(futures):
                        first, block = future.result()
                        if shutil.disk_usage(path.parent).free < 1024 ** 3:
                            raise ValueError('Less than 1 GiB free disk space remains.')
                        output.seek(first)
                        output.write(block)
                        done += len(block)
                        futures.discard(future)
                        notify(f'Downloading AIS · {done // 1024**2} / {total // 1024**2} MB')
            finally:
                stop.set()
                for future in futures:
                    future.cancel()
    except Exception:
        raise
    if done != total or path.stat().st_size != total:
        raise ValueError('Incomplete AIS download; retry the analysis.')
    if checkpoint is not None:
        shutil.rmtree(checkpoint)


def clip(reader, conn, bbox, start, end, notify):
    aliases = {'latitude': 'LAT', 'longitude': 'LON', 'basedatetime': 'BaseDateTime', 'lat': 'LAT', 'lon': 'LON'}
    columns = {name: aliases.get(name.lower().replace('_', ''), name.replace('_', ''))
               for name in (reader.fieldnames or [])}
    if not {'mmsi', 'basedatetime', 'lat', 'lon'}.issubset({name.lower() for name in columns.values()}):
        raise ValueError('AIS archive has an unsupported CSV schema.')
    w, s, e, n = bbox
    batch = []
    for number, record in enumerate(reader, 1):
        if number % 500000 == 0:
            notify(f'Filtering AIS · {number:,} positions checked')
        record = {columns[key]: value for key, value in record.items() if key in columns}
        try:
            lat, lon = float(record.get('LAT', 'nan')), float(record.get('LON', 'nan'))
        except (ValueError, TypeError):
            continue
        if not (s <= lat <= n and w <= lon <= e):
            continue
        row = ingest.row_from_csv(record, 'marinecadastre')
        if row is not None and start <= row[1] <= end:
            batch.append(row)
        if len(batch) >= 20000:
            ingest.ingest_rows(conn, batch, 'marinecadastre')
            batch.clear()
    ingest.ingest_rows(conn, batch, 'marinecadastre')


def cached_window(bbox, start, end):
    """Reuse a completed query covering the required search area and padded time."""
    from datetime import datetime
    root = Path(config.CACHE_DIR) / 'ais_queries'
    for metadata_path in sorted(root.glob('*.json')):
        try:
            info = json.loads(metadata_path.read_text())
            path = metadata_path.with_suffix('.sqlite')
            w, s, e, n = info['bbox']
            if (path.exists() and w <= bbox[0] and s <= bbox[1] and e >= bbox[2] and n >= bbox[3]
                    and datetime.fromisoformat(info['start']) <= start
                    and datetime.fromisoformat(info['end']) >= end):
                return path, {**info, 'status': 'cached', 'message': ''}
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None, None


def prepare(bbox, start, end, notify=lambda message: None):
    """Return (isolated database path or None, honest availability metadata)."""
    info = {'provider': 'MarineCadastre', 'bbox': list(bbox),
            'start': start.isoformat(), 'end': end.isoformat()}
    if not scenes.in_nais_coverage(bbox):
        return None, {**info, 'status': 'unsupported', 'message':
                      'MarineCadastre does not cover this release area. No simulated vessels were substituted.'}
    if start.year < 2015 or (end - start).total_seconds() > 7 * 86400:
        return None, {**info, 'status': 'unsupported', 'message':
                      'Automatic AIS fetching supports daily archives from 2015 and windows up to seven days.'}
    if bbox[0] < -180 or bbox[2] > 180 or bbox[0] > bbox[2]:
        return None, {**info, 'status': 'unsupported', 'message': 'AIS fetching across the date line is not supported.'}
    root = Path(config.CACHE_DIR) / 'ais_queries'
    root.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps(info, sort_keys=True).encode()).hexdigest()[:24]
    dest = root / (key + '.sqlite')
    notify('Preparing recorded AIS for the release area')
    with _LOCK:
        if dest.exists():
            return dest, {**info, 'status': 'cached', 'message': ''}
        try:
            with tempfile.TemporaryDirectory(dir=root) as temporary:
                folder = Path(temporary)
                conn = ingest.connect(folder / 'query.sqlite')
                try:
                    day = start.date()
                    while day <= end.date():
                        url = archive_url(day)
                        notify(f'Fetching recorded AIS for {day}; the first run may take several minutes')
                        archive = folder / ('day.zst' if url.endswith('.zst') else 'day.zip')
                        download(url, archive, notify)
                        if url.endswith('.zst'):
                            try:
                                from compression import zstd
                                stream = zstd.open(archive, 'rt', encoding='utf-8-sig', newline='')
                            except ImportError:
                                raise ValueError('2025+ AIS archives require Python 3.14 or newer.')
                            with stream:
                                clip(csv.DictReader(stream), conn, bbox, int(start.timestamp()), int(end.timestamp()), notify)
                        else:
                            with zipfile.ZipFile(archive) as zipped:
                                names = [name for name in zipped.namelist() if name.lower().endswith('.csv')]
                                if not names:
                                    raise ValueError('AIS archive contains no CSV data.')
                                for name in names:
                                    with zipped.open(name) as raw:
                                        clip(csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8-sig')), conn,
                                             bbox, int(start.timestamp()), int(end.timestamp()), notify)
                        archive.unlink()
                        day += timedelta(days=1)
                    count = conn.execute('SELECT COUNT(*) FROM positions').fetchone()[0]
                finally:
                    conn.close()
                (folder / 'query.sqlite').replace(dest)
            dest.with_suffix('.json').write_text(json.dumps({**info, 'rows': count}))
            return dest, {**info, 'status': 'downloaded', 'rows': count,
                          'message': f'Fetched {count:,} recorded AIS positions for this area and time.'}
        except Exception as exc:
            return None, {**info, 'status': 'unavailable', 'message':
                          f'Recorded AIS could not be fetched: {exc}. Retry Run analysis; completed download chunks are retained for retry; incomplete AIS records are never published.'}
