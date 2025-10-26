import numpy as np
import pytest

@pytest.mark.parametrize("method", ["dbscan"])
def test_cluster_dbscan_labels(fastmda, method):
    a = fastmda.cluster(methods=method, eps=0.6, min_samples=5)
    assert method in a.results
    labels = a.results[method]["labels"]
    assert isinstance(labels, np.ndarray)
    assert labels.ndim == 1
    assert labels.size > 0

@pytest.mark.parametrize("method", ["kmeans", "hierarchical"])
def test_cluster_parametric(fastmda, method):
    a = fastmda.cluster(methods=method, n_clusters=3)
    assert method in a.results
    labels = a.results[method]["labels"]
    assert labels.size > 0

def test_dimred_multi(fastmda):
    a = fastmda.dimred(methods=["pca", "mds", "tsne"])
    assert hasattr(a, "data")

