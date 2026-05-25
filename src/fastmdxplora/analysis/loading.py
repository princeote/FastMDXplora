"""Trajectory loading and topology resolution.

This module provides ``load_trajectory``, the canonical entry point for
turning user-supplied paths into an MDTraj ``Trajectory`` object. It handles:

  - Single or multiple trajectory files (multiple files are concatenated)
  - Explicit topology files when the trajectory format lacks topology
  - Topology auto-resolution (a sibling .pdb when the user omits ``top``)
  - Frame selection (``stride``, ``first``, ``last``)
  - Helpful error messages when files don't exist or are the wrong format

The function is deliberately permissive about input forms (single path, list
of paths, glob pattern) and strict about the resulting object (always a
single concatenated MDTraj trajectory with a topology attached).
"""

from __future__ import annotations

import glob as _glob
from pathlib import Path
from typing import Sequence, Union

import mdtraj as md

from fastmdxplora.utils.logging import get_logger

logger = get_logger("analysis.loading")


# Trajectory formats that carry their own topology and therefore do not
# require an external topology file.
SELF_TOPOLOGY_FORMATS = frozenset({".pdb", ".pdbx", ".cif", ".h5", ".lh5"})

# Trajectory formats that require an external topology file.
EXTERNAL_TOPOLOGY_FORMATS = frozenset(
    {".dcd", ".xtc", ".trr", ".nc", ".netcdf", ".binpos", ".lammpstrj", ".dtr", ".xyz"}
)


PathLike = Union[str, Path]
TrajectoryInput = Union[PathLike, Sequence[PathLike]]


class TrajectoryLoadError(ValueError):
    """Raised when a trajectory cannot be located, opened, or parsed."""


def _resolve_paths(traj: TrajectoryInput) -> list[Path]:
    """Normalize the trajectory argument to a list of concrete file paths.

    Accepts a single path, a list/tuple of paths, or a glob pattern.
    Globs are expanded; the result is sorted lexicographically so that
    multi-shot trajectories with sortable names (run01.dcd, run02.dcd, ...)
    are concatenated in the expected order.
    """
    if isinstance(traj, (str, Path)):
        single = str(traj)
        if any(ch in single for ch in "*?[]"):
            expanded = sorted(_glob.glob(single))
            if not expanded:
                raise TrajectoryLoadError(f"No files match pattern: {single!r}")
            return [Path(p) for p in expanded]
        return [Path(single)]

    if isinstance(traj, Sequence):
        paths = [Path(str(p)) for p in traj]
        if not paths:
            raise TrajectoryLoadError("Trajectory input is an empty sequence.")
        return paths

    raise TrajectoryLoadError(
        f"Unsupported trajectory input type: {type(traj).__name__}."
    )


def _resolve_topology(
    traj_paths: list[Path],
    top: PathLike | None,
) -> Path | None:
    """Decide which topology file to use.

    Logic:
      1. If the user supplied ``top``, validate it exists and return it.
      2. If the first trajectory file is self-topologized (PDB, H5...), no
         external topology is needed.
      3. Otherwise, look for a sibling .pdb file next to the first trajectory.
      4. Otherwise, raise — the user must provide a topology.
    """
    if top is not None:
        top_path = Path(top)
        if not top_path.exists():
            raise TrajectoryLoadError(f"Topology file not found: {top_path}")
        return top_path

    first = traj_paths[0]
    suffix = first.suffix.lower()

    if suffix in SELF_TOPOLOGY_FORMATS:
        return None

    if suffix in EXTERNAL_TOPOLOGY_FORMATS:
        candidate = first.with_suffix(".pdb")
        if candidate.exists():
            logger.debug("Auto-resolved topology: %s", candidate)
            return candidate
        raise TrajectoryLoadError(
            f"Trajectory format {suffix!r} requires a topology file, but none "
            f"was supplied and no {candidate.name} was found alongside "
            f"{first.name}. Pass `top=<path>` explicitly."
        )

    raise TrajectoryLoadError(
        f"Unrecognized trajectory format: {suffix!r} (file: {first})"
    )


def load_trajectory(
    traj: TrajectoryInput,
    top: PathLike | None = None,
    *,
    stride: int | None = None,
    first: int | None = None,
    last: int | None = None,
) -> md.Trajectory:
    """Load one or more trajectory files into a single MDTraj trajectory.

    Parameters
    ----------
    traj : path, list of paths, or glob pattern
        Trajectory file(s) to load. When multiple files are provided, they
        are concatenated in lexicographic order (so name them ``run01.dcd``,
        ``run02.dcd``, ... for multi-shot data).
    top : path, optional
        Topology file. If omitted, the function attempts to auto-resolve
        from a sibling .pdb file.
    stride : int, optional
        Read every ``stride``-th frame.
    first, last : int, optional
        Frame slice applied after loading. ``last`` is exclusive (Python
        slice semantics).

    Returns
    -------
    mdtraj.Trajectory
        A single trajectory with the requested topology attached. Always
        the concatenation of all input files.

    Raises
    ------
    TrajectoryLoadError
        If files are missing, topology cannot be resolved, or MDTraj fails
        to parse the data.

    Examples
    --------
    Single trajectory with auto-resolved topology::

        traj = load_trajectory("production.dcd")  # needs production.pdb

    Multiple trajectories with explicit topology::

        traj = load_trajectory(
            ["run01.dcd", "run02.dcd", "run03.dcd"],
            top="topology.pdb",
        )

    Glob pattern with stride::

        traj = load_trajectory("run*.dcd", top="topology.pdb", stride=10)
    """
    traj_paths = _resolve_paths(traj)
    for p in traj_paths:
        if not p.exists():
            raise TrajectoryLoadError(f"Trajectory file not found: {p}")

    top_path = _resolve_topology(traj_paths, top)

    logger.debug(
        "Loading %d trajectory file(s) with topology=%s, stride=%s",
        len(traj_paths),
        top_path,
        stride,
    )

    # MDTraj's DCD/PDB plugins write raw C-level messages straight to the
    # OS file descriptors ("dcdplugin) detected standard 32-bit DCD
    # file..."), bypassing Python's logging and stream objects. Redirect
    # fds 1 and 2 around the load to suppress them.
    from fastmdxplora.utils import suppress_native_output

    try:
        with suppress_native_output():
            if top_path is not None:
                trajectory = md.load(
                    [str(p) for p in traj_paths],
                    top=str(top_path),
                    stride=stride,
                )
            else:
                trajectory = md.load([str(p) for p in traj_paths], stride=stride)
    except Exception as exc:  # MDTraj raises a variety of types
        raise TrajectoryLoadError(
            f"MDTraj failed to load trajectory: {exc}"
        ) from exc

    # MDTraj returns a list for a single file, ensure we have a Trajectory.
    if isinstance(trajectory, list):
        trajectory = md.join(trajectory)

    if first is not None or last is not None:
        n = trajectory.n_frames
        f = first if first is not None else 0
        l = last if last is not None else n
        if not (0 <= f <= l <= n):
            raise TrajectoryLoadError(
                f"Invalid frame slice [{f}:{l}] for trajectory with {n} frames."
            )
        trajectory = trajectory[f:l]

    logger.debug(
        "Loaded trajectory: %d frames, %d atoms, %d residues",
        trajectory.n_frames,
        trajectory.n_atoms,
        trajectory.n_residues,
    )
    return trajectory
