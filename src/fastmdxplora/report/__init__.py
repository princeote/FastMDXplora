"""Reporting phase.

The report phase produces the user-facing deliverable from a completed
FastMDXplora run:

  - Slides (.pptx) — auto-generated slide deck
  - Document (.md, .pdf) — structured study report
  - Bundle (.zip) — self-contained project archive

This is genuinely new functionality unique to FastMDXplora (not inherited
from the predecessor packages). The report phase consumes outputs from the
setup, simulation, and analysis phases and produces shareable artifacts
suitable for collaborator hand-off or publication appendix.
"""

from fastmdxplora.report.run import run

__all__ = ["run"]
