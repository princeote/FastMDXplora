from __future__ import annotations

import subprocess
import sys

from driftmd.cli import build_parser


def test_cli_parses_run_analysis_report() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "run",
            "--output",
            "out",
            "--include",
            "analyze",
            "report",
            "--trajectory",
            "traj.dcd",
            "--topology",
            "top.pdb",
        ]
    )
    assert args.command == "run"
    assert args.include == ["analyze", "report"]


def test_module_entrypoint_info_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "driftmd", "info"],
        text=True,
        capture_output=True,
        check=True,
    )
    assert "DriftMD Workbench" in result.stdout
