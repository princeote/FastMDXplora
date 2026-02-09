# FastMDAnalysis/src/fastmdanalysis/analysis/mds.py


"""
MDS Analysis Module
"""

from __future__ import annotations

import logging
from typing import Dict

import numpy as np
from sklearn.manifold import MDS

from .base import AnalysisError

logger = logging.getLogger(__name__)


class MDSAnalysis:
    """MDS dimensionality reduction implementation."""
    
    def __init__(
        self,
        n_components: int = 2,
        random_state: int = 42,
        metric: str = "euclidean"
    ):
        self.n_components = n_components
        self.random_state = random_state
        self.metric = metric
        self.model = None
        
    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """Fit MDS and transform data."""
        logger.info("Computing MDS with metric='%s'...", self.metric)
        
        # Try different parameter combinations for sklearn version compatibility
        # Start with basic parameters that always work
        base_params = {
            'n_components': self.n_components,
            'random_state': self.random_state,
        }
        
        # Try different API combinations
        param_combinations = [
            # 1. Old API: metric parameter (sklearn < 1.3)
            {**base_params, 'metric': self.metric},
            # 2. Middle API: dissimilarity parameter (sklearn 1.3-1.4)
            {**base_params, 'dissimilarity': self.metric},
            # 3. New API: metric=bool, dissimilarity=str (sklearn >= 1.4)
            {
                **base_params,
                'metric': True if self.metric == "euclidean" else False,
                'dissimilarity': 'precomputed' if self.metric == "precomputed" else 'euclidean',
            },
            # 4. Bare minimum (should always work)
            base_params,
        ]
        
        # Try each combination until one works
        for params in param_combinations:
            try:
                self.model = MDS(**params)
                # Test if it actually works by trying to fit a tiny sample
                test_X = X[:2] if len(X) > 2 else X
                _ = self.model.fit(test_X)
                break  # Success!
            except (TypeError, ValueError) as e:
                continue
        
        # If all combinations failed, use bare minimum
        if self.model is None:
            self.model = MDS(**base_params)
        
        emb = self.model.fit_transform(X)
        
        logger.info("MDS completed")
        return emb.astype(np.float32)
    
    def get_results(self, emb: np.ndarray, save_data_func) -> Dict:
        """Get MDS results dictionary."""
        return {
            "embeddings": emb,
            "n_components": self.n_components,
            "metric": self.metric,
            "components_file": save_data_func(
                emb, "dimred_mds", header="mds_component_1 mds_component_2", fmt="%.6f"
            ),
        }