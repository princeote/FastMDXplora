"""PDBFixer wrapper.

PDBFixer wrapper providing
a single function that takes a raw PDB and produces a clean,
fully-protonated PDB suitable for solvation and parameterization.

The implementation calls PDBFixer's standard sequence:

  1. ``removeHeterogens`` (optional; removes everything that is not a
     standard residue, with an option to retain crystallographic waters)
  2. ``findMissingResidues`` (chain-break / loop detection)
  3. ``findMissingAtoms`` (heavy-atom completion)
  4. ``addMissingAtoms``
  5. ``addMissingHydrogens(pH)``  — places hydrogens at the specified pH

The function is strict: it raises rather than returning an error code.
This makes phase-level error
handling easy (the orchestrator's per-phase try/except records the
failure cleanly).

Requires :mod:`pdbfixer` and :mod:`openmm`, both conda-forge packages
in the optional ``[setup]`` extras group.
"""

from __future__ import annotations

from pathlib import Path

from fastmdxplora.utils.logging import get_logger

logger = get_logger("setup.pdbfix")


def fix_pdb_with_pdbfixer(
    input_pdb: str,
    output_pdb: str,
    *,
    ph: float = 7.0,
    keep_heterogens: bool = False,
    keep_water: bool = False,
) -> None:
    """Strict PDBFixer wrapper: raises on failure.

    Parameters
    ----------
    input_pdb : path-like
        Input PDB file path.
    output_pdb : path-like
        Where to write the fixed PDB. Parent directories are created.
    ph : float, default 7.0
        pH for hydrogen placement. Determines protonation state of
        titratable residues (Asp, Glu, His, Lys, etc.) via PDBFixer's
        residue-template library.
    keep_heterogens : bool, default False
        If True, retain non-standard residues (ligands, cofactors,
        ions). Default removes them.
    keep_water : bool, default False
        If True (and ``keep_heterogens=False``), retain crystallographic
        waters during heterogen removal. Has no effect when
        ``keep_heterogens=True``.

    Raises
    ------
    ImportError
        If ``pdbfixer`` or ``openmm`` is not installed. Install the
        ``[md]`` extras: ``pip install fastmdxplora[md]``, or
        better via conda: ``conda install -c conda-forge pdbfixer openmm``.
    FileNotFoundError
        If ``input_pdb`` doesn't exist.
    Exception
        Re-raises any error from PDBFixer (residue identification
        failures, malformed input, etc.).

    Notes
    -----
    Provides a clean PDBFixer wrapper with the
    ``fix_pdb_with_pdbfixer`` exactly so users moving between the two
    tools see identical results.
    """
    try:
        from openmm.app import PDBFile
        from pdbfixer import PDBFixer
    except ImportError as exc:
        raise ImportError(
            "fix_pdb_with_pdbfixer requires pdbfixer and openmm. Install "
            "via conda (recommended): conda install -c conda-forge "
            "pdbfixer openmm — or via pip with the optional [setup] "
            "extras: pip install fastmdxplora[md]."
        ) from exc

    inp = Path(input_pdb)
    out = Path(output_pdb)

    if not inp.exists():
        raise FileNotFoundError(f"Input PDB not found: {inp}")

    logger.info("Fixing PDB with PDBFixer: %s (pH=%s)", inp, ph)

    fixer = PDBFixer(filename=str(inp))
    if not keep_heterogens:
        fixer.removeHeterogens(keepWater=keep_water)
    fixer.findMissingResidues()
    fixer.findMissingAtoms()
    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(pH=float(ph))

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        PDBFile.writeFile(fixer.topology, fixer.positions, f, keepIds=True)
    logger.info(" - wrote fixed PDB to %s", out)
