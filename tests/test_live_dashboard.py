"""Tests for the local live dashboard.

These tests assert:

  - endpoint contracts (URLs, response keys) the frontend binds to,
  - failure isolation (traversal, missing files, empty run),
  - the redesigned HTML/CSS/JS assets exist on disk and contain the
    expected AAI-branded module structure.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from fastmdxplora.cli.main import _build_parser
from fastmdxplora.live import protein_preview
from fastmdxplora.live.ligand_detection import detect_ligands, normalise_ligand_resname
from fastmdxplora.live.live_frames import write_live_frame, write_openmm_live_frame
from fastmdxplora.live.protein_preview import protein_preview_payload
from fastmdxplora.live.server import (
    DashboardConfig,
    make_handler,
    start_dashboard_session,
    start_test_server,
)
from fastmdxplora.live.structure_info import count_structure, ligand_atom_counts
from fastmdxplora.live.telemetry import (
    TelemetryWriter,
    analyze_health,
    read_events,
    read_metrics,
    read_status,
)
from fastmdxplora.live.trajectory_playback import (
    PlaybackUnavailable,
    neighborhood_residues,
    playback_info,
)


# ---------------------------------------------------------------------------
# Fixture: tiny four-atom helper used by several tests
# ---------------------------------------------------------------------------
def _tiny_pdb() -> str:
    return "\n".join(
        [
            "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 10.00           C",
            "ATOM      2  CA  GLY A   2       1.500   0.400   0.300  1.00 10.00           C",
            "ATOM      3  CA  SER A   3       2.800   1.200   0.000  1.00 10.00           C",
            "ATOM      4  CA  LEU A   4       4.100   1.400   0.900  1.00 10.00           C",
            "END",
        ]
    )


# ---------------------------------------------------------------------------
# Telemetry basics (unchanged behavior)
# ---------------------------------------------------------------------------
def test_telemetry_writer_creates_status_metrics_and_events(tmp_path: Path) -> None:
    simulation_dir = tmp_path / "run" / "simulation"
    writer = TelemetryWriter(simulation_dir, total_steps=100, planned_frames=10, timestep_fs=2.0, platform="CPU", target_temperature_K=300.0)
    writer.write_status(stage="production", status="running", current_step=25)
    writer.append_metric(stage="production", step=25, simulation_time_ns=0.00005, potential_energy=-123.4, total_energy=-100.0, temperature=299.0, progress_percent=25.0)
    writer.event("frame written")

    status = read_status(tmp_path / "run")
    metrics = read_metrics(tmp_path / "run")
    events = read_events(tmp_path / "run")

    assert status["stage"] == "production"
    assert status["current_step"] == 25
    assert metrics[-1]["potential_energy"] == "-123.4"
    assert events[-1]["message"] == "frame written"


def test_telemetry_writer_file_errors_do_not_raise(tmp_path: Path) -> None:
    blocked_path = tmp_path / "not_a_directory"
    blocked_path.write_text("occupied", encoding="utf-8")
    writer = TelemetryWriter(blocked_path)
    writer.write_status(stage="production")
    writer.append_metric(stage="production", step=1)
    writer.event("event")


def test_health_detects_nan_and_energy_spike() -> None:
    status = {"status": "running", "last_update_timestamp": "2999-01-01T00:00:00+00:00"}
    nan_health = analyze_health(status, [{"stage": "production", "total_energy": "nan"}])
    assert nan_health["state"] == "failed"
    assert "numerically unstable" in nan_health["explanation"]

    spike_health = analyze_health(status, [{"stage": "production", "total_energy": "-100.0"}, {"stage": "production", "total_energy": "50000.0"}])
    assert spike_health["state"] == "warning"
    assert "Energy increased sharply" in spike_health["explanation"]


def test_telemetry_readers_handle_missing_and_malformed_files(tmp_path: Path) -> None:
    run = tmp_path / "run"
    sim = run / "simulation"
    sim.mkdir(parents=True)

    assert read_status(run) == {}
    assert read_metrics(run) == []
    assert read_events(run) == []

    (sim / "live_status.json").write_text("{not-json", encoding="utf-8")
    (sim / "live_metrics.csv").write_text('timestamp,stage,total_energy\n"unterminated', encoding="utf-8")
    (sim / "live_events.log").write_text("free-form event without tabs\n", encoding="utf-8")

    assert read_status(run) == {}
    assert isinstance(read_metrics(run), list)
    assert read_events(run) == [{"timestamp": "", "level": "info", "message": "free-form event without tabs"}]


def test_analyze_health_temperature_and_stale_warning() -> None:
    stale = analyze_health({"status": "running", "last_update_timestamp": "2000-01-01T00:00:00+00:00"}, [], stale_after_seconds=1)
    assert stale["state"] == "warning"
    assert "stale" in stale["message"].lower()

    hot = analyze_health({"status": "running", "target_temperature_K": 300.0}, [{"temperature": "420.0"}])
    assert hot["state"] == "warning"
    assert "Temperature" in hot["message"]


# ---------------------------------------------------------------------------
# Protein preview behaviour (unchanged endpoint contract)
# ---------------------------------------------------------------------------
def test_protein_preview_unavailable_without_structure(tmp_path: Path) -> None:
    payload = protein_preview_payload(tmp_path / "run")
    assert payload["available"] is False
    assert payload["message"] == "No topology/PDB found yet."


def test_protein_preview_uses_existing_image_without_structure(tmp_path: Path) -> None:
    run = tmp_path / "run"
    preview = run / "report" / "dashboard_assets" / "protein_preview.png"
    preview.parent.mkdir(parents=True)
    preview.write_bytes(b"\x89PNG\r\n\x1a\n")

    payload = protein_preview_payload(run)
    assert payload["available"] is True
    assert payload["static_available"] is True
    assert payload["static_mode"] == "existing"
    assert payload["path"] == "report/dashboard_assets/protein_preview.png"


def test_structure_route_serves_topology(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(protein_preview, "_find_pymol_executable", lambda _root: None)
    run = tmp_path / "run"
    topology = run / "simulation" / "topology.pdb"
    topology.parent.mkdir(parents=True)
    topology.write_text(_tiny_pdb(), encoding="utf-8")

    server, base_url = start_test_server(run)
    try:
        response = urlopen(f"{base_url}/structure/topology.pdb", timeout=5)
        body = response.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()

    assert response.headers["Cache-Control"] == "no-store"
    assert "ATOM" in body and "ALA" in body


def test_pymol_script_uses_padded_uncropped_camera(tmp_path: Path, monkeypatch) -> None:
    structure = tmp_path / "topology.pdb"
    output = tmp_path / "protein_preview.png"
    structure.write_text(_tiny_pdb(), encoding="utf-8")
    captured: dict[str, str] = {}

    def _fake_run(command, **_kwargs):
        script = Path(command[-1])
        captured["script"] = script.read_text(encoding="utf-8")
        output.write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setattr(protein_preview.subprocess, "run", _fake_run)
    protein_preview._render_with_pymol("/fake/pymol", structure, output)

    script = captured["script"]
    assert "viewport 1800, 1400" in script
    assert "show cartoon, prot" in script
    assert "spectrum count, rainbow, prot, byres=1" in script
    assert "set_color fastmdx_res_1" in script
    assert "color fastmdx_res_1, prot and resi 1 and chain A" in script
    assert "set ray_opaque_background, off" in script
    assert "set cartoon_fancy_helices, 1" in script
    assert "set cartoon_smooth_loops, 1" in script
    assert "set ray_trace_mode, 1" in script
    assert "set cartoon_tube_radius, 0.45" in script
    assert "set cartoon_sampling, 14" in script
    assert "orient prot" in script
    assert "center prot" in script
    assert "zoom prot, 1.8" in script
    assert "ray 1800, 1200" in script
    assert "width=1800" in script
    assert "height=1200" in script
    assert "dpi=300" in script


def test_dashboard_serve_command_parses() -> None:
    args = _build_parser().parse_args(
        ["dashboard", "serve", "--output", "local_runs/my_run", "--port", "8766"]
    )
    assert args.command == "dashboard"
    assert args.dashboard_command == "serve"
    assert args.output == "local_runs/my_run"
    assert args.port == 8766


# ---------------------------------------------------------------------------
# New dashboards: structure_info, ligand_detection, live_frames, trajectory_playback
# ---------------------------------------------------------------------------
def test_count_structure_basic_protein(tmp_path: Path) -> None:
    (tmp_path / "topology.pdb").write_text(_tiny_pdb(), encoding="utf-8")
    info = count_structure(tmp_path / "topology.pdb")
    assert info["valid"] is True
    assert info["n_chains"] == 1
    assert info["protein_residues"] == 4
    assert info["water_residues"] == 0
    assert info["ions"] == 0
    assert info["ligand_residues_total"] == 0


def test_count_structure_water_atom_record_not_double_counted(tmp_path: Path) -> None:
    # Many PDBs list waters as ATOM HOH. They must not appear in
    # protein_residues.
    pdb = "\n".join([
        "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N",
        "ATOM      2  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C",
        "ATOM      3  OH2 HOH B  10       5.000   5.000   5.000  1.00  0.00           O",
        "END",
    ])
    (tmp_path / "topology.pdb").write_text(pdb, encoding="utf-8")
    info = count_structure(tmp_path / "topology.pdb")
    assert info["valid"] is True
    assert info["protein_residues"] == 1
    assert info["water_residues"] == 1


def test_count_structure_detects_ligand(tmp_path: Path) -> None:
    pdb = "\n".join([
        "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N",
        "ATOM      2  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C",
        "HETATM    3  C1  EPE A 100       4.000   4.000   4.000  1.00 10.00           C",
        "HETATM    4  O1  EPE A 100       4.300   4.300   4.300  1.00 10.00           O",
        "END",
    ])
    (tmp_path / "topology.pdb").write_text(pdb, encoding="utf-8")
    info = count_structure(tmp_path / "topology.pdb")
    assert "EPE" in info["ligand_resnames"]


def test_count_structure_handles_missing(tmp_path: Path) -> None:
    info = count_structure(tmp_path / "no.pdb")
    assert info["valid"] is False


def test_count_structure_rejects_too_large_files(tmp_path: Path) -> None:
    big = tmp_path / "huge.pdb"
    big.write_text("HEADER\n", encoding="utf-8")
    big.write_bytes(b"X" * (9 * 1024 * 1024))  # > 8 MB
    info = count_structure(big)
    assert info["valid"] is False
    assert info["reason"] == "too-large"


def test_detect_ligands_basic(tmp_path: Path) -> None:
    pdb = "\n".join([
        "HETATM    1  C1  EPE A 100       4.000   4.000   4.000  1.00 10.00           C",
        "HETATM    2  C2  BEN B   1       5.000   5.000   5.000  1.00 10.00           C",
        "ATOM      3  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N",
        "END",
    ])
    (tmp_path / "topology.pdb").write_text(pdb, encoding="utf-8")
    info = count_structure(tmp_path / "topology.pdb")
    keys = [(ins["chain"], ins["resname"], ins["resi"]) for ins in info["ligand_instances"]]
    detected = detect_ligands(keys)
    assert set(detected["resnames"]) >= {"EPE"}


def test_detect_ligands_respects_explicit_override() -> None:
    keys = [("A", "NA", "1")]
    out = detect_ligands(keys, explicit=["NA"])
    assert out["resnames"] == ["NA"]
    assert out["instances"][0]["explicit"] is True


def test_detect_ligands_excludes_water_and_ions() -> None:
    keys = [("A", "HOH", "1"), ("A", "NA", "2"), ("A", "EPE", "3")]
    out = detect_ligands(keys)
    assert sorted(out["resnames"]) == ["EPE"]


def test_detect_ligands_includes_cofactors_when_requested() -> None:
    keys = [("A", "GOL", "1"), ("A", "EPE", "2")]
    default = detect_ligands(keys)
    with_cof = detect_ligands(keys, include_cofactors=True)
    assert "GOL" in with_cof["cofactors"]
    assert "GOL" not in default["resnames"]
    assert "GOL" in with_cof["resnames"]


def test_detect_ligands_lexicographic_sort(tmp_path: Path) -> None:
    # Single chain so the (chain, resname, resi) sort key collapses to
    # numeric resi ordering only.
    keys = [("A", "EPE", str(r)) for r in [10, 2, 100]]
    detected = detect_ligands(keys)
    assert [ins["resi"] for ins in detected["instances"]] == ["2", "10", "100"]


def test_ligand_atom_counts_distinguishes_ligands(tmp_path: Path) -> None:
    pdb = "\n".join([
        "HETATM    1  C1  EPE A 100       4.000   4.000   4.000  1.00 10.00           C",
        "HETATM    2  C2  EPE A 100       4.300   4.300   4.300  1.00 10.00           C",
        "HETATM    3  C1  BEN B   1       5.000   5.000   5.000  1.00 10.00           C",
        "HETATM    4  H1  HOH A   2       5.500   5.500   5.500  1.00  0.00           H",
        "END",
    ])
    (tmp_path / "topology.pdb").write_text(pdb, encoding="utf-8")
    counts = ligand_atom_counts(tmp_path / "topology.pdb")
    assert counts == {"EPE": 2, "BEN": 1}


def test_normalise_ligand_resname() -> None:
    assert normalise_ligand_resname("epe") == "EPE"
    assert normalise_ligand_resname("LIG ") == "LIG"
    assert normalise_ligand_resname("") is None
    assert normalise_ligand_resname(None) is None


def test_write_live_frame_round_trip(tmp_path: Path) -> None:
    sim = tmp_path / "simulation"
    result = write_live_frame(sim, pdb_text=_tiny_pdb(), frame_index=42)
    assert result["ok"] is True
    assert (sim / "live_frame.pdb").is_file()
    index = json.loads((sim / "live_frame_index.json").read_text(encoding="utf-8"))
    assert index["live_frame_available"] is True
    assert index["live_frame_index"] == 42


def test_write_live_frame_handles_missing_directory_safely(tmp_path: Path) -> None:
    # write_live_frame must not crash when the target "directory" is a
    # regular file. Putting a regular file at the target slot makes
    # Path.mkdir(parents=True, exist_ok=True) fail both on POSIX and
    # Windows. Cross-platform safe; the original /nonexistent/... path
    # was environment-dependent on Windows because C:\ is normally
    # writable so the parent.mkdir succeeded.
    blocked = tmp_path / "i_am_a_file"
    blocked.write_text("not a directory", encoding="utf-8")
    result = write_live_frame(blocked, pdb_text="ATOM\n", frame_index=1)
    assert result["ok"] is False


def test_playback_returns_unavailable_when_missing(tmp_path: Path) -> None:
    info = playback_info(tmp_path)
    assert info["playback_available"] is False


def test_playback_generation_failure_is_safe(tmp_path: Path, monkeypatch) -> None:
    # Force a failure inside the writer.
    import fastmdxplora.live.trajectory_playback as mod
    monkeypatch.setattr(mod, "_import_openmm", lambda: None)
    (tmp_path / "simulation").mkdir(parents=True)
    (tmp_path / "simulation" / "topology.pdb").write_text(_tiny_pdb(), encoding="utf-8")
    (tmp_path / "simulation" / "production.dcd").write_bytes(b"\x00\x00")
    info = playback_info(tmp_path)
    assert info["playback_available"] is False
    assert info["reason"] == "openmm-not-installed"


def test_neighborhood_residues_per_atom_check(tmp_path: Path) -> None:
    # Atom-wide coordinates in standard PDB column widths so the parser
    # finds the values in the right slots (cols 31-38, 39-46, 47-54).
    pdb = "\n".join([
        "HETATM    1  C1  EPE A 100       4.000   4.000   4.000  1.00 10.00           C",
        "ATOM      2  N   ALA A   1       4.500   4.500   4.500  1.00  0.00           N",  # near
        "ATOM      3  N   ALA A   2      30.000  30.000  30.000  1.00  0.00           N",  # far
        "END",
    ])
    (tmp_path / "topology.pdb").write_text(pdb, encoding="utf-8")
    residues = neighborhood_residues(topology_path=tmp_path / "topology.pdb", ligand_resname="EPE", cutoff_angstrom=5.0)
    assert ("A", 1) in residues
    assert ("A", 2) not in residues


# ---------------------------------------------------------------------------
# Endpoint contract: the redesigned dashboard's HTML/JS layer
# ---------------------------------------------------------------------------
def test_dashboard_html_uses_separated_template() -> None:
    """The HTML shell lives on disk next to the module rather than as a giant f-string."""
    template_path = Path(make_handler.__module__.split(".")[0])
    import fastmdxplora.live as live_pkg
    layout = Path(live_pkg.__file__).with_name("templates") / "dashboard.html"
    assert layout.is_file()


def test_dashboard_html_has_aai_branding(tmp_path: Path) -> None:
    run = tmp_path / "run"
    writer = TelemetryWriter(run / "simulation")
    writer.write_status(stage="NVT")
    server, base_url = start_test_server(run)
    try:
        html = urlopen(f"{base_url}/", timeout=5).read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()

    # Branding hierarchy
    assert "AAI Research Lab" in html or "aai-research-logo" in html
    assert "FastMDXplora" in html
    assert "Fully Automated SysTem for Molecular Dynamics eXploration" in html

    # Sidebar / top bar / nav structure
    assert "sidebar" in html
    assert "top-bar" in html
    assert "data-view-link" in html

    # Asset wiring
    assert "/static/dashboard.css" in html
    assert "/static/dashboard.js" in html
    assert "/static/charts.js" in html
    assert "/static/molecule-viewer.js" in html
    assert "/static/3Dmol-min.js" in html
    assert "/static/aai-research-logo.svg" in html or "/static/aai-research-mark.svg" in html

    # Pages
    for page in ("overview", "live", "viewer", "analysis", "files", "settings"):
        assert f'data-page="{page}"' in html

    # Loading screen + branded particles
    assert "loading-screen" in html

    # No CDN references
    assert "cdn" not in html.lower()
    assert "googleapis" not in html.lower()
    # The documentation + GitHub sidebar links are the only legitimate
    # external refs, both harmless but explicit.
    for allowed in (
        "https://fastmdxplora.readthedocs.io",
        "https://github.com/aai-research-lab/FastMDXplora",
    ):
        assert allowed in html
    assert html.count("https://") == 2


def test_dashboard_css_uses_black_scientific_palette() -> None:
    css_path = Path(make_handler.__module__.split(".")[0])
    import fastmdxplora.live as live_pkg
    css = (Path(live_pkg.__file__).with_name("static") / "dashboard.css").read_text(encoding="utf-8")
    for token in ("--background-primary", "--accent-cyan", "--accent-violet",
                  "--text-primary", "prefers-reduced-motion", "Inter"):
        assert token in css


def test_dashboard_endpoint_no_inline_html_css() -> None:
    """The server.py module no longer contains the giant HTML f-string.

    We assert the absence of known-fingerprinted fragments from the old
    inline template — a tautology-free check.
    """
    server_path = Path(make_handler.__module__.split(".")[0])
    import fastmdxplora.live as live_pkg
    src = (Path(live_pkg.__file__).with_name("server.py")).read_text(encoding="utf-8")
    for marker in (
        'onclick="setProteinPreviewExpanded',
        'spectrum count, rainbow, prot, byres=1',
        'function setProteinPreviewExpanded(expanded)',
    ):
        assert marker not in src, f"legacy inline marker found: {marker!r}"


def test_dashboard_server_serves_new_routes(tmp_path: Path) -> None:
    run = tmp_path / "run"
    sim = run / "simulation"
    sim.mkdir(parents=True)
    (sim / "topology.pdb").write_text(_tiny_pdb(), encoding="utf-8")
    write_live_frame(sim, pdb_text=_tiny_pdb(), frame_index=10)

    server, base_url = start_test_server(run)
    try:
        for path in (
            "/api/status",
            "/api/metrics",
            "/api/events",
            "/api/artifacts",
            "/api/files",          # alias
            "/api/results",
            "/api/analyses",       # alias
            "/api/protein-preview",
            "/api/structure-info",
            "/api/ligands",
            "/api/live-frame-index",
            "/api/live-coordinates",
            "/api/playback-info",
            "/structure/topology.pdb",
            "/structure/live-frame.pdb",
        ):
            response = urlopen(f"{base_url}{path}", timeout=5)
            response.read()
            assert response.headers["Cache-Control"] == "no-store", path
    finally:
        server.shutdown()
        server.server_close()


def test_structure_info_endpoint_payload_keys(tmp_path: Path) -> None:
    run = tmp_path / "run"
    sim = run / "simulation"
    sim.mkdir(parents=True)
    (sim / "topology.pdb").write_text(_tiny_pdb(), encoding="utf-8")
    server, base_url = start_test_server(run, config=DashboardConfig(ligand_resname="LIG"))
    try:
        payload = json.loads(urlopen(f"{base_url}/api/structure-info", timeout=5).read())
    finally:
        server.shutdown()
        server.server_close()
    assert payload["valid"] is True
    assert payload["n_chains"] == 1
    assert payload["protein_residues"] == 4
    assert payload["explicit_ligand"] == "LIG"


def test_live_frame_endpoint_serves_pdb(tmp_path: Path) -> None:
    run = tmp_path / "run"
    sim = run / "simulation"
    sim.mkdir(parents=True)
    write_live_frame(sim, pdb_text=_tiny_pdb(), frame_index=5)
    server, base_url = start_test_server(run)
    try:
        body = urlopen(f"{base_url}/structure/live-frame.pdb", timeout=5).read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
    assert "ATOM" in body and "ALA" in body


def test_live_frame_endpoint_404_when_missing(tmp_path: Path) -> None:
    run = tmp_path / "run"
    sim = run / "simulation"
    sim.mkdir(parents=True)
    server, base_url = start_test_server(run)
    try:
        try:
            urlopen(f"{base_url}/structure/live-frame.pdb", timeout=5)
        except HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("expected 404 on missing live frame")
    finally:
        server.shutdown()
        server.server_close()


def test_playback_info_unavailable_when_no_trajectory(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    server, base_url = start_test_server(run)
    try:
        payload = json.loads(urlopen(f"{base_url}/api/playback-info", timeout=5).read())
    finally:
        server.shutdown()
        server.server_close()
    assert payload["playback_available"] is False


def test_artifacts_response_includes_files(tmp_path: Path) -> None:
    run = tmp_path / "run"
    sim = run / "simulation"
    sim.mkdir(parents=True)
    (sim / "live_status.json").write_text("{}", encoding="utf-8")
    server, base_url = start_test_server(run)
    try:
        payload = json.loads(urlopen(f"{base_url}/api/files", timeout=5).read())
    finally:
        server.shutdown()
        server.server_close()
    assert any(record["path"].endswith("live_status.json") for record in payload["artifacts"])


def test_results_response_keys_match_dashboard_bindings(tmp_path: Path) -> None:
    run = tmp_path / "run"
    sim = run / "simulation"
    sim.mkdir(parents=True)
    (sim / "live_status.json").write_text("{}", encoding="utf-8")
    server, base_url = start_test_server(run)
    try:
        payload = json.loads(urlopen(f"{base_url}/api/results", timeout=5).read())
    finally:
        server.shutdown()
        server.server_close()
    for key in ("refreshed_at", "has_analysis", "has_report", "summary", "system", "phases", "plots", "key_plots", "reports", "artifacts"):
        assert key in payload


def test_dashboard_session_uses_next_port_when_busy(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen()
    requested_port = blocker.getsockname()[1]
    session = start_dashboard_session(output=run, host="127.0.0.1", port=requested_port, max_port_tries=5)
    try:
        assert session.requested_port == requested_port
        assert session.port != requested_port
        assert session.port_was_changed is True
    finally:
        session.stop()
        blocker.close()


def test_dashboard_session_stop_is_safe(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    session = start_dashboard_session(output=run, port=0)
    assert session.thread.is_alive()
    session.stop()
    assert not session.thread.is_alive()


def test_live_server_rejects_artifact_path_traversal(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    server, base_url = start_test_server(run)
    try:
        try:
            urlopen(f"{base_url}/artifacts/../outside.txt", timeout=5)
        except HTTPError as exc:
            assert exc.code in {403, 404}
        else:
            raise AssertionError("path traversal unexpectedly succeeded")
    finally:
        server.shutdown()
        server.server_close()


def test_live_server_does_not_serve_static_path_traversal(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    server, base_url = start_test_server(run)
    try:
        try:
            urlopen(f"{base_url}/static/../server.py", timeout=5)
        except HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("static traversal unexpectedly succeeded")
    finally:
        server.shutdown()
        server.server_close()


def test_static_3dmol_asset_is_served_locally(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    server, base_url = start_test_server(run)
    try:
        response = urlopen(f"{base_url}/static/3Dmol-min.js", timeout=5)
        body = response.read().decode("utf-8", errors="ignore")
    finally:
        server.shutdown()
        server.server_close()
    assert response.headers["Cache-Control"] == "no-store"
    assert "$3Dmol" in body
    assert "http://" not in body[:1000]
    assert "https://" not in body[:1000]


def test_live_json_endpoints_are_no_store(tmp_path: Path) -> None:
    run = tmp_path / "run"
    writer = TelemetryWriter(run / "simulation")
    writer.write_status(stage="production")
    server, base_url = start_test_server(run)
    try:
        for endpoint in (
            "status", "metrics", "events", "artifacts", "results", "files",
            "protein-preview", "structure-info", "ligands",
            "live-frame-index", "live-coordinates", "playback-info",
            "analyses",
        ):
            response = urlopen(f"{base_url}/api/{endpoint}", timeout=5)
            response.read()
            assert response.headers["Cache-Control"] == "no-store", endpoint
    finally:
        server.shutdown()
        server.server_close()


def test_live_json_endpoints_are_sane_for_empty_run(tmp_path: Path) -> None:
    run = tmp_path / "empty_run"
    server, base_url = start_test_server(run)
    try:
        status_payload = json.loads(urlopen(f"{base_url}/api/status", timeout=5).read())
        metrics_payload = json.loads(urlopen(f"{base_url}/api/metrics", timeout=5).read())
        events_payload = json.loads(urlopen(f"{base_url}/api/events", timeout=5).read())
        artifacts_payload = json.loads(urlopen(f"{base_url}/api/artifacts", timeout=5).read())
        results_payload = json.loads(urlopen(f"{base_url}/api/results", timeout=5).read())
        structure_payload = json.loads(urlopen(f"{base_url}/api/structure-info", timeout=5).read())
        ligands_payload = json.loads(urlopen(f"{base_url}/api/ligands", timeout=5).read())
    finally:
        server.shutdown()
        server.server_close()
    assert status_payload["status"] == {}
    assert status_payload["health"]["state"] == "unknown"
    assert metrics_payload["metrics"] == []
    assert events_payload["events"] == []
    assert artifacts_payload["artifacts"] == []
    assert results_payload["has_analysis"] is False
    assert results_payload["has_report"] is False
    assert results_payload["plots"] == []
    assert structure_payload["valid"] is False
    assert ligands_payload["valid"] is False


def test_aai_logo_assets_are_packaged(tmp_path: Path) -> None:
    import fastmdxplora.live as live_pkg
    static = Path(live_pkg.__file__).with_name("static")
    assert (static / "aai-research-logo.svg").is_file()
    assert (static / "aai-research-mark.svg").is_file()
    assert (static / "dashboard.css").is_file()
    assert (static / "dashboard.js").is_file()
    assert (static / "charts.js").is_file()
    assert (static / "molecule-viewer.js").is_file()


def test_static_logo_endpoint_serves_svg(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    server, base_url = start_test_server(run)
    try:
        response = urlopen(f"{base_url}/static/aai-research-logo.svg", timeout=5)
        body = response.read().decode("utf-8", errors="ignore")
    finally:
        server.shutdown()
        server.server_close()
    assert response.headers["Content-Type"].startswith("image/svg+xml") or "svg" in body.lower()
    assert "AAI" in body
