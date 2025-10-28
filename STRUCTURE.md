# FastMDAnalysis Package Structure

This document describes how the repository is organized and where to find things.  
For a compact view of the current layout, see the **[directory tree](./tree.txt)**.

---

## Top-level layout

- **`src/fastmdanalysis/`** – The Python package source (src-layout). This is the importable code that ships on PyPI. 
- **`tests/`** – Unit tests (pytest). 
- **`docs/`** – Sphinx/RTD documentation sources; configured by `.readthedocs.yaml`. 
- **`.github/workflows/`** – Continuous Integration (CI) configs. 
- **`examples/`** – Example scripts demonstrating API/CLI usage. 
- **`assets/`** – Project artwork assets. 
- **`pyproject.toml`** – Build/packaging configuration (PEP 517/518). 
- Other project files: `README.md`, `CONTRIBUTING.md`, `LICENSE`, `requirements.txt`, `coverage.xml`, `tree.txt`. 

> **Note.** Installation exposes a `fastmda` command-line entry point (documented in the README). 
---

## `src/fastmdanalysis/`: the Python package

This directory contains the public API, analysis implementations, CLI, and utilities.

### Package root

- **`__init__.py`**  
  Defines the public API surface (e.g., `FastMDAnalysis` class and top-level helpers). Import paths are designed for clean usage in code and docs.

- **`datasets.py`**  
  Lightweight helpers for example data locations (e.g., TrpCage) and any small metadata that helps examples/tests stay readable.

- **`utils.py`**  
  General utilities. Notably:
  - `load_trajectory(...)`: robust loader that accepts single/multiple paths (lists, comma-separated strings, or glob patterns) and normalizes topology handling.
  - Helper routines (e.g., safe path creation, figure saving).

### `analysis/`: analysis modules

Each analysis is self-contained with a thin, consistent API and plotting helpers.

- **`__init__.py`** – Re-exports the analysis classes/functions for convenient imports.
- **`base.py`** – Shared machinery: a base analysis class, common exceptions, and small utilities reused across analyses.
- **`rmsd.py`** – RMSD computation against a reference frame; alignment options and basic QC plots.
- **`rmsf.py`** – Per-atom RMSF and summaries (tables/plots).
- **`rg.py`** – Radius of gyration (global and, optionally, by chain/segment).
- **`hbonds.py`** – Hydrogen-bond detection (e.g., Baker–Hubbard criteria) and counts/time series.
- **`ss.py`** – Secondary structure assignment wrappers (e.g., DSSP) with state fractions over time.
- **`cluster.py`** – Clustering wrappers (KMeans, DBSCAN, Hierarchical), dendrograms, and cluster occupancy/centroid reporting.
- **`dimred.py`** – Dimensionality reduction (PCA, MDS, t-SNE) with 2D scatter plots and projection exports.
- **`sasa.py`** – Solvent Accessible Surface Area: total, per-residue, and averaged measures.

### `cli/`: command-line interface

A small CLI package powers the `fastmda` command.

- **`__init__.py`** – CLI package init.
- **`_common.py`** – Shared CLI glue: argument builders, logging/config setup, frame/atom selection parsing, and construction of the `FastMDAnalysis` instance.
- **`main.py`** – The CLI entry point that wires subcommands and dispatches to implementations.
- **`analyze.py`** – “Orchestrator” command to run multiple analyses in one invocation, read options from YAML/JSON, and optionally generate slides.
- **`simple.py`** – Legacy single-analysis commands (e.g., `rmsd`, `rg`, `hbonds`, `cluster`, `ss`, `sasa`, `dimred`) retained for convenience.

> The README shows how to invoke the CLI, e.g., `fastmda analyze -traj traj.dcd -top top.pdb ...`. 

---

## Tests

- **`tests/`** houses pytest-based unit tests. Tests target each analysis module and the CLI orchestrator.  
  Typical local run: `pytest -q -m "not slow" --cov=fastmdanalysis --cov-report=term-missing`. 
---

## Documentation

- **`docs/`** contains Sphinx sources (API docs, user guide, developer guide).  
- **`.readthedocs.yaml`** controls RTD builds (Python version, extras, build commands). 
---

## Continuous Integration

- **`.github/workflows/`** defines CI pipelines (tests, coverage, docs build, style checks).  
  Workflows run on PRs and pushes to keep the package reliable. 

---

## Packaging and installation

- **`pyproject.toml`** declares the build system, package metadata, and entry points used to expose the `fastmda` CLI after `pip install fastmdanalysis`. See **README** for usage and options. 
---

## Examples and assets

- **`examples/`**: runnable scripts showing both API and CLI workflows on small datasets.  
- **`assets/`**: branding materials for papers, talks, and tutorials. 
