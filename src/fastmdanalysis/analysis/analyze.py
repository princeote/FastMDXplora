# FastMDAnalysis/src/fastmdanalysis/analysis/analyze.py
"""
Unified analysis orchestrator for FastMDAnalysis.

This module provides a bound method `FastMDAnalysis.analyze(...)` that:
- Runs multiple analysis routines in a single call.
- Supports include/exclude selection with a canonical default order.
- Accepts per-analysis keyword options (filtered against each method's signature).
- Optionally builds a PowerPoint slide deck of figures produced during the run
  via the top-level `slides` argument (bool or explicit output path).

Binding (done once, typically in fastmdanalysis/__init__.py):
----------------------------------------------------------------
from .analysis.analyze import analyze as _analyze
FastMDAnalysis.analyze = _analyze
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, List, Tuple, Union
import inspect
import warnings
import time

# Slide deck utilities (timestamped filename handled inside slideshow.py)
from ..utils.slideshow import slide_show, gather_figures


# Canonical analysis names in preferred execution order.
# Keep this list consistent with the documentation / README.
_DEFAULT_ORDER: Tuple[str, ...] = (
    "rmsd",
    "rmsf",
    "rg",
    "hbonds",
    "ss",
    "sasa",
    "dimred",
    "cluster",
)


@dataclass
class AnalysisResult:
    """Container for per-analysis outcomes."""
    name: str
    ok: bool
    value: Any = None
    error: Optional[BaseException] = None
    seconds: float = 0.0


def _discover_available(self) -> List[str]:
    """
    Return the subset of _DEFAULT_ORDER that this object actually implements.
    Only includes callables (methods) present on the instance.
    """
    available: List[str] = []
    for name in _DEFAULT_ORDER:
        meth = getattr(self, name, None)
        if callable(meth):
            available.append(name)
    return available


def _validate_options(options: Optional[Mapping[str, Mapping[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    """
    Ensure options is a nested mapping {analysis_name: {kw: value}} with plain dicts.
    """
    if options is None:
        return {}
    if not isinstance(options, Mapping):
        raise TypeError("options must be a mapping of {analysis_name: {kw: value}}")
    norm: Dict[str, Dict[str, Any]] = {}
    for analysis, kwargs in options.items():
        if not isinstance(kwargs, Mapping):
            raise TypeError(f"options['{analysis}'] must be a mapping of keyword arguments")
        norm[analysis] = dict(kwargs)
    return norm


def _final_list(
    available: Sequence[str],
    include: Optional[Sequence[str]],
    exclude: Optional[Sequence[str]],
) -> List[str]:
    """
    Resolve the final ordered list of analyses to run.

    Rules
    -----
    - If include is None or ['all'] (case-insensitive), start from all available in default order.
    - Else, keep only included ones (preserving _DEFAULT_ORDER ordering).
    - Then drop any in exclude.
    """
    avail_set = set(available)

    if include is None or (len(include) == 1 and str(include[0]).lower() == "all"):
        candidates = [name for name in _DEFAULT_ORDER if name in avail_set]
    else:
        want = {s.lower() for s in include}
        unknown = want - set(_DEFAULT_ORDER)
        if unknown:
            warnings.warn(
                f"Unknown analyses in include: {sorted(unknown)}; valid names: {_DEFAULT_ORDER}"
            )
        candidates = [name for name in _DEFAULT_ORDER if (name in avail_set and name in want)]

    if exclude:
        drop = {s.lower() for s in exclude}
        candidates = [name for name in candidates if name not in drop]

    if not candidates:
        raise ValueError("No analyses to run after applying include/exclude.")
    return candidates


def _filter_kwargs(callable_obj, kwargs: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Only pass keyword arguments that the callable actually accepts.
    If the callable has **kwargs, pass everything through unchanged.
    """
    if not kwargs:
        return {}
    sig = inspect.signature(callable_obj)
    if any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
        return dict(kwargs)
    accepted = {
        name
        for name, p in sig.parameters.items()
        if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
    }
    return {k: v for k, v in kwargs.items() if k in accepted}


def run(
    self,
    include: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
    options: Optional[Mapping[str, Mapping[str, Any]]] = None,
    stop_on_error: bool = False,
    verbose: bool = True,
    # Top-level slides switch. If True, auto-name the deck. If str/Path, use as output path.
    slides: Optional[Union[bool, str, Path]] = None,
) -> Dict[str, AnalysisResult]:
    """
    Execute multiple analyses on the current FastMDAnalysis instance.

    Parameters
    ----------
    include
        Sequence of analysis names to run (e.g., ["rmsd","rmsf"]).
        Use None or ["all"] to run every available analysis in the default order.
    exclude
        Sequence of analysis names to skip.
    options
        Mapping of per-analysis keyword arguments, e.g.:
        {"rmsd": {"ref": 0, "align": True}, "cluster": {"n_clusters": 5}}
        Unknown keys for a given analysis are ignored (warned if verbose=True).
    stop_on_error
        If True, raise immediately on the first analysis error.
        If False (default), continue and record the error.
    verbose
        If True, print minimal progress messages.
    slides
        If True, create a PowerPoint deck of figures generated during this run
        with a timestamped filename (handled by the slideshow utility).
        If a string/path is provided, use it as the output .pptx path.
        (No per-analysis slides options are supported.)

    Returns
    -------
    Dict[str, AnalysisResult]
        Per-analysis results with timing, success flag, return value, and any exception.
        If slides were requested, includes a "slides" entry describing the deck creation.
    """
    # Resolve available analyses on the given instance
    available = _discover_available(self)
    # Build final plan
    plan = _final_list(available, include, exclude)
    # Normalize options
    opts = _validate_options(options)

    results: Dict[str, AnalysisResult] = {}

    if verbose:
        print(f"[FastMDAnalysis] Running {len(plan)} analyses: {', '.join(plan)}")

    # Track start to collect only figures created during this run
    run_t0 = time.time()

    for name in plan:
        fn = getattr(self, name, None)
        if not callable(fn):
            # Defensive guard; should not occur after availability check
            warnings.warn(f"Skipping '{name}' (not implemented on this instance).")
            continue

        kw = _filter_kwargs(fn, opts.get(name, {}))

        # Warn if user provided extra keys that were dropped
        if verbose and opts.get(name):
            dropped = set(opts[name].keys()) - set(kw.keys())
            if dropped:
                warnings.warn(f"Ignoring unsupported options for '{name}': {sorted(dropped)}")

        if verbose:
            print(f"  • {name}() ...", end="", flush=True)

        t0 = time.perf_counter()
        try:
            value = fn(**kw)  # Execute the actual analysis method
            ok = True
            err = None
        except BaseException as e:  # capture all analysis failures
            ok = False
            value = None
            err = e
            if verbose:
                print(" failed")
            if stop_on_error:
                raise
        finally:
            dt = time.perf_counter() - t0

        results[name] = AnalysisResult(name=name, ok=ok, value=value, error=err, seconds=dt)

        if verbose and ok:
            print(f" done ({dt:.2f}s)")

    # --- Slides (optional, top-level only) ------------------------------------
    if slides:
        t0 = time.perf_counter()
        try:
            # Prefer instance-known figure/output directories if present
            roots: List[Union[str, Path]] = []
            for attr in ("figdir", "outdir", "results_dir", "plot_dir", "plots_dir"):
                d = getattr(self, attr, None)
                if d:
                    roots.append(d)
            # Also scan common locations
            roots.extend([Path.cwd(), Path("figures"), Path("plots")])

            images = gather_figures(roots, since_epoch=run_t0 - 5)

            if not images:
                raise FileNotFoundError("No figures found to include in slide deck.")

            # If slides is a path, use it; else let slideshow assign timestamped filename
            outpath: Optional[Path]
            if isinstance(slides, (str, Path)):
                outpath = Path(slides)
            else:
                outpath = None  # slideshow will generate 'fastmda_slides_<ddmmyy.HHMM>.pptx'

            deck = slide_show(
                images=images,
                outpath=outpath,
                title="FastMDAnalysis — Analysis Slides",
                subtitle=f"{len(images)} figure(s) — generated {time.strftime('%Y-%m-%d %H:%M:%S')}",
            )

            results["slides"] = AnalysisResult(
                name="slides", ok=True, value=deck, error=None, seconds=time.perf_counter() - t0
            )
            if verbose:
                print(f"[FastMDAnalysis] Slides created: {deck}")
        except BaseException as e:
            results["slides"] = AnalysisResult(
                name="slides", ok=False, value=None, error=e, seconds=time.perf_counter() - t0
            )
            if verbose:
                warnings.warn(f"Slide creation failed: {e}")

    return results


def analyze(
    self,
    include: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
    options: Optional[Mapping[str, Mapping[str, Any]]] = None,
    stop_on_error: bool = False,
    verbose: bool = True,
    slides: Optional[Union[bool, str, Path]] = None,
) -> Dict[str, AnalysisResult]:
    """
    Public façade so callers can do: fastmda.analyze(...)

    Parameters mirror `run(...)`. See its docstring for details.
    """
    return run(
        self,
        include=include,
        exclude=exclude,
        options=options,
        stop_on_error=stop_on_error,
        verbose=verbose,
        slides=slides,
    )

