# FastMDAnalysis/src/fastmdanalysis/analysis/hierarchical.py

"""
Hierarchical Clustering Module
"""

from __future__ import annotations

import logging
from typing import Dict

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage

from .base import AnalysisError

logger = logging.getLogger(__name__)


class HierarchicalCluster:
    """Hierarchical clustering implementation."""
    
    def __init__(
        self,
        n_clusters: int,
        linkage_method: str = "ward"
    ):
        self.n_clusters = n_clusters
        self.linkage_method = linkage_method
        self.linkage_matrix = None
        
    def fit_predict(self, X: np.ndarray) -> np.ndarray:
        """Fit hierarchical clustering and return cluster labels (1..K)."""
        logger.info("Running hierarchical clustering with n_clusters=%d, linkage=%s", 
                   self.n_clusters, self.linkage_method)
        
        logger.info("Computing %s linkage for hierarchical clustering...", self.linkage_method)
        self.linkage_matrix = linkage(X, method=self.linkage_method)
        labels = fcluster(self.linkage_matrix, t=int(self.n_clusters), criterion="maxclust").astype(int, copy=False)
        
        logger.info("Hierarchical clustering completed")
        return labels
    
    def get_results(self, labels: np.ndarray, save_data_func) -> Dict:
        """Get hierarchical clustering results dictionary."""
        frame_idx = np.arange(labels.size, dtype=int)
        return {
            "labels": labels,
            "n_clusters": int(self.n_clusters),
            "linkage": self.linkage_matrix,
            "labels_file": save_data_func(
                np.column_stack((frame_idx, labels)), "hierarchical_labels",
                header="frame label(1..K)", fmt="%d",
            ),
            "linkage_file": save_data_func(
                self.linkage_matrix, "hierarchical_linkage",
                header="cluster1 cluster2 distance sample_count", fmt="%.6f",
            ),
        }