# tests/test_dimred_methods.py
from fastmdanalysis import FastMDAnalysis
from fastmdanalysis.datasets import trp_cage as DS

def test_dimred_all(tmp_path):
    fmda = FastMDAnalysis(DS.traj, DS.top, atoms="protein")
    a = fmda.dimred(methods="all")
    assert set(a.results) >= {"pca","mds","tsne"}
    paths = a.plot()
    assert all(p.exists() for p in paths.values())

