from __future__ import annotations

import json
import importlib.util
from pathlib import Path


def _smoke_run():
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_drift_smoke.py"
    spec = importlib.util.spec_from_file_location("run_drift_smoke", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.run


def test_smoke_summary_continue_on_error(tmp_path: Path) -> None:
    good = tmp_path / "good.pdb"
    good.write_text("HEADER good\nEND\n", encoding="utf-8")
    missing = tmp_path / "missing.pdb"
    output = tmp_path / "smoke"

    rc = _smoke_run()(
        ["--output-root", str(output), "--continue-on-error", str(good), str(missing)]
    )

    assert rc == 1
    rows = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert [row["status"] for row in rows] == ["ok", "failed"]
    assert (output / "summary.csv").is_file()
    assert (output / "good" / "report" / "report.md").is_file()


def test_smoke_stops_without_continue_on_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pdb"
    good = tmp_path / "good.pdb"
    good.write_text("HEADER good\nEND\n", encoding="utf-8")
    output = tmp_path / "smoke"

    rc = _smoke_run()(["--output-root", str(output), str(missing), str(good)])

    assert rc == 1
    rows = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
