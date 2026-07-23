"""Trajectory playback helpers for the live dashboard.

The dashboard's "Molecular Viewer" page can step through a downsampled
playback of the production trajectory (200 frames max by default) so the
user can scrub or play it back without the cost (or the file size) of
loading the full scientific DCD. This module never mutates the DCD — it
only reads frames and writes a multi-MODEL PDB companion.

OpenMM is the only consumer-strict dependency for DCD reading, so it's
imported lazily. If OpenMM isn't available, the playback route falls
back to a clean "not available" message; the rest of the dashboard
keeps working.
"""

from __future__ import annotations

import json
import os
import time
from io import StringIO
from pathlib import Path
from typing import Any

PLAYBACK_FILE = "playback.pdb"
PLAYBACK_INDEX_FILE = "playback_index.json"

# Lines that record-level PDB writers emit which conflict when reusing
# between MODEL blocks. CRYST1 may only appear once; HEADER / TITLE /
# COMPND may only appear before the first MODEL.
_HEADER_LIKE_RECORDS = frozenset({
    "CRYST1", "HEADER", "OBSLTE", "TITLE ", "SPLT  ", "CAVEAT",
    "COMPND", "SOURCE", "KEYWDS", "EXPDTA", "NUMMDL", "MDLTYP",
    "AUTHOR", "REVDAT", "DBREF", "DBREF1", "DBREF2", "SEQADV",
    "SEQRES", "MODRES", "HET ", "HETNAM", "HETSYN", "FORMUL",
})


def PlaybackUnavailable(reason: str) -> dict[str, Any]:
    """Return a uniform "not available" envelope for the route handler."""
    return {
        "playback_available": False,
        "reason": reason,
        "n_frames_total": 0,
        "n_frames_browser": 0,
        "frame_indices": [],
        "simulation_time_ns_first": None,
        "simulation_time_ns_last": None,
    }


def _import_openmm() -> dict[str, Any] | None:
    """Return a dict of OpenMM symbols or ``None`` if not importable."""
    try:
        import openmm
        from openmm.app import DCDFile, PDBFile
    except ImportError:
        return None
    return {
        "openmm": openmm,
        "PDBFile": PDBFile,
        "DCDFile": DCDFile,
    }


def playback_info(
    output_dir: str | Path,
    *,
    max_browser_frames: int = 200,
    simulation_time_ns_total: float | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Build the playback companion files and return a status dictionary.

    Parameters
    ----------
    output_dir : path-like
        The dashboard's project root (typically the FastMDXplora run dir).
    max_browser_frames : int
        Cap on the number of frames the browser will load. The trajectory
        is downsampled evenly so the browser never sees more than this
        many frames regardless of how large the production run is.
    simulation_time_ns_total : float | None
        If known, used to compute simulation-time labels for each frame.
    force : bool
        Re-generate even if the companion files already exist. Useful for
        the dashboard's refresh control.

    Returns
    -------
    dict
        Status envelope consumed by the ``/api/playback-info`` route.
    """
    out = Path(output_dir)
    sim_dir = out / "simulation"
    topo_path = sim_dir / "topology.pdb"
    dcd_path = sim_dir / "production.dcd"
    companion_pdb = sim_dir / PLAYBACK_FILE
    companion_idx = sim_dir / PLAYBACK_INDEX_FILE

    if not (topo_path.is_file() and dcd_path.is_file()):
        return PlaybackUnavailable("missing-trajectory")

    if not force and companion_pdb.is_file() and companion_idx.is_file():
        try:
            if companion_pdb.stat().st_mtime >= dcd_path.stat().st_mtime:
                info = _load_index(companion_idx)
                if info.get("playback_available"):
                    return info
        except OSError:
            pass

    omm = _import_openmm()
    if omm is None:
        return PlaybackUnavailable("openmm-not-installed")

    try:
        return _generate_companion(
            omm=omm,
            topology_path=topo_path,
            dcd_path=dcd_path,
            companion_pdb=companion_pdb,
            companion_idx=companion_idx,
            max_browser_frames=max(1, int(max_browser_frames)),
            simulation_time_ns_total=simulation_time_ns_total,
        )
    except Exception as exc:  # noqa: BLE001 — never crash the dashboard
        return PlaybackUnavailable(f"generate-error: {exc}")


def _generate_companion(
    *,
    omm: dict[str, Any],
    topology_path: Path,
    dcd_path: Path,
    companion_pdb: Path,
    companion_idx: Path,
    max_browser_frames: int,
    simulation_time_ns_total: float | None,
) -> dict[str, Any]:
    PDBFile = omm["PDBFile"]
    DCDFile = omm["DCDFile"]

    pdb = PDBFile(str(topology_path))
    topology = pdb.topology

    dcd = DCDFile(str(dcd_path))
    n_total = int(len(dcd))
    if n_total <= 0:
        return PlaybackUnavailable("empty-trajectory")

    if n_total <= max_browser_frames:
        frame_indices = list(range(n_total))
    else:
        # Even downsample so coverage is uniform across the trajectory.
        stride = max(1, n_total // max_browser_frames)
        frame_indices = list(range(0, n_total, stride))[:max_browser_frames]
        if frame_indices[-1] != n_total - 1:
            frame_indices.append(n_total - 1)

    n_browser = len(frame_indices)
    frame_set = set(frame_indices)

    out_lines: list[str] = []
    written = 0
    frame_times_ns: list[float | None] = []
    # DCD iteration is partial-write risky: the OpenMM C++ layer may raise
    # on a torn final frame. Break on the first error so the dashboard
    # still serves whatever it already had.
    try:
        for idx, frame in enumerate(dcd):
            if idx not in frame_set:
                continue
            buf = StringIO()
            try:
                PDBFile.writeFile(topology, frame, buf, keepIds=True)
            except TypeError:
                # Older OpenMM versions don't accept keepIds.
                PDBFile.writeFile(topology, frame, buf)  # type: ignore[call-arg]
            text = buf.getvalue()
            # 3Dmol expects MODEL/ENDMDL wrapping. Strip the per-frame
            # header-record lines that conflict with the multi-MODEL
            # contract (CRYST1 may only appear once).
            if written == 0:
                out_lines.append(f"MODEL     {idx + 1:>4d}")
            else:
                out_lines.append(f"MODEL     {idx + 1:>4d}")
            for ln in text.splitlines():
                stripped = ln[:6].rstrip().upper()
                if not stripped:
                    continue
                if (
                    stripped in _HEADER_LIKE_RECORDS
                    or stripped.startswith("END")
                    or stripped == "MODEL"
                    or stripped == "ENDMDL"
                ):
                    continue
                out_lines.append(ln)
            out_lines.append("ENDMDL")
            written += 1
            if simulation_time_ns_total is not None and n_total > 1:
                frame_times_ns.append(
                    simulation_time_ns_total * (idx / (n_total - 1))
                )
            else:
                frame_times_ns.append(None)
            if written >= n_browser:
                break
    except Exception:
        # Mid-trajectory read error (e.g. simulation still writing).
        # Whatever we already wrote is still servable.
        pass

    if written == 0:
        return PlaybackUnavailable("no-frames-read")
    out_lines.append("END")

    tmp = companion_pdb.with_suffix(".pdb.tmp")
    tmp.write_text("\n".join(out_lines), encoding="utf-8")
    os.replace(tmp, companion_pdb)

    payload = {
        "playback_available": True,
        "n_frames_total": n_total,
        "n_frames_browser": written,
        "frame_indices": [int(i) for i in frame_indices[:written]],
        "frame_times_ns": frame_times_ns,
        "simulation_time_ns_first": (
            frame_times_ns[0] if frame_times_ns and frame_times_ns[0] is not None
            else None
        ),
        "simulation_time_ns_last": (
            frame_times_ns[-1] if frame_times_ns and frame_times_ns[-1] is not None
            else None
        ),
        "companion_pdb": companion_pdb.name,
        "compiled_at": time.time(),
    }
    tmp_idx = companion_idx.with_suffix(".json.tmp")
    tmp_idx.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp_idx, companion_idx)
    return payload


def _load_index(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return PlaybackUnavailable("missing-companion")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return PlaybackUnavailable("invalid-companion")


def neighborhood_residues(
    *,
    topology_path: Path,
    ligand_resname: str,
    cutoff_angstrom: float = 5.0,
    coords_path: Path | None = None,
) -> list[tuple[str, int]]:
    """Residue keys within ``cutoff_angstrom`` of any ligand atom.

    Returns a list of ``(chain, resSeq)`` tuples. Distances are measured
    **per atom** (any ligand atom in contact counts) — not centroid
    sphere — so elongated or peptide-like ligands aren't underestimated.

    Coordinates are read from ``coords_path`` if provided (e.g. the
    live-frame PDB) and otherwise from the topology file's atoms.
    """
    if not topology_path.is_file():
        return []
    coords_source = coords_path if coords_path and coords_path.is_file() else topology_path
    ligand_coords = _ligand_coord_list(coords_source, ligand_resname)
    if not ligand_coords:
        return []
    cutoff_sq = cutoff_angstrom * cutoff_angstrom
    residues: set[tuple[str, int]] = set()
    try:
        with coords_source.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if not (line.startswith("ATOM") or line.startswith("HETATM")):
                    continue
                resname = line[17:20].strip().upper()
                if resname == ligand_resname.upper():
                    continue
                chain_id = line[21:22].strip() or "A"
                try:
                    res_seq = int(line[22:26])
                except ValueError:
                    res_seq = 0
                try:
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                except (ValueError, IndexError):
                    continue
                # Per-atom contact check — fast enough for normal pockets
                # (<200 protein residues × <200 ligand atoms in pure Python).
                if _any_atom_within_cutoff(
                    x, y, z, ligand_coords, cutoff_sq
                ):
                    residues.add((chain_id, res_seq))
    except OSError:
        return []
    return sorted(residues)


def _ligand_coord_list(path: Path, ligand_resname: str) -> list[tuple[float, float, float]]:
    target = ligand_resname.upper()
    coords: list[tuple[float, float, float]] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if not (line.startswith("ATOM") or line.startswith("HETATM")):
                    continue
                resname = line[17:20].strip().upper()
                if resname != target:
                    continue
                try:
                    coords.append(
                        (
                            float(line[30:38]),
                            float(line[38:46]),
                            float(line[46:54]),
                        )
                    )
                except (ValueError, IndexError):
                    continue
    except OSError:
        return []
    return coords


def _any_atom_within_cutoff(
    x: float,
    y: float,
    z: float,
    ligand_coords: list[tuple[float, float, float]],
    cutoff_sq: float,
) -> bool:
    for lx, ly, lz in ligand_coords:
        dx = x - lx
        dy = y - ly
        dz = z - lz
        if dx * dx + dy * dy + dz * dz <= cutoff_sq:
            return True
    return False
