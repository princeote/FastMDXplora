import logging

def test_get_runtime_versions_keys():
    from fastmdanalysis.utils.logging import get_runtime_versions
    v = get_runtime_versions()
    # minimal assertions — keys exist and are strings
    for k in ("fastmdanalysis", "python", "os", "numpy", "mdtraj", "scikit-learn", "matplotlib"):
        assert k in v
        assert isinstance(v[k], str)

def test_log_run_header_emits(caplog):
    from fastmdanalysis.utils.logging import log_run_header
    with caplog.at_level(logging.INFO, logger="fastmdanalysis"):
        log_run_header()  # no logger passed -> uses 'fastmdanalysis'
    msgs = " ".join(r.message for r in caplog.records)
    assert "FastMDAnalysis" in msgs
    assert "numpy" in msgs

def test_setup_library_logging_idempotent(tmp_path):
    from fastmdanalysis.utils.logging import setup_library_logging
    lg1 = setup_library_logging()             # stdout handler
    n1 = len(lg1.handlers)
    lg2 = setup_library_logging()             # should not duplicate handlers
    n2 = len(lg2.handlers)
    assert n1 == n2

