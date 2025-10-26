import sys
import json
import subprocess
from pathlib import Path
import pytest

@pytest.mark.cli
def test_cli_analyze_json(tmp_path, dataset_paths):
    traj, top = dataset_paths
    opts = {"rmsd": {"ref": 0}, "rg": {}}
    opts_path = tmp_path / "opts.json"
    opts_path.write_text(json.dumps(opts))

    outdir = tmp_path / "cli_out"
    cmd = [
        sys.executable, "-m", "fastmdanalysis.cli.main", "analyze",
        "-traj", str(traj), "-top", str(top),
        "-o", str(outdir),
        "--include", "rmsd", "rg",
        "--options", str(opts_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert proc.returncode == 0, proc.stdout

@pytest.mark.cli
@pytest.mark.slow
def test_cli_analyze_slides(tmp_path, dataset_paths):
    pytest.importorskip("pptx")
    traj, top = dataset_paths
    outdir = tmp_path / "cli_out2"
    cmd = [
        sys.executable, "-m", "fastmdanalysis.cli.main", "analyze",
        "-traj", str(traj), "-top", str(top),
        "-o", str(outdir),
        "--include", "rmsd",
        "--options", str(tmp_path / "empty.json"),
        "--slides",
    ]
    (tmp_path / "empty.json").write_text("{}")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert proc.returncode == 0, proc.stdout
    # a deck with timestamped name should exist in CWD (process cwd = tmp_path by default if we set it)
    decks = list(Path.cwd().glob("fastmda_slides_*.pptx"))
    assert decks, "Expected a slide deck to be created"

