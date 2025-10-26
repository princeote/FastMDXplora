from __future__ import annotations

from typing import Any, Dict, List, Optional
import argparse
import logging

from ._common import add_file_args, load_options_file, parse_opt_pairs, deep_merge_options


def register(subparsers: argparse._SubParsersAction, common_parser: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser(
        "analyze", parents=[common_parser], help="Run multiple analyses (include/exclude) with optional slides",
        conflict_handler="resolve",
    )
    add_file_args(p)
    p.add_argument(
        "--include", nargs="+",
        help='Analyses to include (default: "all"). Example: --include rmsd rmsf rg',
    )
    p.add_argument(
        "--exclude", nargs="+",
        help="Analyses to exclude from the full set.",
    )
    p.add_argument(
        "--options", type=str, default=None, metavar="FILE",
        help="Path to options file (YAML .yml/.yaml or JSON .json). Matches the API 'options' schema.",
    )
    p.add_argument(
        "--opt", action="append", default=[], metavar="ANALYSIS.PARAM=VALUE",
        help="(Optional) Override/add a specific option (repeatable). Example: --opt rmsd.ref=0",
    )
    p.add_argument(
        "--stop-on-error", action="store_true",
        help="Abort on first analysis error (default: continue).",
    )
    p.add_argument(
        "--slides", nargs="?", const=True, metavar="OUT.pptx",
        help="Create a PowerPoint deck of figures (optionally specify output path).",
    )
    p.set_defaults(_handler=_handle)


def _handle(args: argparse.Namespace, fastmda, logger: logging.Logger) -> None:
    # Load/merge options
    file_options: Dict[str, Dict[str, Any]] = {}
    if args.options:
        file_options = load_options_file(args.options)
    cli_overrides = parse_opt_pairs(args.opt)
    options = deep_merge_options(file_options, cli_overrides)

    results = fastmda.analyze(
        include=args.include,
        exclude=args.exclude,
        options=options if options else None,
        stop_on_error=args.stop_on_error,
        verbose=True,     # keep progress prints
        slides=args.slides,  # bool or OUT.pptx
    )

    # Summary (exclude slides entry here)
    print("\nSummary:")
    for name, res in results.items():
        if name == "slides":
            continue
        status = "OK" if res.ok else f"FAIL ({type(res.error).__name__}: {res.error})"
        print(f"  {name:<10} {status:<50} {res.seconds:6.2f}s")

    # Slides reporting
    if args.slides:
        sres = results.get("slides")
        if sres and sres.ok:
            print(f"\n[fastmda] Slide deck: {sres.value}")
            logger.info("Slide deck created: %s", sres.value)
        elif sres:
            print(f"\n[fastmda] Slides failed: {sres.error}")
            logger.error("Slides failed: %s", sres.error)

