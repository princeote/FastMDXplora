"""TrpCage reference dataset (placeholder).

A 20-residue miniprotein commonly used to validate MD analysis pipelines.
v0.1.0 exposes a placeholder class with the expected API surface so that
example notebooks and tests can be written against the final API now.
The actual trajectory data files are bundled in a future release.
"""

from __future__ import annotations

from pathlib import Path

# Placeholder paths. In v0.2+ these will resolve to bundled data files
# inside the package.
_DATA_DIR = Path(__file__).parent / "data"


class TrpCage:
    """Reference TrpCage miniprotein trajectory.

    Attributes
    ----------
    traj : str
        Path to the trajectory file (placeholder in v0.1.0).
    top : str
        Path to the topology file (placeholder in v0.1.0).
    """

    traj: str = str(_DATA_DIR / "trp_cage.dcd")
    top: str = str(_DATA_DIR / "trp_cage.pdb")
    pdb_id: str = "1L2Y"
    n_residues: int = 20
    description: str = "TrpCage miniprotein (1L2Y), 20 residues"
