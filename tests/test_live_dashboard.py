from __future__ import annotations

import json
import socket
from pathlib import Path
from urllib.request import urlopen

from fastmdxplora.cli.main import _build_parser
from fastmdxplora.live import protein_preview
from fastmdxplora.live.protein_preview import protein_preview_payload
from fastmdxplora.live.server import start_dashboard_session, start_test_server
from fastmdxplora.live.telemetry import TelemetryWriter, analyze_health, read_events, read_metrics, read_status


def test_telemetry_writer_creates_status_metrics_and_events(tmp_path: Path) -> None:
    simulation_dir = tmp_path / "run" / "simulation"
    writer = TelemetryWriter(
        simulation_dir,
        total_steps=100,
        planned_frames=10,
        timestep_fs=2.0,
        platform="CPU",
        target_temperature_K=300.0,
    )

    writer.write_status(stage="production", status="running", current_step=25)
    writer.append_metric(
        stage="production",
        step=25,
        simulation_time_ns=0.00005,
        potential_energy=-123.4,
        total_energy=-100.0,
        temperature=299.0,
        progress_percent=25.0,
    )
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

    spike_health = analyze_health(
        status,
        [
            {"stage": "production", "total_energy": "-100.0"},
            {"stage": "production", "total_energy": "50000.0"},
        ],
    )
    assert spike_health["state"] == "warning"
    assert "Energy increased sharply" in spike_health["explanation"]


def test_dashboard_server_serves_status_metrics_and_shell(tmp_path: Path) -> None:
    run = tmp_path / "run"
    writer = TelemetryWriter(run / "simulation", total_steps=10)
    writer.write_status(stage="NVT", status="running", current_step=3)
    writer.append_metric(stage="NVT", step=3, total_energy=-10.0)
    (run / "report").mkdir(parents=True)
    (run / "report" / "dashboard.html").write_text("<html>static</html>", encoding="utf-8")

    server, base_url = start_test_server(run)
    try:
        status_payload = json.loads(urlopen(f"{base_url}/api/status", timeout=5).read())
        metrics_payload = json.loads(urlopen(f"{base_url}/api/metrics", timeout=5).read())
        html = urlopen(f"{base_url}/", timeout=5).read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()

    assert status_payload["status"]["stage"] == "NVT"
    assert metrics_payload["metrics"][-1]["total_energy"] == "-10.0"
    assert "Live Simulation" in html
    assert "Dashboard" in html
    assert "Analysis Plots" in html
    assert "Generated Files" in html
    assert "System Info" in html
    assert "Run Status" in html
    assert "/api/status" in html
    assert "/api/results" in html
    assert "/api/protein-preview" in html
    assert "/static/3Dmol-min.js" in html
    assert "structure_url" in html
    assert "live-grid" in html
    assert "live-main-column" in html
    assert "live-bottom-grid" in html
    assert "protein-preview-card" in html
    assert "max-height:520px" in html
    assert "protein-preview-frame" in html
    assert "height:340px" in html
    assert "max-height:340px" in html
    assert "protein-preview-frame img" in html
    assert "object-fit:contain" in html
    assert "#protein-viewer, #protein-3dmol-viewer" in html
    assert "viewer-3dmol" in html
    assert "protein-3dmol-viewer" in html
    assert "$3Dmol.createViewer" in html
    assert "backgroundColor:\"#08111f\"" in html
    assert "addModel(proteinViewer3DmolPdb, \"pdb\")" in html
    assert 'setStyle({}, {cartoon: {color:"spectrum"}})' in html
    assert "proteinViewer3Dmol.spin(active)" in html
    assert "proteinViewer3Dmol.zoomTo()" in html
    assert "PyMOL Preview" in html
    assert "Interactive 3D" in html
    assert "Spin" in html
    assert "Reset view" in html
    assert 'id="protein-expand"' in html
    assert 'id="protein-collapse"' in html
    assert 'onclick="setProteinPreviewExpanded(true)"' in html
    assert 'onclick="setProteinPreviewExpanded(false)"' in html
    assert "protein-preview-card expanded" not in html
    assert "protein-preview-full" not in html
    assert html.index('id="stage"') < html.index("<h2>Protein Preview</h2>")
    assert html.index('id="progress-fill"') < html.index("<h2>Protein Preview</h2>")
    assert html.index('id="metrics-chart"') < html.index("<h2>Protein Preview</h2>")
    assert "viewer-canvas" in html
    assert "parsePdbTrace" in html
    assert "load3DmolViewer" in html
    assert "loadSchematicViewer" in html
    assert "schematic fallback" in html
    assert "PyMOL render" in html
    assert "Interactive 3Dmol cartoon viewer" in html
    assert 'id="protein-view-static">PyMOL Preview' in html
    assert 'id="protein-view-3d">Interactive 3D' in html
    assert '<div class="protein-view" id="protein-viewer-wrap">' in html
    assert '<div class="protein-view hidden" id="protein-fallback-wrap">' in html
    assert '<div class="protein-view hidden" id="protein-static-wrap">' in html
    assert "regenerate-preview" in html
    assert "setProteinPreviewExpanded" in html
    assert "https://" not in html
    assert "cdn" not in html.lower()
    assert "plot-footer" in html
    assert "plot-title" in html
    assert "artifact-path" in html
    assert "display_path" in html
    assert "-webkit-line-clamp:2" in html
    assert "overflow-wrap:anywhere" in html
    assert "size-button" in html
    assert "refresh-results" in html
    assert "Last refreshed" in html
    assert "Analysis outputs not available yet" in html
    assert "Quick Actions" in html
    assert "Phase Summary" in html
    assert "Live Status Summary" in html
    assert "Results Dashboard" not in html
    assert "Key Plots" not in html
    assert "dashboard-key-plots" not in html
    assert "<iframe" not in html
    assert "static-dashboard-frame" not in html


def test_artifacts_and_results_rescan_after_server_start(tmp_path: Path) -> None:
    run = tmp_path / "run"
    (run / "simulation").mkdir(parents=True)
    (run / "simulation" / "live_status.json").write_text("{}", encoding="utf-8")

    server, base_url = start_test_server(run)
    try:
        initial = json.loads(urlopen(f"{base_url}/api/results", timeout=5).read())
        assert initial["has_analysis"] is False
        assert initial["has_report"] is False

        (run / "analysis" / "rmsd").mkdir(parents=True)
        (run / "analysis" / "rmsd" / "rmsd.png").write_bytes(b"png")
        (run / "analysis" / "sasa").mkdir(parents=True)
        (run / "analysis" / "sasa" / "sasa.png").write_bytes(b"png")
        (run / "report" / "dashboard_assets").mkdir(parents=True)
        (run / "report" / "dashboard_assets" / "cluster_hierarchical_dendrogram_dashboard.png").write_bytes(b"png")
        (run / "report" / "report.md").write_text("# Report", encoding="utf-8")
        (run / "report" / "dashboard.html").write_text("<html>new</html>", encoding="utf-8")

        artifacts_response = urlopen(f"{base_url}/api/artifacts", timeout=5)
        artifacts_payload = json.loads(artifacts_response.read())
        results_payload = json.loads(urlopen(f"{base_url}/api/results", timeout=5).read())
    finally:
        server.shutdown()
        server.server_close()

    assert artifacts_response.headers["Cache-Control"] == "no-store"
    artifact_paths = {record["path"] for record in artifacts_payload["artifacts"]}
    assert "analysis/rmsd/rmsd.png" in artifact_paths
    assert "report/report.md" in artifact_paths
    report_record = next(record for record in artifacts_payload["artifacts"] if record["path"] == "report/dashboard.html")
    assert report_record["display_path"] == "report/dashboard.html"
    assert results_payload["has_analysis"] is True
    assert results_payload["has_report"] is True
    titles = {plot["title"] for plot in results_payload["plots"]}
    assert "RMSD" in titles
    assert "Hierarchical dendrogram" in titles
    assert "cluster_hierarchical_dendrogram_dashboard.png" not in titles
    categories = {plot["category"] for plot in results_payload["plots"]}
    assert "Core Metrics" in categories
    assert "Additional Analysis" in categories
    assert "Clustering" in categories
    rmsd_plot = next(plot for plot in results_payload["plots"] if plot["title"] == "RMSD")
    assert rmsd_plot["href"].endswith(f"?v={int((run / 'analysis' / 'rmsd' / 'rmsd.png').stat().st_mtime)}")
    assert rmsd_plot["display_path"] == ".../rmsd/rmsd.png"
    dendrogram = next(plot for plot in results_payload["plots"] if plot["title"] == "Hierarchical dendrogram")
    assert dendrogram["mode"] == "dashboard view"
    assert dendrogram["display_path"] == ".../dashboard_assets/cluster_hierarchical_dendrogram_dashboard.png"
    assert results_payload["dashboard"]["path"] == "report/dashboard.html"
    assert any(record["path"] == "report/dashboard.html" for record in results_payload["reports"])


def test_live_json_endpoints_are_no_store(tmp_path: Path) -> None:
    run = tmp_path / "run"
    writer = TelemetryWriter(run / "simulation")
    writer.write_status(stage="production")

    server, base_url = start_test_server(run)
    try:
        for endpoint in ("status", "metrics", "events", "artifacts", "results", "protein-preview"):
            response = urlopen(f"{base_url}/api/{endpoint}", timeout=5)
            response.read()
            assert response.headers["Cache-Control"] == "no-store"
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


def test_dashboard_session_uses_next_port_when_requested_port_is_busy(
    tmp_path: Path,
) -> None:
    run = tmp_path / "run"
    run.mkdir()
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen()
    requested_port = blocker.getsockname()[1]

    session = start_dashboard_session(
        output=run,
        host="127.0.0.1",
        port=requested_port,
        max_port_tries=5,
    )
    try:
        assert session.requested_port == requested_port
        assert session.port != requested_port
        assert session.port_was_changed is True
        assert session.url == f"http://127.0.0.1:{session.port}"
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


def test_protein_preview_unavailable_without_structure(tmp_path: Path) -> None:
    payload = protein_preview_payload(tmp_path / "run")

    assert payload["available"] is False
    assert payload["message"] == "No topology/PDB found yet."


def test_protein_preview_requires_pymol_when_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("fastmdxplora.live.protein_preview._find_pymol_executable", lambda _root: None)
    run = tmp_path / "run"
    topology = run / "simulation" / "topology.pdb"
    topology.parent.mkdir(parents=True)
    topology.write_text(_tiny_pdb(), encoding="utf-8")

    payload = protein_preview_payload(run)

    assert payload["available"] is True
    assert payload["static_available"] is False
    assert payload["static_mode"] is None
    assert payload["static_image_url"] is None
    assert payload["structure_available"] is True
    assert payload["viewer_available"] is True
    assert payload["viewer_mode"] == "3dmol"
    assert payload["fallback_available"] is True
    assert payload["fallback_mode"] == "schematic"
    assert "PyMOL preview unavailable" in payload["message"]


def test_protein_preview_api_finds_topology(tmp_path: Path, monkeypatch) -> None:
    def _fake_render(_pymol, _structure, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setattr("fastmdxplora.live.protein_preview._find_pymol_executable", lambda _root: "/fake/pymol")
    monkeypatch.setattr("fastmdxplora.live.protein_preview._render_with_pymol", _fake_render)
    run = tmp_path / "run"
    topology = run / "simulation" / "topology.pdb"
    topology.parent.mkdir(parents=True)
    topology.write_text(_tiny_pdb(), encoding="utf-8")

    server, base_url = start_test_server(run)
    try:
        payload = json.loads(urlopen(f"{base_url}/api/protein-preview", timeout=5).read())
    finally:
        server.shutdown()
        server.server_close()

    assert payload["available"] is True
    assert "mode" not in payload
    assert payload["static_available"] is True
    assert payload["static_mode"] == "pymol"
    assert payload["path"] == "simulation/protein_preview.png"
    assert "?v=" in payload["href"]
    assert payload["image_url"] == payload["href"]
    assert payload["static_image_url"] == payload["href"]
    assert payload["structure_path"] == "simulation/topology.pdb"
    assert payload["structure_url"].startswith("/structure/topology.pdb?v=")
    assert payload["structure_available"] is True
    assert payload["viewer_available"] is True
    assert payload["viewer_mode"] == "3dmol"
    assert payload["fallback_available"] is True
    assert payload["fallback_mode"] == "schematic"
    assert (run / payload["path"]).read_bytes().startswith(b"\x89PNG")


def test_structure_route_serves_topology(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("fastmdxplora.live.protein_preview._find_pymol_executable", lambda _root: None)
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
    assert "ATOM" in body
    assert "ALA" in body


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
    assert "set_color fastmdx_res_4" in script
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
