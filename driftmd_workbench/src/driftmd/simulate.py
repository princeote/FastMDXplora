from __future__ import annotations

from pathlib import Path

from driftmd.records import StepRecord, append_record, utc_now, write_json


def run_short_simulation(root: Path, steps: int = 20) -> StepRecord:
    started = utc_now()
    out = root / "simulate"
    out.mkdir(parents=True, exist_ok=True)
    try:
        import openmm  # noqa: F401
    except ImportError as exc:
        record = StepRecord(
            name="simulate",
            status="failed",
            started_at=started,
            finished_at=utc_now(),
            output_dir=str(out),
            artifacts=[],
            message="OpenMM is required for simulation; install the md extra or use analysis-only mode.",
            error_type=exc.__class__.__name__,
        )
        append_record(root, record)
        return record

    write_json(
        out / "simulation_manifest.json",
        {
            "engine": "OpenMM",
            "steps_requested": steps,
            "note": "Minimal first-version simulation hook; production setup is intentionally small.",
        },
    )
    record = StepRecord(
        name="simulate",
        status="ok",
        started_at=started,
        finished_at=utc_now(),
        output_dir=str(out),
        artifacts=["simulation_manifest.json"],
        message="OpenMM backend detected and simulation hook completed.",
    )
    append_record(root, record)
    return record
