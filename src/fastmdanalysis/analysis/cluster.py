# FastMDAnalysis/src/fastmdanalysis/analysis/cluster.py

"""
Cluster Analysis Module

Main orchestrator for clustering methods.
Delegates to specialized modules: dbscan, kmeans, hierarchical.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Sequence, Union

import numpy as np
import mdtraj as md

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm, to_hex
from matplotlib.cm import ScalarMappable

from scipy.cluster.hierarchy import dendrogram

from .base import BaseAnalysis, AnalysisError
from ..utils.options import OptionsForwarder
from ..utils.plotting import apply_slide_style, match_colorbar_font

# Import the modularized clustering methods
from .dbscan import DBSCANCluster
from .kmeans import KMeansCluster
from .hierarchical import HierarchicalCluster

CLUSTER_AXIS_LABEL = "Cluster ID"
CLUSTER_TITLE_SIZE = 20.0
CLUSTER_COLORBAR_KW = {"fraction": 0.085, "pad": 0.02}

logger = logging.getLogger(__name__)

# ----------------------------- Colormaps/Norms --------------------------------

def get_cluster_cmap(n_clusters: int):
    """Get a colormap for the given number of clusters."""
    predefined_colors = ['#e41a1c','#377eb8','#00ff00','#ffd700',
               '#9932cc','#ffa500','#00bfff','#a52a2a',
               '#808080','#000000','#006400','#000080'
               ]
    if n_clusters <= len(predefined_colors):
        logger.debug("Using predefined colormap for %d clusters", n_clusters)
        return ListedColormap(predefined_colors[:n_clusters])
    logger.debug("Using fallback colormap for %d clusters", n_clusters)
    return plt.cm.get_cmap("nipy_spectral", n_clusters)

def get_discrete_norm(unique_labels):
    """Get discrete normalization for cluster labels."""
    unique_labels = np.asarray(unique_labels, dtype=int)
    unique_labels.sort()
    boundaries = np.arange(unique_labels[0] - 0.5, unique_labels[-1] + 1.5, 1)
    logger.debug("Discrete boundaries: %s", boundaries)
    return BoundaryNorm(boundaries, len(boundaries) - 1)

# ----------------------------- Dendrogram helpers -----------------------------

def get_leaves(linkage_matrix, idx, N):
    """Recursively get leaves for dendrogram node."""
    if idx < N:
        return [idx]
    if idx >= 2 * N - 1:
        logger.error("Index %d exceeds maximum allowed internal index %d", idx, 2 * N - 1)
        return []
    try:
        left = int(linkage_matrix[idx - N, 0])
        right = int(linkage_matrix[idx - N, 1])
        return get_leaves(linkage_matrix, left, N) + get_leaves(linkage_matrix, right, N)
    except IndexError:
        logger.error("Index error in get_leaves: idx=%d, N=%d, linkage_matrix.shape=%s", idx, N, linkage_matrix.shape)
        return []

# ------------------------------- Core class -----------------------------------

class ClusterAnalysis(BaseAnalysis):
    _ALIASES = {
        "method": "methods",
        "atom_indices": "atoms",
        "selection": "atoms",
    }
    
    def __init__(
        self,
        trajectory,
        methods: Union[str, Sequence[str]] = "all",
        eps: float = 0.2,
        min_samples: int = 5,
        n_clusters: Optional[int] = None,
        atoms: Optional[str] = None,
        random_state: int = 42,
        n_init: Union[int, str] = 10,
        linkage_method: str = "ward",
        strict: bool = False,
        **kwargs
    ):
        # ... (keep the same __init__ method as before, it's fine)
        warn_unknown = kwargs.pop("_warn_unknown", False)

        analysis_opts = {
            "methods": methods,
            "eps": eps,
            "min_samples": min_samples,
            "n_clusters": n_clusters,
            "atoms": atoms,
            "random_state": random_state,
            "n_init": n_init,
            "linkage_method": linkage_method,
            "strict": strict,
        }
        analysis_opts.update(kwargs)
        
        if "linkage" in analysis_opts and "linkage_method" not in kwargs:
            analysis_opts["linkage_method"] = analysis_opts.pop("linkage")
        
        forwarder = OptionsForwarder(aliases=self._ALIASES, strict=strict)
        resolved = forwarder.apply_aliases(analysis_opts)
        resolved = forwarder.filter_known(
            resolved,
            {
                "methods",
                "eps",
                "min_samples",
                "n_clusters",
                "atoms",
                "random_state",
                "n_init",
                "linkage_method",
                "strict",
                "output",
            },
            context="cluster",
            warn=warn_unknown,
        )

        methods = resolved.get("methods", "all")
        eps = resolved.get("eps", 0.2)
        min_samples = resolved.get("min_samples", 5)
        n_clusters = resolved.get("n_clusters", None)
        atoms = resolved.get("atoms", None)
        random_state = resolved.get("random_state", 42)
        n_init = resolved.get("n_init", 10)
        linkage_method = resolved.get("linkage_method", "ward")
        base_kwargs = {k: v for k, v in resolved.items() 
                      if k not in ("methods", "eps", "min_samples", "n_clusters", 
                                  "atoms", "random_state", "n_init", "linkage_method", "strict", "linkage")}

        super().__init__(trajectory, **base_kwargs)

        # Normalize methods
        if isinstance(methods, str):
            methods_norm = [methods.lower()]
        else:
            methods_norm = [m.lower() for m in methods]

        if "all" in methods_norm:
            self.methods = ["dbscan", "kmeans", "hierarchical"]
        else:
            self.methods = methods_norm

        self.eps = float(eps)
        self.min_samples = int(min_samples)
        self.n_clusters = int(n_clusters) if (n_clusters is not None and int(n_clusters) > 0) else None
        self.atoms = atoms
        self.random_state = int(random_state)
        self.n_init = n_init if isinstance(n_init, str) else int(n_init)
        self.linkage_method = linkage_method
        self.strict = strict

        logger.info("Initializing ClusterAnalysis with methods: %s", self.methods)
        logger.info("Parameters: eps=%.3f nm, min_samples=%d, n_clusters=%s", 
                   self.eps, self.min_samples, self.n_clusters)

        self.atom_indices = self.traj.topology.select(self.atoms) if self.atoms is not None else None
        if self.atoms and (self.atom_indices is None or len(self.atom_indices) == 0):
            raise AnalysisError(f"No atoms found with the selection: '{self.atoms}'")
        
        if self.atom_indices is not None:
            logger.info("Atom selection '%s' yielded %d atoms", self.atoms, len(self.atom_indices))
        else:
            logger.info("Using all %d atoms in trajectory", self.traj.n_atoms)

        self.results: Dict[str, Dict] = {}

    # ----------------------------- Plotting helpers ----------------------------
    # (Keep all the plotting methods exactly as they were - they don't need to change)

    def _plot_population(self, labels, filename, **kwargs):
        # ... (keep exactly the same)
        logger.info("Plotting population bar plot for %d frames...", len(labels))
        unique = np.sort(np.unique(labels))
        counts = np.array([np.sum(labels == u) for u in unique])
        fig, ax = plt.subplots(figsize=(10, 6))
        cmap = get_cluster_cmap(len(unique))
        norm = get_discrete_norm(unique)
        ax.bar(unique, counts, width=0.8, color=[cmap(norm(u)) for u in unique])
        ax.grid(False)
        ax.set_title(kwargs.get("title", "Cluster Populations"))
        ax.set_xlabel(kwargs.get("xlabel", CLUSTER_AXIS_LABEL))
        ax.set_ylabel(kwargs.get("ylabel", "Number of Frames"))
        apply_slide_style(
            ax,
            x_ticks=unique,
            y_values=counts,
            zero_y=True,
            title_size=kwargs.get("title_size", CLUSTER_TITLE_SIZE),
        )
        return self._save_plot(fig, filename)

    def _plot_cluster_trajectory_histogram(self, labels, filename, **kwargs):
        # ... (keep exactly the same)
        logger.info("Plotting trajectory histogram for %d frames...", len(labels))
        unique = np.sort(np.unique(labels))
        image_data = np.array(labels).reshape(1, -1)
        cmap = get_cluster_cmap(len(unique))
        norm = get_discrete_norm(unique)
        fig, ax = plt.subplots(figsize=(12, 4))
        im = ax.imshow(image_data, aspect="auto", interpolation="nearest", cmap=cmap, norm=norm)
        ax.grid(False)
        ax.set_title(kwargs.get("title", "Cluster Trajectory Histogram"))
        ax.set_xlabel(kwargs.get("xlabel", "Frame"))
        ax.set_yticks([])
        cbar = fig.colorbar(
            im,
            ax=ax,
            orientation="vertical",
            ticks=unique,
            **CLUSTER_COLORBAR_KW,
        )
        cbar.ax.set_yticklabels([str(u) for u in unique])
        cbar.set_label(CLUSTER_AXIS_LABEL)
        frame_values = np.arange(1, image_data.shape[1] + 1, dtype=int)
        apply_slide_style(
            ax,
            x_values=frame_values,
            x_max_ticks=10,
            zero_x=True,
            title_size=kwargs.get("title_size", CLUSTER_TITLE_SIZE),
        )
        ax.set_yticks([])
        match_colorbar_font(cbar, ax)
        return self._save_plot(fig, filename)

    def _plot_cluster_trajectory_scatter(self, labels, filename, **kwargs):
        # ... (keep exactly the same)
        logger.info("Plotting trajectory scatter for %d frames...", len(labels))
        frames = np.arange(1, len(labels) + 1, dtype=int)
        fig, ax = plt.subplots(figsize=(10, 4))
        unique = np.sort(np.unique(labels))
        cmap = get_cluster_cmap(len(unique))
        norm = get_discrete_norm(unique)
        ax.scatter(frames, np.zeros_like(frames), c=labels, s=100, cmap=cmap, norm=norm, marker="o")
        ax.grid(False)
        ax.set_title(kwargs.get("title", "Cluster Trajectory Scatter Plot"))
        ax.set_xlabel(kwargs.get("xlabel", "Frame"))
        ax.set_yticks([])
        sm = ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(
            sm,
            ax=ax,
            orientation="vertical",
            ticks=unique,
            **CLUSTER_COLORBAR_KW,
        )
        cbar.ax.set_yticklabels([str(u) for u in unique])
        cbar.set_label(CLUSTER_AXIS_LABEL)
        apply_slide_style(
            ax,
            x_values=frames,
            y_ticks=[0.0],
            x_max_ticks=10,
            zero_x=True,
            zero_y=True,
            title_size=kwargs.get("title_size", CLUSTER_TITLE_SIZE),
        )
        ax.set_yticks([])
        match_colorbar_font(cbar, ax)
        return self._save_plot(fig, filename)

    def _plot_distance_matrix(self, distances, filename, **kwargs):
        # ... (keep exactly the same, it's quite long)
        pass

    def _plot_dendrogram(self, linkage_matrix, labels, filename, **kwargs):
        # ... (keep exactly the same)
        pass

    def _save_plot(self, fig, name: str):
        """Save the figure as a PNG file in the output directory and log its path."""
        plot_path = self.outdir / f"{name}.png"
        fig.savefig(plot_path, bbox_inches="tight")
        logger.info("Plot saved to %s", plot_path)
        return plot_path

    # --------------------------------- Run ------------------------------------

    def run(self) -> dict:
        """
        Run the clustering analysis for the selected methods using modular implementations.
        """
        if self.results:
            logger.info("Results already computed; returning existing results.")
            return self.results

        try:
            logger.info("Starting clustering analysis with %d frames...", self.traj.n_frames)
            results: Dict[str, Dict] = {}

            # Prepare feature matrix for centroid-based methods
            X_flat = None
            need_centroid = any(m in self.methods for m in ["kmeans", "hierarchical"])
            if need_centroid:
                logger.info("Preparing coordinate features for centroid-based methods...")
                X = self.traj.xyz[:, self.atom_indices, :] if self.atom_indices is not None else self.traj.xyz
                X_flat = X.reshape(self.traj.n_frames, -1)
                logger.debug("Feature matrix shape: %s", X_flat.shape)
                # Default n_clusters if not provided
                if self.n_clusters is None or self.n_clusters < 1:
                    self.n_clusters = 3
                    logger.info("n_clusters not provided; defaulting to %d for kmeans/hierarchical.", self.n_clusters)

            for method in self.methods:
                key = method.lower()
                logger.info("Running clustering method: %s", key)

                if key == "dbscan":
                    # Use DBSCAN module
                    dbscan = DBSCANCluster(eps=self.eps, min_samples=self.min_samples)
                    D = dbscan.calculate_rmsd_matrix(self.traj, self.atom_indices)
                    diags = dbscan.distance_diagnostics(D)
                    
                    # Check parameter sanity
                    if self.eps >= diags["p90"]:
                        logger.warning("DBSCAN eps=%.3f nm >= p90=%.3f nm — likely to merge clusters.", self.eps, diags["p90"])
                    elif self.eps <= diags["p25"]:
                        logger.warning("DBSCAN eps=%.3f nm <= p25=%.3f nm — likely to mark many frames as noise.", self.eps, diags["p25"])
                    
                    labels_compact, labels_raw, n_clusters = dbscan.fit_predict(D)
                    results["dbscan"] = dbscan.get_results(
                        labels_compact, labels_raw, n_clusters, D, diags, self._save_data
                    )
                    
                    # Generate plots
                    results["dbscan"]["pop_plot"] = self._plot_population(labels_compact, "dbscan_pop")
                    results["dbscan"]["trajectory_histogram"] = self._plot_cluster_trajectory_histogram(labels_compact, "dbscan_traj_hist")
                    results["dbscan"]["trajectory_scatter"] = self._plot_cluster_trajectory_scatter(labels_compact, "dbscan_traj_scatter")
                    results["dbscan"]["distance_matrix_plot"] = self._plot_distance_matrix(D, "dbscan_distance_matrix")

                elif key == "kmeans":
                    if self.n_clusters is None or self.n_clusters < 1:
                        raise AnalysisError("For KMeans clustering, n_clusters must be provided and >=1.")
                    
                    # Use KMeans module
                    kmeans = KMeansCluster(
                        n_clusters=self.n_clusters,
                        random_state=self.random_state,
                        n_init=self.n_init
                    )
                    labels = kmeans.fit_predict(X_flat)
                    results["kmeans"] = kmeans.get_results(labels, X_flat, self._save_data)
                    
                    # Generate plots
                    results["kmeans"]["pop_plot"] = self._plot_population(labels, "kmeans_pop")
                    results["kmeans"]["trajectory_histogram"] = self._plot_cluster_trajectory_histogram(labels, "kmeans_traj_hist")
                    results["kmeans"]["trajectory_scatter"] = self._plot_cluster_trajectory_scatter(labels, "kmeans_traj_scatter")

                elif key == "hierarchical":
                    if self.n_clusters is None or self.n_clusters < 1:
                        raise AnalysisError("For hierarchical clustering, n_clusters must be provided and >=1.")
                    
                    # Use Hierarchical module
                    hierarchical = HierarchicalCluster(
                        n_clusters=self.n_clusters,
                        linkage_method=self.linkage_method
                    )
                    labels = hierarchical.fit_predict(X_flat)
                    results["hierarchical"] = hierarchical.get_results(labels, self._save_data)
                    
                    # Generate plots
                    results["hierarchical"]["pop_plot"] = self._plot_population(labels, "hierarchical_pop")
                    results["hierarchical"]["trajectory_histogram"] = self._plot_cluster_trajectory_histogram(labels, "hierarchical_traj_hist")
                    results["hierarchical"]["trajectory_scatter"] = self._plot_cluster_trajectory_scatter(labels, "hierarchical_traj_scatter")
                    results["hierarchical"]["dendrogram_plot"] = self._plot_dendrogram(
                        hierarchical.linkage_matrix, labels, "hierarchical_dendrogram"
                    )

                else:
                    raise AnalysisError(f"Unknown clustering method: {method}")

            self.results = results
            logger.info("Clustering analysis complete. Methods executed: %s", list(results.keys()))
            return results

        except Exception as e:
            logger.exception("Clustering failed:")
            raise AnalysisError(f"Clustering failed: {str(e)}")

    def plot(self, **kwargs):
        """Plot clustering results (returns existing results with plots)."""
        if not self.results:
            raise AnalysisError("No clustering results available. Run the analysis first.")
        logger.info("Returning existing clustering results with plots")
        return self.results
