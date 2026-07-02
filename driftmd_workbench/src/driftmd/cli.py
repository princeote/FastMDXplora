from __future__ import annotations

import argparse
import sys
from pathlib import Path

from driftmd import __version__
from driftmd.analyze import analyze_trajectory
from driftmd.prepare import prepare_structure
from driftmd.report import build_report
from driftmd.simulate import run_short_simulation
from driftmd.workflow import PHASES, run_workflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="driftmd")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("info", help="show package and backend information")

    p_prepare = sub.add_parser("prepare", help="stage a structure for a workflow")
    p_prepare.add_argument("--structure", required=True)
    p_prepare.add_argument("--output", required=True)

    p_sim = sub.add_parser("simulate", help="run the OpenMM simulation hook")
    p_sim.add_argument("--output", required=True)
    p_sim.add_argument("--steps", type=int, default=20)

    p_analyze = sub.add_parser("analyze", help="analyze an existing trajectory")
    p_analyze.add_argument("--trajectory", required=True)
    p_analyze.add_argument("--topology", required=True)
    p_analyze.add_argument("--output", required=True)

    p_report = sub.add_parser("report", help="generate reports from an output folder")
    p_report.add_argument("--output", required=True)
    p_report.add_argument("--title", default="DriftMD Workflow Report")

    p_run = sub.add_parser("run", help="run selected workflow phases")
    p_run.add_argument("--structure")
    p_run.add_argument("--output", required=True)
    p_run.add_argument("--include", nargs="+", choices=PHASES, default=list(PHASES))
    p_run.add_argument("--trajectory")
    p_run.add_argument("--topology")
    p_run.add_argument("--title", default="DriftMD Workflow Report")
    return parser


def _info() -> int:
    try:
        import openmm  # noqa: F401

        openmm_status = "available"
    except ImportError:
        openmm_status = "not installed"
    print(f"DriftMD Workbench {__version__}")
    print(f"OpenMM backend: {openmm_status}")
    print("Use `python -m driftmd ...` when the `driftmd` command is not on PATH.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"driftmd {__version__}")
        return 0
    if args.command is None:
        parser.print_help()
        return 0
    try:
        if args.command == "info":
            return _info()
        if args.command == "prepare":
            prepare_structure(Path(args.structure), Path(args.output))
        elif args.command == "simulate":
            run_short_simulation(Path(args.output), steps=args.steps)
        elif args.command == "analyze":
            analyze_trajectory(Path(args.trajectory), Path(args.topology), Path(args.output))
        elif args.command == "report":
            build_report(Path(args.output), title=args.title)
        elif args.command == "run":
            run_workflow(
                structure=Path(args.structure) if args.structure else None,
                output=Path(args.output),
                phases=list(args.include),
                trajectory=Path(args.trajectory) if args.trajectory else None,
                topology=Path(args.topology) if args.topology else None,
                title=args.title,
            )
        else:
            parser.error("unknown command")
    except Exception as exc:  # noqa: BLE001 - CLI should produce concise failures
        print(f"driftmd: {exc}", file=sys.stderr)
        return 2
    return 0
