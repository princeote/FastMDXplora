"""Batch / parameter-sweep support for FastMDXplora.

This is the internal execution layer. Users always drive runs through
``fastmdxplora.FastMDXplora`` (one system or many — same interface);
``BatchExplorer`` is the machinery underneath. Input is always a
``systems:`` list (even one system is a batch of one), and an optional
``sweep`` of parameter axes runs the full cross-product. A single run
writes the familiar flat output layout; multiple runs each get their own
``runs/<id>/`` subdirectory indexed by a top-level
``batch_manifest.json``, plus a cross-run ``comparison/`` report.

Public helpers
--------------
- :func:`expand_runs` -- pure systems × sweep expansion
- :class:`RunSpec` -- one concrete run
- :class:`SweepError` -- raised on malformed systems/sweep specs

To (re)build the cross-run comparison report, use
``fastmdxplora.FastMDXplora(...).compare()`` — not a function here.
"""

from fastmdxplora.batch.explorer import BatchExplorer
from fastmdxplora.batch.sweep import (
    RunSpec,
    SweepError,
    expand_runs,
    normalize_sweep,
    normalize_systems,
)

__all__ = [
    "BatchExplorer",
    "RunSpec",
    "SweepError",
    "expand_runs",
    "normalize_sweep",
    "normalize_systems",
]
