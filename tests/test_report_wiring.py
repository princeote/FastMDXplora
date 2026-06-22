"""Tests for the report-phase consumption of analysis-phase outputs.

These tests verify that after a real analysis run, the report phase:
  1. Embeds analysis figures into report.md with correct relative paths
  2. Shows per-analysis options (from the options.json files) in the document
  3. Generates image slides in the .pptx for each analysis figure
  4. Fans out multi-method analyses (cluster, dimred) into separate slides
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import mdtraj as md
import numpy as np
import pytest

from fastmdxplora import FastMDXplora
from fastmdxplora.cli.main import main as cli_main


# ---------------------------------------------------------------------------
# Helper: build a real trajectory + run a real analysis phase
# ---------------------------------------------------------------------------
def _make_traj_files(tmp_path: Path, *, n_residues: int = 5, n_frames: int = 25) -> Path:
    """Save a compact-globule trajectory under simulation/ so analysis can find it.

    Returns the project root (the directory containing simulation/).
    """
    rng = np.random.RandomState(0)
    top = md.Topology()
    chain = top.add_chain()
    for i in range(n_residues):
        res = top.add_residue("ALA", chain, resSeq=i + 1)
        for nm in ("N", "CA", "C", "O", "CB"):
            el = {
                "N": md.element.nitrogen,
                "CA": md.element.carbon,
                "C": md.element.carbon,
                "O": md.element.oxygen,
                "CB": md.element.carbon,
            }[nm]
            top.add_atom(nm, el, res)
    top.create_standard_bonds()

    base = rng.uniform(-0.2, 0.2, size=(top.n_atoms, 3))
    xyz = np.tile(base[None, :, :], (n_frames, 1, 1)) + rng.normal(
        scale=0.02, size=(n_frames, top.n_atoms, 3)
    )
    traj = md.Trajectory(
        xyz=xyz.astype(np.float32), topology=top, time=np.arange(n_frames) * 20.0
    )

    sim = tmp_path / "simulation"
    sim.mkdir(parents=True)
    traj[0].save_pdb(str(sim / "topology.pdb"))
    traj.save_dcd(str(sim / "production.dcd"))
    return tmp_path


@pytest.fixture
def project_with_analysis(tmp_path: Path) -> Path:
    """Project directory after a real analysis phase has run on RMSD + Rg."""
    root = _make_traj_files(tmp_path / "proj")
    fmdx = FastMDXplora(
        system=str(root / "simulation" / "topology.pdb"),
        output_dir=root,
    )
    fmdx.explore(
        include=["analysis"],
        options={"analysis": {"include": ["rmsd", "rg"]}},
    )
    return root


@pytest.fixture
def project_with_multi_method(tmp_path: Path) -> Path:
    """Project after analysis with multi-method cluster + dimred."""
    root = _make_traj_files(tmp_path / "proj", n_residues=6, n_frames=30)
    fmdx = FastMDXplora(
        system=str(root / "simulation" / "topology.pdb"),
        output_dir=root,
    )
    fmdx.explore(
        include=["analysis"],
        options={
            "analysis": {
                "include": ["cluster", "dimred"],
                "options": {
                    "cluster": {"methods": ["kmeans", "hierarchical"], "n_clusters": 3},
                    "dimred": {"methods": ["pca", "tsne"]},
                },
            }
        },
    )
    return root


# ===========================================================================
# Markdown report
# ===========================================================================
class TestReportDocument:
    def test_report_embeds_analysis_figures(self, project_with_analysis: Path):
        """The Markdown report should reference each analysis's PNG file."""
        fmdx = FastMDXplora(
            system=str(project_with_analysis / "simulation" / "topology.pdb"),
            output_dir=project_with_analysis,
        )
        fmdx.report()
        text = (project_with_analysis / "report" / "report.md").read_text(encoding="utf-8")
        # Each analysis's figure should be referenced
        assert "analysis/rmsd/rmsd.png" in text
        assert "analysis/rg/rg.png" in text
        # No "deferred" / placeholder language
        assert "deferred" not in text.lower()
        assert "wired in" not in text.lower()

    def test_report_shows_actual_options(self, project_with_analysis: Path):
        """Options from options.json should appear in the report parameters block."""
        fmdx = FastMDXplora(
            system=str(project_with_analysis / "simulation" / "topology.pdb"),
            output_dir=project_with_analysis,
        )
        fmdx.report()
        text = (project_with_analysis / "report" / "report.md").read_text(encoding="utf-8")
        # RMSD options should appear
        assert "`align`" in text
        assert "`ref`" in text
        # And the actual values, not the placeholder
        assert "Run with default options" not in text

    def test_report_includes_trajectory_metadata(self, project_with_analysis: Path):
        """The report should mention how many frames/residues were analyzed."""
        fmdx = FastMDXplora(
            system=str(project_with_analysis / "simulation" / "topology.pdb"),
            output_dir=project_with_analysis,
        )
        fmdx.report()
        text = (project_with_analysis / "report" / "report.md").read_text(encoding="utf-8")
        # We built a 25-frame, 5-residue trajectory
        assert "25 frames" in text
        assert "5 residues" in text

    def test_report_includes_all_figures_for_multi_method(
        self, project_with_multi_method: Path
    ):
        """For cluster/dimred, every method's PNG should be referenced."""
        fmdx = FastMDXplora(
            system=str(project_with_multi_method / "simulation" / "topology.pdb"),
            output_dir=project_with_multi_method,
        )
        fmdx.report()
        text = (project_with_multi_method / "report" / "report.md").read_text(encoding="utf-8")
        # cluster has two methods
        assert "cluster/cluster_kmeans.png" in text
        assert "cluster/cluster_hierarchical.png" in text
        # dimred has two methods
        assert "dimred/dimred_pca.png" in text
        assert "dimred/dimred_tsne.png" in text


# ===========================================================================
# PPTX slide deck
# ===========================================================================
class TestSlideDeck:
    def test_pptx_embeds_analysis_figures(self, project_with_analysis: Path):
        """Each analysis figure should appear as an image on its own slide."""
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE

        fmdx = FastMDXplora(
            system=str(project_with_analysis / "simulation" / "topology.pdb"),
            output_dir=project_with_analysis,
        )
        fmdx.report()
        prs = Presentation(str(project_with_analysis / "report" / "slides.pptx"))

        # Count image slides
        image_slides = [
            s for s in prs.slides
            if any(shape.shape_type == MSO_SHAPE_TYPE.PICTURE for shape in s.shapes)
        ]
        # We ran RMSD + Rg → exactly 2 image slides
        assert len(image_slides) == 2

    def test_pptx_image_slides_titled_by_analysis(self, project_with_analysis: Path):
        """Image-slide titles should be the analysis names (uppercase)."""
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE

        fmdx = FastMDXplora(
            system=str(project_with_analysis / "simulation" / "topology.pdb"),
            output_dir=project_with_analysis,
        )
        fmdx.report()
        prs = Presentation(str(project_with_analysis / "report" / "slides.pptx"))

        titles = {
            slide.shapes.title.text
            for slide in prs.slides
            if any(shape.shape_type == MSO_SHAPE_TYPE.PICTURE for shape in slide.shapes)
        }
        assert "RMSD" in titles
        assert "RG" in titles

    def test_pptx_fans_out_multi_method_analyses(
        self, project_with_multi_method: Path
    ):
        """A two-method cluster should produce two image slides."""
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE

        fmdx = FastMDXplora(
            system=str(project_with_multi_method / "simulation" / "topology.pdb"),
            output_dir=project_with_multi_method,
        )
        fmdx.report()
        prs = Presentation(str(project_with_multi_method / "report" / "slides.pptx"))

        image_slides = [
            s for s in prs.slides
            if any(shape.shape_type == MSO_SHAPE_TYPE.PICTURE for shape in s.shapes)
        ]
        # cluster: 2 methods, dimred: 2 methods → 4 image slides total
        assert len(image_slides) == 4

    def test_pptx_multi_method_subtitle_records_method(
        self, project_with_multi_method: Path
    ):
        """Multi-method image slides should have a subtitle indicating the method."""
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE

        fmdx = FastMDXplora(
            system=str(project_with_multi_method / "simulation" / "topology.pdb"),
            output_dir=project_with_multi_method,
        )
        fmdx.report()
        prs = Presentation(str(project_with_multi_method / "report" / "slides.pptx"))

        # Find all text on image-bearing slides
        all_text = []
        for slide in prs.slides:
            if not any(
                shape.shape_type == MSO_SHAPE_TYPE.PICTURE for shape in slide.shapes
            ):
                continue
            for shape in slide.shapes:
                if shape.has_text_frame:
                    all_text.append(shape.text_frame.text)
        joined = "\n".join(all_text).lower()
        # The subtitle text should include method names somewhere
        for method in ("kmeans", "hierarchical", "pca", "tsne"):
            assert method in joined, f"method {method} missing from slide text"


# ===========================================================================
# End-to-end with no analyses (deferred case)
# ===========================================================================
def test_report_handles_missing_analyses_gracefully(tmp_path: Path):
    """When no analysis has run, the report should still build a coherent deck."""
    fmdx = FastMDXplora(
        system="1L2Y",  # no trajectory at all
        output_dir=tmp_path,
    )
    result = fmdx.report()
    assert result.status == "ok"
    # The deck should exist; image-slide count is zero because no analyses ran
    from pptx import Presentation

    prs = Presentation(str(tmp_path / "report" / "slides.pptx"))
    assert len(prs.slides) >= 1


def test_deferred_analysis_message_is_current_and_actionable(tmp_path: Path):
    fmdx = FastMDXplora(system="1L2Y", output_dir=tmp_path)
    result = fmdx.analyze()

    assert result.status == "ok"
    manifest = json.loads(
        (tmp_path / "analysis" / "analysis_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "deferred"
    assert "v0.2" not in manifest["note"]
    assert "Run the simulation phase first" in manifest["note"]


# ===========================================================================
# Robustness for report-only mode and generated artifacts
# ===========================================================================
def test_report_only_cli_escapes_weird_markdown_text(tmp_path: Path):
    """Report-only mode should not let titles/messages reshape Markdown."""
    root = tmp_path / "existing run with spaces"
    analysis = root / "analysis"
    analysis.mkdir(parents=True)
    weird_system = "sys|`tick` [brackets]\n# injected\tpath"
    weird_title = "Study | `ticks` [link](x)\n# injected"
    weird_author = "Author | # name\nnext"
    weird_message = "bad | `tick`\n# injected failure"

    (root / "manifest.json").write_text(
        json.dumps({"system": weird_system}),
        encoding="utf-8",
    )
    (analysis / "analysis_manifest.json").write_text(
        json.dumps(
            {
                "plan": ["rmsd"],
                "results": {"rmsd": {"status": "error", "message": weird_message}},
            }
        ),
        encoding="utf-8",
    )

    rc = cli_main(
        [
            "report",
            "--output",
            str(root),
            "--title",
            weird_title,
            "--author",
            weird_author,
            "--no-slides",
            "--no-bundle",
        ]
    )

    assert rc == 0
    text = (root / "report" / "report.md").read_text(encoding="utf-8")
    first_line = text.splitlines()[0]
    assert first_line.startswith("# Study")
    assert "\\|" in first_line
    assert "\\`ticks\\`" in first_line
    assert "\n# injected" not in text
    assert "bad \\| \\`tick\\` \\# injected failure" in text


def test_report_phase_manifest_artifacts_exist(tmp_path: Path):
    fmdx = FastMDXplora(system="sys|odd", output_dir=tmp_path / "run")
    results = fmdx.explore(
        include=["report"],
        options={"report": {"title": "Odd | title", "slides": False, "bundle": False}},
    )

    report_phase = results[0].phase("report")
    assert report_phase is not None
    manifest = json.loads((fmdx.output_dir / "manifest.json").read_text(encoding="utf-8"))
    report_record = next(p for p in manifest["phases"] if p["name"] == "report")
    assert report_record["artifacts"] == ["report.md"]
    for artifact in report_record["artifacts"]:
        assert (Path(report_record["output_dir"]) / artifact).is_file()


def test_report_bundle_excludes_cache_and_temp_files(tmp_path: Path):
    root = tmp_path / "run"
    (root / "analysis").mkdir(parents=True)
    (root / "__pycache__").mkdir()
    (root / ".cache").mkdir()
    (root / "__pycache__" / "module.cpython-310.pyc").write_bytes(b"cached")
    (root / ".cache" / "plot.tmp").write_text("cache", encoding="utf-8")
    (root / "scratch.tmp").write_text("temp", encoding="utf-8")
    (root / "keep.dat").write_text("artifact", encoding="utf-8")

    fmdx = FastMDXplora(system="1L2Y", output_dir=root)
    result = fmdx.report(document=False, slides=False, bundle=True)

    assert result.status == "ok"
    bundle = root / "report" / "project_bundle.zip"
    with zipfile.ZipFile(bundle) as zf:
        names = set(zf.namelist())
    assert "keep.dat" in names
    assert "scratch.tmp" not in names
    assert "__pycache__/module.cpython-310.pyc" not in names
    assert ".cache/plot.tmp" not in names
    assert "report/project_bundle.zip" not in names


def test_powerpoint_handles_weird_title_and_system(tmp_path: Path):
    from pptx import Presentation

    title = "T" * 800 + " | `tick`\n# heading"
    system = "system with spaces | [id]\nnext"
    fmdx = FastMDXplora(system=system, output_dir=tmp_path / "run")
    result = fmdx.report(title=title, bundle=False)

    assert result.status == "ok"
    pptx = fmdx.output_dir / "report" / "slides.pptx"
    assert pptx.is_file()
    prs = Presentation(str(pptx))
    assert len(prs.slides) >= 1
    assert "\n# heading" not in prs.slides[0].shapes.title.text


def test_analysis_report_only_wording_uses_existing_trajectory(tmp_path: Path):
    from pptx import Presentation

    root = tmp_path / "analysis_only"
    analysis = root / "analysis"
    analysis.mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "system": "1L2Y",
                "phases": [
                    {"name": "analysis", "status": "ok"},
                    {"name": "report", "status": "ok"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (analysis / "analysis_manifest.json").write_text(
        json.dumps(
            {
                "plan": ["rmsd"],
                "n_frames": 10,
                "n_residues": 20,
                "results": {"rmsd": {"status": "ok"}},
            }
        ),
        encoding="utf-8",
    )
    rmsd_dir = analysis / "rmsd"
    rmsd_dir.mkdir()
    (rmsd_dir / "options.json").write_text(
        json.dumps({"selection": "name CA", "options": {"align": True}}),
        encoding="utf-8",
    )

    fmdx = FastMDXplora(system="1L2Y", output_dir=root)
    result = fmdx.report(title="Analysis-only Trp-cage report", bundle=False)

    assert result.status == "ok"
    report = (root / "report" / "report.md").read_text(encoding="utf-8")
    assert "end-to-end molecular dynamics study" not in report
    assert "Simulation parameters were not recorded for this run" not in report
    assert "This report was generated from an existing trajectory" in report
    assert "Setup and simulation were not run in this workflow" in report
    assert "Simulation was not run in this workflow" in report

    outline = (root / "report" / "slides_outline.md").read_text(encoding="utf-8")
    assert "Analysis/report workflow from an existing trajectory" in outline
    assert "Setup and simulation were not run in this workflow" in outline
    assert "## 2. Setup" not in outline
    assert "## 3. Simulation" not in outline

    prs = Presentation(str(root / "report" / "slides.pptx"))
    all_text = "\n".join(
        shape.text
        for slide in prs.slides
        for shape in slide.shapes
        if hasattr(shape, "text")
    )
    assert "Analysis/report workflow from an existing trajectory" in all_text
    assert "Setup and simulation were not run in this workflow" in all_text


def test_full_pipeline_report_keeps_end_to_end_wording(tmp_path: Path):
    root = tmp_path / "full_pipeline"
    (root / "setup").mkdir(parents=True)
    (root / "simulation").mkdir()
    (root / "analysis").mkdir()
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "system": "1L2Y",
                "phases": [
                    {"name": "setup", "status": "ok"},
                    {"name": "simulation", "status": "ok"},
                    {"name": "analysis", "status": "ok"},
                    {"name": "report", "status": "ok"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "setup" / "setup_parameters.json").write_text(
        json.dumps({"parameters": {"ph": 7.0}}),
        encoding="utf-8",
    )
    (root / "simulation" / "simulation_parameters.json").write_text(
        json.dumps({"parameters": {"duration_ns": 0.001}}),
        encoding="utf-8",
    )
    (root / "analysis" / "analysis_manifest.json").write_text(
        json.dumps({"plan": [], "results": {}}),
        encoding="utf-8",
    )

    fmdx = FastMDXplora(system="1L2Y", output_dir=root)
    result = fmdx.report(title="Full pipeline report", slides=False, bundle=False)

    assert result.status == "ok"
    report = (root / "report" / "report.md").read_text(encoding="utf-8")
    assert "end-to-end molecular dynamics study" in report
    assert "Production MD was performed" in report
    assert "Setup and simulation were not run in this workflow" not in report
