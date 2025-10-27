from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.manifold import MDS, TSNE

from .base import BaseAnalysis


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


def _auto_tsne_perplexity(n_frames: int, user_value: Optional[int] = None) -> int:
    """
    Choose a sensible t-SNE perplexity. Clamp to [5, 30] and < n_frames.
    """
    if user_value is not None:
        p = int(user_value)
    else:
        # simple heuristic: ~ min(30, max(5, n/10))
        p = max(5, min(30, n_frames // 10 if n_frames > 0 else 30))
    # t-SNE requires perplexity < n_samples
    p = min(p, max(1, n_frames - 1))
    return max(5, p)


class DimRedAnalysis(BaseAnalysis):
    """
    Dimensionality reduction (PCA, MDS, t-SNE) on Cartesian coordinates.

    Parameters
    ----------
    trajectory : mdtraj.Trajectory
        The trajectory to analyze.
    methods : {"all", "pca", "mds", "tsne"} or list of them
        Which embeddings to compute. "all" runs pca, mds, tsne.
    atoms : str, optional
        MDTraj atom selection string.
    outdir : str, optional
        Output directory (default: "dimred_output").
    tsne_perplexity : int, optional
        Override the auto-chosen t-SNE perplexity.
    tsne_max_iter : int, optional
        Iterations for t-SNE (default 500, avoids deprecated `n_iter`).
    random_state : int, optional
        Random seed for reproducibility (default 42).
    """

    def __init__(
        self,
        trajectory,
        methods: Union[str, Sequence[str]] = "all",
        atoms: Optional[str] = None,
        outdir: Optional[PathLike] = None,
        tsne_perplexity: Optional[int] = None,
        tsne_max_iter: int = 500,
        random_state: int = 42,
    ):
        # Initialize the base class with the trajectory
        super().__init__(trajectory, output=outdir)
        
        self.atoms = atoms
        self.methods = _as_list(methods)
        self.tsne_perplexity = tsne_perplexity
        self.tsne_max_iter = int(tsne_max_iter)
        self.random_state = int(random_state)

        # Results: method -> ndarray of shape (n_frames, 2)
        self.results: Dict[str, np.ndarray] = {}

    # ------------------------------- helpers ---------------------------------

    def _flatten_xyz(self) -> np.ndarray:
        """
        Return (n_frames, n_atoms*3) float32 array for (optionally) selected atoms.
        """
        t = self.traj
        if self.atoms:
            idx = t.topology.select(self.atoms)
            if idx.size == 0:
                raise ValueError(f"Atom selection returned 0 atoms: {self.atoms}")
            t = t.atom_slice(idx, inplace=False)

        # (n_frames, n_atoms, 3) -> (n_frames, n_atoms * 3)
        X = t.xyz.astype(np.float32).reshape((t.n_frames, -1), order="C")
        return X

    def _save_array(self, name: str, arr: np.ndarray) -> Path:
        """Save array to file using BaseAnalysis method."""
        return self._save_data(arr, f"dimred_{name}")

    def _plot_one(self, name: str, emb: np.ndarray) -> Path:
        """
        Scatter colored by frame index; returns the saved PNG path.
        """
        fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)

        # Color by frame index with a colorbar
        c = np.arange(emb.shape[0], dtype=np.int32)
        sc = ax.scatter(emb[:, 0], emb[:, 1], s=20, c=c, cmap="viridis", alpha=0.7)
        cb = fig.colorbar(sc, ax=ax)
        cb.set_label("Frame Index")

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

        # Save plot using BaseAnalysis method
        out = self._save_plot(fig, f"dimred_{name}")
        plt.close(fig)
        return out

    # --------------------------------- API -----------------------------------

    def run(self) -> "DimRedAnalysis":
        """
        Compute the requested embeddings and save numeric outputs immediately.
        Also logs brief progress via BaseAnalysis logger (if configured).
        """
        X_flat = self._flatten_xyz()
        n_frames = X_flat.shape[0]

        # PCA
        if "pca" in self.methods:
            pca = PCA(n_components=2, random_state=self.random_state)
            emb = pca.fit_transform(X_flat)
            self.results["pca"] = emb.astype(np.float32)
            self._save_array("pca", self.results["pca"])

        # MDS (silence FutureWarning by setting n_init explicitly)
        if "mds" in self.methods:
            mds = MDS(
                n_components=2,
                n_init=4,  # default value today; avoids FutureWarning("...will change...")
                random_state=self.random_state,
                normalized_stress="auto",
            )
            emb = mds.fit_transform(X_flat)
            self.results["mds"] = emb.astype(np.float32)
            self._save_array("mds", self.results["mds"])

        # t-SNE
        if "tsne" in self.methods:
            perplexity = _auto_tsne_perplexity(n_frames, self.tsne_perplexity)
            tsne = TSNE(
                n_components=2,
                perplexity=perplexity,
                max_iter=self.tsne_max_iter,  # use max_iter (not deprecated n_iter)
                random_state=self.random_state,
                init="pca",
                learning_rate="auto",
            )
            emb = tsne.fit_transform(X_flat)
            self.results["tsne"] = emb.astype(np.float32)
            self._save_array("tsne", self.results["tsne"])

        # Generate plots automatically after computation
        self.plot()
        
        return self

    def plot(self) -> Dict[str, Path]:
        """
        Generate and save plots for each computed embedding, returning a {method: Path} map.
        """
        out: Dict[str, Path] = {}
        for name, emb in self.results.items():
            out[name] = self._plot_one(name, emb)
        return out