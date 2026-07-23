from __future__ import annotations

from pathlib import Path

from driftmd.analyze import analyze_trajectory
from driftmd.prepare import prepare_structure
from driftmd.records import StepRecord
from driftmd.report import build_report
from driftmd.simulate import run_short_simulation

PHASES = ("prepare", "simulate", "analyze", "report")


def run_workflow(
    *,
    structure: Path | None,
    output: Path,
    phases: list[str],
    trajectory: Path | None = None,
    topology: Path | None = None,
    title: str = "DriftMD Workflow Report",
) -> list[StepRecord]:
    output.mkdir(parents=True, exist_ok=True)
    records: list[StepRecord] = []
    for phase in phases:
        if phase == "prepare":
            if structure is None:
                raise ValueError("prepare requires --structure")
            records.append(prepare_structure(structure, output))
        elif phase == "simulate":
            records.append(run_short_simulation(output))
        elif phase == "analyze":
            if trajectory is None or topology is None:
                raise ValueError("analyze requires --trajectory and --topology")
            records.append(analyze_trajectory(trajectory, topology, output))
        elif phase == "report":
            records.append(build_report(output, title=title))
        else:
            raise ValueError(f"unknown phase: {phase}")
    return records
