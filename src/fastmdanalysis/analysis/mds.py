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
        
        # Parse sklearn version string (handle "1.3.0", "1.3.0.post1", etc.)
        version_str = sklearn_version.split('+')[0].split('-')[0]
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
        logger.debug("Sklearn version: %s -> %s", sklearn_version, version_tuple)
        
        # Base parameters that always work
        base_params = {
            'n_components': self.n_components,
            'random_state': self.random_state,
        }
        
        # ===== HANDLE METRIC/DISSIMILARITY PARAMETER BASED ON SKLEARN VERSION =====
        
        # Try to determine which API to use by testing parameters
        # Order: newest API first, fall back to older APIs
        
        # First, check if metric_mds parameter exists (sklearn >= 1.10)
        try:
            if self.metric == "euclidean":
                test_params = {'metric_mds': True, 'n_components': 2}
                _ = MDS(**test_params)
                base_params['metric_mds'] = True
                logger.debug("Using metric_mds=True (sklearn >= 1.10 API)")
            elif self.metric == "precomputed":
                test_params = {'metric_mds': False, 'n_components': 2}
                _ = MDS(**test_params)
                base_params['metric_mds'] = False
                logger.debug("Using metric_mds=False (sklearn >= 1.10 API)")
            else:
                # For non-standard metrics, try dissimilarity
                test_params = {'dissimilarity': self.metric, 'n_components': 2}
                _ = MDS(**test_params)
                base_params['dissimilarity'] = self.metric
                logger.debug("Using dissimilarity='%s'", self.metric)
                
        except TypeError:
            # metric_mds not available, try metric=True/False (sklearn 1.4-1.9)
            try:
                if self.metric == "euclidean":
                    test_params = {'metric': True, 'n_components': 2}
                    _ = MDS(**test_params)
                    base_params['metric'] = True
                    logger.debug("Using metric=True (sklearn 1.4-1.9 API)")
                elif self.metric == "precomputed":
                    test_params = {'metric': False, 'n_components': 2}
                    _ = MDS(**test_params)
                    base_params['metric'] = False
                    logger.debug("Using metric=False (sklearn 1.4-1.9 API)")
                else:
                    # For non-standard metrics, try dissimilarity
                    test_params = {'dissimilarity': self.metric, 'n_components': 2}
                    _ = MDS(**test_params)
                    base_params['dissimilarity'] = self.metric
                    logger.debug("Using dissimilarity='%s'", self.metric)
                    
            except TypeError:
                # metric=True/False not available, try dissimilarity (sklearn 1.3)
                try:
                    test_params = {'dissimilarity': self.metric, 'n_components': 2}
                    _ = MDS(**test_params)
                    base_params['dissimilarity'] = self.metric
                    logger.debug("Using dissimilarity='%s' (sklearn 1.3 API)", self.metric)
                except TypeError:
                    # Last resort: try old metric parameter (sklearn < 1.3)
                    try:
                        test_params = {'metric': self.metric, 'n_components': 2}
                        _ = MDS(**test_params)
                        base_params['metric'] = self.metric
                        logger.debug("Using metric='%s' (sklearn < 1.3 API)", self.metric)
                    except TypeError:
                        # If nothing works, use minimal parameters
                        logger.warning("Could not determine MDS API, using minimal parameters")
                        # Don't set any metric/dissimilarity parameter
        
        # ===== ADD OPTIONAL PARAMETERS TO SUPPRESS WARNINGS =====
        
        optional_params = [
            ('n_init', 4),           # Suppress n_init warning (sklearn >= 1.9)
            ('init', 'random'),      # Suppress init warning (sklearn >= 1.10)
            ('normalized_stress', 'auto'),
        ]
        
        for param_name, param_value in optional_params:
            try:
                test_params = {param_name: param_value, 'n_components': 2}
                _ = MDS(**test_params)
                base_params[param_name] = param_value
                logger.debug("Added optional parameter %s=%s", param_name, param_value)
            except TypeError:
                # Parameter not available in this sklearn version
                base_params.pop(param_name, None)
        
        # ===== CREATE AND FIT MDS MODEL =====
        
        logger.debug("Creating MDS with final parameters: %s", base_params)
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