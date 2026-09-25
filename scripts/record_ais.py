"""Record live AIS into the store, so a spill detected today has real traffic.

The problem statement allows synthetic traffic where real tracks are not
available, and the Caspian and Arabian Sea scenes use it, honestly labelled.
This is the other half of that: a recorder, so the "real AIS if available"
branch is genuinely available for anything observed from now on.

It is a recorder and not a fetcher, and the distinction matters. A live feed
cannot produce history: the demo scenes are 2023 and 2024 Sentinel-1
acquisitions, and no amount of streaming today will yield vessel positions from
then. What this does is what an operational system does -- it has been
recording, so when a slick is found the traffic around its origin window is
already on disk.

Positions are written through `row_from_csv` in the same 16-column
MarineCadastre shape as every other source, with `source='aisstream_live'`, so
the scorer cannot tell them apart and the provenance is still auditable.

The key is read from the environment and is never written anywhere:

    export AISSTREAM_API_KEY=...        # or pass --api-key
    python scripts/record_ais.py --all --minutes 30
    python scripts/record_ais.py --scene caspian_baku_seeps --minutes 120
    python scripts/record_ais.py --bbox 71.4 18.9 71.8 19.2 --minutes 10
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import scenes as scenes_mod            # noqa: E402
from app.ais import ingest as ais_ingest        # noqa: E402

WS_URL = "wss://stream.aisstream.io/v0/stream"
SOURCE = "aisstream_live"

from app.ais.recorder import Recorder, _dims, _meta_time, _text, _imo


async def run(api_key: str, boxes: List[List[List[float]]], minutes: float,
              rec: Recorder) -> None:
    import websockets

    deadline = time.time() + minutes * 60.0
    subscription = {
        "APIKey": api_key,
        "BoundingBoxes": boxes,
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    }

    attempt = 0
    last_report = time.time()

    while time.time() < deadline:
        remaining = deadline - time.time()
        try:
            async with websockets.connect(WS_URL, ping_interval=20,
                                          ping_timeout=20) as ws:
                await ws.send(json.dumps(subscription))
                attempt = 0
                print("connected; listening for %.1f more minutes" % (remaining / 60.0),
                      flush=True)

                while time.time() < deadline:
                    try:
                        raw = await asyncio.wait_for(
                            ws.recv(), timeout=min(30.0, max(1.0, deadline - time.time())))
                    except asyncio.TimeoutError:
                        continue

                    try:
                        payload = json.loads(raw)
                    except Exception:
                        continue

                    # A bad key comes back as an error frame, not a refusal to
                    # connect, so say so plainly instead of listening to silence.
                    if "error" in payload or "Error" in payload:
                        raise SystemExit("aisstream rejected the subscription: %s"
                                         % (payload.get("error") or payload.get("Error")))

                    kind = payload.get("MessageType")
                    meta = payload.get("MetaData") or {}
                    body = (payload.get("Message") or {}).get(kind) or {}
                    if kind == "PositionReport":
                        rec.on_position(body, meta)
                    elif kind == "ShipStaticData":
                        rec.on_static(body, meta)

                    if time.time() - last_report >= 15.0:
                        rec.flush()
                        print("  %5d positions from %4d vessels, %5d written"
                              % (rec.seen, len(rec.mmsis), rec.written), flush=True)
                        last_report = time.time()

        except SystemExit:
            raise
        except Exception as exc:
            rec.flush()
            attempt += 1
            if time.time() >= deadline:
                break
            wait = min(30.0, 2.0 ** min(attempt, 5))
            print("  connection lost (%s); retrying in %.0fs" % (exc, wait), flush=True)
            await asyncio.sleep(wait)

    rec.flush()


def boxes_for(scene_ids: List[str], margin: float) -> List[List[List[float]]]:
    """aisstream wants [[lat1, lon1], [lat2, lon2]] per box."""
    out = []
    for s in scenes_mod.all_scenes(include_selftest=False):
        if scene_ids and s.id not in scene_ids:
            continue
        w, so, e, n = [float(v) for v in s.bounds]
        out.append([[so - margin, w - margin], [n + margin, e + margin]])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="record over every indexed scene")
    ap.add_argument("--scene", action="append", default=[])
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"),
                    help="an explicit box instead of a scene footprint")
    ap.add_argument("--margin-deg", type=float, default=0.5)
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--api-key", default=None,
                    help="defaults to $AISSTREAM_API_KEY; never stored")
    args = ap.parse_args()

    api_key = args.api_key or os.environ.get("AISSTREAM_API_KEY", "")
    if not api_key:
        raise SystemExit(
            "No API key. Set AISSTREAM_API_KEY in the environment or pass --api-key.\n"
            "It is read at run time and never written to the repository.")

    if args.bbox:
        w, s, e, n = args.bbox
        boxes = [[[s, w], [n, e]]]
    else:
        if not (args.all or args.scene):
            raise SystemExit("pass --all, --scene ID, or --bbox W S E N")
        boxes = boxes_for(args.scene, args.margin_deg)
    if not boxes:
        raise SystemExit("no scenes matched")

    print("recording %d box(es) for %.0f minutes" % (len(boxes), args.minutes))
    for b in boxes:
        print("   lat %.3f..%.3f  lon %.3f..%.3f" % (b[0][0], b[1][0], b[0][1], b[1][1]))
    print()

    rec = Recorder()
    before = ais_ingest.stats(rec.conn)
    try:
        asyncio.run(run(api_key, boxes, args.minutes, rec))
    except KeyboardInterrupt:
        print("\ninterrupted; flushing what was heard")
        rec.flush()

    after = ais_ingest.stats(rec.conn)
    print()
    print("heard   : %d positions from %d vessels" % (rec.seen, len(rec.mmsis)))
    print("written : %d new rows" % rec.written)
    print("store   : %d rows, %d vessels (was %d rows, %d vessels)"
          % (after.rows, after.vessels, before.rows, before.vessels))
    if rec.seen == 0:
        print()
        print("Nothing was heard. That is normal for a small box over quiet water")
        print("in a short window; widen --margin-deg or lengthen --minutes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
