# Installation

FastMDXplora's four phases have different dependency footprints. The analysis
and report phases work from pip alone; the setup and simulation phases need
PDBFixer and OpenMM, which are distributed primarily through conda-forge. The
full conda-based install is supported on Python 3.9 through 3.12. For a new
user, installing Python 3.10 or 3.11 first is the simplest path.

## Full install (all four phases)

The setup and simulation chemistry stack (OpenMM, PDBFixer) installs most
reliably from conda-forge, so the full install uses the bundled
`environment.yml`. `mamba` is recommended (a faster conda solver); plain
`conda` works too.

```bash
git clone https://github.com/aai-research-lab/FastMDXplora.git
cd FastMDXplora
mamba env create -f environment.yml || conda env create -f environment.yml
conda activate fastmdxplora
pip install -e .
```

## Git clone + setup using the install flow

If you are starting from a fresh clone, the recommended path is to run the
built-in install command through Python’s module entry point. This works even
before the `fastmdx` console script is installed, so it is the most reliable
option for a brand-new user:

```bash
git clone https://github.com/aai-research-lab/FastMDXplora.git
cd FastMDXplora
python -m fastmdxplora.cli.main install
```

For contributors who want an editable install while developing, use:

```bash
python -m fastmdxplora.cli.main install-e
```

If you want a health check or want to repair an existing setup, run:

```bash
python -m fastmdxplora.cli.main health
```

The standalone helper remains available as `python health.py` if you prefer to
run the diagnostics directly.

### Optional extras

```bash
pip install -e ".[ligand]"   # OpenFF small-molecule parameterization
pip install -e ".[plumed]"   # PLUMED enhanced sampling
```

The `plumed` extra also requires the `openmm-plumed` conda package:

```bash
conda install -c conda-forge openmm-plumed
```

## Analysis and report only (from PyPI)

If you only need to analyze existing trajectories and build reports (no
setup or simulation), plain pip is enough, with no conda required:

```bash
pip install fastmdxplora
```

The `fastmdx` command and `import fastmdxplora` are available either way. The
short alias package `fastmdx` installs the same software:

```bash
pip install fastmdx
```

## Verifying the install

```bash
fastmdx --version
python -c "import fastmdxplora; print(fastmdxplora.__version__)"
```

To check whether a GPU-capable OpenMM platform is available:

```python
import openmm
plats = [openmm.Platform.getPlatform(i).getName()
         for i in range(openmm.Platform.getNumPlatforms())]
print("CUDA available" if "CUDA" in plats else "CPU-only; simulations will run on CPU")
```
