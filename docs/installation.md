# Installation

FastMDXplora's four phases have different dependency footprints. The analysis
and report phases work from pip alone; the setup and simulation phases need
PDBFixer and OpenMM, which are distributed primarily through conda-forge. Pick
the route that matches what you need.

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

### Windows local development install

On Windows PowerShell, the most reliable local development path is to use the
Python launcher and call pip through Python:

```powershell
cd C:\Users\User\OneDrive\Documents\GitHub\FastMDXplora
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[test]"
python -m fastmdxplora.cli.main --version
python -m fastmdxplora.cli.main info
```

If activation is blocked by PowerShell's execution policy, allow local scripts
for your user account:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Activation is optional. You can also run the virtual environment's Python
directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m fastmdxplora.cli.main --version
```

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

If the package imports but the `fastmdx` command is not recognized, the
console-script directory is probably not on PATH. This is common on Windows
with Microsoft Store Python or a mismatched PowerShell environment. Use the
module entrypoint as a robust fallback:

```powershell
python -m pip show fastmdxplora
python -c "import sys; print(sys.executable)"
python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
python -m fastmdxplora.cli.main --version
python -m fastmdxplora.cli.main info
```

Reinstalling with the same Python can recreate the console script:

```powershell
python -m pip install -e .
```

Avoid mixing multiple Python installs in one terminal. The Python used for
`python -m pip install ...` should be the same Python used for
`python -m fastmdxplora.cli.main ...`.

To check whether a GPU-capable OpenMM platform is available:

```python
import openmm
plats = [openmm.Platform.getPlatform(i).getName()
         for i in range(openmm.Platform.getNumPlatforms())]
print("CUDA available" if "CUDA" in plats else "CPU-only; simulations will run on CPU")
```
