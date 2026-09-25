# Running TideTrace on this Mac

From Terminal:

```sh
cd /Users/sam/Documents/Navtatva/tidetrace
./start.command
```

Or double-click `start.command` in Finder. Open http://127.0.0.1:8000,
choose a scene, and click **Run analysis**. Stop the server with Ctrl+C in
its terminal. Only one server can use port 8000 at a time.

The launcher uses this project's `.venv` directly; activation is unnecessary.
The server listens only on this machine, not the local network.

## Installed environment

- Python 3.14.3 in `.venv`.
- All packages in `requirements.txt`, plus ReportLab for PDF reports.
- PyTorch, segmentation-models-pytorch, and Hugging Face Hub.
- The project's trained `models/oil_unet_best.pt` checkpoint; inference uses CPU.
- Local Leaflet assets and Natural Earth world/coastline data.

To recreate the environment if needed:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-user -r requirements.txt reportlab torch segmentation-models-pytorch huggingface_hub
.venv/bin/python scripts/hf_sync.py pull-model
```

`--no-user` overrides this Mac's pip user-install setting, which otherwise
prevents installing into a virtual environment.
`requirements-local.lock.txt` records the exact installed versions; on a
compatible Mac/Python environment, install it with
`.venv/bin/python -m pip install --no-user -r requirements-local.lock.txt`.

## Demo data

The initial setup runs:

```sh
.venv/bin/python scripts/bootstrap_demo.py --scenes mc20 arabian_sea caspian_baku santa_barbara --basemap-zoom 10
.venv/bin/python scripts/fetch_world_land.py
.venv/bin/python scripts/fetch_land_mask.py --all --force
```

Use `fetch_land_mask.py`, the newer land-and-lakes downloader. The older
`build_land_mask.py` mentioned in the upstream README misclassifies inland seas.
Basemap tiles are cached through zoom 10; higher zoom imagery can be fetched with
`.venv/bin/python scripts/fetch_basemap.py --all`.

AIS traffic for Arabian Sea and Caspian scenes is explicitly simulated by the
project. US scenes require separate MarineCadastre ingestion for recorded vessel
attribution; bootstrap deliberately does not fabricate those tracks:

```sh
.venv/bin/python scripts/fetch_marinecadastre_ais.py --scene gom_mc20_chronic_slick --days 3
.venv/bin/python scripts/fetch_marinecadastre_ais.py --scene santa_barbara_seeps --days 3
```

Those optional commands download large nationwide daily archives before clipping
them. Metocean availability depends on the providers; inspect the console's Data
view for the source and any missing-current warnings.
For this setup, Gulf, Arabian Sea, and Santa Barbara caches contain Open-Meteo wind and currents.
The Caspian provider returned no currents, so its cached drift is wind-driven.

## Verification

```sh
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
```

The initial environment passed all 126 tests. A small local fix excludes `.venv`
and `venv` from the repository credential scan, which otherwise falsely matches
embedded data in an installed Pillow module.
The live Gulf scene also completed U-Net detection, hindcast, and forecast in
about 10 seconds, producing 29 oil polygons. Recorded US AIS was not ingested.
The Caspian end-to-end run also returned `status: ok`, with one oil polygon and
four ranked candidates from the explicitly simulated AIS store (96 vessels across
the Arabian Sea and Caspian scenes).
Bootstrap finished successfully with `READY`: four full-resolution SAR files,
four metocean cubes, 5,845 AIS rows, and 386 map tiles at zoom levels 5–10.

## Uploaded observations and automatic AIS

Open **Change scene → Add a radar observation**, choose a calibrated one- or
 two-band SAR GeoTIFF, and enter the actual acquisition time in UTC. Uploads are
limited to 256 MB and 16,777,216 pixels. Optical RGB imagery is not supported.
Choose **Run analysis** after the image is registered.

If oil is detected, uploaded observations fetch MarineCadastre AIS around the
estimated release area and time, including three hours of track padding. The
cache has a 100 km extra spatial margin for approach/departure tracks; trajectories
beyond that margin are clipped. It supports daily archives from 2015 onward
when published by NOAA, including the 2025+ Zstandard format (Python 3.14+).
Older yearly geodatabases are not supported. This is historical U.S. coverage,
not a worldwide or live AIS feed. Rough geographic eligibility is not a guarantee
of receiver coverage. Empty data is never proof that no vessel was present.

The first request downloads relevant nationwide daily files **one at a time**,
filters them locally, and deletes the raw archives. A few dates can still require
hundreds of MB of network traffic and several minutes. Byte-range retries recover
interrupted downloads; each daily transfer is limited to 2 GiB / 15 minutes and
requires at least 3 GiB free temporary space. Only complete query databases are
published under `data/cache/ais_queries`; repeating the same query reuses them.
Missing dates, malformed data and network errors do not become empty cached results.
Use Run analysis again to retry. Query caches persist and can be removed while the
server is stopped to reclaim space; future runs fetch them again.

Uploaded-scene attribution reads an isolated recorded-AIS cache and never falls
back to the simulated demo store. Existing preset scenes retain their offline
behavior. Clean observations skip AIS fetching because there is no slick to trace.

Wind/current fetching is not part of this change. An upload without an applicable
metocean cache uses the existing assumed constant field; the UI explicitly warns
that its drift and vessel rankings are not reliable evidence of a discharge.

## Live AIS connection

Double-click `configure-live-ais.command` and enter an AISStream API key from
https://aisstream.io. The input is hidden; the key is stored with owner-only
permissions at `~/.config/navtatva/aisstream.key`, outside the repository and the
publicly served data directory. The service checks for it every five seconds.
Alternatively, set `AISSTREAM_API_KEY` before starting the server; that environment
variable takes precedence over the file. Never place a key under `data/`.

While the app is running, one compressed WebSocket subscribes to the indexed
observation footprints, each padded by two degrees. New uploads update the
subscription automatically. The recorder receives Class A/B position messages,
flushes them every two seconds, reconnects with backoff after interruptions, and
flushes pending positions at shutdown. Status appears at the bottom of the UI and
at `/api/ais/live/status`; no key or raw provider error is returned there.

Records live in `data/ais/live.sqlite`, separate from simulated demo traffic.
Uploaded-scene analysis first checks this store for the release location and time.
If matching records exist, it uses them and explicitly warns that reception can
have gaps. If none match, it uses the existing MarineCadastre historical fetch.
Starting a connection cannot retrieve past movements, and a connected status does
not establish full geographic or time coverage. Keep the app running before new
observations arrive. This change does not add a continuously animated vessel map:
the map still shows tracks selected by each analysis.

Set `TIDETRACE_LIVE_AIS=0` before launching to disable the recorder. Recordings
persist across restarts; there is currently no automatic retention policy, so
monitor disk usage for long-running deployments. External provider authentication
must be verified after supplying your key.


## Observation-time data and trajectories (September 2026)

The Mac launcher enables historical AIS fetching for U.S. preset scenes as well
as uploads. The first analysis downloads the matching NOAA daily archive, clips
it to the release area/time, and caches only a fully completed query. Downloads
use up to sixteen bounded range requests concurrently. Completed byte ranges are
retained after interruption, validated against the provider ETag, and reused on retry. Provider failures remain
visible and can be retried with Run analysis. Use `TIDETRACE_OFFLINE=1 ./start.command`
for the preset-scene offline workflow.

Ocean Dynamics and map arrows now read the same observation-time metocean cube
as the drift calculation. Missing currents or winds are not replaced with made-up
values. The Caspian cache has wind but no currents; resolving this needs a current
dataset covering that basin and acquisition date. Cached cubes do not contain
wave measurements. The display distinguishes unknown values from measured zeroes.

Live AIS starts empty until an AISStream key is configured and real positions
arrive. Live traffic is separate from historical attribution and cannot backfill
2023/2024 observations. No fabricated corridor vessels are labelled as live.

Drift is integrated at ten-minute resolution with hourly uncertainty summaries;
the map shows individual model members and their median. AIS track geometry keeps
raw received positions and separates reporting gaps into dashed estimated spans.
The Arabian Sea and Caspian demo traffic remains explicitly simulated, now with
gradual route changes rather than two-endpoint straight transits. Regenerate those
local demo stores with `scripts/build_synthetic_ais.py --all` using the project Python.

The Mac launcher also enables fetching metocean when no covering cache exists.
Existing observation-time cubes are reused first. Set `TIDETRACE_OPEN_METEO_LIVE=0`
to disable fetching new cubes. On Python 3.14+, 2023/2024 AIS uses NOAA's smaller
Zstandard archives. Failed downloads leave resumable chunks under
`data/cache/ais_downloads`; completed queries remain under `data/cache/ais_queries`.
