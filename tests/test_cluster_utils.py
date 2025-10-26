# tests/test_cluster_utils.py
import numpy as np
from fastmdanalysis.analysis.cluster import relabel_compact_positive

def test_relabel_compact_positive_with_noise():
    raw = np.array([0, 0, -1, 2, 2, 5])
    lab, mapping, noise = relabel_compact_positive(raw, start=1, noise_as_last=True)
    # non-negative labels compacted to 1..K
    assert set(lab[raw >= 0]) == {1, 2, 3}
    # noise mapped to K+1
    assert noise == 4
    assert lab[2] == 4

