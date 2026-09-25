"""App-managed live AIS recording, isolated from simulated demo positions."""
from __future__ import annotations

import asyncio
import json
import math
import os
import random
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .. import config, scenes
from .recorder import Recorder

WS_URL = 'wss://stream.aisstream.io/v0/stream'
KEY_FILE = Path.home() / '.config' / 'navtatva' / 'aisstream.key'


def read_key():
    key = os.environ.get('AISSTREAM_API_KEY', '').strip()
    if key:
        return key
    try:
        return KEY_FILE.read_text().strip()
    except OSError:
        return ''


def save_key(api_key: str) -> bool:
    """Save an AISStream API key safely to the user's config directory."""
    api_key = api_key.strip()
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(api_key)
    return True


def db_path():
    return Path(config.AIS_DIR) / 'live.sqlite'


def subscription_boxes():
    boxes = []
    for scene in scenes.all_scenes():
        if scene.selftest:
            continue
        w, s, e, n = scene.bounds
        box = [[max(-90, s - 2), max(-180, w - 2)],
               [min(90, n + 2), min(180, e + 2)]]
        if box not in boxes:
            boxes.append(box)
    return boxes


class LiveService:
    def __init__(self):
        self.state = 'not_configured'
        self.last_message = None
        self.written = 0
        self.boxes = 0
        self.task = None
        self.active_vessels: Dict[int, Dict[str, Any]] = {}

    def get_active_vessels(self, bbox: Optional[Tuple[float, float, float, float]] = None) -> List[Dict[str, Any]]:
        """Return currently tracked real-time vessels, optionally clipped to bbox."""
        out = []
        now_ts = datetime.now(timezone.utc).timestamp()
        for v in self.active_vessels.values():
            try:
                t_v = datetime.fromisoformat(v["updated_at"].replace("Z", "+00:00")).timestamp()
                if now_ts - t_v > 3600:
                    continue
            except Exception:
                pass
            if bbox:
                w, s, e, n = bbox
                if not (s <= v["lat"] <= n and w <= v["lon"] <= e):
                    continue
            clean_v = {k: val for k, val in v.items() if not k.startswith("_")}
            out.append(clean_v)
        return out

    def status(self):
        key = read_key()
        return {'state': self.state, 'configured': bool(key),
                'last_message': self.last_message, 'positions_this_session': self.written,
                'areas': self.boxes,
                'active_vessels': len(self.get_active_vessels()),
                'mode': 'aisstream_live' if bool(key) else 'not_configured',
                'message': {
                    'not_configured': 'Live AIS needs an AISStream API key.',
                    'connecting': 'Connecting to AISStream…',
                    'connected': 'Live AIS connected; recording incoming vessel positions.',
                    'retrying': 'Live AIS connection interrupted; reconnecting.',
                    'rejected': 'AISStream rejected the subscription. Check the API key and account limits.',
                    'idle': 'Add an observation to choose an area to monitor.',
                    'unavailable': 'Live AIS dependency or storage is unavailable.',
                    'stopped': 'Live AIS recorder stopped.',
                }.get(self.state, self.state)}

    async def run(self):
        attempt = 0
        while True:
            if os.environ.get('TIDETRACE_LIVE_AIS', '1') == '0':
                self.state = 'stopped'
                await asyncio.sleep(5)
                continue
            key = read_key()
            boxes = subscription_boxes()
            self.boxes = len(boxes)
            if not key or not boxes:
                self.state = 'not_configured' if not key else 'idle'
                await asyncio.sleep(2.5)
                continue
            rec = None
            previous_written = self.written
            try:
                from websockets.asyncio.client import connect
                rec = Recorder(path=db_path())
                self.state = 'connecting'
                async with connect(WS_URL, compression='deflate', ping_interval=20,
                                   ping_timeout=20, open_timeout=15) as ws:
                    def subscription():
                        return json.dumps({'APIKey': key, 'BoundingBoxes': boxes,
                            'FilterMessageTypes': ['PositionReport', 'StandardClassBPositionReport',
                                'ExtendedClassBPositionReport', 'ShipStaticData']})
                    await ws.send(subscription())
                    last_flush = last_check = time.monotonic()
                    while True:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=2)
                        except asyncio.TimeoutError:
                            raw = None
                        if raw:
                            payload = json.loads(raw)
                            if 'error' in payload or 'Error' in payload:
                                self.state = 'rejected'
                                break
                            kind = payload.get('MessageType')
                            meta = payload.get('MetaData') or {}
                            body = (payload.get('Message') or {}).get(kind) or {}
                            if kind == 'SubscriptionConfirmation':
                                self.state = 'connected'
                                attempt = 0
                            elif kind in ('PositionReport', 'StandardClassBPositionReport', 'ExtendedClassBPositionReport'):
                                if body.get('Valid') is not False:
                                    rec.on_position(body, meta)
                                    mmsi = meta.get("MMSI") or body.get("UserID")
                                    lat = body.get("Latitude", meta.get("Latitude"))
                                    lon = body.get("Longitude", meta.get("Longitude"))
                                    if mmsi and lat is not None and lon is not None:
                                        heading = body.get("TrueHeading")
                                        self.active_vessels[int(mmsi)] = {
                                            "mmsi": int(mmsi),
                                            "name": (meta.get("ShipName") or "").strip() or f"MMSI {mmsi}",
                                            "type": str(meta.get("ShipType") or body.get("Type") or "70"),
                                            "lat": float(lat),
                                            "lon": float(lon),
                                            "sog": float(body.get("Sog") or 0.0),
                                            "cog": float(body.get("Cog") or 0.0),
                                            "heading": float(heading) if heading is not None and heading != 511 else None,
                                            "status": str(body.get("NavigationalStatus") or "0"),
                                            "updated_at": datetime.now(timezone.utc).isoformat(),
                                            "source": "aisstream_live",
                                        }
                                    self.last_message = datetime.now(timezone.utc).isoformat()
                                    self.state = 'connected'
                            elif kind == 'ShipStaticData':
                                rec.on_static(body, meta)
                                mmsi = meta.get("MMSI") or body.get("UserID")
                                if mmsi and int(mmsi) in self.active_vessels:
                                    v = self.active_vessels[int(mmsi)]
                                    v["name"] = (body.get("Name") or meta.get("ShipName") or v["name"]).strip()
                                    v["type"] = str(body.get("Type") or v["type"])
                        now = time.monotonic()
                        if now - last_flush >= 2:
                            rec.flush()
                            self.written = previous_written + rec.written
                            last_flush = now
                        if now - last_check >= 5:
                            if read_key() != key:
                                break
                            new_boxes = subscription_boxes()
                            if new_boxes and new_boxes != boxes:
                                boxes = new_boxes
                                self.boxes = len(boxes)
                                await ws.send(subscription())
                            last_check = now
                if self.state != 'rejected':
                    self.state = 'retrying'
            except asyncio.CancelledError:
                raise
            except ImportError:
                self.state = 'unavailable'
            except Exception:
                # Never return raw provider errors: they can echo subscriptions.
                self.state = 'retrying'
            finally:
                if rec is not None:
                    try:
                        rec.flush()
                        self.written = previous_written + rec.written
                    except Exception:
                        self.state = 'unavailable'
                    finally:
                        rec.conn.close()
            attempt += 1
            await asyncio.sleep(min(30, 2 ** min(attempt, 5)) + random.random())

    async def start(self):
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.run())

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        self.state = 'stopped'


service = LiveService()


def recorded_window(bbox, start, end):
    """Never present a currently connected stream as proof of historical coverage."""
    path = db_path()
    if not path.exists():
        return None, None
    w, s, e, n = bbox
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as conn:
        count, first, last = conn.execute(
            "SELECT COUNT(*), MIN(ts), MAX(ts) FROM positions WHERE source='aisstream_live' "
            'AND ts BETWEEN ? AND ? AND lon BETWEEN ? AND ? AND lat BETWEEN ? AND ?',
            (int(start.timestamp()), int(end.timestamp()), w, e, s, n)).fetchone()
    if not count:
        return None, None
    return path, {'provider': 'AISStream', 'status': 'live_recorded', 'rows': count,
                  'start': start.isoformat(), 'end': end.isoformat(), 'bbox': list(bbox),
                  'first_record': datetime.fromtimestamp(first, timezone.utc).isoformat(),
                  'last_record': datetime.fromtimestamp(last, timezone.utc).isoformat(),
                  'message': f'Using {count:,} locally recorded live AIS positions. Reception may have gaps; these records do not establish complete coverage of the search window.'}
