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
        
        # Parse sklearn version (e.g., "1.3.0" -> (1, 3, 0))
        # Handle version strings like "1.3.0.post1" or "1.3"
        version_str = sklearn_version.split('+')[0].split('-')[0]
        version_parts = []
        for part in version_str.split('.'):
            if part.isdigit():
                version_parts.append(int(part))
            else:
                # Handle non-numeric parts like "post1"
                break
        version_tuple = tuple(version_parts)
        
        # Build base parameters
        mds_params = {
            'n_components': self.n_components,
            'random_state': self.random_state,
        }
        
        # Determine API based on sklearn version
        if version_tuple >= (1, 4):
            # sklearn >= 1.4: metric=bool, dissimilarity=str
            mds_params.update({
                'init': 'random',
                'normalized_stress': 'auto',
                'metric': True if self.metric == "euclidean" else False,
                'dissimilarity': 'precomputed' if self.metric == "precomputed" else 'euclidean',
            })
        elif version_tuple >= (1, 3):
            # sklearn 1.3: dissimilarity param
            mds_params.update({
                'init': 'random',
                'normalized_stress': 'auto',
                'dissimilarity': self.metric,
            })
        else:
            # sklearn < 1.3: metric param
            mds_params['metric'] = self.metric
            
            # Try to add init parameter if supported
            try:
                # Test if init parameter exists
                test = MDS(init='random', n_components=2, random_state=42)
                mds_params['init'] = 'random'
            except TypeError:
                # init parameter not available
                pass
        
        # Try to add n_init parameter (suppresses warning in sklearn >= 1.9)
        try:
            # Test if n_init parameter exists
            test = MDS(n_init=4, n_components=2, random_state=42)
            mds_params['n_init'] = 4
        except TypeError:
            # n_init parameter not available
            pass
        
        # Create and fit MDS model
        self.model = MDS(**mds_params)
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