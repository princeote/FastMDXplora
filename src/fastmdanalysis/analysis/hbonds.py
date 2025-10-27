"""
Hydrogen Bonds Analysis Module

Detects hydrogen bonds in an MD trajectory using the Baker–Hubbard algorithm.
If an atom selection is provided (via the 'atoms' parameter), the trajectory is subset accordingly.
If the selection yields a topology with no bonds (e.g., Cα-only), we automatically fall back to
using the full protein selection for H-bond detection.

The analysis computes the number of hydrogen bonds for each frame, saves the resulting data,
and automatically generates a default plot of hydrogen bonds versus frame.
Users can later replot the data with customizable plotting options.
"""
from __future__ import annotations

from typing import Dict, List, Optional
import logging
from pathlib import Path

import numpy as np
import mdtraj as md
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from .base import BaseAnalysis, AnalysisError

log = logging.getLogger(__name__)


class HBondsAnalysis(BaseAnalysis):
    def __init__(self, trajectory, atoms: Optional[str] = None, **kwargs):
        """
        Initialize Hydrogen Bonds analysis.

        Parameters
        ----------
        trajectory : mdtraj.Trajectory
            The MD trajectory to analyze.
        atoms : str, optional
            MDTraj atom selection string specifying which atoms to use.
            If provided, the trajectory will be subset using this selection.
            If None, all atoms in the trajectory are used.
        kwargs : dict
            Additional keyword arguments passed to BaseAnalysis.
        """
        super().__init__(trajectory, **kwargs)
        self.atoms = atoms
        self.data: Optional[np.ndarray] = None
        self.results: Dict[str, object] = {}

    @staticmethod
    def _has_bonds(traj: md.Trajectory) -> bool:
        try:
            return traj.topology.n_bonds > 0
        except Exception:
            return False

    def _prepare_work_trajectory(self) -> tuple[md.Trajectory, str, bool]:
        """
        Build the trajectory to use for H-bond detection.

        Returns
        -------
        (work_traj, selection_label, used_fallback)
        """
        # First, honor user selection (if any)
        if self.atoms:
            sel_idx = self.traj.topology.select(self.atoms)
            if sel_idx is None or len(sel_idx) == 0:
                raise AnalysisError(f"No atoms selected using the selection: '{self.atoms}'")
            work = self.traj.atom_slice(sel_idx)
            selection_label = self.atoms
        else:
            work = self.traj
            selection_label = "all atoms"

        # Try to (re)create bonds
        try:
            work.topology.create_standard_bonds()
        except Exception:
            pass

        # If no bonds (e.g., Cα-only), fall back to protein (or full traj)
        if not self._has_bonds(work):
            # Prefer protein subset if present
            try:
                prot_idx = self.traj.topology.select("protein")
            except Exception:
                prot_idx = np.arange(self.traj.n_atoms)
            if prot_idx is None or len(prot_idx) == 0:
                # Fall back to full trajectory
                fallback = self.traj
                fb_label = "all atoms (fallback)"
            else:
                fallback = self.traj.atom_slice(prot_idx)
                fb_label = "protein (fallback)"

            try:
                fallback.topology.create_standard_bonds()
            except Exception:
                pass

            if not self._has_bonds(fallback):
                raise AnalysisError(
                    "Hydrogen bonds analysis requires a bonded topology. "
                    "Could not infer bonds even after fallback to protein/all atoms. "
                    "Ensure your topology has standard residues or CONECT records."
                )

            return fallback, fb_label, True

        return work, selection_label, False

    def run(self) -> dict:
        """
        Compute hydrogen bonds per frame using the Baker–Hubbard algorithm.

        Returns
        -------
        dict
            {
              "hbonds_counts": (n_frames, 1) array with number of H-bonds per frame,
              "raw_hbonds_per_frame": list of per-frame arrays of (donor, hydrogen, acceptor) indices,
              "selection_used": label for which selection was used,
              "fallback": bool indicating if a fallback selection was needed
            }
        """
        try:
            # Prepare working trajectory (with auto-fallback if needed)
            work, label, used_fallback = self._prepare_work_trajectory()
            log.info(
                "HBonds: starting (atoms=%s, n_frames=%d, n_atoms=%d%s)",
                self.atoms if self.atoms is not None else "None",
                work.n_frames,
                work.n_atoms,
                ", fallback used" if used_fallback else "",
            )

            # Per-frame H-bond detection and counting
            counts = np.zeros(work.n_frames, dtype=int)
            raw_by_frame: List[np.ndarray] = []
            for i in range(work.n_frames):
                # Baker–Hubbard on a single frame
                hb_i = md.baker_hubbard(work[i], periodic=False)
                raw_by_frame.append(hb_i)
                counts[i] = len(hb_i)

            self.data = counts.reshape(-1, 1)
            self.results = {
                "hbonds_counts": self.data,
                "raw_hbonds_per_frame": raw_by_frame,
                "selection_used": label,
                "fallback": used_fallback,
            }

            # Save counts
            self._save_data(self.data, "hbonds_counts")
            # Write a small note if fallback happened
            if used_fallback:
                note = Path(self.outdir) / "hbonds_NOTE.txt"
                note.write_text(
                    "HBonds: your atom selection resulted in a topology with no bonds "
                    "(e.g., Cα-only). FastMDAnalysis automatically fell back to 'protein' "
                    "or all atoms to compute hydrogen bonds.\n"
                )

            # Auto-plot
            self.plot()
            log.info("HBonds: done.")
            return self.results

        except AnalysisError:
            raise
        except Exception as e:
            raise AnalysisError(f"Hydrogen bonds analysis failed: {e}")

    def plot(self, data=None, **kwargs):
        """
        Generate a plot of hydrogen bonds versus frame.

        Parameters
        ----------
        data : array-like, optional
            The hydrogen bond count data to plot. If None, uses the data computed by run().
        kwargs : dict
            Customizable matplotlib-style keyword arguments. For example:
                - title: Plot title (default: "Hydrogen Bonds per Frame").
                - xlabel: x-axis label (default: "Frame").
                - ylabel: y-axis label (default: "Number of H-Bonds").
                - color: Line or marker color.
                - linestyle: Line style (default: "-" for solid line).

        Returns
        -------
        Path
            The file path to the saved plot.
        """
        if data is None:
            data = self.data
        if data is None:
            raise AnalysisError("No hydrogen bonds data available to plot. Please run analysis first.")

        frames = np.arange(len(data))
        title = kwargs.get("title", "Hydrogen Bonds per Frame")
        xlabel = kwargs.get("xlabel", "Frame")
        ylabel = kwargs.get("ylabel", "Number of H-Bonds")
        color = kwargs.get("color")
        linestyle = kwargs.get("linestyle", "-")

        fig = plt.figure(figsize=(10, 6))
        plot_kwargs = {"marker": "o", "linestyle": linestyle}
        if color is not None:
            plot_kwargs["color"] = color
        plt.plot(frames, np.asarray(data).flatten(), **plot_kwargs)
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.grid(alpha=0.3)
        ax = plt.gca()
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))

        plot_path = self._save_plot(fig, "hbonds")
        plt.close(fig)
        return plot_path

