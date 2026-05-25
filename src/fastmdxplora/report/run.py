"""Top-level report phase entry point.

Combines outputs from the document, slides, and bundle generators into a
unified report artifact set.
"""

from __future__ import annotations

from fastmdxplora.utils.logging import get_logger
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastmdxplora.report.bundle import build_bundle
from fastmdxplora.report.document import build_document
from fastmdxplora.report.slides import build_slides

if TYPE_CHECKING:
    from fastmdxplora.orchestrator import FastMDXplora

logger = get_logger("report")


DEFAULTS: dict[str, Any] = {
    "document": True,
    "slides": True,
    "bundle": True,
    "title": None,  # auto-derive from system
    "author": None,
    "include_methods": True,
    "include_reproducibility": True,
}


def run(
    *,
    orchestrator: "FastMDXplora",
    output_dir: Path,
    **options: Any,
) -> list[str]:
    """Run the report phase.

    Parameters
    ----------
    orchestrator : FastMDXplora
        Parent orchestrator (used to locate sibling phase outputs).
    output_dir : Path
        Where to write report artifacts.
    **options
        See ``DEFAULTS``.

    Returns
    -------
    list of str
        Paths (relative to ``output_dir``) of artifacts produced.
    """
    params = {**DEFAULTS, **options}
    title = params["title"] or f"FastMDXplora Study — {orchestrator.system}"

    presenter = getattr(orchestrator, "_presenter", None)
    artifacts: list[str] = []

    if params["document"]:
        doc_artifacts = build_document(
            orchestrator=orchestrator,
            output_dir=output_dir,
            title=title,
            author=params["author"],
            include_methods=params["include_methods"],
            include_reproducibility=params["include_reproducibility"],
        )
        artifacts.extend(doc_artifacts)
        if presenter:
            presenter.step("Wrote report.md")

    if params["slides"]:
        slide_artifacts = build_slides(
            orchestrator=orchestrator,
            output_dir=output_dir,
            title=title,
        )
        artifacts.extend(slide_artifacts)
        if presenter:
            for art in slide_artifacts:
                presenter.step(f"Wrote {art}")

    if params["bundle"]:
        bundle_artifacts = build_bundle(
            orchestrator=orchestrator,
            output_dir=output_dir,
        )
        artifacts.extend(bundle_artifacts)
        if presenter:
            presenter.step("Wrote project_bundle.zip")

    logger.debug("report: wrote %d artifact(s) to %s", len(artifacts), output_dir)
    return artifacts
