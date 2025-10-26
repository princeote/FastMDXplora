import numpy as np

def test_rmsd_basic(fastmda):
    a = fastmda.rmsd(ref=0)
    assert hasattr(a, "data")
    assert isinstance(a.data, np.ndarray)
    assert a.data.size > 0
    assert np.isfinite(a.data).all()

def test_rmsf_basic(fastmda):
    a = fastmda.rmsf()
    assert hasattr(a, "data")
    assert a.data.ndim in (1, 2)
    assert np.isfinite(a.data).all()

def test_rg_basic(fastmda):
    a = fastmda.rg()
    assert hasattr(a, "data")
    assert np.isfinite(a.data).all()

def test_hbonds_basic(fastmda):
    a = fastmda.hbonds()
    assert hasattr(a, "data")

def test_ss_basic(fastmda):
    a = fastmda.ss()
    assert hasattr(a, "data")

def test_sasa_basic(fastmda):
    a = fastmda.sasa(probe_radius=0.14)
    assert hasattr(a, "data")

