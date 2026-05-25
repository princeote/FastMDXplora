"""``fastmdanalysis`` is the former name of this project.

FastMDAnalysis has been renamed and substantially expanded as **FastMDXplora**
(Fully Automated SysTem for Molecular Dynamics eXploration). FastMDXplora is
the direct successor: it keeps the same automated, reproducibility-by-design
analysis and adds full molecular dynamics setup, simulation (including
enhanced sampling), and protein-ligand workflows.

This package is a thin redirect that installs ``fastmdxplora`` and re-exports
its namespace, so existing ``pip install fastmdanalysis`` users are not broken.

Please migrate to the new name:

    pip install fastmdxplora
    import fastmdxplora

The original FastMDAnalysis work is published as:
    Aina, A.; Kwan, D. FastMDAnalysis: Software for Automated Analysis of
    Molecular Dynamics Trajectories. J. Comput. Chem. 2026, 47, e70350.
"""

import warnings

warnings.warn(
    "The 'fastmdanalysis' package has been renamed and expanded as "
    "'fastmdxplora'. Please install and import 'fastmdxplora' instead. "
    "This redirect package will not receive further updates.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export the canonical package so existing imports keep working.
from fastmdxplora import *  # noqa: F401,F403,E402

try:
    from fastmdxplora import __version__  # noqa: F401
except Exception:  # pragma: no cover
    __version__ = "2.0.0"
