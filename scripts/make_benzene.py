#!/usr/bin/env python
"""Generate a benzene ligand as an SDF file for testing the protein-ligand path.

Benzene is the canonical small-molecule test ligand (12 atoms, near-instant
OpenFF charge assignment) used to smoke-test protein-ligand parameterization.
This writes a 3D, hydrogen-explicit ``benzene.sdf`` that OpenFF reads cleanly.

Usage
-----
    python scripts/make_benzene.py                 # -> ./benzene.sdf
    python scripts/make_benzene.py -o /tmp/lig.sdf # custom output path
    python scripts/make_benzene.py --smiles "Cc1ccccc1" --name toluene

Then feed it to FastMDXplora's ligand-capable force field:

    fastmdx explore --system 1L2Y --setup-forcefield amber-openff \\
        --setup-ligand benzene.sdf \\
        --simulate-nvt-steps 2 --simulate-npt-steps 2 \\
        --simulate-production-steps 4 --simulate-trajectory-interval-steps 1 \\
        --output /tmp/lig_test

Requires RDKit, which ships with the OpenFF stack
(``pip install 'fastmdxplora[ligand]'`` or
``conda install -c conda-forge openff-toolkit openmmforcefields``).
"""

from __future__ import annotations

import argparse
import sys


def make_ligand_sdf(smiles: str, name: str, output: str, seed: int = 42) -> str:
    """Embed a SMILES string to 3D and write a named SDF. Returns the path."""
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
    except ImportError:
        sys.exit(
            "RDKit is required. Install the ligand extra "
            "(pip install 'fastmdxplora[ligand]') or via conda-forge "
            "(conda install -c conda-forge rdkit)."
        )

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        sys.exit(f"Could not parse SMILES: {smiles!r}")

    # Explicit hydrogens + a single 3D conformer with a light cleanup — OpenFF
    # needs explicit Hs and at least one conformer to parameterize the ligand.
    mol = Chem.AddHs(mol)
    if AllChem.EmbedMolecule(mol, randomSeed=seed) != 0:
        sys.exit(f"Could not embed a 3D conformer for SMILES {smiles!r}")
    AllChem.MMFFOptimizeMolecule(mol)
    mol.SetProp("_Name", name)

    writer = Chem.SDWriter(output)
    writer.write(mol)
    writer.close()
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a test ligand SDF from SMILES (default: benzene).",
    )
    parser.add_argument(
        "-o", "--output", default="benzene.sdf",
        help="Output SDF path (default: benzene.sdf).",
    )
    parser.add_argument(
        "--smiles", default="c1ccccc1",
        help="Ligand SMILES (default: benzene 'c1ccccc1').",
    )
    parser.add_argument(
        "--name", default="benzene",
        help="Molecule name written into the SDF (default: benzene).",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for 3D embedding (default: 42, for reproducibility).",
    )
    args = parser.parse_args(argv)

    path = make_ligand_sdf(args.smiles, args.name, args.output, args.seed)
    print(f"Wrote {args.name} ({args.smiles}) -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
