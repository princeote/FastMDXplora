# Installation

FastMDXplora is designed so a brand-new user can go from a fresh machine to a runnable simulation in **3 commands** on **Linux, macOS, or Windows**. The same commands work everywhere. **Miniforge is auto-installed** when no conda is on PATH, so a fresh machine is enough — no prior Python, conda, or OpenMM install needed.

This page covers every supported starting point and gives troubleshooting tips. If you just want to get going, the [Quick install](#quick-install-any-os) section is enough.

## Quick install (any OS)

```bash
git clone https://github.com/aai-research-lab/FastMDXplora.git   # 1
cd FastMDXplora                                                  # 2
python -m fastmdxplora.cli.main install                         # 3
```

The third command (`install`) does everything else:

1. Detects whether conda or mamba is already on your `PATH`.
2. If not, downloads and installs **Miniforge** for your platform (Linux x86_64 / aarch64, macOS x86_64 / arm64, Windows x86_64 / aarch64) into `~/miniforge3`.
3. Creates a `fastmdxplora` conda environment with **Python 3.10**.
4. Installs **OpenMM** and **PDBFixer** (the only heavy chemistry dependencies).
5. Installs **FastMDXplora** itself into that environment.
6. Runs `fastmdx info` as a smoke test.

Then activate the environment and run a first simulation:

```bash
conda activate fastmdxplora
fastmdx explore --system 1L2Y
```

`1L2Y` is a small trp-cage PDB that exercises every phase on a fast turnaround. Replace it with any 4-character PDB ID or with the path to a local `.pdb` / `.cif` file.

> Need to install for development instead? Use `python -m fastmdxplora.cli.main install-e` — same flow but the local checkout is installed in editable mode.

## Prerequisites

- A **shell** (bash / zsh / PowerShell) with **internet access**.
- `git` on `PATH` (preinstalled on modern macOS and Windows 10+; on bare Linux you may need to install via your package manager).
- A terminal that supports **UTF-8** output (the CLI renders a box-drawing banner).
- **~1.5 GB of free disk** for the full install (Miniforge downloads ~150 MB; the `fastmdxplora` conda environment adds another ~800 MB of OpenMM / MDTraj / matplotlib / etc.).
- Python is **not required** up front — if you don't have it, `install` will install Miniforge, which brings Python 3.10 along for the ride.

## Scenarios your new user might be in

### Scenario A — Fresh machine, nothing installed (cold start)

You have a brand-new machine (or a fresh VM, a new WSL distro, etc.) that has no Python, conda, or mamba yet.

Just run the three commands above. The third command detects the missing conda and downloads Miniforge for your OS from `github.com/conda-forge/miniforge/releases/latest/download/`. Miniforge is then installed into `~/miniforge3` (Linux/macOS) or `%USERPROFILE%\miniforge3` (Windows).

Time: roughly 5–10 minutes for Miniforge + ~5–10 minutes for `mamba`-style env resolution (classic `conda` works too but is slower). Disk cost: ~1 GB.

### Scenario B — You already have conda or mamba installed

Skip the auto-install. The same `python -m fastmdxplora.cli.main install` command detects your existing conda/mamba, skips the Miniforge download, and creates the `fastmdxplora` environment directly.

If you don't yet have conda/mamba, Miniforge is the easiest source (it's conda + mamba + conda-forge preconfigured). The bootstrap installs it for you, so you don't need to grab it manually.

### Scenario C — You only need analysis + reporting, not MD

```bash
pip install fastmdxplora
fastmdx explore --system 1L2Y --include analyze report
```

This installs FastMDXplora from PyPI directly into your system Python (no conda env required). The `analyze` and `report` phases only need pip-installable dependencies (MDTraj, matplotlib, scikit-learn, python-pptx), all of which are bundled.

The `setup` and `simulation` phases need OpenMM + PDBFixer. If you run them and they're missing, FastMDXplora's self-healing prologue will print the exact install command and exit cleanly — no stack trace.

### Scenario D — conda-forge (one command, when published)

> Coming soon. A single-command install is in progress via a `recipes/fastmdxplora/meta.yaml` recipe, which would give:
>
> ```bash
> conda install -c conda-forge fastmdxplora
> fastmdx explore --system 1L2Y
> ```
>
> Use Scenario A or B until the recipe clears review.

### Scenario E — Editable install (contributors hacking on FastMDXplora)

This is for users who want to **modify FastMDXplora's source** — adding a new analysis, fixing a bug, or contributing back upstream. The flow mirrors Scenarios A and B (clone the repo, `cd` into it, run the bootstrap), but the bootstrap is `install-e` instead of `install`. The local checkout is then installed in **editable mode** (`pip install -e .`) so any change you make under `src/fastmdxplora/` shows up the next time you run `fastmdx`.

```bash
git clone https://github.com/aai-research-lab/FastMDXplora.git   # 1
cd FastMDXplora                                                  # 2
python -m fastmdxplora.cli.main install-e                       # 3
```

What `install-e` does differently from `install`:

- Miniforge auto-install (if needed), conda env creation with Python 3.10, OpenMM + PDBFixer drop-in, and the `fastmdx info` smoke test are unchanged.
- The last step uses `pip install -e .` (editable) on the local repository checkout instead of pulling `fastmdxplora` from PyPI — your edits to `src/fastmdxplora/` immediately affect the next `fastmdx` invocation.

Then activate and run as usual:

```bash
conda activate fastmdxplora
fastmdx explore --system 1L2Y
```

To validate changes locally, install the test extras and run the suite. **Run these inside the `fastmdxplora` conda env from the previous step** (`conda activate fastmdxplora`) so the editable `src/` and `pytest` are on `PATH`:

```bash
pip install -e ".[test]"     # adds pytest, pytest-cov, ruff
pytest                       # full test suite
ruff check src tests         # lint with project conventions
```

For full contributor conventions (test requirements, coding style, PR workflow) see [CONTRIBUTING.md](../CONTRIBUTING.md).

## Verify the install

```bash
fastmdx --version    # e.g. fastmdx 2.0.1 (FastMDXplora)
fastmdx info         # version, detected phases, OpenMM/PDBFixer status, citation
```

`fastmdx info` reports which backends are present. If `PDBFixer: installed` and `OpenMM: installed` both say yes, all four phases will work end-to-end.

To check whether a GPU-capable OpenMM platform is available:

```python
import openmm as mm
plats = [mm.Platform.getPlatform(i).getName()
         for i in range(mm.Platform.getNumPlatforms())]
print("Available platforms:", plats)
print("CUDA available" if "CUDA" in plats else "CPU-only: simulations will run on CPU")
```

## If something goes wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| `git` not found | `git` is not installed (rare on modern Windows and macOS, but possible on stripped-down Linux installs) | Install Git from https://git-scm.com/downloads, then re-run the first command |
| `python` isn't recognized | `python` is not on `PATH`, so the bootstrap can't even start | Install Miniforge manually from https://conda-forge.org/miniforge/ — it ships Python and conda together — then re-run the install command |
| `[FAILED] Python X.Y.Z is too new` from `python health.py` | Python ≥ 3.13 (the OpenMM / PDBFixer chemistry stack caps out at 3.12) | Use Python 3.10 or 3.11 — `install` defaults to 3.10, which is the smoothest supported version |
| `conda` / `mamba` not on PATH after Miniforge install | New shell didn't pick it up | On Linux/macOS: `source ~/miniforge3/etc/profile.d/conda.sh`. On Windows: open a fresh `cmd` or PowerShell |
| Simulation phase missing OpenMM | You used `pip install fastmdxplora` without installing the chemistry stack | `conda install -c conda-forge openmm pdbfixer` (recommended) or `pip install "fastmdxplora[md]"` (best-effort) |
| Self-heal prints a friendly install hint at exit 2 | A `setup` / `simulate` / `explore` command needs OpenMM and it's missing | Follow the install command in the hint, or use `--include analyze report` to skip chemistry phases |
| PDB won't download | No internet to RCSB, or your input wasn't a valid 4-character ID | Use a local `.pdb` / `.cif` path instead, or check the ID |

## Diagnostic entry points

| Command | What it does |
|---|---|
| `python -m fastmdxplora.cli.main health` | Runs the repository doctor (verifies repo layout, deps, imports, runs a smoke test). Add `--no-fix` for diagnose-only mode. |
| `python -m fastmdxplora.cli.main info` | Prints FastMDXplora version + detected backends. |
| `python fastmdx --version` | Version only. Available before `pip install` (uses the pure-Python shim in the repo root). |

`health` from inside a fresh clone is what's caught the highest-friction install bugs historically, so run it if anything seems off.

## Why Python 3.9–3.12 (and not 3.13)?

The chemistry phases depend on **OpenMM** and **PDBFixer**, which are primarily distributed through **conda-forge**. Their current wheels target Python 3.9–3.12. The `health.py` doctor and the bootstrap both enforce this range from a single source of truth (`fastmdxplora.MIN_PYTHON = (3, 9)` and `MAX_PYTHON = (3, 13)`). Python 3.13 and newer are detected as out-of-range.

If your environment is too new, install Python 3.10 or 3.11 in a dedicated conda env and re-run the bootstrap. The `install` command already defaults to Python 3.10, which is the smoothest supported version.

## Where to go next

- **Ready to run?** Try the [Usage examples](usage_examples.md).
- **Need a specific output config?** See [Configuration files](configuration.md).
- **Want to write your own analyses or extend FastMDXplora?** See [Phases](phases.md) and the [API reference](api.md).
- **Want to contribute?** See [CONTRIBUTING.md](../CONTRIBUTING.md).
