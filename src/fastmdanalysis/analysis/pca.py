# FastMDAnalysis/src/fastmdanalysis/analysis/pca.py


"""
PCA Analysis Module
"""

from __future__ import annotations

import logging
from typing import Dict

import numpy as np
from sklearn.decomposition import PCA

from .base import AnalysisError

logger = logging.getLogger(__name__)


class PCAAnalysis:
    """PCA dimensionality reduction implementation."""
    
    def __init__(
        self,
        n_components: int = 2,
        random_state: int = 42
    ):
        self.n_components = n_components
        self.random_state = random_state
        self.model = None
        self.explained_variance_ratio_ = None
        
    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """Fit PCA and transform data."""
        logger.info("Computing PCA with n_components=%d...", self.n_components)
        
        self.model = PCA(n_components=self.n_components, random_state=self.random_state)
        emb = self.model.fit_transform(X)
        self.explained_variance_ratio_ = self.model.explained_variance_ratio_
        
        logger.info("PCA completed: explained variance ratio: %s", 
                   self.explained_variance_ratio_)
        return emb.astype(np.float32)
    
    def get_results(self, emb: np.ndarray, save_data_func) -> Dict:
        """Get PCA results dictionary."""
        return {
            "embeddings": emb,
            "n_components": self.n_components,
            "explained_variance_ratio": self.explained_variance_ratio_,
            "components_file": save_data_func(
                emb, "dimred_pca", header="pca_component_1 pca_component_2", fmt="%.6f"
            ),
        }