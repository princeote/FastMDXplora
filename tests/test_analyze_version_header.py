from pathlib import Path

def test_analyze_calls_version_header(monkeypatch, tmp_path, capsys):
    # Import the module under test
    import fastmdanalysis.analysis.analyze as az

    # Stub the log header to count invocations
    calls = {"n": 0}
    def fake_header(logger=None, **_):
        calls["n"] += 1
    monkeypatch.setattr("fastmdanalysis.analysis.analyze._log_run_header", fake_header, raising=True)

    # Fake "self" with one analysis method that creates an outdir
    class FakeSelf:
        traj = type("T", (), {"n_frames": 100})()  # just to let cluster defaults compute if needed
        def rmsd(self, **kwargs):
            class Result:
                outdir = tmp_path / "rmsd"
            Path(Result.outdir).mkdir(parents=True, exist_ok=True)
            return Result()

    # Run the orchestrator
    res = az.run(FakeSelf(), include=["rmsd"], verbose=True, slides=False, output=tmp_path / "out")

    # Header should be emitted exactly once per run
    assert calls["n"] == 1
    assert "rmsd" in res and res["rmsd"].ok

    # Summary prints to stdout
    out = capsys.readouterr().out
    assert "Summary:" in out
    assert "Output collected in:" in out

