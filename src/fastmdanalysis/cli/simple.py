from __future__ import annotations

from typing import Dict, Any, Callable, Optional
import argparse
import logging

from ._common import add_file_args


def register_simple(subparsers: argparse._SubParsersAction, common_parser: argparse.ArgumentParser) -> None:
    """
    Register simple wrappers around FastMDAnalysis methods. Each entry defines:
    - name: subcommand & method name
    - help: help text
    - args: a function that adds any extra CLI args for that method
    - call: a function that calls the method with parsed args
    """
    specs = [
        {
            "name": "rmsd",
            "help": "RMSD analysis",
            "args": _args_rmsd,
            "call": _call_rmsd,
        },
        {"name": "rmsf", "help": "RMSF analysis", "args": None, "call": _call_passthrough("rmsf")},
        {"name": "rg", "help": "Radius of gyration analysis", "args": None, "call": _call_passthrough("rg")},
        {"name": "hbonds", "help": "Hydrogen bonds analysis", "args": None, "call": _call_passthrough("hbonds")},
        {
            "name": "cluster",
            "help": "Clustering analysis",
            "args": _args_cluster,
            "call": _call_cluster,
        },
        {"name": "ss", "help": "Secondary structure (SS) analysis", "args": None, "call": _call_passthrough("ss")},
        {
            "name": "sasa",
            "help": "Solvent accessible surface area (SASA) analysis",
            "args": _args_sasa,
            "call": _call_sasa,
        },
        {
            "name": "dimred",
            "help": "Dimensionality reduction analysis",
            "args": _args_dimred,
            "call": _call_dimred,
        },
    ]

    for spec in specs:
        p = subparsers.add_parser(spec["name"], parents=[common_parser], help=spec["help"], conflict_handler="resolve")
        add_file_args(p)
        if spec["args"]:
            spec["args"](p)
        p.set_defaults(_handler=_make_handler(spec["call"], spec["name"]))


def _make_handler(caller: Callable[[Any, argparse.Namespace], Any], name: str):
    def _handler(args: argparse.Namespace, fastmda, logger: logging.Logger) -> None:
        logger.info("Running %s analysis...", name)
        try:
            result = caller(fastmda, args)
            # Try to call .run() if the result exposes it (legacy pattern)
            ran = False
            runner = getattr(result, "run", None)
            if callable(runner):
                result = runner()
                ran = True
            if not ran:
                logger.debug("No .run() method detected; assuming analysis executed inside the method.")
            # Optional plotting
            plotter = getattr(result, "plot", None)
            if callable(plotter):
                plot_res = plotter()
                if isinstance(plot_res, dict):
                    for key, path in plot_res.items():
                        logger.info("Plot for %s saved to: %s", key, path)
                else:
                    logger.info("Plot saved to: %s", plot_res)
            logger.info("%s analysis completed successfully.", name)
        except Exception as e:
            logger.error("Error during %s analysis: %s", name, e)
            raise SystemExit(1)
    return _handler


# --------- Per-method arg adders & callers -----------------------------------

def _args_rmsd(p: argparse.ArgumentParser) -> None:
    # Support: --reference-frame, --ref, and (via argv normalization) -ref
    p.add_argument(
        "--reference-frame", "--ref",
        dest="reference_frame", type=int, default=0,
        help="Reference frame index for RMSD analysis",
    )


def _call_rmsd(fastmda, args: argparse.Namespace):
    return fastmda.rmsd(ref=args.reference_frame, atoms=getattr(args, "atoms", None), output=args.output)


def _args_cluster(p: argparse.ArgumentParser) -> None:
    p.add_argument("--eps", type=float, default=0.5, help="DBSCAN: Maximum distance between samples")
    p.add_argument("--min_samples", type=int, default=5, help="DBSCAN: Minimum samples in a neighborhood")
    p.add_argument("--methods", type=str, nargs="+", default=["dbscan"],
                   help="Clustering methods (e.g., 'dbscan', 'kmeans', 'hierarchical').")
    p.add_argument("--n_clusters", type=int, default=None, help="For KMeans/Hierarchical: number of clusters")


def _call_cluster(fastmda, args: argparse.Namespace):
    return fastmda.cluster(
        methods=args.methods, eps=args.eps, min_samples=args.min_samples,
        n_clusters=args.n_clusters, atoms=getattr(args, "atoms", None), output=args.output
    )


def _args_sasa(p: argparse.ArgumentParser) -> None:
    p.add_argument("--probe_radius", type=float, default=0.14, help="Probe radius (in nm) for SASA calculation")


def _call_sasa(fastmda, args: argparse.Namespace):
    return fastmda.sasa(probe_radius=args.probe_radius, atoms=getattr(args, "atoms", None), output=args.output)


def _args_dimred(p: argparse.ArgumentParser) -> None:
    p.add_argument("--methods", type=str, nargs="+", default=["all"],
                   help="Dimensionality reduction methods (e.g., 'pca', 'mds', 'tsne'). 'all' uses all methods.")


def _call_dimred(fastmda, args: argparse.Namespace):
    return fastmda.dimred(methods=args.methods, atoms=getattr(args, "atoms", None), output=args.output)


def _call_passthrough(method_name: str):
    def _caller(fastmda, args: argparse.Namespace):
        method = getattr(fastmda, method_name)
        return method(atoms=getattr(args, "atoms", None), output=args.output)
    return _caller

