# src/fastmdanalysis/utils/logging.py
from __future__ import annotations

import logging
import platform
import sys
from typing import Dict, Optional

# Public API of this module
__all__ = ["get_runtime_versions", "log_run_header"]


def _safe_import_version(module_name: str) -> str:
    """
    Best-effort retrieval of a module's __version__ without raising.
    Returns "n/a" if the module is not importable; "unknown" if no __version__.
    """
    try:
        mod = __import__(module_name)
    except Exception:
        return "n/a"
    return getattr(mod, "__version__", "unknown")


def _fastmdanalysis_version() -> str:
    """
    Resolve FastMDAnalysis version from the package __version__ or importlib.metadata.
    """
    # Try direct import from package
    try:
        # Avoid circular imports at module import time
        from .. import __version__ as v  # type: ignore
        if isinstance(v, str) and v:
            return v
    except Exception:
        pass

    # Fallback to importlib.metadata
    try:
        from importlib.metadata import PackageNotFoundError, version  # type: ignore
    except Exception:
        try:
            # Python <3.8 backport
            from importlib_metadata import PackageNotFoundError, version  # type: ignore
        except Exception:
            return "unknown"

    try:
        return version("fastmdanalysis")
    except PackageNotFoundError:
        return "unknown"
    except Exception:
        return "unknown"


def get_runtime_versions(*, extras: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Collect versions of FastMDAnalysis, Python, OS, and common dependencies.

    Parameters
    ----------
    extras : dict[str, str], optional
        Mapping of label -> module_name for additional libraries you want logged,
        e.g., {"pandas": "pandas", "scipy": "scipy"}.

    Returns
    -------
    dict[str, str]
        A flat mapping suitable for logging or testing.
    """
    versions: Dict[str, str] = {
        "fastmdanalysis": _fastmdanalysis_version(),
        "python": sys.version.split()[0],
        "os": platform.platform(),
        "numpy": _safe_import_version("numpy"),
        "mdtraj": _safe_import_version("mdtraj"),
        "scikit-learn": _safe_import_version("sklearn"),
        "matplotlib": _safe_import_version("matplotlib"),
    }
    if extras:
        for label, module_name in extras.items():
            versions[label] = _safe_import_version(module_name)
    return versions


def log_run_header(
    logger: Optional[logging.Logger] = None,
    *,
    level: int = logging.INFO,
    extras: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Log a concise, two-line version header for provenance.

    Parameters
    ----------
    logger : logging.Logger, optional
        Logger to use. Defaults to 'fastmdanalysis' logger if None.
    level : int
        Logging level for the header lines (default: logging.INFO).
    extras : dict[str, str], optional
        Additional label -> module_name entries to include in the second line.

    Returns
    -------
    dict[str, str]
        The collected versions (useful for unit tests).
    """
    lg = logger or logging.getLogger("fastmdanalysis")
    v = get_runtime_versions(extras=extras)

    # Line 1: core runtime
    lg.log(
        level,
        "FastMDAnalysis %s | Python %s | OS %s",
        v.get("fastmdanalysis", "unknown"),
        v.get("python", "unknown"),
        v.get("os", "unknown"),
    )

    # Line 2: key libraries (+ any extras)
    libs = ["numpy", "mdtraj", "scikit-learn", "matplotlib"]
    if extras:
        libs.extend(extras.keys())

    lib_report = " | ".join(f"{name} {v.get(name, 'n/a')}" for name in libs)
    lg.log(level, "%s", lib_report)

    return v





def setup_library_logging(level: int = logging.INFO, logfile: str | None = None) -> logging.Logger:
    """
    Attach a basic handler to the 'fastmdanalysis' logger for library/API use.
    Safe to call multiple times. If `logfile` is provided and a FileHandler
    is not already attached, one will be added (in addition to any stream handler).
    """
    lg = logging.getLogger("fastmdanalysis")
    lg.setLevel(level)

    # Simple reusable formatter
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    if not lg.handlers:
        # First-time setup: choose handler based on logfile presence
        handler = logging.FileHandler(logfile) if logfile else logging.StreamHandler()
        handler.setFormatter(fmt)
        lg.addHandler(handler)
    else:
        # Upgrade path: if logfile requested and no FileHandler yet, add one
        if logfile is not None and not any(isinstance(h, logging.FileHandler) for h in lg.handlers):
            fh = logging.FileHandler(logfile)
            fh.setFormatter(fmt)
            lg.addHandler(fh)

    return lg


