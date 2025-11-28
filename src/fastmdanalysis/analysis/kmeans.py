#FastMDAnalysis/src/fastmdanalysis/analysis/kmeans.py

"""
KMeans Clustering Module
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

import numpy as np
from sklearn.cluster import KMeans

from .base import AnalysisError

logger = logging.getLogger(__name__)


class KMeansCluster:
    """KMeans clustering implementation."""
    
    def __init__(
        self,
        n_clusters: int,
        random_state: int = 42,
        n_init: int = 10
    ):
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.n_init = n_init
        self.model = None
        
    def fit_predict(self, X: np.ndarray) -> np.ndarray:
        """Fit KMeans and return cluster labels (1..K)."""
        logger.info("Running KMeans with n_clusters=%d, random_state=%d", 
                   self.n_clusters, self.random_state)
        
        self.model = KMeans(
            n_clusters=int(self.n_clusters), 
            random_state=self.random_state, 
            n_init=self.n_init
        )
        labels0 = self.model.fit_predict(X).astype(int, copy=False)  # 0..K-1
        labels = labels0 + 1  # 1..K
        
        logger.info("KMeans completed with inertia: %.4f", self.model.inertia_)
        return labels
    
    def get_results(self, labels: np.ndarray, X: np.ndarray, save_data_func) -> Dict:
        """Get KMeans results dictionary."""
        frame_idx = np.arange(labels.size, dtype=int)
        return {
            "labels": labels,
            "n_clusters": int(self.n_clusters),
            "inertia_": float(self.model.inertia_),
            "labels_file": save_data_func(
                np.column_stack((frame_idx, labels)), "kmeans_labels",
                header="frame label(1..K)", fmt="%d",
            ),
            "coordinates_file": save_data_func(
                X, "kmeans_coordinates",
                header="Flattened coordinates", fmt="%.6f",
            ),
        }