# tests/test_analyze_orchestrator.py
import types
import warnings
import numpy as np
import pytest

from fastmdanalysis import FastMDAnalysis
from fastmdanalysis.datasets import trp_cage as DS

def make_fastmda():
    return FastMDAnalysis(DS.traj, DS.top, atoms="protein")

def test_include_exclude_subset(tmp_path):
    fmda = make_fastmda()
    res = fmda.analyze(include=["rmsd","rg"], exclude=["rg"], verbose=False)
    assert set(res.keys()) == {"rmsd"}
    assert res["rmsd"].ok and res["rmsd"].seconds >= 0

def test_options_filtering_warns(tmp_path):
    fmda = make_fastmda()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # pass an unsupported kw to rmsd; it should be dropped with a warning
        res = fmda.analyze(include=["rmsd"], options={"rmsd": {"nonexistent_kw": 123}}, verbose=True)
        assert res["rmsd"].ok
        assert any("unsupported options for 'rmsd'" in str(x.message).lower() for x in w)

def test_stop_on_error_continues(tmp_path):
    fmda = make_fastmda()
    # Force rmsf to fail by giving an empty selection
    res = fmda.analyze(include=["rmsd","rmsf"], options={"rmsf": {"atoms": "name ZZ"}}, stop_on_error=False, verbose=False)
    assert res["rmsd"].ok
    assert not res["rmsf"].ok
    assert res["rmsf"].error is not None

def test_slides_hook_monkeypatched(tmp_path, monkeypatch):
    fmda = make_fastmda()

    # fake images list (with duplicates) returned by gather_figures
    def fake_gather(roots, since_epoch=None):
        return [tmp_path/"a.png", tmp_path/"a.png", tmp_path/"b.png"]
    monkeypatch.setattr("fastmdanalysis.analysis.analyze.gather_figures", fake_gather)

    # stub slide_show that asserts deduping happened upstream/inside slideshow
    def fake_slide_show(images, outpath=None, title=None, subtitle=None):
        assert len(images) == 2  # no duplicates
        p = tmp_path/"deck.pptx"
        p.write_bytes(b"fake")
        return p
    monkeypatch.setattr("fastmdanalysis.analysis.analyze.slide_show", fake_slide_show)

    res = fmda.analyze(include=["rmsd"], slides=True, verbose=False)
    assert "slides" in res and res["slides"].ok

from pathlib import Path

def test_slides_moves_deck_into_output(tmp_path, fastmda, monkeypatch):
    # Collect everything under a temp output dir
    outdir = tmp_path / "collect"

    # Return duplicates -> analyzer should de-dupe before calling slide_show
    def fake_gather(roots, since_epoch=None):
        return [tmp_path / "img1.png", tmp_path / "img1.png", tmp_path / "img2.png"]

    monkeypatch.setattr("fastmdanalysis.analysis.analyze.gather_figures", fake_gather)

    # Write deck OUTSIDE the analyze output dir so relocation branch runs
    def fake_slide_show(images, outpath=None, title=None, subtitle=None):
        assert len(images) == 2  # de-duped
        p = tmp_path / "elsewhere" / "deck.pptx"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"fake")
        return p

    monkeypatch.setattr("fastmdanalysis.analysis.analyze.slide_show", fake_slide_show)

    res = fastmda.analyze(include=["rmsd"], slides=True, verbose=False, output=outdir)
    assert "slides" in res and res["slides"].ok
    # Deck should now live under our output folder
    assert Path(res["slides"].value).parent.resolve() == outdir.resolve()

