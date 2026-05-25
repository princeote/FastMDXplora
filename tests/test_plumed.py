"""Tests for the PLUMED enhanced-sampling integration.

These exercise the parts that don't require the openmm-plumed package: the
disabled no-op, PLUMED output-path redirection, inline-vs-file script
resolution, schema/CLI wiring, and the graceful-degradation error when the
package is missing. The actual biasing (adding a real PlumedForce and running
biased dynamics) is verified on a machine with openmm-plumed installed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fastmdxplora.simulation import plumed as plumed_mod
from fastmdxplora.simulation.plumed import (
    PlumedError,
    add_plumed_force,
    adjust_plumed_output_paths,
    load_plumed_script,
)


class TestDisabledNoOp:
    def test_none_config_returns_none(self):
        system = MagicMock()
        assert add_plumed_force({}, system, None, Path("/tmp")) is None
        system.addForce.assert_not_called()

    def test_disabled_returns_none(self):
        system = MagicMock()
        assert add_plumed_force({}, system, {"enabled": False}, Path("/tmp")) is None
        system.addForce.assert_not_called()


class TestPathAdjustment:
    def test_redirects_file_outputs(self, tmp_path):
        script = (
            "d: DISTANCE ATOMS=1,2\n"
            "PRINT ARG=d FILE=COLVAR STRIDE=10\n"
            "METAD ARG=d FILE=HILLS PACE=500 HEIGHT=1.0 SIGMA=0.1\n"
        )
        out = adjust_plumed_output_paths(script, tmp_path)
        # COLVAR and HILLS now point under tmp_path (forward slashes).
        assert f"FILE={(tmp_path / 'COLVAR').as_posix()}" in out
        assert f"FILE={(tmp_path / 'HILLS').as_posix()}" in out
        # Non-FILE lines untouched.
        assert "d: DISTANCE ATOMS=1,2" in out

    def test_strips_directory_keeps_basename(self, tmp_path):
        script = "PRINT ARG=d FILE=/some/other/dir/COLVAR STRIDE=1\n"
        out = adjust_plumed_output_paths(script, tmp_path)
        assert f"FILE={(tmp_path / 'COLVAR').as_posix()}" in out
        assert "/some/other/dir" not in out


class TestScriptLoading:
    def test_inline_multiline_script_returned_asis(self):
        script = "d: DISTANCE ATOMS=1,2\nPRINT ARG=d FILE=COLVAR\n"
        assert load_plumed_script(script) == script

    def test_reads_existing_file(self, tmp_path):
        f = tmp_path / "bias.dat"
        f.write_text("d: DISTANCE ATOMS=1,2\n", encoding="utf-8")
        assert "DISTANCE" in load_plumed_script(str(f))

    def test_missing_pathlike_raises(self):
        with pytest.raises(PlumedError, match="not found"):
            load_plumed_script("nonexistent/path/to/bias.dat")


class TestEnabledRequiresScript:
    def test_enabled_without_script_raises(self, tmp_path):
        system = MagicMock()
        with pytest.raises(PlumedError, match="no 'script'"):
            add_plumed_force({}, system, {"enabled": True}, tmp_path)


class TestGracefulDegradation:
    def test_missing_package_raises_actionable(self, tmp_path, monkeypatch):
        # Simulate openmm-plumed not being importable.
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "openmmplumed":
                raise ImportError("no module named openmmplumed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        system = MagicMock()
        with pytest.raises(PlumedError, match="openmm-plumed"):
            add_plumed_force(
                {}, system, {"enabled": True, "script": "d: DISTANCE ATOMS=1,2"},
                tmp_path,
            )


class TestEnabledAddsForce:
    def test_adds_force_and_writes_resolved_script(self, tmp_path, monkeypatch):
        # Fake the PlumedForce so we don't need the real package.
        created = {}

        def fake_import_plumed():
            def PlumedForce(script):
                created["script"] = script
                return MagicMock(name="PlumedForce")
            return PlumedForce

        monkeypatch.setattr(plumed_mod, "_import_plumed", fake_import_plumed)
        system = MagicMock()
        force = add_plumed_force(
            {}, system,
            {"enabled": True, "script": "d: DISTANCE ATOMS=1,2\nPRINT ARG=d FILE=COLVAR\n"},
            tmp_path,
        )
        assert force is not None
        system.addForce.assert_called_once()
        # Resolved script written for reproducibility, with redirected FILE.
        resolved = tmp_path / "plumed.dat"
        assert resolved.exists()
        assert (tmp_path / "COLVAR").as_posix() in resolved.read_text()


class TestSchemaAndCLIWiring:
    def test_schema_has_plumed(self):
        from fastmdxplora.config.schema import PHASE_SCHEMAS
        assert PHASE_SCHEMAS["simulation"].get("plumed") is not None

    def test_pipeline_default_plumed_none(self):
        from fastmdxplora.simulation.pipeline import DEFAULTS
        assert DEFAULTS["plumed"] is None

    def test_cli_flag_builds_plumed_dict(self):
        import argparse
        from fastmdxplora.cli.main import _build_explore_config

        args = argparse.Namespace(
            config=None, system="1L2Y", output_dir=None, verbose=False,
            include=None, exclude=None,
            simulate__plumed_script="bias.dat",
        )
        # Fill any other harvested attrs as None so harvesting is clean.
        config = _build_explore_config(args)
        sim = config.get("simulation", {})
        assert "plumed_script" not in sim
        assert sim.get("plumed") == {"enabled": True, "script": "bias.dat"}
