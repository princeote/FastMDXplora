# src/fastmdanalysis/cli/main.py
from __future__ import annotations

import sys
import argparse

from ._common import (
    make_common_parser,
    setup_logging,
    parse_frames,
    build_instance,
    expand_trajectory_args,
    normalize_topology_arg,
)
from . import analyze as analyze_cmd
from . import simple as simple_cmd
from ..utils.logging import log_run_header  


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

    # Emit version/runtime header for provenance
    try:
        log_run_header(logger)
    except Exception:
        # Never fail the CLI due to logging
        pass

    logger.info("Parsed arguments: %s", args)

    # Normalize IO args centrally (Option A)
    try:
        # expand space/comma/glob and validate existence
        trajs = expand_trajectory_args(args.trajectory)
        top = normalize_topology_arg(args.topology)
        # write back normalized values so handlers can use them if needed
        args.trajectory = trajs
        args.topology = top
    except SystemExit:
        # clear error message already formed in helper
        raise
    except Exception as e:
        logger.error("Invalid input paths: %s", e)
        sys.exit(2)

    # Shared init
    frames = parse_frames(getattr(args, "frames", None))
    atoms = getattr(args, "atoms", None)

    try:
        fastmda = build_instance(trajs, top, frames=frames, atoms=atoms)
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
