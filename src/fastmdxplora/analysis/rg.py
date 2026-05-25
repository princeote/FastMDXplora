"""Radius of Gyration (Rg).

Per-frame radius of gyration, a measure of overall molecular size and
compactness. For a single-chain protein, Rg typically tracks folding
state — unfolded conformations have higher Rg, compact native states
have lower Rg.

The formula::

    Rg(t) = sqrt( sum_i m_i * |r_i(t) - r_cm(t)|^2  /  sum_i m_i )

is computed by MDTraj's :func:`mdtraj.compute_rg`. By default the
calculation uses atomic masses from the topology (so the mass-weighted
Rg is reported); if a residue has no mass information (e.g. a custom
non-standard residue), MDTraj defaults to unit weights and the result
becomes the unweighted Rg.
"""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import mdtraj as md
import numpy as np

from fastmdxplora.analysis.base import Analysis
from fastmdxplora.analysis.orchestrator import register_analysis


class Rg(Analysis):
    """Per-frame radius of gyration.

    Parameters
    ----------
    by_chain : bool, default False
        If True, compute Rg separately for each chain in the topology
        (in addition to the whole-system Rg). Useful for multi-chain
        complexes where you want to track the compactness of each subunit.
    selection : str, optional
        MDTraj atom selection. Defaults to ``None`` which means "use all
        atoms" — appropriate for Rg of the entire system. For a protein
        Rg in a solvated system, pass ``selection="protein"``.
    **kwargs
        Standard base-class options.

    Output
    ------
    Single-column ``rg.dat`` (Rg in nm per frame), or multi-column when
    ``by_chain=True``: ``frame, total, chain0, chain1, ...``.
    """

    name = "rg"
    description = "Radius of gyration"
    default_selection = None  # use all atoms by default

    def __init__(
        self,
        *,
        by_chain: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.by_chain: bool = bool(by_chain)
        self.options.update(by_chain=self.by_chain)

    def compute(self, traj: md.Trajectory) -> np.ndarray:
        """Compute Rg per frame.

        Returns
        -------
        np.ndarray
            If ``by_chain=False``: shape (n_frames,), Rg in nm.
            If ``by_chain=True``: shape (n_frames, 1+n_chains), columns are
            ``[Rg_total, Rg_chain0, Rg_chain1, ...]``.
        """
        atom_idx = self.select_atoms(traj)

        # Sub-trajectory on the selected atoms, so compute_rg uses the right mass
        if len(atom_idx) < traj.n_atoms:
            sub = traj.atom_slice(atom_idx)
        else:
            sub = traj

        rg_total = md.compute_rg(sub).astype(np.float64)

        if not self.by_chain:
            return rg_total

        # Per-chain breakdown on the selected sub-topology
        n_chains = sub.topology.n_chains
        if n_chains <= 1:
            # No useful breakdown; still return the column for consistency.
            return rg_total.reshape(-1, 1)

        columns = [rg_total]
        for chain_idx in range(n_chains):
            chain_atoms = [
                a.index for a in sub.topology.chain(chain_idx).atoms
            ]
            if not chain_atoms:
                continue
            chain_traj = sub.atom_slice(chain_atoms)
            columns.append(md.compute_rg(chain_traj).astype(np.float64))

        self._n_chains = len(columns) - 1
        return np.column_stack(columns)

    def plot(self, result: np.ndarray, ax: plt.Axes) -> None:
        x, _ = self.frame_axis_for_plot(self._traj_for_plot, result)

        if result.ndim == 1:
            ax.plot(x, result, linewidth=1.4, label="total")
        else:
            ax.plot(x, result[:, 0], linewidth=1.6, label="total")
            for i in range(1, result.shape[1]):
                ax.plot(x, result[:, i], linewidth=1.0, label=f"chain {i - 1}")
            ax.legend(loc="best")

    # Same trajectory caching pattern as RMSD so the plot can read it.
    _traj_for_plot: md.Trajectory | None = None

    def run(self, traj: md.Trajectory):
        self._traj_for_plot = traj
        return super().run(traj)

    def frame_axis_for_plot(
        self, traj: md.Trajectory | None, result: np.ndarray
    ) -> tuple[np.ndarray, str]:
        if traj is None:
            n = result.shape[0] if result.ndim > 0 else len(result)
            return np.arange(n), "Frame"
        return self.frame_axis(traj)

    def default_xlabel(self) -> str | None:
        if self._traj_for_plot is None:
            return "Frame"
        _, label = self.frame_axis(self._traj_for_plot)
        return label

    def default_ylabel(self) -> str | None:
        return "Rg (nm)"


register_analysis(Rg.name, Rg)
