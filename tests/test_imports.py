"""Smoke tests: package imports cleanly and exposes the documented metadata."""

from __future__ import annotations


def test_top_level_imports() -> None:
    import fastmdxplora

    assert hasattr(fastmdxplora, "FastMDXplora")
    assert hasattr(fastmdxplora, "__version__")
    assert hasattr(fastmdxplora, "__author__")
    assert hasattr(fastmdxplora, "__license__")
    assert hasattr(fastmdxplora, "__expansion__")
    assert hasattr(fastmdxplora, "__citation__")
    assert hasattr(fastmdxplora, "__doi__")


def test_expansion_string() -> None:
    import fastmdxplora

    assert (
        fastmdxplora.__expansion__
        == "Fully Automated SysTem for Molecular Dynamics eXploration"
    )


def test_citation_string() -> None:
    import fastmdxplora

    assert "10.1002/jcc.70350" in fastmdxplora.__citation__
    assert "Aina" in fastmdxplora.__citation__


def test_doi() -> None:
    import fastmdxplora

    assert fastmdxplora.__doi__ == "10.1002/jcc.70350"


def test_subpackages_importable() -> None:
    import fastmdxplora.analysis  # noqa: F401
    import fastmdxplora.report  # noqa: F401
    import fastmdxplora.setup  # noqa: F401
    import fastmdxplora.simulation  # noqa: F401


def test_alias_pattern_works() -> None:
    """Users may write `import fastmdxplora as fastmdx`."""
    import fastmdxplora as fastmdx

    assert fastmdx.FastMDXplora is not None


def test_datasets_helper() -> None:
    from fastmdxplora.datasets import TrpCage

    assert TrpCage.pdb_id == "1L2Y"
    assert TrpCage.n_residues == 20
