from __future__ import annotations

import sys
import argparse
from pathlib import Path

from ._common import make_common_parser, setup_logging, parse_frames, build_instance
from . import analyze as analyze_cmd
from . import simple as simple_cmd


def _build_parser() -> argparse.ArgumentParser:
    common = make_common_parser()
    parser = argparse.ArgumentParser(
        description="FastMDAnalysis: Fast Automated MD Trajectory Analysis",
        epilog="Docs: https://fastmdanalysis.readthedocs.io/en/latest/",
        parents=[common],
    )
    subparsers = parser.add_subparsers(dest="command", help="Analysis type", required=True)

    # Register subcommands
    analyze_cmd.register(subparsers, common)
    simple_cmd.register_simple(subparsers, common)

    return parser


def _normalize_argv(argv: list[str]) -> list[str]:
    """
    Lightweight normalization to support user-friendly '-ref' (single hyphen) for RMSD.
    Maps:
      - '-ref'      -> '--reference-frame'
      - '-ref=VAL'  -> '--reference-frame=VAL'
    """
    out: list[str] = []
    for tok in argv:
        if tok == "-ref":
            out.append("--reference-frame")
        elif tok.startswith("-ref="):
            out.append("--reference-frame=" + tok.split("=", 1)[1])
        else:
            out.append(tok)
    return out


def main() -> None:
    parser = _build_parser()
    argv = _normalize_argv(sys.argv[1:])
    args = parser.parse_args(argv)

    # Output dir per command
    output_dir = args.output if getattr(args, "output", None) else f"{args.command}_output"
    logger = setup_logging(output_dir, getattr(args, "verbose", False), args.command)
    logger.info("Parsed arguments: %s", args)

    # Shared init
    frames = parse_frames(getattr(args, "frames", None))
    atoms = getattr(args, "atoms", None)

    try:
        fastmda = build_instance(args.trajectory, args.topology, frames=frames, atoms=atoms)
    except SystemExit:
        raise
    except Exception as e:
        logger.error("Error initializing FastMDAnalysis: %s", e)
        sys.exit(1)

    # Dispatch to the registered handler
    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.error("No handler registered for the selected subcommand.")
    handler(args, fastmda, logger)

