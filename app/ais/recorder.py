"""AISStream message normalization shared by the service and CLI recorder."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from . import ingest as ais_ingest
SOURCE = "aisstream_live"

# ITU-R M.1371 sends dimensions as distances from the reference point to bow,
# stern, port and starboard. Length and beam are the sums.
def _dims(d: Optional[dict]) -> Tuple[Optional[float], Optional[float]]:
    if not isinstance(d, dict):
        return None, None
    a, b = d.get("A"), d.get("B")
    c, e = d.get("C"), d.get("D")
    length = (a + b) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None
    width = (c + e) if isinstance(c, (int, float)) and isinstance(e, (int, float)) else None
    return length, width


def _meta_time(meta: Dict[str, Any]) -> str:
    """aisstream stamps `time_utc`; fall back to arrival time if it is absent."""
    raw = meta.get("time_utc") or meta.get("TimeUtc")
    if isinstance(raw, str) and raw:
        # e.g. "2026-09-04 21:15:03.123456789 +0000 UTC" -- keep it parseable.
        cleaned = raw.split(" +")[0].split(" UTC")[0].strip()
        if "." in cleaned:
            cleaned = cleaned.split(".")[0]
        return cleaned.replace(" ", "T")
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")



def _text(v) -> Optional[str]:
    """`row_from_csv` parses MarineCadastre CSV, so its contract is strings.

    aisstream sends these fields as integers -- type, navigational status, IMO --
    and handing an int to a parser that calls .strip() on it crashes on the first
    vessel that reports static data. Coerce here, at the boundary, rather than
    loosening a parser that is right to expect what a CSV gives it.
    """
    if v is None or v == "":
        return None
    return str(v)


def _imo(v) -> Optional[str]:
    """MarineCadastre writes IMO as `IMO9260427`; aisstream sends 9260427.

    Zero is the "not available" sentinel, not an IMO number, so it becomes None
    rather than the string "0" -- which would otherwise be stored as though the
    vessel really were registered under that number.
    """
    if isinstance(v, (int, float)):
        return "IMO%d" % int(v) if int(v) > 0 else None
    return _text(v)

class Recorder:
    """Accumulates position reports, enriched with static data when it arrives.

    Static data (name, type, IMO, dimensions) comes in its own message class and
    far less often than positions, so it is cached per MMSI and applied to every
    position recorded for that vessel. A vessel whose static message never
    arrives still gets its positions, with the name aisstream puts in MetaData.
    """

    def __init__(self, flush_every: int = 400, path=None):
        self.static: Dict[int, Dict[str, Any]] = {}
        self.pending: List[Dict[str, Any]] = []
        self.flush_every = flush_every
        self.written = 0
        self.seen = 0
        self.mmsis = set()
        self.conn = ais_ingest.connect(path)

    def on_static(self, msg: Dict[str, Any], meta: Dict[str, Any]) -> None:
        mmsi = meta.get("MMSI") or msg.get("UserID")
        if not mmsi:
            return
        length, width = _dims(msg.get("Dimension"))
        self.static[int(mmsi)] = {
            "VesselName": (msg.get("Name") or meta.get("ShipName") or "").strip(),
            "IMO": _imo(msg.get("ImoNumber")),
            "CallSign": (msg.get("CallSign") or "").strip(),
            "VesselType": _text(msg.get("Type")),
            "Length": length,
            "Width": width,
            "Draft": msg.get("MaximumStaticDraught"),
            "Cargo": _text(msg.get("Type")),
        }

    def on_position(self, msg: Dict[str, Any], meta: Dict[str, Any]) -> None:
        mmsi = meta.get("MMSI") or msg.get("UserID")
        lat = msg.get("Latitude", meta.get("Latitude"))
        lon = msg.get("Longitude", meta.get("Longitude"))
        if mmsi is None or lat is None or lon is None:
            return
        if not (-90 <= float(lat) <= 90) or not (-180 <= float(lon) <= 180):
            return

        self.seen += 1
        self.mmsis.add(int(mmsi))
        stat = self.static.get(int(mmsi), {})

        heading = msg.get("TrueHeading")
        if heading == 511:          # 511 is the "not available" sentinel
            heading = None
        cog = msg.get("Cog")
        if cog is not None and float(cog) >= 360:
            cog = None
        sog = msg.get("Sog")
        if sog is not None and float(sog) >= 102.3:
            sog = None

        rec = {
            "MMSI": int(mmsi),
            "BaseDateTime": _meta_time(meta),
            "LAT": float(lat),
            "LON": float(lon),
            "SOG": sog,
            "COG": cog,
            "Heading": heading,
            "VesselName": stat.get("VesselName") or (meta.get("ShipName") or "").strip(),
            "IMO": stat.get("IMO"),
            "CallSign": stat.get("CallSign"),
            "VesselType": stat.get("VesselType"),
            "Status": _text(msg.get("NavigationalStatus")),
            "Length": stat.get("Length"),
            "Width": stat.get("Width"),
            "Draft": stat.get("Draft"),
            "Cargo": stat.get("Cargo"),
        }
        self.pending.append(rec)
        if len(self.pending) >= self.flush_every:
            self.flush()

    def flush(self) -> int:
        """Write through the normal ingest path, so validation is shared.

        Flushing as we go rather than at the end means a session that is killed,
        or that loses its connection for good, still leaves everything it heard
        up to that point on disk.
        """
        if not self.pending:
            return 0
        rows = []
        for rec in self.pending:
            row = ais_ingest.row_from_csv(rec, SOURCE)
            if row is not None:
                rows.append(row)
        n = ais_ingest.ingest_rows(self.conn, rows, SOURCE) if rows else 0
        self.written += n
        self.pending = []
        return n

