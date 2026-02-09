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
        
        # Base parameters that should always work
        base_params = {
            'n_components': self.n_components,
            'random_state': self.random_state,
        }
        
        # Try different API combinations in order of preference
        param_combinations = [
            # 1. Try with n_init=4 to suppress warning (sklearn >= 1.9)
            {**base_params, 'metric': self.metric, 'n_init': 4},
            # 2. Try with n_init=4 and dissimilarity (middle API)
            {**base_params, 'dissimilarity': self.metric, 'n_init': 4},
            # 3. Try with n_init=4 and new API (metric=bool, dissimilarity=str)
            {
                **base_params,
                'metric': True if self.metric == "euclidean" else False,
                'dissimilarity': 'precomputed' if self.metric == "precomputed" else 'euclidean',
                'n_init': 4,
            },
            # 4. Try without n_init (older sklearn)
            {**base_params, 'metric': self.metric},
            {**base_params, 'dissimilarity': self.metric},
            {
                **base_params,
                'metric': True if self.metric == "euclidean" else False,
                'dissimilarity': 'precomputed' if self.metric == "precomputed" else 'euclidean',
            },
            # 5. Bare minimum (should always work)
            base_params,
        ]
        
        # Try each combination until one works
        self.model = None
        for params in param_combinations:
            try:
                self.model = MDS(**params)
                # Quick test with minimal data to validate parameters
                test_data = X[:min(3, len(X))]
                _ = self.model.fit(test_data)
                logger.debug("MDS initialized successfully with params: %s", params)
                break  # Success!
            except (TypeError, ValueError, AttributeError) as e:
                logger.debug("MDS params failed %s: %s", params, str(e)[:100])
                continue
        
        # If all combinations failed, use bare minimum
        if self.model is None:
            logger.warning("All MDS parameter combinations failed, using bare minimum")
            self.model = MDS(**base_params)
        
        # Fit and transform
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