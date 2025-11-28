# FastMDAnalysis/src/fastmdanalysis/analysis/hbonds.py

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
import inspect
from pathlib import Path

import numpy as np
import mdtraj as md
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from .base import BaseAnalysis, AnalysisError
from ..utils.options import OptionsForwarder
from ..utils.plotting import apply_slide_style

log = logging.getLogger(__name__)


class HBondsAnalysis(BaseAnalysis):
    _ALIASES = {
        "atom_indices": "atoms",
        "selection": "atoms",
        "distance_cutoff_nm": "distance",
        "angle_cutoff_deg": "angle",
    }
    
    def __init__(
        self, 
        trajectory, 
        atoms: Optional[str] = None,
        distance: float = 0.25,
        angle: float = 120.0,
        periodic: bool = False,
        sidechain_only: bool = False,
        exclude_water: bool = False,
        strict: bool = False,
        **kwargs
    ):
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
            Aliases: atom_indices, selection
        distance : float
            Distance cutoff in nm (default 0.25). Alias: distance_cutoff_nm
        angle : float
            Angle cutoff in degrees (default 120). Alias: angle_cutoff_deg
        periodic : bool
            Whether to use periodic boundary conditions (default False).
        sidechain_only : bool
            If True, only consider sidechain-sidechain H-bonds (default False).
        exclude_water : bool
            If True, exclude water molecules from H-bond detection (default False).
        strict : bool
            If True, raise errors for unknown options. If False, log warnings.
        kwargs : dict
            Additional keyword arguments passed to BaseAnalysis.
        """
        log.info("Initializing hydrogen bonds analysis")
        log.debug("Input parameters: atoms=%s, distance=%.3f nm, angle=%.1f°, periodic=%s, "
                 "sidechain_only=%s, exclude_water=%s, strict=%s",
                 atoms, distance, angle, periodic, sidechain_only, exclude_water, strict)
        
        warn_unknown = kwargs.pop("_warn_unknown", False)

        analysis_opts = {
            "atoms": atoms,
            "distance": distance,
            "angle": angle,
            "periodic": periodic,
            "sidechain_only": sidechain_only,
            "exclude_water": exclude_water,
            "strict": strict,
        }
        analysis_opts.update(kwargs)
        
        forwarder = OptionsForwarder(aliases=self._ALIASES, strict=strict)
        resolved = forwarder.apply_aliases(analysis_opts)
        resolved = forwarder.filter_known(
            resolved,
            {
                "atoms",
                "distance",
                "angle",
                "periodic",
                "sidechain_only",
                "exclude_water",
                "strict",
                "output",
            },
            context="hbonds",
            warn=warn_unknown,
        )

        atoms = resolved.get("atoms", None)
        distance = resolved.get("distance", 0.25)
        angle = resolved.get("angle", 120.0)
        periodic = resolved.get("periodic", False)
        sidechain_only = resolved.get("sidechain_only", False)
        exclude_water = resolved.get("exclude_water", False)
        base_kwargs = {k: v for k, v in resolved.items() 
                      if k not in ("atoms", "distance", "angle", "periodic", 
                                  "sidechain_only", "exclude_water", "strict")}

        super().__init__(trajectory, **base_kwargs)
        self.atoms = atoms
        self.distance = float(distance)
        self.angle = float(angle)
        self.periodic = bool(periodic)
        self.sidechain_only = bool(sidechain_only)
        self.exclude_water = bool(exclude_water)
        self.strict = strict
        self.data: Optional[np.ndarray] = None
        self.results: Dict[str, object] = {}
        
        log.info("HBonds analysis initialized with %d frames, %d atoms", 
                trajectory.n_frames, trajectory.n_atoms)
        if atoms:
            log.info("Atom selection: %s", atoms)

    @staticmethod
    def _has_bonds(traj: md.Trajectory) -> bool:
        """Check if trajectory has bonds defined."""
        try:
            has_bonds = traj.topology.n_bonds > 0
            log.debug("Topology bond check: %d bonds found", traj.topology.n_bonds)
            return has_bonds
        except Exception as e:
            log.debug("Error checking bonds: %s", e)
            return False

    def _prepare_work_trajectory(self) -> tuple[md.Trajectory, str, bool]:
        """
        Build the trajectory to use for H-bond detection.

        Returns
        -------
        (work_traj, selection_label, used_fallback)
        """
        log.debug("Preparing working trajectory for H-bond detection")
        
        # First, honor user selection (if any)
        if self.atoms:
            log.debug("Selecting atoms with: %s", self.atoms)
            sel_idx = self.traj.topology.select(self.atoms)
            if sel_idx is None or len(sel_idx) == 0:
                log.error("No atoms selected using selection: %s", self.atoms)
                raise AnalysisError(f"No atoms selected using the selection: '{self.atoms}'")
            work = self.traj.atom_slice(sel_idx)
            selection_label = self.atoms
            log.info("Selected %d atoms from trajectory", work.n_atoms)
        else:
            work = self.traj
            selection_label = "all atoms"
            log.debug("Using all %d atoms", work.n_atoms)
            
        if self.exclude_water and not self.atoms:
            try:
                log.debug("Attempting to exclude water molecules")
                non_water_idx = self.traj.topology.select("not water")
                if non_water_idx is not None and len(non_water_idx) > 0:
                    work = self.traj.atom_slice(non_water_idx)
                    selection_label = "all atoms (excluding water)"
                    log.info("Excluded water molecules - %d atoms remaining", work.n_atoms)
            except Exception as e:
                log.warning("Failed to exclude water: %s", e)

        # Try to (re)create bonds
        log.debug("Creating standard bonds for topology")
        try:
            work.topology.create_standard_bonds()
            log.debug("Standard bonds created successfully")
        except Exception as e:
            log.debug("Could not create standard bonds: %s", e)

        # If no bonds (e.g., Cα-only), fall back to protein (or full traj)
        if not self._has_bonds(work):
            log.warning("Selected atoms have no bonds - attempting fallback to protein/all atoms")
            
            # Prefer protein subset if present
            try:
                prot_idx = self.traj.topology.select("protein")
                log.debug("Protein selection found %d atoms", len(prot_idx) if prot_idx is not None else 0)
            except Exception as e:
                log.debug("Error selecting protein: %s", e)
                prot_idx = np.arange(self.traj.n_atoms)
                
            if prot_idx is None or len(prot_idx) == 0:
                # Fall back to full trajectory
                fallback = self.traj
                fb_label = "all atoms (fallback)"
                log.info("No protein atoms found - falling back to all %d atoms", fallback.n_atoms)
            else:
                fallback = self.traj.atom_slice(prot_idx)
                fb_label = "protein (fallback)"
                log.info("Falling back to protein selection with %d atoms", fallback.n_atoms)

            try:
                fallback.topology.create_standard_bonds()
                log.debug("Standard bonds created for fallback topology")
            except Exception as e:
                log.debug("Could not create bonds for fallback: %s", e)

            if not self._has_bonds(fallback):
                log.error("No bonds found even after fallback - topology may be incomplete")
                raise AnalysisError(
                    "Hydrogen bonds analysis requires a bonded topology. "
                    "Could not infer bonds even after fallback to protein/all atoms. "
                    "Ensure your topology has standard residues or CONECT records."
                )

            return fallback, fb_label, True

        log.debug("Working trajectory prepared with %d atoms, %d bonds", 
                 work.n_atoms, work.topology.n_bonds)
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
        log.info("Starting hydrogen bonds analysis")
        try:
            # Prepare working trajectory (with auto-fallback if needed)
            work, label, used_fallback = self._prepare_work_trajectory()
            log.info(
                "HBonds analysis: using %s (n_frames=%d, n_atoms=%d%s)",
                label, work.n_frames, work.n_atoms,
                ", FALLBACK USED" if used_fallback else ""
            )

            # Per-frame H-bond detection and counting
            log.debug("Detecting hydrogen bonds across %d frames", work.n_frames)
            counts = np.zeros(work.n_frames, dtype=int)
            raw_by_frame: List[np.ndarray] = []
            
            # Prepare Baker-Hubbard parameters
            bh_kwargs = {"periodic": self.periodic}
            try:
                sig = inspect.signature(md.baker_hubbard)
                if 'dist' in sig.parameters:
                    bh_kwargs['dist'] = self.distance
                if 'angle' in sig.parameters:
                    # MDTraj expects angle in radians, we store in degrees
                    bh_kwargs['angle'] = np.deg2rad(self.angle)
                log.debug("Using Baker-Hubbard parameters: %s", bh_kwargs)
            except Exception as e:
                log.debug("Could not inspect baker_hubbard signature, using defaults: %s", e)
            
            # Process each frame
            for i in range(work.n_frames):
                # Baker–Hubbard on a single frame
                try:
                    hb_i = md.baker_hubbard(work[i], **bh_kwargs)
                except TypeError:
                    # Fallback if kwargs not supported
                    log.debug("Baker-Hubbard with custom kwargs failed, using defaults")
                    hb_i = md.baker_hubbard(work[i], periodic=self.periodic)
                    
                raw_by_frame.append(hb_i)
                counts[i] = len(hb_i)
                
                if i % max(1, work.n_frames // 10) == 0:  # Log progress every ~10%
                    log.debug("Processed frame %d/%d: %d H-bonds", i + 1, work.n_frames, counts[i])

            self.data = counts.reshape(-1, 1)
            self.results = {
                "hbonds_counts": self.data,
                "raw_hbonds_per_frame": raw_by_frame,
                "selection_used": label,
                "fallback": used_fallback,
            }

            # Save counts
            log.debug("Saving H-bond counts data")
            self._save_data(self.data, "hbonds_counts")
            
            # Write a small note if fallback happened
            if used_fallback:
                note_path = Path(self.outdir) / "hbonds_NOTE.txt"
                note_path.write_text(
                    "HBonds: your atom selection resulted in a topology with no bonds "
                    "(e.g., C-alpha-only). FastMDAnalysis automatically fell back to 'protein' "
                    "or all atoms to compute hydrogen bonds.\n"
                )
                log.info("Fallback note written to: %s", note_path)

            # Auto-plot
            log.debug("Generating H-bonds plot")
            plot_path = self.plot()
            
            log.info("HBonds analysis completed - mean: %.2f, std: %.2f, range: [%d, %d]",
                    np.mean(counts), np.std(counts), np.min(counts), np.max(counts))
            log.info("H-bonds plot saved to: %s", plot_path)
            
            return self.results

        except AnalysisError:
            log.error("HBonds analysis failed with AnalysisError")
            raise
        except Exception as e:
            log.error("HBonds analysis failed with unexpected error: %s", str(e))
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
        log.debug("Generating hydrogen bonds plot")
        
        if data is None:
            data = self.data
        if data is None:
            log.error("No hydrogen bonds data available for plotting")
            raise AnalysisError("No hydrogen bonds data available to plot. Please run analysis first.")

        frames = np.arange(1, len(data) + 1, dtype=int)
        title = kwargs.get("title", "Hydrogen Bonds per Frame")
        xlabel = kwargs.get("xlabel", "Frame")
        ylabel = kwargs.get("ylabel", "Number of H-Bonds")
        color = kwargs.get("color")
        linestyle = kwargs.get("linestyle", "-")

        log.debug("Plotting %d frames with custom params: title='%s', color=%s, linestyle=%s",
                 len(frames), title, color, linestyle)

        fig, ax = plt.subplots(figsize=(10, 6))
        plot_kwargs = {"marker": "o", "linestyle": linestyle}
        if color is not None:
            plot_kwargs["color"] = color
        y_vals = np.asarray(data, dtype=float).flatten()
        ax.plot(frames, y_vals, **plot_kwargs)
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.3)

        apply_slide_style(
            ax,
            x_values=frames,
            y_values=y_vals,
            x_max_ticks=8,
            y_max_ticks=6,
            zero_x=True,
            zero_y=True,
        )

        plot_path = self._save_plot(fig, "hbonds")
        plt.close(fig)
        
        log.debug("H-bonds plot saved to: %s", plot_path)
        return plot_path

