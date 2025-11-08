"""
CLI integration tests for FastMDAnalysis.

These tests invoke the CLI by importing main directly to avoid module conflicts
that occur with `python -m fastmdanalysis.cli.main`.
"""

import sys
import json
import subprocess
from pathlib import Path
from typing import List
import pytest


def _run(cmd: List[str], cwd: Path = None) -> subprocess.CompletedProcess[str]:
    """Run a command and return the completed process with captured output."""
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=cwd,
    )


def _run_cli_direct(args: List[str], cwd: Path = None) -> subprocess.CompletedProcess[str]:
    """Run CLI by importing main directly to avoid module conflicts."""
    python_code = f'''
import sys
sys.path.insert(0, "/Users/aaina/aai-research-lab/FastMDAnalysis/src")

from fastmdanalysis.cli.main import main
import sys

# Set up command line arguments
sys.argv = ["fastmdanalysis"] + {args}

try:
    main()
    print("CLI completed successfully")
except SystemExit as e:
    print(f"CLI exited with code: {{e.code}}")
except Exception as e:
    print(f"CLI error: {{e}}")
    import traceback
    traceback.print_exc()
'''
    
    cmd = [sys.executable, "-c", python_code]
    return _run(cmd, cwd=cwd)


@pytest.mark.cli
def test_cli_analyze_json(tmp_path: Path, dataset_paths):
    """Test CLI with JSON options file."""
    traj, top = dataset_paths
    
    # Options file enabling two quick analyses
    opts = {"rmsd": {"ref": 0}, "rg": {}}
    opts_path = tmp_path / "opts.json"
    opts_path.write_text(json.dumps(opts))

    outdir = tmp_path / "cli_out"
    args = [
        "analyze",
        "-traj", str(traj), "-top", str(top),
        "-o", str(outdir),
        "--include", "rmsd", "rg",
        "--options", str(opts_path),
    ]
    
    proc = _run_cli_direct(args, cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout


@pytest.mark.cli
@pytest.mark.slow  
def test_cli_analyze_slides(tmp_path: Path, dataset_paths):
    """Test CLI with --slides option creates a PowerPoint deck in analyze_output."""
    pytest.importorskip("pptx")  # Skip if python-pptx not available
    
    traj, top = dataset_paths
    
    args = [
        "analyze",
        "-traj", str(traj), "-top", str(top),
        "--include", "rmsd",
        "--slides",
    ]
    
    proc = _run_cli_direct(args, cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout
    
    # Look for slide deck in analyze_output (current behavior)
    analyze_output = tmp_path / "analyze_output"
    decks = list(analyze_output.glob("fastmda_slides_*.pptx"))
    
    assert decks, "Expected a slide deck to be created in analyze_output"
    assert decks[0].stat().st_size > 0, "Slide deck file is empty"


@pytest.mark.cli
def test_cli_analyze_minimal(tmp_path: Path, dataset_paths):
    """Minimal test with just RMSD calculation."""
    traj, top = dataset_paths
    
    args = [
        "analyze", 
        "-traj", str(traj), "-top", str(top),
        "--include", "rmsd",
    ]
    
    proc = _run_cli_direct(args, cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout


@pytest.mark.cli
def test_cli_analyze_slides_with_custom_output_dir(tmp_path: Path, dataset_paths):
    """Test CLI with --slides and custom output directory via -o."""
    pytest.importorskip("pptx")
    
    traj, top = dataset_paths
    custom_outdir = tmp_path / "my_custom_output"
    
    args = [
        "analyze",
        "-traj", str(traj), "-top", str(top),
        "-o", str(custom_outdir),
        "--include", "rmsd", "rg",
        "--slides",
    ]
    
    proc = _run_cli_direct(args, cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout
    
    decks = list(custom_outdir.glob("fastmda_slides_*.pptx"))
    assert decks, f"Expected slide deck in custom output directory {custom_outdir}"
    assert decks[0].stat().st_size > 0, "Slide deck file should not be empty"
    assert (custom_outdir / "rmsd").exists(), "RMSD output should be in custom directory"
    assert (custom_outdir / "rg").exists(), "RG output should be in custom directory"


@pytest.mark.cli
def test_cli_analyze_slides_multiple_analyses(tmp_path: Path, dataset_paths):
    """Test CLI with --slides using multiple analyses that generate figures."""
    pytest.importorskip("pptx")
    
    traj, top = dataset_paths
    
    # Use analyses that generate figures
    args = [
        "analyze",
        "-traj", str(traj), "-top", str(top),
        "--include", "rmsd", "rg", "rmsf",
        "--slides",
    ]
    
    proc = _run_cli_direct(args, cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout
    
    # Look for slide deck
    analyze_output = tmp_path / "analyze_output"
    decks = list(analyze_output.glob("fastmda_slides_*.pptx"))
    
    assert decks, "Expected slide deck with multiple analyses"