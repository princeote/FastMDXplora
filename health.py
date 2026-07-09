#!/usr/bin/env python3
"""Repository doctor and initialization script for FastMDXplora.

Place this file in the repository root and run it once after cloning:

    python health.py

It detects the host OS and architecture, validates the repository layout,
checks Python/runtime dependencies, attempts to fix missing imports with pip
or conda, and performs a lightweight smoke test of the FastMDXplora CLI.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SRC_ROOT = ROOT / "src"
PYPROJECT_TOML = ROOT / "pyproject.toml"
REQUIREMENTS_TXT = ROOT / "requirements.txt"
ENVIRONMENT_YML = ROOT / "environment.yml"

DEFAULT_CONDA_ENV = "fastmdxplora"

# Insert the in-tree source root on sys.path so we can read the canonical
# Python-version range straight out of the package. Keeps the doctor
# honest with what install.py / pyproject.toml will actually enforce.
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

try:
    from fastmdxplora import (
        MAX_PYTHON as _MAX_PYTHON,
        MIN_PYTHON as _MIN_PYTHON,
        python_range_string as _PYTHON_RANGE_STR,
    )
except Exception:  # pragma: no cover — only hit if checkout is broken
    _MIN_PYTHON = (3, 9)
    _MAX_PYTHON = (3, 13)

    def _PYTHON_RANGE_STR() -> str:
        return (
            f"Python {_MIN_PYTHON[0]}.{_MIN_PYTHON[1]}"
            f"\u2013{_MAX_PYTHON[0]}.{_MAX_PYTHON[1] - 1}"
        )
MAX_PYTHON_STR = _PYTHON_RANGE_STR().rsplit("\u2013", 1)[-1]
MIN_PYTHON_STR = f"{_MIN_PYTHON[0]}.{_MIN_PYTHON[1]}"

CORE_PATHS = [
    ROOT / "README.md",
    ROOT / "pyproject.toml",
    ROOT / "src" / "fastmdxplora" / "__init__.py",
    ROOT / "src" / "fastmdxplora" / "cli" / "main.py",
    ROOT / "src" / "fastmdxplora" / "orchestrator.py",
    ROOT / "tests",
]

PACKAGE_IMPORT_OVERRIDES = {
    "python-pptx": "pptx",
    "scikit-learn": "sklearn",
    "pyyaml": "yaml",
    "openmm-plumed": "openmmplumed",
}

OPTIONAL_SIMULATION_BACKENDS = [
    ("PDBFixer", "pdbfixer", "conda install -c conda-forge pdbfixer"),
    ("OpenMM", "openmm", "conda install -c conda-forge openmm"),
]

MINIFORGE_BASE_URL = "https://github.com/conda-forge/miniforge/releases/latest/download"
MINIFORGE_PREFIX = Path.home() / "miniforge3"
MINIFORGE_INSTALLERS = {
    ("Linux", "x86_64"): "Miniforge3-Linux-x86_64.sh",
    ("Linux", "aarch64"): "Miniforge3-Linux-aarch64.sh",
    ("Darwin", "x86_64"): "Miniforge3-MacOSX-x86_64.sh",
    ("Darwin", "arm64"): "Miniforge3-MacOSX-arm64.sh",
    ("Windows", "x86_64"): "Miniforge3-Windows-x86_64.exe",
    ("Windows", "aarch64"): "Miniforge3-Windows-aarch64.exe",
}


class Status:
    OK = "OK"
    MISSING = "MISSING"
    FIXING = "FIXING"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


def fmt(message: str, status: str = Status.OK) -> str:
    return f"[{status}] {message}"


def help_note(message: str) -> str:
    return f"      -> {message}"


def run_command(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            **kwargs,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, "", f"Command not found: {cmd[0]}")


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _normalize_arch(arch: str) -> str:
    arch = arch.lower()
    if arch in ("amd64", "x86_64"):
        return "x86_64"
    if arch in ("aarch64", "arm64"):
        return "aarch64"
    return arch


def _miniforge_installer_name() -> str | None:
    system = platform.system()
    arch = _normalize_arch(platform.machine() or "")
    return MINIFORGE_INSTALLERS.get((system, arch))


def _miniforge_installer_path() -> Path:
    installer_name = _miniforge_installer_name()
    if installer_name is None:
        raise RuntimeError(f"No Miniforge installer available for this platform: {platform.system()} {platform.machine()}")
    return Path(tempfile.gettempdir()) / installer_name


def _locate_conda_cli() -> list[str] | None:
    for tool in ("mamba", "conda"):
        if command_exists(tool):
            return [tool]
    for tool_name in ("mamba", "conda"):
        candidate = _conda_executable_from_prefix(MINIFORGE_PREFIX, tool_name)
        if candidate is not None:
            return [str(candidate)]
    return None


def _conda_executable_from_prefix(prefix: Path, tool_name: str) -> Path | None:
    if platform.system() == "Windows":
        path = prefix / "Scripts" / f"{tool_name}.exe"
    else:
        path = prefix / "bin" / tool_name
    return path if path.exists() else None


def _download_miniforge_installer(installer_path: Path) -> bool:
    url = f"{MINIFORGE_BASE_URL}/{installer_path.name}"
    try:
        print(fmt(f"Downloading Miniforge installer: {url}", Status.FIXING))
        urllib.request.urlretrieve(url, installer_path)
        if platform.system() != "Windows":
            try:
                installer_path.chmod(0o755)
            except OSError:
                pass
        return True
    except Exception as exc:
        print(fmt(f"Failed to download Miniforge: {exc}", Status.FAILED))
        return False


def _install_miniforge() -> bool:
    installer_path = _miniforge_installer_path()
    if not installer_path.exists():
        if not _download_miniforge_installer(installer_path):
            return False
    install_prefix = MINIFORGE_PREFIX
    install_prefix.mkdir(parents=True, exist_ok=True)
    
    system = platform.system()
    if system == "Windows":
        command = [str(installer_path), "/InstallationType=JustMe", "/RegisterPython=0", "/S", f"/D={install_prefix}"]
    elif system == "Darwin":
        command = ["/bin/bash", str(installer_path), "-b", "-p", str(install_prefix)]
    else:  # Linux and others
        command = ["/bin/bash", str(installer_path), "-b", "-p", str(install_prefix)]
    
    print(fmt(f"Installing Miniforge to {install_prefix}", Status.FIXING))
    result = run_command(command)
    if result.returncode != 0:
        print(fmt(f"Miniforge installation failed: {result.stderr.strip()}", Status.FAILED))
        print(help_note("If the download or installation fails, manually install from https://conda-forge.org/miniforge/"))
        return False
    print(fmt("Miniforge installed successfully", Status.OK))
    return True


def _ensure_conda_available() -> list[str] | None:
    command = _locate_conda_cli()
    if command is not None:
        return command
    print(fmt("No conda or mamba found on PATH", Status.MISSING))
    if ENVIRONMENT_YML.exists():
        if _install_miniforge():
            return _locate_conda_cli()
    return None


def parse_pyproject() -> tuple[list[str], dict[str, list[str]]]:
    if not PYPROJECT_TOML.exists():
        return [], {}

    text = PYPROJECT_TOML.read_text(encoding="utf-8")

    try:
        if sys.version_info >= (3, 11):
            import tomllib

            data = tomllib.loads(text)
        else:
            import tomli  # type: ignore[import]

            data = tomli.loads(text)
    except (ImportError, SyntaxError, ValueError):
        data = _manual_parse_pyproject(text)

    project = data.get("project", {}) if isinstance(data, dict) else {}
    dependencies = project.get("dependencies", []) if isinstance(project, dict) else []
    optional = project.get("optional-dependencies", {}) if isinstance(project, dict) else {}
    return list(dependencies), {k: list(v) for k, v in optional.items()}


def _manual_parse_pyproject(text: str) -> dict[str, Any]:
    def extract_list(key: str, segment: str) -> list[str]:
        pattern = re.compile(rf"^{re.escape(key)}\s*=\s*\[", re.MULTILINE)
        match = pattern.search(segment)
        if not match:
            return []
        start = match.end() - 1
        bracket = 0
        end = None
        for idx, char in enumerate(segment[start:], start=start):
            if char == "[":
                bracket += 1
            elif char == "]":
                bracket -= 1
                if bracket == 0:
                    end = idx + 1
                    break
        if end is None:
            return []
        raw_list = segment[start:end]
        try:
            return ast.literal_eval(raw_list)
        except Exception:
            items = re.findall(r'''['"]([^'"]+)['"]''', raw_list)
            return items

    def extract_section(section_header: str) -> str:
        pattern = re.compile(rf"^\s*\[{re.escape(section_header)}\]", re.MULTILINE)
        match = pattern.search(text)
        if not match:
            return ""
        start = match.end()
        next_match = pattern.search(text, start)
        end = next_match.start() if next_match else len(text)
        return text[start:end]

    result: dict[str, Any] = {}
    project_section = extract_section("project")
    result["project"] = {
        "dependencies": extract_list("dependencies", project_section),
    }
    optional = {}
    optional_section = extract_section("project.optional-dependencies")
    if optional_section:
        current_key = None
        buffer = []
        for line in optional_section.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key_match = re.match(r"^(\w[\w-]*)\s*=\s*\[", stripped)
            if key_match:
                if current_key and buffer:
                    optional[current_key] = extract_list(current_key, "\n".join(buffer))
                current_key = key_match.group(1)
                buffer = [stripped]
            elif current_key is not None:
                buffer.append(stripped)
        if current_key and buffer:
            optional[current_key] = extract_list(current_key, "\n".join(buffer))
    result["project"]["optional-dependencies"] = optional
    return result


def parse_requirements() -> list[str]:
    if not REQUIREMENTS_TXT.exists():
        return []
    lines = []
    for raw in REQUIREMENTS_TXT.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        lines.append(line)
    return lines


def parse_environment_name() -> str:
    if not ENVIRONMENT_YML.exists():
        return DEFAULT_CONDA_ENV
    for line in ENVIRONMENT_YML.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            _, _, value = stripped.partition(":")
            value = value.strip().strip('"').strip("'")
            return value or DEFAULT_CONDA_ENV
    return DEFAULT_CONDA_ENV


def normalize_package_name(spec: str) -> str:
    return re.split(r"[<>=!\[ ]", spec, maxsplit=1)[0].strip().lower()


def import_name_for_package(dist_name: str) -> str:
    dist_name = dist_name.lower()
    if dist_name in PACKAGE_IMPORT_OVERRIDES:
        return PACKAGE_IMPORT_OVERRIDES[dist_name]
    return dist_name.replace("-", "_")


def check_python_version() -> bool:
    current = sys.version_info[:2]
    if current < _MIN_PYTHON:
        print(fmt(f"Python {MIN_PYTHON_STR} or newer is required; found {platform.python_version()}", Status.FAILED))
        print(help_note(f"Install {_PYTHON_RANGE_STR()} from https://python.org or Miniforge/Conda on Linux/macOS/Windows, then rerun this script."))
        return False
    if current >= _MAX_PYTHON:
        print(fmt(f"Python {platform.python_version()} is too new; FastMDXplora supports {_PYTHON_RANGE_STR()} (the OpenMM/PDBFixer chemistry stack caps out at 3.12)", Status.FAILED))
        print(help_note(f"Install {_PYTHON_RANGE_STR()} (3.10 or 3.11 recommended) into a dedicated environment with conda/Miniforge, then rerun this script."))
        return False
    print(fmt(f"Python {platform.python_version()} is present", Status.OK))
    return True


def detect_system() -> dict[str, str]:
    system = platform.system()
    arch = platform.machine() or "unknown"
    distro = ""
    if system == "Linux":
        distro = _detect_linux_distribution()
    elif system == "Darwin":
        distro = "macOS"
    elif system == "Windows":
        distro = "Windows"
    else:
        distro = system
    return {"system": system, "distro": distro, "arch": arch}


def _detect_linux_distribution() -> str:
    os_release = Path("/etc/os-release")
    if not os_release.exists():
        os_release = Path("/etc/os-release")
    if os_release.exists():
        try:
            text = os_release.read_text(encoding="utf-8", errors="ignore")
            data = {}
            for line in text.splitlines():
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                data[key.strip()] = value.strip().strip('"').strip("'")
            name = data.get("NAME", "Linux")
            version = data.get("VERSION_ID", "")
            if name.lower() == "zorin os":
                return f"Zorin OS {version}".strip()
            if name and version:
                return f"{name} {version}".strip()
            return name
        except Exception:
            pass
    return "Linux"


def environment_type() -> str:
    if "CONDA_PREFIX" in os.environ:
        return "conda"
    if "VIRTUAL_ENV" in os.environ or sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return "virtualenv"
    return "system"


def verify_paths() -> bool:
    missing = False
    print(fmt("Verifying repository layout", Status.OK))
    for path in CORE_PATHS:
        if path.exists():
            print(fmt(f"Found {path.relative_to(ROOT)}", Status.OK))
        else:
            print(fmt(f"Missing {path.relative_to(ROOT)}", Status.MISSING))
            missing = True
    if not ENVIRONMENT_YML.exists():
        print(fmt("No environment.yml found; conda-based full install is optional", Status.SKIPPED))
    if missing:
        print(help_note("Run this script from the FastMDXplora repository root directory."))
        print(help_note("If you just cloned the repository, use: cd <repo_path> && python health.py"))
    return not missing


def check_imports(package_names: list[str]) -> dict[str, bool]:
    import importlib

    results: dict[str, bool] = {}
    for pkg in package_names:
        module_name = import_name_for_package(pkg)
        try:
            importlib.import_module(module_name)
            results[pkg] = True
            print(fmt(f"Import succeeded: {module_name}", Status.OK))
        except Exception as exc:
            results[pkg] = False
            print(fmt(f"Import failed: {module_name} ({exc.__class__.__name__})", Status.MISSING))
    return results


def pip_install(package: str, env_cmd: list[str] | None = None) -> bool:
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", package]
    if env_cmd:
        cmd = [*env_cmd, *cmd]
    print(fmt(f"Installing {package}", Status.FIXING))
    result = run_command(cmd, cwd=str(ROOT))
    if result.returncode == 0:
        print(fmt(f"Installed {package}", Status.OK))
        return True
    print(fmt(f"Failed to install {package}: {result.stderr.strip()}", Status.FAILED))
    return False


def install_local_package(env_cmd: list[str] | None = None) -> bool:
    cmd = [sys.executable, "-m", "pip", "install", "-e", "."]
    if env_cmd:
        cmd = [*env_cmd, *cmd]
    print(fmt("Installing local package fastmdxplora", Status.FIXING))
    result = run_command(cmd, cwd=str(ROOT))
    if result.returncode == 0:
        print(fmt("Local package installed", Status.OK))
        return True
    print(fmt(f"Local package installation failed: {result.stderr.strip()}", Status.FAILED))
    print(help_note("The health script attempted to install the local package automatically."))
    print(help_note("Fix the environment issue or permissions, then rerun: python health.py"))
    return False


def install_pip_extras(extra: str, env_cmd: list[str] | None = None) -> bool:
    package = f".[{extra}]"
    print(fmt(f"Installing pip extras {package}", Status.FIXING))
    return pip_install(package, env_cmd=env_cmd)


def parse_conda_envs(conda_cli: str) -> list[str]:
    result = run_command([conda_cli, "env", "list", "--json"])
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
        envs = data.get("envs", [])
        return [Path(p).name for p in envs if p]
    except json.JSONDecodeError:
        return []


def conda_create_env(conda_cli: str, env_name: str) -> bool:
    print(fmt(f"Creating conda environment '{env_name}' from environment.yml", Status.FIXING))
    result = run_command([conda_cli, "env", "create", "-f", str(ENVIRONMENT_YML), "-n", env_name], cwd=str(ROOT))
    if result.returncode == 0:
        print(fmt(f"Conda environment '{env_name}' created", Status.OK))
        return True
    print(fmt(f"Failed to create conda env: {result.stderr.strip()}", Status.FAILED))
    return False


def conda_run_command(conda_cli: str, env_name: str, command: list[str]) -> subprocess.CompletedProcess:
    return run_command([conda_cli, "run", "-n", env_name, *command], cwd=str(ROOT))


def get_conda_runner(use_fix: bool = True) -> tuple[list[str] | None, str | None]:
    if not ENVIRONMENT_YML.exists():
        return None, None
    conda_cli = _ensure_conda_available() if use_fix else _locate_conda_cli()
    if conda_cli is None:
        print(fmt("No conda or mamba found; falling back to pip install", Status.SKIPPED))
        return None, None
    env_name = parse_environment_name()
    envs = parse_conda_envs(conda_cli[0])
    if env_name not in envs:
        if not use_fix:
            return conda_cli, env_name
        if conda_create_env(conda_cli[0], env_name):
            return conda_cli, env_name
        return None, None
    print(fmt(f"Found existing conda environment '{env_name}'", Status.OK))
    return conda_cli, env_name


def smoke_test(env_cmd: list[str] | None = None, env_name: str | None = None) -> bool:
    if env_cmd is not None and env_name is not None:
        command = [env_cmd[0], "run", "-n", env_name, sys.executable, "-m", "fastmdxplora.cli.main", "info"]
        process = run_command(command, cwd=str(ROOT))
    else:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        command = [sys.executable, "-m", "fastmdxplora.cli.main", "info"]
        process = run_command(command, cwd=str(ROOT), env=env)

    if process.returncode == 0:
        print(fmt("Smoke test passed: FastMDXplora CLI imported and info command worked", Status.OK))
        return True
    print(fmt("Smoke test failed", Status.FAILED))
    print(process.stdout)
    print(process.stderr)
    print(help_note("The health script installs the local package automatically."))
    print(help_note("Fix the underlying installation issue or dependency error, then rerun: python health.py"))
    return False


def get_missing_imports(dependencies: list[str]) -> list[str]:
    missing = []
    for spec in dependencies:
        name = normalize_package_name(spec)
        module_name = import_name_for_package(name)
        try:
            __import__(module_name)
        except Exception:
            missing.append(name)
    return missing


def ensure_local_package_installed(env_cmd: list[str] | None = None) -> bool:
    try:
        sys.path.insert(0, str(SRC_ROOT))
        import fastmdxplora  # noqa: F401
        print(fmt("Local package fastmdxplora is importable", Status.OK))
        return True
    except Exception as exc:
        print(fmt(f"Local package import failed: {exc.__class__.__name__}", Status.MISSING))
        if env_cmd is None:
            return install_local_package(None)
        command = [env_cmd[0], "run", "-n", parse_environment_name(), sys.executable, "-m", "pip", "install", "-e", "."]
        print(fmt("Installing local package inside conda environment", Status.FIXING))
        result = run_command(command, cwd=str(ROOT))
        if result.returncode == 0:
            print(fmt("Local package installed in conda environment", Status.OK))
            return True
        print(fmt(f"Failed local install in conda environment: {result.stderr.strip()}", Status.FAILED))
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FastMDXplora repository doctor and initialization tool")
    parser.add_argument("--no-fix", action="store_true", help="Only diagnose problems; do not install or modify anything")
    parser.add_argument("--yes", action="store_true", help="Accept all fixes automatically")
    args = parser.parse_args(argv)

    print("\nFastMDXplora Repository Doctor")
    print("=" * 36)
    print(f"Repository root: {ROOT}")

    status_ok = True
    system = detect_system()
    print(fmt(f"Platform: {system['system']} ({system['distro']}) {system['arch']}", Status.OK))
    print(fmt(f"Environment type: {environment_type()}", Status.OK))

    if not check_python_version():
        status_ok = False

    if not verify_paths():
        status_ok = False

    dependencies, optional = parse_pyproject()
    if dependencies:
        print(fmt(f"Parsed {len(dependencies)} project dependencies from pyproject.toml", Status.OK))
    if optional:
        print(fmt(f"Parsed {len(optional)} optional dependency groups", Status.OK))

    requirements = parse_requirements()
    if requirements:
        print(fmt(f"Parsed {len(requirements)} requirements from requirements.txt", Status.OK))

    conda_cmd, conda_env = get_conda_runner() if not args.no_fix else (None, None)
    if conda_cmd and conda_env:
        print(fmt(f"Using conda environment {conda_env}", Status.OK))

    if not args.no_fix:
        if not ensure_local_package_installed(conda_cmd):
            status_ok = False
        else:
            missing = get_missing_imports(dependencies)
            if missing:
                print(fmt(f"Found {len(missing)} missing runtime imports", Status.MISSING))
                if conda_cmd and conda_env:
                    print(fmt("Attempting to install optional md extras via conda environment", Status.FIXING))
                    install_pip_extras("md", env_cmd=conda_cmd)
                else:
                    if install_pip_extras("md"):
                        print(fmt("Optional MD extras installed via pip", Status.OK))
                missing = get_missing_imports(dependencies)
                if missing:
                    print(fmt(f"Still missing imports after fix attempts: {', '.join(missing)}", Status.FAILED))
                    status_ok = False
            else:
                print(fmt("All required runtime imports are present", Status.OK))
    else:
        print(fmt("Fix mode skipped (--no-fix)", Status.SKIPPED))

    if not args.no_fix:
        if conda_cmd and conda_env:
            print(fmt("Installing local package and extras in conda environment", Status.OK))
            install_local_package(env_cmd=conda_cmd)
        else:
            print(fmt("Installing local package into current Python environment", Status.OK))
            install_local_package(None)

    print(fmt("Running lightweight smoke test", Status.OK))
    if conda_cmd and conda_env:
        smoke_ok = smoke_test(env_cmd=conda_cmd, env_name=conda_env)
    else:
        smoke_ok = smoke_test()
    if not smoke_ok:
        status_ok = False

    print("\nSummary")
    print("-" * 36)
    if status_ok:
        print(fmt("Repository is ready for FastMDXplora execution", Status.OK))
        if conda_cmd and conda_env:
            print("Run your study inside the conda environment:")
            print(f"  conda activate {conda_env}")
            print("  python -m fastmdxplora.cli.main explore --help")
        else:
            print("Run FastMDXplora from this environment:")
            print("  python -m fastmdxplora.cli.main explore --help")
    else:
        print(fmt("One or more checks failed. Review the messages above.", Status.FAILED))
        if not command_exists("python"):
            print(help_note("Install Python 3.9+ and rerun this script."))
        if ENVIRONMENT_YML.exists() and not (command_exists("mamba") or command_exists("conda")):
            print(help_note("Install Miniforge, Miniconda, or Anaconda, then rerun health.py for the full simulation stack."))
        if ENVIRONMENT_YML.exists() and (command_exists("mamba") or command_exists("conda")):
            print(help_note("If environment creation failed earlier, retry: conda env create -f environment.yml"))
        print(help_note("The health script installs the local package automatically."))
        print(help_note("Fix any installation or permission issue, then rerun: python health.py"))
        if ENVIRONMENT_YML.exists():
            print(help_note("After environment creation, rerun health.py to verify everything."))
    return 0 if status_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
