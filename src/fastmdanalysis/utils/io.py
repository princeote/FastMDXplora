# FastMDAnalysis/src/fastmdanalysis/utils/io.py
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union
import glob
import warnings

import mdtraj as md

PathLike = Union[str, Path]


def _as_paths(maybe_paths: Union[PathLike, Sequence[PathLike]]) -> List[Path]:
    """Normalize a string/Path or a sequence (supports glob patterns) into a list of Paths."""
    if isinstance(maybe_paths, (str, Path)):
        maybe_paths = [maybe_paths]  # type: ignore[list-item]
    out: List[Path] = []
    for item in maybe_paths:  # type: ignore[assignment]
        p = Path(item).expanduser()
        # Allow simple glob patterns in strings
        if any(ch in str(p) for ch in ["*", "?", "[", "]"]):
            for hit in glob.glob(str(p), recursive=True):
                out.append(Path(hit))
        else:
            out.append(p)
    # Deduplicate while preserving order
    seen = set()
    uniq: List[Path] = []
    for p in out:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq


def load_trajectory(
    traj: Union[PathLike, Sequence[PathLike]],
    top: PathLike,
    frames: Optional[Tuple[Optional[int], Optional[int], Optional[int]]] = None,
    atoms: Optional[str] = None,
):
    """
    Load one or more trajectory files with a single topology, then optionally
    slice by frames and atom selection (MDTraj DSL).

    Parameters
    ----------
    traj
        Single file path, a sequence of paths, or glob patterns.
    top
        Topology file (e.g., .pdb, .prmtop, .psf).
    frames
        (start, stop, stride) to slice after loading. Any can be None.
    atoms
        MDTraj selection string (e.g., "protein and name CA").

    Returns
    -------
    mdtraj.Trajectory
    """
    top_path = Path(top).expanduser()
    if not top_path.exists():
        raise FileNotFoundError(f"Topology file not found: {top_path}")

    traj_files = [p for p in _as_paths(traj) if Path(p).exists()]
    if not traj_files:
        raise FileNotFoundError(f"No trajectory files found from input: {traj}")

    # Load and concatenate in order.
    # Suppress benign CRYST1 unit-cell warnings from MDTraj when reading PDB tops.
    trajs = []
    for p in traj_files:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"Unlikely unit cell vectors detected.*CRYST1",
                category=UserWarning,
                module=r"mdtraj\.formats\.pdb\.pdbfile",
            )
            t_part = md.load(str(p), top=str(top_path))
        trajs.append(t_part)

    t = trajs[0]
    for more in trajs[1:]:
        t = t.join(more)  # concatenate along time axis

    # Frame slicing after load (start/stop/stride)
    if frames is not None:
        start, stop, stride = frames
        t = t[start:stop:stride]  # slicing tolerates None

    # Atom selection
    if atoms:
        idx = t.topology.select(atoms)
        if idx.size == 0:
            raise ValueError(f"Atom selection returned 0 atoms: {atoms}")
        t = t.atom_slice(idx, inplace=False)

    return t
