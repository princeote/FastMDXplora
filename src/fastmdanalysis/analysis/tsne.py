# FastMDAnalysis/src/fastmdanalysis/analysis/tsne.py

"""
t-SNE Analysis Module
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

import numpy as np
from sklearn.manifold import TSNE

from .base import AnalysisError

logger = logging.getLogger(__name__)


def _auto_tsne_perplexity(n_frames: int, user_value: Optional[int] = None) -> int:
    """
    Choose a sensible t-SNE perplexity. Clamp to [5, 30] and < n_frames.
    """
    if user_value is not None:
        p = int(user_value)
    else:
        # simple heuristic: ~ min(30, max(5, n/10))
        p = max(5, min(30, n_frames // 10 if n_frames > 0 else 30))
    # t-SNE requires perplexity < n_samples
    p = min(p, max(1, n_frames - 1))
    return max(5, p)


class TSNEAnalysis:
    """t-SNE dimensionality reduction implementation."""
    
    def __init__(
        self,
        n_components: int = 2,
        random_state: int = 42,
        perplexity: Optional[int] = None,
        max_iter: int = 500
    ):
        self.n_components = n_components
        self.random_state = random_state
        self.perplexity = perplexity
        self.max_iter = max_iter
        self.model = None
        
    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """Fit t-SNE and transform data."""
        n_frames = X.shape[0]
        perplexity = _auto_tsne_perplexity(n_frames, self.perplexity)
        
        logger.info("Computing t-SNE with perplexity=%d, max_iter=%d...", 
                   perplexity, self.max_iter)
        
        self.model = TSNE(
            n_components=self.n_components,
            perplexity=perplexity,
            max_iter=self.max_iter,
            random_state=self.random_state,
            init="pca",
            learning_rate="auto",
        )
        emb = self.model.fit_transform(X)
        
        logger.info("t-SNE completed")
        return emb.astype(np.float32)
    
    def get_results(self, emb: np.ndarray, save_data_func) -> Dict:
        """Get t-SNE results dictionary."""
        return {
            "embeddings": emb,
            "n_components": self.n_components,
            "perplexity": self.model.perplexity if self.model else self.perplexity,
            "max_iter": self.max_iter,
            "components_file": save_data_func(
                emb, "dimred_tsne", header="tsne_component_1 tsne_component_2", fmt="%.6f"
            ),
        }
