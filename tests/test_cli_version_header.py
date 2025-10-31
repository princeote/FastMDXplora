import sys
import importlib
from types import SimpleNamespace

def test_cli_calls_version_header(monkeypatch, tmp_path):
    # Import the submodule explicitly (avoid shadowing by fastmdanalysis.cli.__init__)
    cli_main = importlib.import_module("fastmdanalysis.cli.main")

    # 1) Stub subcommand registration: minimal 'noop' that accepts the same I/O flags
    def register_fake(subparsers, common):
        p = subparsers.add_parser("noop", parents=[common])
        p.add_argument("--trajectory", nargs="+", required=True)   # <-- add
        p.add_argument("--topology", required=True)                # <-- add
        p.add_argument("--output", default=str(tmp_path / "noop_output"))
        p.set_defaults(_handler=lambda args, fastmda, logger: None)
    monkeypatch.setattr(cli_main.analyze_cmd, "register", register_fake, raising=True)
    monkeypatch.setattr(cli_main.simple_cmd, "register_simple", lambda s, c: None, raising=True)

    # 2) Stub helpers used by main()
    class DummyLogger:
        def __init__(self): self.messages = []
        def info(self, msg, *a): self.messages.append(("INFO", msg % a if a else msg))
        def error(self, msg, *a): self.messages.append(("ERROR", msg % a if a else msg))
    dummy_logger = DummyLogger()
    monkeypatch.setattr(cli_main, "setup_logging", lambda *a, **k: dummy_logger, raising=False)
    monkeypatch.setattr(cli_main, "expand_trajectory_args", lambda x: ["traj.dcd"], raising=False)
    monkeypatch.setattr(cli_main, "normalize_topology_arg", lambda x: "top.pdb", raising=False)
    monkeypatch.setattr(cli_main, "build_instance", lambda *a, **k: SimpleNamespace(), raising=False)

    # 3) Spy on log_run_header
    called = {"n": 0}
    def fake_log_run_header(logger):
        called["n"] += 1
    monkeypatch.setattr(cli_main, "log_run_header", fake_log_run_header, raising=True)

    # 4) Provide argv and run
    argv = ["prog", "noop", "--trajectory", "traj.dcd", "--topology", "top.pdb", "--output", str(tmp_path)]
    monkeypatch.setattr(sys, "argv", argv)
    cli_main.main()  # should not raise

    # 5) Assert header was called exactly once
    assert called["n"] == 1

