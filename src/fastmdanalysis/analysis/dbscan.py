# FastMDAnalysis/src/fastmdanalysis/analysis/dbscan.py

"""
DBSCAN Clustering Module
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

import numpy as np
import mdtraj as md
from sklearn.cluster import DBSCAN

from .base import AnalysisError

logger = logging.getLogger(__name__)


def relabel_compact_positive(
    labels_raw: np.ndarray,
    start: int = 1,
    noise_as_last: bool = True
) -> Tuple[np.ndarray, Dict[int, int], Optional[int]]:
    """
    Map labels to contiguous positive integers 1..K; optionally map noise (-1) to K+1.
    """
    logger.debug("Relabeling %d labels to compact positive integers", len(labels_raw))
    raw = np.asarray(labels_raw, dtype=int)
    uniq_nonneg = sorted([u for u in np.unique(raw) if u >= 0])
    mapping = {u: (i + start) for i, u in enumerate(uniq_nonneg)}

    labels = np.empty_like(raw)
    for u, m in mapping.items():
        labels[raw == u] = m

    noise_label = None
    if np.any(raw == -1):
        noise_label = start + len(uniq_nonneg)
        labels[raw == -1] = noise_label
        logger.debug("Noise detected and mapped to label %d", noise_label)
    
    logger.debug("Relabeling complete: %d unique clusters%s", len(uniq_nonneg), 
                 " + noise" if noise_label is not None else "")
    return labels, mapping, noise_label


class DBSCANCluster:
    """DBSCAN clustering implementation."""
    
    def __init__(
        self,
        eps: float = 0.2,
        min_samples: int = 5
    ):
        self.eps = eps
        self.min_samples = min_samples
        self.model = None
        
    def calculate_rmsd_matrix(self, traj: md.Trajectory, atom_indices: Optional[np.ndarray] = None) -> np.ndarray:
        """Compute symmetric pairwise RMSD matrix (nm) over frames."""
        logger.info("Calculating RMSD matrix for %d frames...", traj.n_frames)
        T = traj.n_frames
        D = np.empty((T, T), dtype=np.float32)
        for i in range(T):
            ref = traj[i]
            if atom_indices is not None:
                D[:, i] = md.rmsd(traj, ref, atom_indices=atom_indices)
            else:
                D[:, i] = md.rmsd(traj, ref)
        D = 0.5 * (D + D.T)
        np.fill_diagonal(D, 0.0)
        logger.debug("RMSD matrix: shape=%s min=%.4f max=%.4f nm", D.shape, float(D.min()), float(D.max()))
        return D
    
    def distance_diagnostics(self, D: np.ndarray) -> Dict[str, float]:
        """Calculate distance matrix diagnostics."""
        tri = D[np.triu_indices_from(D, k=1)]
        if tri.size == 0:
            logger.warning("Empty distance matrix triangle")
            return {"p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0, "max": 0.0}
        diags = {
            "p25": float(np.percentile(tri, 25)),
            "p50": float(np.percentile(tri, 50)),
            "p75": float(np.percentile(tri, 75)),
            "p90": float(np.percentile(tri, 90)),
            "max": float(np.max(tri)),
        }
        logger.info("RMSD percentiles (nm): p25=%.3f p50=%.3f p75=%.3f p90=%.3f max=%.3f",
                    diags["p25"], diags["p50"], diags["p75"], diags["p90"], diags["max"])
        return diags
    
    def fit_predict(self, D: np.ndarray) -> np.ndarray:
        """Fit DBSCAN and return compact cluster labels (1..K, noise=K+1)."""
        logger.info("Running DBSCAN with eps=%.3f nm, min_samples=%d", self.eps, self.min_samples)
        
        self.model = DBSCAN(eps=self.eps, min_samples=self.min_samples, metric="precomputed")
        labels_raw = self.model.fit_predict(D).astype(int, copy=False)  # sklearn: -1=noise
        labels_compact, mapping, noise_label = relabel_compact_positive(labels_raw, start=1, noise_as_last=True)
        
        n_clusters = int(len(set(labels_compact)) - (1 if noise_label is not None else 0))
        logger.info("DBSCAN found %d clusters (excluding noise)", n_clusters)
        if noise_label is not None:
            noise_count = np.sum(labels_compact == noise_label)
            logger.info("DBSCAN noise: %d frames mapped to label %d", noise_count, noise_label)
            
        return labels_compact, labels_raw, n_clusters
    
    def get_results(self, labels_compact: np.ndarray, labels_raw: np.ndarray, n_clusters: int, 
                   D: np.ndarray, diags: Dict, save_data_func) -> Dict:
        """Get DBSCAN results dictionary."""
        frame_idx = np.arange(labels_compact.size, dtype=int)
        return {
            "labels_raw": labels_raw,
            "labels": labels_compact,
            "n_clusters": n_clusters,
            "eps_nm": float(self.eps),
            "min_samples": int(self.min_samples),
            "distance_percentiles_nm": diags,
            "distance_matrix": D,
            "labels_file_compact": save_data_func(
                np.column_stack((frame_idx, labels_compact)),
                "dbscan_labels_compact",
                header="frame label(1..K; noise=K+1)", fmt="%d",
            ),
            "labels_file_raw": save_data_func(
                np.column_stack((frame_idx, labels_raw)),
                "dbscan_labels_raw",
                header="frame label_raw(-1=noise)", fmt="%d",
            ),
        }