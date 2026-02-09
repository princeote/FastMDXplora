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
        # Each combination tries to suppress specific warnings
        param_combinations = [
            # Combination 1: Full suppression (n_init=4, init='random') + new API
            {
                **base_params,
                'metric': True if self.metric == "euclidean" else False,
                'dissimilarity': 'precomputed' if self.metric == "precomputed" else 'euclidean',
                'n_init': 4,
                'init': 'random',
                'normalized_stress': 'auto',
            },
            # Combination 2: Full suppression + middle API
            {
                **base_params,
                'dissimilarity': self.metric,
                'n_init': 4,
                'init': 'random',
                'normalized_stress': 'auto',
            },
            # Combination 3: Full suppression + old API
            {
                **base_params,
                'metric': self.metric,
                'n_init': 4,
                'init': 'random',
                'normalized_stress': 'auto',
            },
            # Combination 4: Just init='random' + new API
            {
                **base_params,
                'metric': True if self.metric == "euclidean" else False,
                'dissimilarity': 'precomputed' if self.metric == "precomputed" else 'euclidean',
                'init': 'random',
            },
            # Combination 5: Just init='random' + middle API
            {
                **base_params,
                'dissimilarity': self.metric,
                'init': 'random',
            },
            # Combination 6: Just init='random' + old API
            {
                **base_params,
                'metric': self.metric,
                'init': 'random',
            },
            # Combination 7: Just n_init=4 + new API
            {
                **base_params,
                'metric': True if self.metric == "euclidean" else False,
                'dissimilarity': 'precomputed' if self.metric == "precomputed" else 'euclidean',
                'n_init': 4,
            },
            # Combination 8: Just n_init=4 + middle API
            {
                **base_params,
                'dissimilarity': self.metric,
                'n_init': 4,
            },
            # Combination 9: Just n_init=4 + old API
            {
                **base_params,
                'metric': self.metric,
                'n_init': 4,
            },
            # Combination 10: Basic new API
            {
                **base_params,
                'metric': True if self.metric == "euclidean" else False,
                'dissimilarity': 'precomputed' if self.metric == "precomputed" else 'euclidean',
            },
            # Combination 11: Basic middle API
            {
                **base_params,
                'dissimilarity': self.metric,
            },
            # Combination 12: Basic old API
            {
                **base_params,
                'metric': self.metric,
            },
            # Combination 13: Bare minimum (no metric/dissimilarity at all)
            base_params,
        ]
        
        # Try each combination until one works
        self.model = None
        successful_params = None
        
        for params in param_combinations:
            try:
                # Remove None values if any parameter checking added them
                clean_params = {k: v for k, v in params.items() if v is not None}
                self.model = MDS(**clean_params)
                
                # Quick test with minimal data to validate parameters
                test_size = min(3, len(X))
                if test_size > 0:
                    test_data = X[:test_size]
                    _ = self.model.fit(test_data)
                
                successful_params = clean_params
                logger.debug("MDS initialized successfully with params: %s", clean_params)
                break  # Success!
                
            except (TypeError, ValueError, AttributeError) as e:
                # Log only first few failures to avoid spam
                if param_combinations.index(params) < 5:
                    logger.debug("MDS params failed %s: %s", list(params.keys())[:3], str(e)[:80])
                continue
        
        # If all combinations failed, use bare minimum (should never happen)
        if self.model is None:
            logger.warning("All MDS parameter combinations failed, using bare minimum")
            self.model = MDS(**base_params)
            successful_params = base_params
        
        # Fit and transform with the successful parameters
        logger.debug("Final MDS parameters: %s", successful_params)
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