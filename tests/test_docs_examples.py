"""Lightweight checks for documented command examples.

These tests keep README/docs snippets from drifting away from the CLI surface.
They intentionally parse commands rather than executing MD-heavy workflows.
"""

from __future__ import annotations

import shlex

import pytest

from fastmdxplora.cli.main import _build_parser
from fastmdxplora.config import validate_config
from scripts.run_pdb_smoke_campaign import build_parser as build_campaign_parser


@pytest.mark.parametrize(
    "command",
    [
        "explore --system protein.pdb --dry-run",
        "xplore -s 1L2Y --dry-run",
        (
            "explore -s protein.pdb --setup-ph 7.4 "
            "--simulate-duration-ns 100 --simulate-platform CUDA --dry-run"
        ),
        (
            "explore -s protein.pdb --include setup simulation "
            "--simulate-preset gentle --simulate-platform CPU --dry-run"
        ),
        "setup --system protein.pdb --ph 6.5 --box-shape octahedron",
        (
            "simulate --system protein.pdb --output ./trpcage_study "
            "--duration-ns 50.0 --platform CUDA"
        ),
        "analyze --output ./trpcage_study --analyses rmsd rg --selection 'name CA'",
        "report --output ./trpcage_study --no-slides",
        "init-config --minimal -o study.yml",
        "info",
    ],
)
def test_documented_fastmdx_commands_parse(command: str) -> None:
    parser = _build_parser()
    parser.parse_args(shlex.split(command))


def test_documented_campaign_command_parses() -> None:
    parser = build_campaign_parser()
    args = parser.parse_args(
        shlex.split(
            "--input-list examples/pdb_list.txt "
            "--output-root runs/pdb_smoke_starter "
            "--preset gentle --continue-on-error"
        )
    )

    assert args.preset == "gentle"
    assert args.continue_on_error is True


def test_documented_configuration_shape_validates() -> None:
    validate_config(
        {
            "systems": [{"id": "trpcage", "system": "1L2Y"}],
            "setup": {"ph": 7.0, "forcefield": "charmm36"},
            "simulation": {"preset": "gentle", "duration_ns": 10},
            "analysis": {"scope": "solute", "include": ["rmsd", "rmsf", "rg"]},
            "report": {"title": "My study", "slides": True, "comparison": True},
        },
        require_systems=True,
    )
