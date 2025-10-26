import pytest
from pathlib import Path

def test_analyze_include_exclude(fastmda):
    res = fastmda.analyze(include=["rmsd", "rg"], options={"rmsd": {"ref": 0}})
    assert "rmsd" in res and "rg" in res
    assert res["rmsd"].ok and res["rg"].ok

@pytest.mark.slow
def test_analyze_with_slides(fastmda, monkeypatch):
    pptx = pytest.importorskip("pptx")
    res = fastmda.analyze(include=["rmsd"], options={"rmsd": {"ref": 0}}, slides=True)
    s = res.get("slides")
    assert s and s.ok
    assert Path(s.value).exists()

