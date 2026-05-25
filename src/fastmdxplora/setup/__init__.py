"""System preparation phase.

The setup phase accepts a system input (PDB file path, PDB ID, or
sequence) and produces a simulation-ready system: fixed residues, added
hydrogens at the requested pH, solvated, ionized, and parameterized with
the chosen force field. Outputs include a topology PDB plus serialized
OpenMM ``System`` and ``State`` XMLs that the simulation phase consumes
directly.

Public API
----------
- :func:`run` -- the orchestrator-facing entry point
- :func:`fix_pdb_with_pdbfixer` -- the PDBFixer wrapper (matches
  the expected PDBFixer signature)
- :func:`prepare_system` -- solvate, ionize, parameterize, serialize

PDBFixer and OpenMM are optional dependencies installed via the
``[setup]`` extras group (conda-forge recommended).
"""

from fastmdxplora.setup.pdbfix import fix_pdb_with_pdbfixer
from fastmdxplora.setup.pipeline import run
from fastmdxplora.setup.prepare import prepare_system

__all__ = ["fix_pdb_with_pdbfixer", "prepare_system", "run"]
