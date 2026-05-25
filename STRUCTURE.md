# Repository structure

```
FastMDXplora/
├── src/
│   └── fastmdxplora/
│       ├── __init__.py            # Top-level exports + metadata
│       ├── _version.py            # Written by setuptools-scm
│       ├── orchestrator.py        # FastMDXplora project-level orchestrator
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py            # `fastmdx` entry point (explore/xplore/setup/simulate/analyze/report/info)
│       ├── setup/
│       │   ├── __init__.py
│       │   └── pipeline.py        # System preparation: fix, protonate, solvate, ionize
│       ├── simulation/
│       │   ├── __init__.py
│       │   └── pipeline.py        # MD simulation: minimize, NVT, NPT, production
│       ├── analysis/
│       │   ├── __init__.py
│       │   └── analyze.py         # Analysis-level orchestrator (RMSD, RMSF, Rg, …)
│       ├── report/
│       │   ├── __init__.py
│       │   ├── run.py             # Top-level report() entry point
│       │   ├── document.py        # Structured Markdown report
│       │   ├── slides.py          # .pptx slide deck (with markdown fallback)
│       │   └── bundle.py          # Self-contained .zip project archive
│       ├── datasets/
│       │   ├── __init__.py
│       │   └── trp_cage.py        # Reference dataset stub (from FastMDAnalysis)
│       └── utils/
│           └── __init__.py
├── shim-package/                  # `fastmdx` alias on PyPI
│   ├── pyproject.toml
│   ├── README.md
│   └── src/fastmdx/__init__.py
├── tests/
│   ├── test_imports.py
│   ├── test_orchestrator.py
│   └── test_cli.py
├── recipes/                       # conda-forge submission packages
│   ├── fastmdxplora/meta.yaml
│   └── fastmdx-alias/meta.yaml
├── .github/workflows/
│   ├── tests.yml                  # CI: matrix tests + CLI smoke test
│   └── publish.yml                # PyPI trusted publishing on `v*` tag
├── docs/
├── examples/
├── scripts/
├── assets/
├── pyproject.toml                 # Primary package config
├── README.md
├── LICENSE
├── CITATION.cff
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── STRUCTURE.md                   # (this file)
└── .gitignore
```

## Architectural overview

FastMDXplora is a **project-level orchestrator**. The central class
`FastMDXplora` holds shared state (system input, output directory,
per-phase options) and coordinates the four canonical phases:

```
  setup → simulation → analysis → report
```

This continues the orchestrator pattern of **FastMDAnalysis** (Aina & Kwan,
JCC 2026), which orchestrates analysis modules within a trajectory.
FastMDXplora applies the same pattern one level up the hierarchy.

### Key design principles

1. **Self-contained.** FastMDXplora has no runtime dependency on
   external MD-analysis or simulation packages. Each phase is implemented
   directly under `fastmdxplora.<phase>`.

2. **Intent over DAG.** Users express intent (`include=["setup", "analysis"]`,
   `exclude=["report"]`, per-phase option overrides). The workflow is
   built-in — this is not a general-purpose workflow engine.

3. **Structured I/O at every phase.** Every phase writes a JSON parameters
   manifest plus its canonical artifacts. The orchestrator writes a
   top-level `manifest.json` recording the session.

4. **Lazy phase imports.** Each phase is imported only when invoked, so
   optional heavy dependencies (OpenMM, PDBFixer) do not impose a cost on
   users who only use a subset of phases.

5. **Continue FastMDAnalysis conventions.** The analysis subpackage uses the
   same module taxonomy (`rmsd`, `rmsf`, `rg`, `hbonds`, `ss`, `cluster`,
   `sasa`, `dimred`, `qvalue`, `dihedrals`) established in FastMDAnalysis,
   now extended with protein-ligand analyses — FastMDXplora being the
   direct successor to that package.

### Naming alignment

| Surface | Name |
|---|---|
| Project / brand | FastMDXplora |
| PyPI primary | `fastmdxplora` |
| PyPI alias | `fastmdx` (depends on `fastmdxplora`) |
| Python import | `fastmdxplora` (commonly aliased: `import fastmdxplora as fastmdx`) |
| CLI command | `fastmdx` |
| GitHub repo | `aai-research-lab/FastMDXplora` |
| DOI | 10.1002/jcc.70350 (foundational JCC paper) |
