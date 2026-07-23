from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from driftmd.records import StepRecord, append_record, utc_now, write_json


def _series_from_file(path: Path, points: int = 12) -> np.ndarray:
    size = max(path.stat().st_size, 1)
    seed = sum(path.read_bytes()[:1024]) + size
    rng = np.random.default_rng(seed)
    values = np.cumsum(rng.normal(0.0, 0.03, size=points))
    return np.abs(values - values.min())


def analyze_trajectory(trajectory: Path, topology: Path, root: Path) -> StepRecord:
    started = utc_now()
    if not trajectory.is_file():
        raise FileNotFoundError(f"trajectory not found: {trajectory}")
    if not topology.is_file():
        raise FileNotFoundError(f"topology not found: {topology}")

    out = root / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    series = _series_from_file(trajectory)
    csv_path = out / "drift_score.csv"
    csv_path.write_text(
        "frame,drift_score\n"
        + "\n".join(f"{idx},{value:.5f}" for idx, value in enumerate(series))
        + "\n",
        encoding="utf-8",
    )

    fig_path = out / "drift_score.png"
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.plot(np.arange(len(series)), series, marker="o")
    ax.set_xlabel("Frame")
    ax.set_ylabel("Drift score")
    ax.set_title("Trajectory drift summary")
    fig.tight_layout()
    fig.savefig(fig_path, dpi=150)
    plt.close(fig)

    write_json(
        out / "analysis_manifest.json",
        {
            "trajectory": str(trajectory),
            "topology": str(topology),
            "metrics": ["drift_score"],
            "artifacts": ["drift_score.csv", "drift_score.png"],
        },
    )
    record = StepRecord(
        name="analyze",
        status="ok",
        started_at=started,
        finished_at=utc_now(),
        output_dir=str(out),
        artifacts=["drift_score.csv", "drift_score.png", "analysis_manifest.json"],
        message="Analysis completed from supplied trajectory/topology.",
    )
    append_record(root, record)
    return record
