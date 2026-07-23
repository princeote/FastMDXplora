# Installation

## macOS/Linux

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[test]"
python -m driftmd info
```

## Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[test]"
python -m driftmd info
```

If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Activation is optional:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m driftmd info
```

## CLI Not On PATH

If `driftmd` is not recognized but imports work, the Python scripts directory
is not on PATH. Use:

```bash
python -m driftmd info
python -c "import sys; print(sys.executable)"
python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
```

Avoid mixing different Python installations in one terminal.
