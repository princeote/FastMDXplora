from __future__ import annotations

import warnings
import numpy as np

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from sklearn.decomposition import PCA
from sklearn.manifold import MDS, TSNE

from .base import BaseAnalysis, AnalysisError

class DimRedAnalysis(BaseAnalysis):
    def __init__(self, trajectory, methods="all", atoms="protein and name CA", **kwargs):
        super().__init__(trajectory, **kwargs)
        if isinstance(methods, str):
            if methods.lower() == "all":
                self.methods = ["pca", "mds", "tsne"]
            else:
                self.methods = [methods.lower()]
        elif isinstance(methods, list):
            methods_lower = [m.lower() for m in methods]
            self.methods = ["pca", "mds", "tsne"] if "all" in methods_lower else methods_lower
        else:
            raise AnalysisError("Parameter 'methods' must be a string or a list of strings.")

        self.atoms = atoms
        if self.atoms is not None:
            self.atom_indices = self.traj.topology.select(self.atoms)
            if self.atom_indices is None or len(self.atom_indices) == 0:
                raise AnalysisError("No atoms found using the given atom selection for dimensionality reduction.")
            self._feature_traj = self.traj.atom_slice(self.atom_indices)
        else:
            self.atom_indices = None
            self._feature_traj = self.traj
        self.results = {}
        self.data = None

    def run(self) -> dict:
        X = self._feature_traj.xyz
        X_flat = X.reshape(self._feature_traj.n_frames, -1)

        for method in self.methods:
            if method == "pca":
                pca = PCA(n_components=2)
                emb = pca.fit_transform(X_flat)
                self.results["pca"] = emb
                self._save_data(emb, "dimred_pca")

            elif method == "mds":
                # Stable across sklearn versions
                mds = MDS(n_components=2, random_state=42, dissimilarity="euclidean")
                emb = mds.fit_transform(X_flat)
                self.results["mds"] = emb
                self._save_data(emb, "dimred_mds")

            elif method in ["tsne", "t-sne"]:
                # Prefer max_iter (>=1.5); fall back to n_iter for older sklearn without warning
                try:
                    tsne = TSNE(n_components=2, random_state=42, metric="euclidean", max_iter=1000)
                except TypeError:
                    tsne = TSNE(n_components=2, random_state=42, metric="euclidean", n_iter=1000)
                emb = tsne.fit_transform(X_flat)
                self.results["tsne"] = emb
                self._save_data(emb, "dimred_tsne")

            else:
                raise AnalysisError(f"Unknown dimensionality reduction method: {method}")

        self.data = self.results
        self.plot()
        return self.results

    def plot(self, data=None, method=None, **kwargs):
        if data is None:
            data = self.data
        if data is None:
            raise AnalysisError("No dimensionality reduction data available to plot. Please run analysis first.")

        def _plot_embedding(embedding, method_name):
            title = kwargs.get("title", f"{method_name.upper()} Projection")
            xlabel = kwargs.get("xlabel", "Component 1")
            ylabel = kwargs.get("ylabel", "Component 2")
            marker = kwargs.get("marker", "o")
            cmap = kwargs.get("cmap", "viridis")

            fig = plt.figure(figsize=(10, 8))
            colors = np.arange(self.traj.n_frames)
            sc = plt.scatter(embedding[:, 0], embedding[:, 1], c=colors, cmap=cmap, marker=marker)
            plt.title(title)
            plt.xlabel(xlabel)
            plt.ylabel(ylabel)
            plt.grid(alpha=0.3)
            cbar = plt.colorbar(sc)
            cbar.set_label("Frame Index")
            plot_path = self._save_plot(fig, f"dimred_{method_name}")
            plt.close(fig)
            return plot_path

        if method:
            m = method.lower()
            if m not in data:
                raise AnalysisError(f"Dimensionality reduction method '{m}' not found in results.")
            return _plot_embedding(data[m], m)
        else:
            out = {}
            for m, emb in data.items():
                out[m] = _plot_embedding(emb, m)
            return out

