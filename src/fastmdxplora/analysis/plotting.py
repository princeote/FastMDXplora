"""Plotting utilities for analysis figures.

Provides a single point of style configuration so every analysis figure
looks consistent. The defaults are tuned for publication-quality output:
sans-serif fonts at 11pt, 100 DPI on screen / 300 DPI on save, sensible
margins, and a colorblind-aware palette (Tableau 10) for categorical data.

The module also pins the matplotlib backend to ``Agg`` when imported in a
headless environment (no DISPLAY, common on HPC nodes and CI), so analyses
do not silently hang waiting for a display.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastmdxplora.utils.logging import get_logger

logger = get_logger("analysis.plotting")

# Force a non-interactive backend before pyplot is imported. FastMDXplora
# always writes figures to files and never displays them, so an interactive
# backend is never wanted — and MD commonly runs headless (CI, HPC, servers)
# where interactive backends crash (e.g. "Can't find a usable init.tcl").
# This must happen before pyplot is imported. Respect an explicit MPLBACKEND.
if "MPLBACKEND" not in os.environ:
    import matplotlib

    matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  -- backend set above


# Tableau 10 — colorblind-aware, distinct in print and on screen
PALETTE = (
    "#4E79A7",
    "#F28E2B",
    "#E15759",
    "#76B7B2",
    "#59A14F",
    "#EDC948",
    "#B07AA1",
    "#FF9DA7",
    "#9C755F",
    "#BAB0AC",
)


def apply_style() -> None:
    """Apply the FastMDXplora plotting style globally.

    Called automatically by :func:`new_figure`; safe to call again to
    reset after user customizations.
    """
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"],
            "font.size": 11,
            "axes.labelsize": 12,
            "axes.titlesize": 13,
            "axes.titleweight": "semibold",
            "axes.linewidth": 1.0,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "axes.prop_cycle": plt.cycler(color=PALETTE),
            "grid.color": "#DDDDDD",
            "grid.linewidth": 0.6,
            "grid.linestyle": "--",
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "legend.frameon": False,
            "figure.dpi": 100,
            "figure.figsize": (6.5, 4.5),
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "lines.linewidth": 1.4,
        }
    )


def new_figure(
    *,
    figsize: tuple[float, float] | None = None,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    **subplot_kwargs: Any,
) -> tuple[plt.Figure, plt.Axes]:
    """Create a figure pre-styled with FastMDXplora defaults.

    Parameters
    ----------
    figsize : (float, float), optional
        Figure size in inches. Defaults to (6.5, 4.5).
    title, xlabel, ylabel : str, optional
        Set at creation time so analyses can be one-liners.
    **subplot_kwargs
        Additional keyword arguments passed to ``plt.subplots`` (e.g.
        ``nrows=2, sharex=True``).

    Returns
    -------
    (Figure, Axes)
        For multi-subplot figures the Axes object follows matplotlib's
        normal conventions (array of axes).
    """
    apply_style()
    fig, ax = plt.subplots(figsize=figsize, **subplot_kwargs)
    # Apply title/labels to a single Axes; for multi-subplot figures the
    # user should set these per-axis after creation.
    if not isinstance(ax, (list, tuple)) and hasattr(ax, "set_title"):
        if title:
            ax.set_title(title)
        if xlabel:
            ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)
    return fig, ax


def save_figure(
    fig: plt.Figure,
    path: str | Path,
    *,
    dpi: int = 300,
    close: bool = True,
) -> Path:
    """Save a figure to disk and (by default) close it.

    Closing is the safe default: leaving figures open eventually exhausts
    matplotlib's figure manager when many analyses run in sequence.

    Returns the resolved Path that was written.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    if close:
        plt.close(fig)
    logger.debug("Saved figure: %s", out)
    return out
