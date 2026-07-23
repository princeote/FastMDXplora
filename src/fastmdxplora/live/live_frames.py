"""Atomic, fail-safe writing of live simulation frames for the dashboard.

The dashboard polls ``/structure/live-frame.pdb`` so the molecular viewer
can track the simulation as it runs. We never want this side-channel to
crash or even pause the OpenMM loop, so every operation here:

  - is bounded by a try/except (returns ``False`` on any failure);
  - writes to a temp file and then uses ``os.replace`` for an atomic
    rename — the dashboard cannot read a half-written PDB;
  - records the frame index and mtime in ``live_frame_index.json`` so
    the browser can cheaply detect "something changed" without parsing
    the PDB header.

The simulation runner calls :func:`write_live_frame` once per telemetry
interval. The dashboard never reads coordinates from in-process state —
it always asks the server, which reads from disk. This keeps cross-thread
state-sharing simple and lets the dashboard work even after the
simulation has exited (it just stops updating).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

LIVE_FRAME_FILE = "live_frame.pdb"
LIVE_FRAME_INDEX_FILE = "live_frame_index.json"


def write_live_frame(
    output_dir: str | Path,
    *,
    pdb_text: str,
    frame_index: int | None = None,
) -> dict[str, Any]:
    """Atomically write ``pdb_text`` as ``live_frame.pdb``.

    Returns a small status dict; failures are swallowed (the simulation
    continues) but recorded with ``ok=False`` for telemetry purposes.
    """
    out = Path(output_dir)
    frames_path = out / LIVE_FRAME_FILE
    index_path = out / LIVE_FRAME_INDEX_FILE

    try:
        out.mkdir(parents=True, exist_ok=True)
        tmp = frames_path.with_suffix(".pdb.tmp")
        tmp.write_text(pdb_text, encoding="utf-8")
        os.replace(tmp, frames_path)
    except OSError as exc:
        return {"ok": False, "error": f"write-error: {exc}", "frame_index": frame_index}

    mtime = frames_path.stat().st_mtime if frames_path.exists() else time.time()
    index_payload = {
        "live_frame_available": True,
        "live_frame_index": int(frame_index) if frame_index is not None else None,
        "live_frame_updated_at": _iso_now(time.time()),
        "live_frame_mtime": mtime,
        "live_frame_size": frames_path.stat().st_size,
    }
    try:
        tmp_idx = index_path.with_suffix(".json.tmp")
        tmp_idx.write_text(json.dumps(index_payload), encoding="utf-8")
        os.replace(tmp_idx, index_path)
    except OSError:
        # Best-effort; the frame itself succeeded and that's what matters.
        pass
    return {"ok": True, **index_payload}


def write_openmm_live_frame(
    output_dir: str | Path,
    *,
    pdbfile_writer: Any,
    topology: Any,
    positions: Any,
    frame_index: int | None = None,
) -> dict[str, Any]:
    """Convenience wrapper around :func:`write_live_frame` for OpenMM.

    ``pdbfile_writer`` is typically ``openmm.app.PDBFile.writeFile``;
    accepting it as a callable lets this module stay free of any direct
    OpenMM import (the rest of the live module already imports openmm
    lazily only when telemetry is on).
    """
    try:
        from io import StringIO

        buf = StringIO()
        pdbfile_writer(topology, positions, buf)
        text = buf.getvalue()
    except Exception as exc:  # noqa: BLE001 - dashboard writes must never crash sim
        return {"ok": False, "error": f"openmm-snapshot: {exc}", "frame_index": frame_index}
    return write_live_frame(output_dir, pdb_text=text, frame_index=frame_index)


def read_live_frame_index(output_dir: str | Path) -> dict[str, Any]:
    """Read the latest frame companion JSON, defaulting to ``available=False``."""
    out = Path(output_dir)
    idx_path = out / LIVE_FRAME_INDEX_FILE
    if not idx_path.is_file():
        return {"live_frame_available": False}
    try:
        return json.loads(idx_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"live_frame_available": False}


def live_frame_pdb_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / LIVE_FRAME_FILE


def live_frame_exists(output_dir: str | Path) -> bool:
    """Cheap existence check used by the route handler."""
    return live_frame_pdb_path(output_dir).is_file()


def _iso_now(timestamp: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
