# tests/conftest.py
# Enable Matplotlib's built-in pytest fixtures (e.g., `matplotlib`)
pytest_plugins = ("matplotlib.testing.conftest",)

import warnings
from pathlib import Path
import pytest
import mdtraj as md

from fastmdanalysis.utils import load_trajectory
from fastmdanalysis import FastMDAnalysis

# Silence the benign MDTraj CRYST1 warning in this dataset
warnings.filterwarnings(
    "ignore",
    message="Unlikely unit cell vectors detected in PDB file likely resulting from a dummy CRYST1 record",
    category=UserWarning,
    module="mdtraj",
)

@pytest.fixture(scope="session")
def dataset_paths():
    """Return (traj_path, top_path) for the small TrpCage dataset."""
    from fastmdanalysis import datasets
    if hasattr(datasets, "TrpCage"):
        ds = datasets.TrpCage
        return ds.traj, ds.top
    # fallback for older naming
    ds = getattr(datasets, "trp_cage")
    return ds.traj, ds.top

@pytest.fixture(scope="session")
def traj(dataset_paths):
    traj_path, top_path = dataset_paths
    # Subsample frames to keep CI fast
    t = load_trajectory(traj_path, top_path, frames=(0, None, 10))
    t.topology.create_standard_bonds()
    return t

@pytest.fixture(scope="function")
def outdir(tmp_path):
    return tmp_path

@pytest.fixture(scope="function")
def fastmda(dataset_paths):
    traj_path, top_path = dataset_paths
    # Same frame stride for consistency with 'traj' fixture
    return FastMDAnalysis(traj_path, top_path, frames=(0, None, 10), atoms="protein")
