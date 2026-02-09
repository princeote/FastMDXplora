# FastMDAnalysis/src/fastmdanalysis/analysis/mds.py


"""
MDS Analysis Module
"""

from __future__ import annotations

import logging
from typing import Dict

import numpy as np
from sklearn import __version__ as sklearn_version
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
        
        # Parse sklearn version (handle versions like "1.3.0" or "1.3.0.post1")
        version_str = sklearn_version.split('+')[0].split('-')[0]  # Remove +local or -dev suffixes
        version_parts = []
        for part in version_str.split('.'):
            if part.isdigit():
                version_parts.append(int(part))
            else:
                # Stop at non-numeric part like "post1"
                break
        
        # Ensure we have at least major.minor
        while len(version_parts) < 2:
            version_parts.append(0)
        
        version_tuple = tuple(version_parts[:2])  # Use only major.minor
        
        # Base parameters that always work
        base_params = {
            'n_components': self.n_components,
            'random_state': self.random_state,
        }
        
        # Determine which API to use based on sklearn version
        logger.debug("Sklearn version: %s -> %s", sklearn_version, version_tuple)
        
        if version_tuple >= (1, 4):
            # sklearn >= 1.4: Use new API (metric=bool), avoid deprecated 'dissimilarity'
            # The 'dissimilarity' param is deprecated in 1.4, removed in 1.10
            if self.metric == "euclidean":
                base_params['metric'] = True
            elif self.metric == "precomputed":
                base_params['metric'] = False
            else:
                # For other metrics, fall back to older API
                base_params['dissimilarity'] = self.metric
                
        elif version_tuple >= (1, 3):
            # sklearn 1.3: Use 'dissimilarity' parameter (not deprecated yet)
            base_params['dissimilarity'] = self.metric
            
        else:
            # sklearn < 1.3: Use 'metric' parameter
            base_params['metric'] = self.metric
        
        # Try to add optional parameters to suppress warnings
        optional_params = [
            ('n_init', 4),      # Suppresses: "The default value of `n_init` will change..."
            ('init', 'random'), # Suppresses: "The default value of `init` will change..."
            ('normalized_stress', 'auto'),
        ]
        
        for param_name, param_value in optional_params:
            try:
                # Test if parameter exists by creating a test MDS instance
                test_params = {param_name: param_value, 'n_components': 2}
                _ = MDS(**test_params)
                base_params[param_name] = param_value
                logger.debug("Added parameter %s=%s", param_name, param_value)
            except TypeError:
                logger.debug("Parameter %s not available in this sklearn version", param_name)
                # Remove if we added it earlier in a different code path
                base_params.pop(param_name, None)
        
        # Create the MDS model
        logger.debug("Creating MDS with parameters: %s", base_params)
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