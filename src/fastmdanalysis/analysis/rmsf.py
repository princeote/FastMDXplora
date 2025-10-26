# FastMDAnalysis/src/fastmdanalysis/analysis/rmsf.py
"""
RMSF Analysis Module

Calculates the Root-Mean-Square Fluctuation (RMSF) for each atom in an MD
trajectory. If an atom selection is provided, only those atoms are analyzed;
otherwise, all atoms are used. The analysis computes the fluctuations relative
to the average structure, saves the computed data, and automatically generates
a bar plot. The plotter now *auto-thins* crowded x-axis tick labels and can
label by residue when appropriate.

Typical use (inside FastMDAnalysis):
------------------------------------
res = fastmda.rmsf(atoms="protein and name CA")  # computes & plots
# or re-plot with custom axes:
res.plot(by="residue", max_ticks=25, rotate=60, filename="rmsf_ca.png")
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Union
from pathlib import Path

import numpy as np
import mdtraj as md

# Headless rendering for CLI / batch usage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .base import BaseAnalysis, AnalysisError


# ------------------------------- Helpers --------------------------------------


def _infer_residue_labels(residues: Sequence[md.core.residue.Residue]) -> List[str]:
    """
    Build compact labels like '42-ALA' for a sequence of MDTraj residues.
    """
    labels: List[str] = []
    for r in residues:
        try:
            # r.resSeq is PDB-style numbering (preferred), fall back to 0-based index
            resnum = getattr(r, "resSeq", None)
            if resnum is None:
                resnum = r.index
            name = getattr(r, "name", "RES")
            labels.append(f"{resnum}-{name}")
        except Exception:
            labels.append(str(getattr(r, "index", "?")))
    return labels


def _auto_tick_step(n: int, max_ticks: int) -> int:
    """
    Compute a thinning step so that ~max_ticks or fewer labels are drawn.
    """
    if n <= 0:
        return 1
    if n <= max_ticks:
        return 1
    # ceil(n / max_ticks)
    return int(np.ceil(n / float(max_ticks)))


# ------------------------------- Analysis -------------------------------------


class RMSFAnalysis(BaseAnalysis):
    """
    Per-atom RMSF analysis with an x-axis that stays readable for long selections.
    """

    # ---- Construction --------------------------------------------------------
    def __init__(self, trajectory: md.Trajectory, atoms: Optional[str] = None, **kwargs):
        """
        Parameters
        ----------
        trajectory
            MDTraj trajectory to analyze.
        atoms
            MDTraj selection string (e.g., "protein and name CA"). If None, all atoms are used.
        kwargs
            Passed through to BaseAnalysis (e.g., output directories/labels if supported there).
        """
        super().__init__(trajectory, **kwargs)
        self.atoms: Optional[str] = atoms

        # Populated during run()
        self.data: Optional[np.ndarray] = None              # shape (N, 1)
        self.results: Dict[str, np.ndarray] = {}
        self._sel_indices: Optional[np.ndarray] = None      # global atom indices (length N)
        self._sel_residues: Optional[List[md.core.residue.Residue]] = None  # residues for selected atoms

    # ---- Core computation ----------------------------------------------------
    def run(self) -> Dict[str, np.ndarray]:
        """
        Compute RMSF (nm) for each selected atom relative to the average structure.

        Returns
        -------
        dict
            {"rmsf": (N, 1) array of per-atom RMSF values in nm}
        """
        try:
            # Atom selection (global indices)
            if self.atoms:
                sel = self.traj.topology.select(self.atoms)
                if sel is None or len(sel) == 0:
                    raise AnalysisError(f"No atoms selected using selection: '{self.atoms}'")
                subtraj = self.traj.atom_slice(sel)
                self._sel_indices = np.asarray(sel, dtype=int)
            else:
                subtraj = self.traj
                # Use global indices 0..N-1 when plotting (display as 1..N by default)
                self._sel_indices = None

            # Track residue list for labeling (aligned to subtraj atoms)
            try:
                self._sel_residues = [atom.residue for atom in subtraj.topology.atoms]
            except Exception:
                self._sel_residues = None

            # Average structure as reference
            avg_xyz = np.mean(subtraj.xyz, axis=0, keepdims=True)
            ref = md.Trajectory(avg_xyz, subtraj.topology)

            # Per-atom RMSF (nm) relative to average structure
            rmsf_values = md.rmsf(subtraj, ref)  # returns shape (N,)
            self.data = rmsf_values.reshape(-1, 1)
            self.results = {"rmsf": self.data}

            # Persist data and make a default plot
            self._save_data(self.data, "rmsf")
            self.plot()

            return self.results
        except AnalysisError:
            raise
        except Exception as e:
            raise AnalysisError(f"RMSF analysis failed: {e}")

    # ---- Plotting ------------------------------------------------------------
    def plot(
        self,
        data: Optional[Union[Sequence[float], np.ndarray]] = None,
        *,
        by: str = "auto",           # 'auto' | 'atom' | 'residue'
        max_ticks: int = 30,        # hard cap on number of labeled x ticks
        tick_step: Optional[int] = None,  # show every Nth tick (overrides max_ticks)
        rotate: int = 45,           # tick label rotation
        figsize=(12, 6),
        title: str = "RMSF per Atom",
        xlabel: Optional[str] = None,
        ylabel: str = "RMSF (nm)",
        color: Optional[str] = None,
        filename: str = "rmsf.png",
    ) -> Path:
        """
        Generate a bar plot of RMSF with a readable x-axis.

        Parameters
        ----------
        data
            RMSF values to plot. If None, uses computed data from run().
        by
            'auto' chooses 'residue' if residue info is available and N>60; else 'atom'.
        max_ticks
            Target maximum number of x tick labels (used when tick_step is None).
        tick_step
            Force showing every Nth tick. If provided, overrides max_ticks heuristic.
        rotate
            Rotation angle for x-tick labels (degrees).
        figsize, title, xlabel, ylabel, color, filename
            Usual matplotlib/IO controls. If xlabel is None, it is inferred from 'by'.

        Returns
        -------
        Path
            File path of the saved plot image.
        """
        if data is None:
            data = self.data
        if data is None:
            raise AnalysisError("No RMSF data available to plot. Run the analysis first.")

        y = np.asarray(data, dtype=float).flatten()
        n = int(y.size)
        x = np.arange(n)

        # Decide labeling mode
        if by not in ("auto", "atom", "residue"):
            raise AnalysisError(f"Invalid 'by' value: {by}. Use 'auto', 'atom', or 'residue'.")
        if by == "auto":
            by = "residue" if (self._sel_residues is not None and n > 60) else "atom"

        # Build full label set
        if by == "residue" and self._sel_residues is not None:
            labels_all = _infer_residue_labels(self._sel_residues)
            xlabel_eff = "Residue"
        else:
            # Prefer global atom indices if selection was provided; else 1..N
            if self._sel_indices is not None and len(self._sel_indices) == n:
                labels_all = [str(int(k)) for k in self._sel_indices]
            else:
                labels_all = [str(i + 1) for i in x]  # 1-based for readability
            xlabel_eff = "Atom Index"

        # Determine ticks
        step = tick_step if tick_step is not None else _auto_tick_step(n, max_ticks)
        ticks = x[::step]
        ticklabels = [labels_all[i] for i in ticks]

        # Plot
        fig, ax = plt.subplots(figsize=figsize)
        bar_kwargs = {"width": 0.9}
        if color is not None:
            bar_kwargs["color"] = color
        ax.bar(x, y, **bar_kwargs)

        ax.set_title(title)
        ax.set_xlabel(xlabel if (xlabel is not None) else xlabel_eff)
        ax.set_ylabel(ylabel)

        ax.set_xticks(ticks)
        ax.set_xticklabels(ticklabels, rotation=rotate, ha="right")

        # Subtle grid: y prominent, x light for readability
        ax.grid(axis="y", alpha=0.3)
        ax.grid(axis="x", alpha=0.12)

        fig.tight_layout()
        outpath = self._save_plot(fig, "rmsf", filename=filename)
        plt.close(fig)
        return outpath
