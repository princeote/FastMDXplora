import logging

def test_version_and_null_handler():
    import fastmdanalysis as fma
    assert isinstance(fma.__version__, str)
    assert len(fma.__version__) > 0
    lg = logging.getLogger("fastmdanalysis")
    # Library should be quiet by default
    assert any(isinstance(h, logging.NullHandler) for h in lg.handlers)

