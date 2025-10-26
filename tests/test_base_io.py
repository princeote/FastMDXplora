# tests/test_base_io.py
import numpy as np
from pathlib import Path
from fastmdanalysis.analysis.base import BaseAnalysis

class _Dummy(BaseAnalysis):
    def run(self): return {}
    def plot(self): return {}

def test_save_data_formats(tmp_path):
    d = _Dummy(trajectory=None, output=tmp_path)
    # floats
    p1 = d._save_data(np.array([[1.23, 4.56],[7.89, 0.12]], dtype=float), "floats")
    assert Path(p1).exists()
    # ints
    p2 = d._save_data(np.array([[1,2,3]], dtype=int), "ints")
    assert Path(p2).exists()
    # object/non-ndarray
    p3 = d._save_data({"key": "val"}, "obj")
    assert Path(p3).exists()

def test_save_plot(tmp_path, matplotlib):
    import matplotlib.pyplot as plt
    d = _Dummy(trajectory=None, output=tmp_path)
    fig = plt.figure()
    out = d._save_plot(fig, "fig")
    assert Path(out).exists()

import mdtraj as md
import numpy as np
import pytest
from fastmdanalysis.utils import load_trajectory

def test_load_trajectory_with_atom_selection(dataset_paths):
    traj_path, top_path = dataset_paths
    # Load a small stride for speed
    t_all = load_trajectory(traj_path, top_path, frames=(0, None, 10))
    sel = t_all.topology.select("protein and name CA")
    t_sel = load_trajectory(traj_path, top_path, frames=(0, None, 10), atoms="protein and name CA")
    assert t_sel.topology.n_atoms == sel.size
    # frame slicing preserved
    assert t_sel.n_frames == t_all.n_frames

def test_load_trajectory_bad_selection_raises(dataset_paths):
    traj_path, top_path = dataset_paths
    with pytest.raises(ValueError):
        load_trajectory(traj_path, top_path, atoms="name DOES_NOT_EXIST_XXX")

