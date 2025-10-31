# tests/test_utils_logging_coverage.py
import logging
import importlib
import types

def test_log_run_header_with_explicit_logger_and_extras(caplog, tmp_path):
    """Covers: explicit logger path, extras branch, libs list extension."""
    from fastmdanalysis.utils import logging as fma_log

    lg = logging.getLogger("fastmdanalysis")  # same name used by module
    # Ensure a visible handler for caplog capture
    if not lg.handlers:
        handler = logging.StreamHandler()
        lg.addHandler(handler)
        lg.setLevel(logging.INFO)

    with caplog.at_level(logging.INFO, logger="fastmdanalysis"):
        versions = fma_log.log_run_header(logger=lg, extras={"pandas": "pandas", "nonexist": "no_such_mod"})

    # Basic assertions
    msgs = " | ".join(r.message for r in caplog.records)
    assert "FastMDAnalysis" in msgs
    assert "numpy" in msgs
    # Extras included in second line
    assert "pandas" in msgs
    # 'nonexist' should be present with "n/a" value in the collected map
    assert versions.get("nonexist") in {"n/a", "unknown"}

def test_get_runtime_versions_extras_missing_module(monkeypatch):
    """Covers: _safe_import_version exception -> 'n/a'."""
    from fastmdanalysis.utils.logging import get_runtime_versions
    v = get_runtime_versions(extras={"ghost": "this_module_does_not_exist"})
    assert v["ghost"] == "n/a"

def test_setup_library_logging_stream_and_file(tmp_path, monkeypatch):
    """Covers: stream handler path (no logfile) and file handler path (with logfile)."""
    from fastmdanalysis.utils.logging import setup_library_logging

    # Stream path
    lg = setup_library_logging()
    n_handlers_before = len(lg.handlers)
    # Idempotent: calling again shouldn't add handlers
    lg2 = setup_library_logging()
    assert lg is lg2
    assert len(lg2.handlers) == n_handlers_before

    # File path
    logf = tmp_path / "fma.log"
    lg_file = setup_library_logging(logfile=str(logf))
    # At least one handler exists; one of them should be a FileHandler when logfile is set
    assert any(isinstance(h, logging.FileHandler) for h in lg_file.handlers)
    lg_file.info("hello-file")
    # Flush and check file got content
    for h in lg_file.handlers:
        try:
            h.flush()
        except Exception:
            pass
    assert logf.read_text() != ""

def test_fastmdanalysis_version_fallback_to_importlib_and_unknown(monkeypatch):
    """
    Covers: _fastmdanalysis_version path when fastmdanalysis.__version__ is missing
    and importlib.metadata.version raises PackageNotFoundError -> 'unknown'.
    """
    import fastmdanalysis
    from fastmdanalysis.utils import logging as fma_log

    # Remove __version__ attribute temporarily
    monkeypatch.delattr(fastmdanalysis, "__version__", raising=False)

    # Monkeypatch importlib.metadata.version to raise PackageNotFoundError
    import importlib.metadata as im
    def raise_pnf(_):
        raise im.PackageNotFoundError
    monkeypatch.setattr(im, "version", raise_pnf, raising=True)

    # Now call the function that resolves versions
    v = fma_log.get_runtime_versions()
    assert v["fastmdanalysis"] in {"unknown", "0+unknown"}  # depending on packaging
    assert isinstance(v["python"], str)

def test_log_run_header_custom_level_and_default_logger(caplog, monkeypatch):
    """Covers: default logger path (logger=None) and custom level argument."""
    from fastmdanalysis.utils.logging import log_run_header, setup_library_logging

    # Attach a handler so default logger emits
    setup_library_logging(level=logging.WARNING)

    with caplog.at_level(logging.WARNING, logger="fastmdanalysis"):
        log_run_header(level=logging.WARNING)  # use default logger at WARNING
    msgs = " ".join(r.message for r in caplog.records)
    assert "FastMDAnalysis" in msgs


# tests/test_utils_logging_coverage.py (replace the test with this version)
def test_setup_library_logging_stream_then_file(tmp_path, monkeypatch):
    import logging
    from fastmdanalysis.utils.logging import setup_library_logging

    # --- Reset global logger to a clean state (avoid cross-test contamination)
    root = logging.getLogger("fastmdanalysis")
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    # First: stream handler
    lg = setup_library_logging()
    assert any(isinstance(h, logging.StreamHandler) for h in lg.handlers)
    assert not any(isinstance(h, logging.FileHandler) for h in lg.handlers)

    # Then: add file handler via upgrade path
    logf = tmp_path / "fma.log"
    lg2 = setup_library_logging(logfile=str(logf))
    assert lg is lg2  # same logger object
    assert any(isinstance(h, logging.FileHandler) for h in lg.handlers)

    lg.info("hello")
    for h in lg.handlers:
        try:
            h.flush()
        except Exception:
            pass
    assert logf.read_text() != ""


# tests/test_utils_logging_coverage.py (replace the backport test with this version)
def test_fastmdanalysis_version_backport_branch(monkeypatch):
    import builtins, sys, types
    import fastmdanalysis
    from fastmdanalysis.utils.logging import get_runtime_versions

    # Remove package __version__ so resolver tries importlib
    monkeypatch.delattr(fastmdanalysis, "__version__", raising=False)

    # Make importing 'importlib.metadata' fail inside the resolver
    real_import = builtins.__import__
    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "importlib.metadata" or (name == "importlib" and "metadata" in (fromlist or ())):
            raise ImportError("block importlib.metadata")
        return real_import(name, globals, locals, fromlist, level)
    monkeypatch.setattr(builtins, "__import__", fake_import)

    # Provide a fake importlib_metadata backport
    mod = types.ModuleType("importlib_metadata")
    class PNF(Exception): pass
    mod.PackageNotFoundError = PNF
    mod.version = lambda dist: "0.0-test"
    sys.modules["importlib_metadata"] = mod

    v = get_runtime_versions()
    # We should have used the backport and gotten the fake version
    assert v["fastmdanalysis"] == "0.0-test"

