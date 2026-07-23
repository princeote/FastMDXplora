from __future__ import annotations

import json
from pathlib import Path

from driftmd.workflow import run_workflow


def _write_input_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    pdb = tmp_path / "input.pdb"
    pdb.write_text(
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n",
        encoding="utf-8",
    )
    trajectory = tmp_path / "trajectory.dcd"
    trajectory.write_bytes(b"not a real dcd but enough for fast analysis tests")
    topology = tmp_path / "topology.pdb"
    topology.write_text(pdb.read_text(encoding="utf-8"), encoding="utf-8")
    return pdb, trajectory, topology


def test_analysis_report_only_manifest_and_wording(tmp_path: Path) -> None:
    _, trajectory, topology = _write_input_files(tmp_path)
    output = tmp_path / "run"

    run_workflow(
        structure=None,
        output=output,
        phases=["analyze", "report"],
        trajectory=trajectory,
        topology=topology,
        title="Analysis-only report",
    )

    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert [phase["name"] for phase in manifest["phases"]] == ["analyze", "report"]
    assert not (output / "prepare").exists()
    assert not (output / "simulate").exists()
    report = (output / "report" / "report.md").read_text(encoding="utf-8")
    outline = (output / "report" / "slides_outline.md").read_text(encoding="utf-8")
    assert "existing trajectory" in report
    assert "Preparation and simulation were not run" in report
    assert "complete prepare, simulate, and analyze workflow" not in report
    assert "## Simulation" not in outline


def test_selected_prepare_phase_only(tmp_path: Path) -> None:
    pdb, _, _ = _write_input_files(tmp_path)
    output = tmp_path / "prepared"

    run_workflow(structure=pdb, output=output, phases=["prepare"])

    assert (output / "prepare" / "prepared_structure.pdb").is_file()
    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert [phase["name"] for phase in manifest["phases"]] == ["prepare"]


def test_report_artifacts_are_created(tmp_path: Path) -> None:
    _, trajectory, topology = _write_input_files(tmp_path)
    output = tmp_path / "run"
    run_workflow(
        structure=None,
        output=output,
        phases=["analyze", "report"],
        trajectory=trajectory,
        topology=topology,
    )

    assert (output / "analysis" / "drift_score.csv").is_file()
    assert (output / "analysis" / "drift_score.png").is_file()
    assert (output / "report" / "report.md").is_file()
    assert (output / "report" / "slides_outline.md").is_file()
    assert (output / "report" / "workflow_bundle.zip").is_file()
