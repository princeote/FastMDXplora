from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from fastmdxplora.live import launcher as launch
from fastmdxplora.live import live_frames as frames
from fastmdxplora.live import trajectory_playback as playback
from fastmdxplora.live.ligand_detection import detect_ligands, filter_pdb_to_ligand
from fastmdxplora.live.structure_info import _count_structure_cached, count_structure, ligand_atom_counts


def _atom(record="ATOM", res="ALA", chain="A", seq=1, x=0.0, y=0.0, z=0.0) -> str:
    return f"{record:<6}{1:5d}  CA  {res:>3} {chain}{seq:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00 10.00           C"


def _launch_payload() -> dict:
    return {
        "system": "1L2Y", "run_name": "run",
        "setup": {"ph": 7, "forcefield": "charmm36", "water_model": "auto",
                  "ion_concentration_M": .15, "solvent_padding_nm": 1},
        "simulation": {"minimize": True, "nvt_steps": 1, "npt_steps": 1,
                       "production_steps": 10, "timestep_fs": 2, "temperature_K": 300,
                       "friction_per_ps": 1, "integrator": "langevin_middle", "platform": "CPU",
                       "precision": "mixed", "trajectory_interval_steps": 2,
                       "checkpoint_interval_steps": 0, "telemetry_interval": 2},
        "workflow": {"run_analysis": True, "run_report": True, "analyses": ["rmsd"],
                     "report_document": True, "report_slides": True, "report_bundle": True},
    }


class _Topology:
    def __init__(self, selected=(0, 1), fail=False):
        self.selected, self.fail = selected, fail

    def select(self, _query):
        if self.fail:
            raise RuntimeError("selection failed")
        return list(self.selected)


class _BrowserTrajectory:
    def __init__(self, times=(0.0, 0.0)):
        self.time = list(times)

    def save_pdb(self, path):
        Path(path).write_text(_atom() + "\nEND\n", encoding="utf-8")


class _Trajectory:
    def __init__(self, n_frames=5, times=(0.0, 0.0)):
        self.n_frames, self.times = n_frames, times

    def __getitem__(self, _indices):
        return _BrowserTrajectory(self.times)


class _MD:
    def __init__(self, *, n_frames=5, selected=(0, 1), select_fail=False, dcd_fail=False):
        self.topology = _Topology(selected, select_fail)
        self.trajectory = _Trajectory(n_frames)
        self.dcd_fail = dcd_fail

    def load_pdb(self, _path):
        return SimpleNamespace(topology=self.topology)

    def load_dcd(self, *_args, **_kwargs):
        if self.dcd_fail:
            raise RuntimeError("busy dcd")
        return self.trajectory


def test_playback_dcd_cache_fallback_and_helpers(tmp_path: Path, monkeypatch) -> None:
    out, sim = tmp_path / "run", tmp_path / "run" / "simulation"
    sim.mkdir(parents=True)
    (sim / "topology.pdb").write_text(_atom() + "\nEND\n", encoding="utf-8")
    (sim / "production.dcd").write_bytes(b"dcd")
    (sim / "live_status.json").write_text('{"status":"completed"}', encoding="utf-8")
    monkeypatch.setattr(playback, "_import_mdtraj", lambda: _MD())

    result = playback.playback_info(out, max_browser_frames=3, simulation_time_ns_total=1.0)
    assert result["source_kind"] == "production-dcd" and result["frame_times_ns"][-1] == 1.0
    assert playback.playback_info(out) == json.loads((sim / "playback_index.json").read_text())
    assert playback._even_indices(10, 2) == [0, 9]
    assert playback._even_indices(3, 5) == [0, 1, 2]
    assert playback._load_index(tmp_path / "missing.json")["reason"] == "invalid-companion"

    # A temporarily unreadable DCD falls back to completed live-history snapshots.
    for i in range(2):
        p = sim / f"h{i}.pdb"
        p.write_text(_atom(seq=i + 1) + "\nEND\n", encoding="utf-8")
    (sim / "live_frame_history.json").write_text(json.dumps({"frames": [
        {"path": "h0.pdb", "sequence": 0, "frame_index": 0, "simulation_time_ns": 0.0},
        {"path": "h1.pdb", "sequence": 1, "frame_index": 1, "simulation_time_ns": 0.1},
    ]}), encoding="utf-8")
    monkeypatch.setattr(playback, "_import_mdtraj", lambda: _MD(dcd_fail=True))
    result = playback.playback_info(out, force=True)
    assert result["source_kind"] == "live-history"


def test_playback_error_branches_and_neighborhood(tmp_path: Path) -> None:
    topology = tmp_path / "top.pdb"
    topology.write_text("\n".join([
        _atom("HETATM", "LIG", seq=9),
        _atom("ATOM", "ALA", seq=1, x=1),
        "ATOM bad-coordinate-line",
        "END",
    ]), encoding="utf-8")
    assert playback.neighborhood_residues(topology_path=topology, ligand_resname="LIG") == [("A", 1)]
    assert playback.neighborhood_residues(topology_path=tmp_path / "none", ligand_resname="LIG") == []
    assert playback.neighborhood_residues(topology_path=topology, ligand_resname="XXX") == []

    idx = tmp_path / "index.json"
    pdb = tmp_path / "playback.pdb"
    one = playback._generate_from_dcd(
        md=_MD(n_frames=1, selected=(), select_fail=True), topology_path=topology,
        dcd_path=tmp_path / "x.dcd", companion_pdb=pdb, companion_idx=idx,
        max_browser_frames=2, simulation_time_ns_total=None, source_signature="x",
    )
    assert one["reason"] == "not-enough-trajectory-frames"

    unreadable = playback._generate_from_history(
        sim_dir=tmp_path, records=[{"path": "missing"}, {"path": "also-missing"}],
        companion_pdb=pdb, companion_idx=idx, max_browser_frames=2, source_signature="x",
    )
    assert unreadable["reason"] == "not-enough-readable-history-frames"


def test_launcher_validation_command_and_runtime_branches(tmp_path: Path, monkeypatch) -> None:
    bad = _launch_payload()
    bad.update(system="x" * 4097)
    bad["setup"].update(ph="bad", forcefield="bad", ion_concentration_M="bad", solvent_padding_nm=99)
    bad["simulation"].update(integrator="bad", platform="bad", precision="bad", nvt_steps="bad")
    bad["workflow"].update(run_analysis=False, run_report=True, analyses="bad")
    result = launch.validate_launcher_payload(bad)
    assert not result["valid"] and result["warnings"]
    assert {"system", "setup.ph", "setup.forcefield", "simulation.integrator"} <= result["errors"].keys()

    cfg = launch.validate_launcher_payload(_launch_payload())["config"]
    cfg["setup"].update(water_model="tip3p", keep_heterogens=True, keep_water=True)
    cfg["simulation"]["minimize"] = False
    cfg["workflow"].update(run_analysis=False, report_document=False, report_slides=False, report_bundle=False)
    command = launch.build_launcher_command(cfg, tmp_path / "out")
    for flag in ("--setup-water-model", "--setup-keep-heterogens", "--setup-keep-water",
                 "--simulate-no-minimize", "--include", "--report-no-document",
                 "--report-no-slides", "--report-no-bundle"):
        assert flag in command

    runtime = launch.DashboardRuntime(tmp_path / "workspace", tmp_path / "runs")
    assert runtime.launch({"system": ""})["valid"] is False
    runtime.process = SimpleNamespace(poll=lambda: 0)
    assert runtime.snapshot()["status"] == "completed"
    runtime.process = SimpleNamespace(poll=lambda: 2)
    runtime.process_returncode = None
    assert runtime.snapshot()["status"] == "failed"

    terminated = []
    runtime.process = SimpleNamespace(poll=lambda: None, terminate=lambda: terminated.append(True))
    assert runtime.stop()["stopped"] and terminated
    assert runtime.launch(_launch_payload())["errors"]["run"]

    occupied = launch.DashboardRuntime(tmp_path / "w2", tmp_path / "runs2")
    target = occupied.launch_root / "run"
    target.mkdir()
    (target / "file").write_text("x", encoding="utf-8")
    assert "not empty" in occupied.launch(_launch_payload())["errors"]["run_name"]

    failing = launch.DashboardRuntime(tmp_path / "w3", tmp_path / "runs3")
    monkeypatch.setattr(launch.subprocess, "Popen", lambda *_a, **_k: (_ for _ in ()).throw(OSError("no")))
    with pytest.raises(OSError):
        failing.launch(_launch_payload())


def test_live_frame_failure_fallbacks_and_bounded_archive(tmp_path: Path, monkeypatch) -> None:
    text = "CRYST1".ljust(80) + "\n" + _atom() + "\nTER\nEND\n"
    assert "CRYST1" in frames.dashboard_display_pdb(text) and "TER" in frames.dashboard_display_pdb(text)

    with patch.object(Path, "stat", side_effect=OSError), patch.object(frames, "_atomic_json", side_effect=OSError):
        result = frames.write_live_frame(tmp_path / "fallback", pdb_text=text, frame_index=1)
    assert result["ok"] and result["live_frame_size"] == len(text.encode())

    def old_writer(_topology, _positions, buf):
        buf.write(text)
    assert frames.write_openmm_live_frame(tmp_path / "openmm", pdbfile_writer=old_writer,
                                          topology=None, positions=None)["ok"]
    assert not frames.write_openmm_live_frame(tmp_path, pdbfile_writer=lambda *_a, **_k: None,
                                              topology=None, positions=None)["ok"]
    assert not frames.write_openmm_live_frame(tmp_path, pdbfile_writer=lambda *_a, **_k: 1 / 0,
                                              topology=None, positions=None)["ok"]

    archive = tmp_path / "archive"
    for i in range(3):
        assert frames.write_live_frame(archive, pdb_text=text, frame_index=i, archive=True,
                                       max_history_frames=2)["ok"]
    history = frames.read_live_frame_history(archive)
    assert history["count"] == 2 and history["frames"][0]["frame_index"] == 1

    (archive / frames.LIVE_FRAME_INDEX_FILE).write_text("bad", encoding="utf-8")
    assert frames.read_live_frame_index(archive) == {"live_frame_available": False}
    monkeypatch.setattr(Path, "mkdir", lambda *_a, **_k: (_ for _ in ()).throw(OSError("blocked")))
    assert frames._archive_frame(tmp_path / "blocked", pdb_text=text, frame_index=0, stage="NVT",
                                 simulation_time_ns=0, max_history_frames=2)["count"] == 0


def test_ligand_and_structure_edge_paths(tmp_path: Path) -> None:
    detected = detect_ligands([("A", "", "1"), ("A", "ALA", "2"), ("A", "LIG", "10A")])
    assert detected["resnames"] == ["LIG"]
    pdb = "HEADER keep\n" + _atom("HETATM", "LIG") + "\n" + _atom("ATOM", "ALA")
    assert filter_pdb_to_ligand(pdb, "") == pdb
    filtered = filter_pdb_to_ligand(pdb, "lig")
    assert "LIG" in filtered and "ALA" not in filtered and "HEADER" in filtered

    structure = tmp_path / "structure.pdb"
    structure.write_text("\n".join([_atom("HETATM", "NA"), "ATOM bad-coordinate-line", "END"]), encoding="utf-8")
    info = count_structure(structure)
    assert info["ions"] == 1

    empty = tmp_path / "empty.pdb"
    empty.write_text("HEADER\nEND\n", encoding="utf-8")
    assert count_structure(empty)["centroid_angstrom"] == [None, None, None]
    assert _count_structure_cached(str(tmp_path), 0, 0)["reason"].startswith("read-error")

    fake_path = SimpleNamespace(is_file=lambda: True, stat=lambda: (_ for _ in ()).throw(OSError("stat")), as_posix=lambda: "fake")
    with patch("fastmdxplora.live.structure_info.Path", return_value=fake_path):
        assert count_structure(structure)["reason"].startswith("stat-error")
    with patch.object(Path, "open", side_effect=OSError("read")):
        assert ligand_atom_counts(structure) == {}


def test_orchestrator_dashboard_telemetry_paths(tmp_path: Path, monkeypatch) -> None:
    from fastmdxplora.orchestrator import FastMDXplora, PhaseResult

    app = object.__new__(FastMDXplora)
    app.output_dir = tmp_path / "run"
    app.output_dir.mkdir()
    app.options = {"simulation": {}}

    class Writer:
        def __init__(self):
            self.root = app.output_dir / "simulation"
            self.statuses, self.stages, self.events = [], [], []

        def write_status(self, **kwargs): self.statuses.append(kwargs)
        def mark_stage(self, *args, **kwargs): self.stages.append((args, kwargs))
        def event(self, *args, **kwargs): self.events.append((args, kwargs))

    writer = Writer()
    monkeypatch.setenv("FASTMDX_DASHBOARD_ACTIVE", "1")
    monkeypatch.setenv("FASTMDX_DASHBOARD_OUTPUT", str(app.output_dir))
    monkeypatch.setattr("fastmdxplora.live.telemetry.TelemetryWriter", lambda *_a, **_k: writer)
    assert app._dashboard_writer() is writer
    monkeypatch.setattr("fastmdxplora.live.telemetry.TelemetryWriter", lambda *_a, **_k: 1 / 0)
    assert app._dashboard_writer() is None

    FastMDXplora._initialize_dashboard_timeline(writer, ["setup", "simulation", "report"])
    assert writer.statuses[-1]["stage_states"]["analysis"] == "skipped"
    FastMDXplora._initialize_dashboard_timeline(writer, [])
    assert writer.statuses[-1]["status"] == "completed"

    FastMDXplora._mark_dashboard_phase_start(None, "setup", {})
    FastMDXplora._mark_dashboard_phase_start(writer, "simulation", {"minimize": False})
    FastMDXplora._mark_dashboard_phase_start(writer, "analysis", {})

    ok = PhaseResult("simulation", "ok", app.output_dir)
    skipped = PhaseResult("report", "skipped", app.output_dir)
    failed = PhaseResult("analysis", "error", app.output_dir, message="boom")
    monkeypatch.setattr("fastmdxplora.live.telemetry.read_status", lambda _root: {
        "stage_states": {"minimization": "waiting", "nvt": "current",
                         "npt": "completed", "production": "waiting"}
    })
    FastMDXplora._mark_dashboard_phase_end(None, "setup", ok)
    FastMDXplora._mark_dashboard_phase_end(writer, "simulation", ok)
    FastMDXplora._mark_dashboard_phase_end(writer, "report", skipped)
    FastMDXplora._mark_dashboard_phase_end(writer, "analysis", failed)
    assert any(args[1] == "failed" for args, _kwargs in writer.stages)
    assert writer.events[-1][1]["level"] == "error"


def test_server_helpers_cover_changed_display_branches(tmp_path: Path, monkeypatch) -> None:
    from fastmdxplora.live import server

    assert server.DashboardConfig(binding_pocket_cutoff_A=4.5).binding_pocket_cutoff_m == 4.5
    assert server._artifact_records(tmp_path / "missing") == []
    assert server._summary_records(tmp_path, {"phases": [{"status": "ok"}]}, {}, {})[0]["value"] == "completed"
    assert server._summary_records(tmp_path, {"phases": [{"status": "failed"}]}, {}, {})[0]["value"] == "failed"
    assert server._summary_records(tmp_path, {"phases": [{"status": "running"}]}, {}, {})[0]["value"] == "in progress"

    monkeypatch.setattr(server, "read_metrics", lambda *_a, **_k: [{"temperature": 301}, {"temperature": None}])
    assert server._last_metric_value(tmp_path, "temperature") is None
    monkeypatch.setattr(server, "read_metrics", lambda *_a, **_k: [{"temperature": 301}])
    assert server._last_metric_value(tmp_path, "temperature") == "301"

    assert server._run_title(tmp_path, {"title": "Named"}) == "Named"
    assert server._run_title(tmp_path, {"system": "/x/1abc.pdb"}).startswith("1abc")
    assert server._setup_details({"parameters": {}, "resolved_forcefield": {"ligand": {"name": "LIG"}}})["ligand"] == "LIG"
    assert server._analysis_records({"status": "skipped", "note": "none"}, [], [])[0]["status"] == "skipped"
    assert server._phase_records({"phases": [{"name": "setup", "status": "ok"}]})[0]["status"] == "ok"
    assert server._plot_title("analysis/rmsd/rmsd_plot.png") == "RMSD"
    assert server._plot_title("report/dashboard_assets/rmsd.png") == "RMSD"
    assert server._plot_category("analysis/cluster/plot.png") == "Clustering"
    assert server._plot_category("analysis/sasa/plot.png") == "Additional Analysis"
    assert server._plot_category("misc/plot.png") == "Other"

    monkeypatch.setattr(server.subprocess, "Popen", lambda *_a, **_k: object())
    assert server._open_local_path(tmp_path)[0] is True
    monkeypatch.setattr(server.subprocess, "Popen", lambda *_a, **_k: (_ for _ in ()).throw(OSError("no opener")))
    assert server._open_local_path(tmp_path) == (False, "no opener")


def test_server_error_and_launcher_routes(tmp_path: Path, monkeypatch) -> None:
    import urllib.error
    import urllib.request
    from fastmdxplora.live import server as live_server

    root = tmp_path / "run"
    root.mkdir()
    monkeypatch.setattr(live_server, "_open_local_path", lambda _path: (True, "opened"))
    httpd, url = live_server.start_test_server(root, home_mode=True)

    def get(path: str, expected: int = 200):
        try:
            with urllib.request.urlopen(url + path) as response:
                assert response.status == expected
                return response.read()
        except urllib.error.HTTPError as exc:
            assert exc.code == expected
            return exc.read()

    def post(path: str, value, expected: int):
        request = urllib.request.Request(
            url + path, data=json.dumps(value).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(request) as response:
                assert response.status == expected
                return response.read()
        except urllib.error.HTTPError as exc:
            assert exc.code == expected
            return exc.read()

    try:
        get("/api/playback-info?max=bad")
        get("/api/open-output")
        get("/structure/playback.pdb", 404)
        get("/analysis-figures-svg.zip", 404)
        get("/structure/topology.pdb", 404)
        get("/artifacts/missing.txt", 404)
        get("/static/missing.txt", 404)
        get("/not-found", 404)
        post("/api/launcher/launch", {"system": ""}, 422)
        post("/api/launcher/stop", {}, 200)
        post("/not-found", {}, 404)
        post("/api/launcher/validate", [], 500)

        monkeypatch.setattr(live_server, "_results_payload", lambda _root: (_ for _ in ()).throw(RuntimeError("route")))
        get("/api/results", 500)
    finally:
        httpd.shutdown()
        httpd.server_close()
