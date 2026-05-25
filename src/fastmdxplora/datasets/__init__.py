"""Reference datasets bundled with FastMDXplora.

In v0.1.0 this is a thin namespace; in v0.2+ it will host reference
trajectories (such as TrpCage).
"""

from fastmdxplora.datasets.trp_cage import TrpCage

__all__ = ["TrpCage"]
