# FastMDAnalysis/src/fastmdanalysis/analysis/dimred.py

"""
Dimensionality Reduction Analysis Module

Main orchestrator for dimensionality reduction methods.
Delegates to specialized modules: pca, mds, tsne.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union
import logging

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize

from .base import BaseAnalysis, AnalysisError
from ..utils.options import OptionsForwarder
from ..utils.plotting import apply_slide_style, match_colorbar_font, auto_ticks

# Import the modularized dimensionality reduction methods
from .pca import PCAAnalysis
from .mds import MDSAnalysis
from .tsne import TSNEAnalysis

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


def _as_list(methods: Union[str, Sequence[str]]) -> List[str]:
    """
    Normalize methods to a lowercase list in canonical order.
    Supports: "all", comma-separated string, or an iterable.
    """
    if isinstance(methods, str):
        if methods.lower() == "all":
            return ["pca", "mds", "tsne"]
        items = [m.strip().lower() for m in methods.split(",")]
    else:
        items = [str(m).strip().lower() for m in methods]

    if "all" in items:
        return ["pca", "mds", "tsne"]

    order = ["pca", "mds", "tsne"]
    items_set = set(items)
    return [m for m in order if m in items_set]


class DimRedAnalysis(BaseAnalysis):
    """
    Dimensionality reduction (PCA, MDS, t-SNE) on Cartesian coordinates.

    Parameters
    ----------
    trajectory : mdtraj.Trajectory
        The trajectory to analyze.
    methods : {"all", "pca", "mds", "tsne"} or list of them
        Which embeddings to compute. "all" runs pca, mds, tsne.
        Alias: method (singular)
    atoms : str, optional
        MDTraj atom selection string.
    outdir : str, optional
        Output directory (default: "dimred_output").
    n_components : int, optional
        Number of components for dimensionality reduction (default 2).
    random_state : int, optional
        Random seed for reproducibility (default 42).
    perplexity : int, optional
        t-SNE perplexity (overrides tsne_perplexity).
    n_iter : int, optional
        t-SNE iterations (deprecated, use max_iter).
    max_iter : int, optional
        t-SNE max iterations (default 500).
    metric : str, optional
        Metric for MDS (default "euclidean"). Use "precomputed" for dissimilarity matrix.
    dissimilarity : str, optional
        Alias for metric in MDS.
    strict : bool
        If True, raise errors for unknown options. If False, log warnings.
    """

    _ALIASES = {
        "method": "methods",
        "atom_indices": "atoms",
        "selection": "atoms",
        "tsne_perplexity": "perplexity",
        "tsne_max_iter": "max_iter",
        "n_iter": "max_iter",  # deprecated but map it
        "dissimilarity": "metric",
    }

    def __init__(
        self,
        trajectory,
        methods: Union[str, Sequence[str]] = "all",
        atoms: Optional[str] = None,
        outdir: Optional[PathLike] = None,
        n_components: int = 2,
        random_state: int = 42,
        perplexity: Optional[int] = None,
        max_iter: int = 500,
        metric: str = "euclidean",
        strict: bool = False,
        **kwargs
    ):
        warn_unknown = kwargs.pop("_warn_unknown", False)

        analysis_opts = {
            "methods": methods,
            "atoms": atoms,
            "output": outdir,
            "n_components": n_components,
            "random_state": random_state,
            "perplexity": perplexity,
            "max_iter": max_iter,
            "metric": metric,
            "strict": strict,
        }
        analysis_opts.update(kwargs)
        
        forwarder = OptionsForwarder(aliases=self._ALIASES, strict=strict)
        resolved = forwarder.apply_aliases(analysis_opts)
        resolved = forwarder.filter_known(
            resolved,
            {
                "methods",
                "atoms",
                "output",
                "n_components",
                "random_state",
                "perplexity",
                "max_iter",
                "metric",
                "strict",
            },
            context="dimred",
            warn=warn_unknown,
        )

        methods = resolved.get("methods", "all")
        atoms = resolved.get("atoms", None)
        outdir = resolved.get("output", None)
        n_components = resolved.get("n_components", 2)
        random_state = resolved.get("random_state", 42)
        perplexity = resolved.get("perplexity", None)
        max_iter = resolved.get("max_iter", 500)
        metric = resolved.get("metric", "euclidean")
        
        # Initialize the base class with the trajectory
        super().__init__(trajectory, output=outdir)
        
        self.atoms = atoms
        self.methods = _as_list(methods)
        self.n_components = int(n_components)
        self.random_state = int(random_state)
        self.tsne_perplexity = perplexity
        self.tsne_max_iter = int(max_iter)
        self.mds_metric = metric
        self.strict = strict

        logger.info("Initialized dimensionality reduction analysis")
        logger.info("Methods: %s, n_components=%d, atoms=%s", 
                   self.methods, self.n_components, self.atoms if self.atoms else "ALL")
        if "tsne" in self.methods:
            logger.info("t-SNE parameters: max_iter=%d, perplexity=%s", 
                       self.tsne_max_iter, self.tsne_perplexity)

        # Results: method -> ndarray of shape (n_frames, 2)
        self.results: Dict[str, np.ndarray] = {}

    # ------------------------------- helpers ---------------------------------

    def _flatten_xyz(self) -> np.ndarray:
        """
        Return (n_frames, n_atoms*3) float32 array for (optionally) selected atoms.
        """
        t = self.traj
        if self.atoms:
            logger.info("Selecting atoms: %s", self.atoms)
            idx = t.topology.select(self.atoms)
            if idx.size == 0:
                raise AnalysisError(f"Atom selection returned 0 atoms: {self.atoms}")
            t = t.atom_slice(idx, inplace=False)
            logger.info("Atom selection yielded %d atoms", len(idx))

        # (n_frames, n_atoms, 3) -> (n_frames, n_atoms * 3)
        X = t.xyz.astype(np.float32).reshape((t.n_frames, -1), order="C")
        logger.debug("Flattened coordinates: shape=%s", X.shape)
        return X

    def _save_array(self, name: str, arr: np.ndarray) -> Path:
        """Save array to file using BaseAnalysis method."""
        logger.debug("Saving %s coordinates to file", name)
        path = self._save_data(arr, f"dimred_{name}")
        logger.info("%s coordinates saved to %s", name.upper(), path)
        return path

    def _plot_one(self, name: str, emb: np.ndarray) -> Path:
        """
        Scatter colored by frame index; returns the saved PNG path.
        """
        logger.debug("Generating %s projection plot", name)
        fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)

        # Color by frame index with a colorbar
        n_frames = emb.shape[0]
        frame_colors = np.arange(1, n_frames + 1, dtype=np.int32)
        norm = Normalize(vmin=0.0, vmax=float(n_frames))
        sc = ax.scatter(
            emb[:, 0],
            emb[:, 1],
            s=20,
            c=frame_colors,
            cmap="viridis",
            alpha=0.7,
            norm=norm,
        )
        cb = fig.colorbar(sc, ax=ax)
        cb.set_label("Frame Index")
        
        # Fixed: Use auto_ticks directly without manually adding endpoints
        # This prevents duplicate ticks at boundaries
        if n_frames <= 1:
            ticks = np.asarray([0.0, float(n_frames)])
        else:
            # Let auto_ticks handle the tick generation properly
            ticks = auto_ticks(
                np.array([0.0, float(n_frames)], dtype=float),
                max_ticks=6,
                include_zero=True,
            )
            # Ensure we have reasonable fallback if auto_ticks returns None
            if ticks is None or ticks.size == 0:
                ticks = np.linspace(0.0, float(n_frames), num=min(6, n_frames + 1))
        
        # Remove any ticks that are very close to each other (within 1% of range)
        if ticks.size > 1:
            tick_range = float(n_frames)
            min_tick_separation = tick_range * 0.01  # 1% of total range
            unique_ticks = [ticks[0]]
            for i in range(1, len(ticks)):
                if abs(ticks[i] - unique_ticks[-1]) > min_tick_separation:
                    unique_ticks.append(ticks[i])
            ticks = np.array(unique_ticks)
        
        cb.set_ticks(ticks)
        cb.set_ticklabels([f"{int(round(t))}" for t in ticks])

        # Set titles and labels based on method
        title_map = {
            "pca": "PCA Projection",
            "mds": "MDS Projection", 
            "tsne": "t-SNE Projection"
        }
        title = title_map.get(name, f"{name.upper()} Projection")
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel("Component 1", fontsize=12)
        ax.set_ylabel("Component 2", fontsize=12)
        
        # Add grid for better readability
        ax.grid(True, alpha=0.3)
        
        # Remove top and right spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        apply_slide_style(
            ax,
            x_values=emb[:, 0],
            y_values=emb[:, 1],
            x_max_ticks=6,
            y_max_ticks=6,
        )
        match_colorbar_font(cb, ax)

        # Save plot using BaseAnalysis method
        out = self._save_plot(fig, f"dimred_{name}")
        plt.close(fig)
        logger.debug("%s projection plot saved to %s", name.upper(), out)
        return out

    # --------------------------------- API -----------------------------------

    def run(self) -> "DimRedAnalysis":
        """
        Compute the requested embeddings and save numeric outputs immediately.
        """
        try:
            logger.info("Starting dimensionality reduction analysis...")
            X_flat = self._flatten_xyz()
            n_frames = X_flat.shape[0]
            n_features = X_flat.shape[1]
            
            logger.info("Input data: %d frames, %d features", n_frames, n_features)

            # Use modularized methods
            for method in self.methods:
                logger.info("Running dimensionality reduction method: %s", method)

                if method == "pca":
                    # Use PCA module
                    pca = PCAAnalysis(
                        n_components=self.n_components,
                        random_state=self.random_state
                    )
                    emb = pca.fit_transform(X_flat)
                    self.results["pca"] = emb
                    self._save_array("pca", emb)
                    logger.info("PCA explained variance ratio: %s", pca.explained_variance_ratio_)

                elif method == "mds":
                    # Use MDS module
                    mds = MDSAnalysis(
                        n_components=self.n_components,
                        random_state=self.random_state,
                        metric=self.mds_metric
                    )
                    emb = mds.fit_transform(X_flat)
                    self.results["mds"] = emb
                    self._save_array("mds", emb)

                elif method == "tsne":
                    # Use t-SNE module
                    tsne = TSNEAnalysis(
                        n_components=self.n_components,
                        random_state=self.random_state,
                        perplexity=self.tsne_perplexity,
                        max_iter=self.tsne_max_iter
                    )
                    emb = tsne.fit_transform(X_flat)
                    self.results["tsne"] = emb
                    self._save_array("tsne", emb)

                else:
                    raise AnalysisError(f"Unknown dimensionality reduction method: {method}")

            # Generate plots automatically after computation
            logger.info("Generating projection plots...")
            self.plot()

            logger.info("Dimensionality reduction analysis complete. Methods computed: %s", 
                       list(self.results.keys()))
            return self

        except AnalysisError:
            raise
        except Exception as e:
            logger.exception("Dimensionality reduction failed")
            raise AnalysisError(f"Dimensionality reduction failed: {e}")

    def plot(self) -> Dict[str, Path]:
        """
        Generate and save plots for each computed embedding, returning a {method: Path} map.
        """
        if not self.results:
            raise AnalysisError("No dimensionality reduction results available. Run the analysis first.")

        logger.info("Generating projection plots for methods: %s", list(self.results.keys()))
        out: Dict[str, Path] = {}
        for name, emb in self.results.items():
            out[name] = self._plot_one(name, emb)
        
        logger.info("All projection plots generated: %s", list(out.keys()))
        return out

    def _save_plot(self, fig, name: str):
        """Save the figure as a PNG file in the output directory and log its path."""
        plot_path = self.outdir / f"{name}.png"
        fig.savefig(plot_path, bbox_inches="tight")
        logger.info("Plot saved to %s", plot_path)
        return plot_path
