"""Structure metadata helpers for the live dashboard.

Counts chains, residues, atoms, water molecules, ions, and likely non-protein
ligands from a PDB file. Designed to be safe for the dashboard: it never
raises and returns a JSON-serialisable dictionary with sensible fallbacks.

The water/ion/amino-acid residue sets are the canonical copies in
:mod:`fastmdxplora.live.ligand_detection`; re-imported here so a
change to one place updates both modules.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from fastmdxplora.live.ligand_detection import (
    AMINO_ACID_RESNAMES,
    ION_RESNAMES,
    WATER_RESNAMES,
    detect_ligands,
)

# Maximum PDB size the dashboard will scan inline. Anything larger may
# be a viral capsid or a poorly-prepared system; rather than stall the
# polling loop we report "too-large" and let the user pre-render.
_MAX_PDB_BYTES_FOR_INLINE_SCAN = 8 * 1024 * 1024  # 8 MB

# Wide guard against corrupt numeric columns parsing into absurd values
# (PDB row chunks occasionally misalign on weird lines).
_COORD_SANITY_LIMIT = 1_000_000.0  # angstrom


def count_structure(path: str | Path) -> dict[str, Any]:
    """Walk a PDB and return chain / residue / atom / ligand counters.

    The returned dictionary is JSON-friendly: every numeric field is int,
    every list field is a list of strings. Any IO / parse failure yields
    a ``{"valid": False}`` envelope so the dashboard can render an honest
    "structure could not be read" state instead of crashing.
    """
    p = Path(path)
    if not p.is_file():
        return {"valid": False, "reason": "missing", "path": p.as_posix()}
    try:
        file_size = p.stat().st_size
    except OSError as exc:
        return {"valid": False, "reason": f"stat-error: {exc}", "path": p.as_posix()}
    if file_size > _MAX_PDB_BYTES_FOR_INLINE_SCAN:
        return {
            "valid": False,
            "reason": "too-large",
            "path": p.as_posix(),
            "size": file_size,
        }

    chains: set[str] = set()
    protein_residue_keys: set[tuple[str, str, str]] = set()
    non_protein_residue_keys: set[tuple[str, str, str]] = set()
    waters = 0
    ions = 0
    atoms = 0
    protein_atoms = 0
    hetatm_atoms = 0
    min_coords = [float("inf"), float("inf"), float("inf")]
    max_coords = [float("-inf"), float("-inf"), float("-inf")]

    try:
        with p.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if not (line.startswith("ATOM") or line.startswith("HETATM")):
                    continue
                atoms += 1
                is_atom = line.startswith("ATOM")
                if is_atom:
                    protein_atoms += 1
                else:
                    hetatm_atoms += 1
                chain_id = line[21:22].strip() or "A"
                resname = line[17:20].strip().upper()
                resi = line[22:26].strip()
                chains.add(chain_id)

                # Many PDBs list crystallographic waters/ions as ATOM.
                # Decide by residue name first so they aren't double
                # counted as protein, regardless of the record type.
                if resname in WATER_RESNAMES:
                    waters += 1
                    continue
                if resname in ION_RESNAMES:
                    ions += 1
                    continue

                key = (chain_id, resname, resi)
                if resname in AMINO_ACID_RESNAMES:
                    protein_residue_keys.add(key)
                elif is_atom:
                    # Genuinely a non-water, non-ion ATOM record — rare,
                    # but found in some ligand-flavoured PDBs. Treat as
                    # non-protein residue so ligand detection picks it up.
                    non_protein_residue_keys.add(key)
                else:
                    non_protein_residue_keys.add(key)

                # Coordinate parsing (PDB column widths). _COORD_SANITY_LIMIT
                # only guards against parsing-broken columns; it does not
                # silently drop otherwise valid coordinates.
                try:
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                    if all(-_COORD_SANITY_LIMIT <= v <= _COORD_SANITY_LIMIT
                           for v in (x, y, z)):
                        min_coords[0] = min(min_coords[0], x)
                        min_coords[1] = min(min_coords[1], y)
                        min_coords[2] = min(min_coords[2], z)
                        max_coords[0] = max(max_coords[0], x)
                        max_coords[1] = max(max_coords[1], y)
                        max_coords[2] = max(max_coords[2], z)
                except (ValueError, IndexError):
                    pass
    except OSError as exc:
        return {"valid": False, "reason": f"read-error: {exc}", "path": p.as_posix()}

    # Ligand detection consumes *non-protein* residue keys so amino-acid
    # counts never get mixed into the ligand panel.
    ligand_info = detect_ligands(non_protein_residue_keys)
    bounding_extent = (
        [max_coords[i] - min_coords[i] if min_coords[i] != float("inf") else 0.0
         for i in range(3)]
        if min_coords[0] != float("inf")
        else [0.0, 0.0, 0.0]
    )
    return {
        "valid": True,
        "path": p.as_posix(),
        "atoms": atoms,
        "protein_atoms": protein_atoms,
        "hetatm_atoms": hetatm_atoms,
        "chains": sorted(chains),
        "n_chains": len(chains),
        "protein_residues": len(protein_residue_keys),
        "water_residues": waters,
        "ions": ions,
        "ligand_residues_total": len(ligand_info["instances"]),
        "ligand_resnames": ligand_info["resnames"],
        "ligand_instances": ligand_info["instances"],
        "extents_angstrom": [round(v, 2) for v in bounding_extent],
        "centroid_angstrom": [
            round((min_coords[i] + max_coords[i]) / 2, 2) if min_coords[i] != float("inf") else None
            for i in range(3)
        ],
    }


def ligand_atom_counts(path: str | Path) -> dict[str, int]:
    """Return a Counter of ligand residue names → atom count.

    Useful for the ligand tools pane of the molecular viewer. Returns an
    empty dict if the path doesn't exist or can't be read.
    """
    p = Path(path)
    if not p.is_file():
        return {}
    counts: Counter[str] = Counter()
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if not line.startswith("HETATM"):
                    continue
                resname = line[17:20].strip().upper()
                if resname in WATER_RESNAMES or resname in ION_RESNAMES:
                    continue
                counts[resname] += 1
    except OSError:
        return {}
    return dict(counts)
