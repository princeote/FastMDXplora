# tests/test_analysis_errors.py
import pytest
from fastmdanalysis import FastMDAnalysis
from fastmdanalysis.datasets import trp_cage as DS
from fastmdanalysis.analysis.base import AnalysisError

@pytest.mark.parametrize("method", ["rmsd","rmsf","rg","hbonds","sasa"])
def test_bad_selection_raises(method):
    fmda = FastMDAnalysis(DS.traj, DS.top)
    fn = getattr(fmda, method)
    with pytest.raises(AnalysisError):
        # impossible atom name → empty selection
        fn(atoms="name ZZ")

