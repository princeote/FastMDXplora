from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Iterable

from fastmdxplora import MAX_PYTHON, MIN_PYTHON, python_range_string

DEFAULT_ENV_NAME = "fastmdxplora"
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


def _build_bootstrap_yaml() -> str:
    """Render the conda env file using the canonical Python range.

    Kept in sync with ``pyproject.toml`` and the doctor check in
    ``health.py`` via :data:`fastmdxplora.MIN_PYTHON` /
    :data:`fastmdxplora.MAX_PYTHON`.
    """
    min_str = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    max_str = f"{MAX_PYTHON[0]}.{MAX_PYTHON[1]}"
    return f"""name: fastmdxplora
channels:
  - conda-forge
dependencies:
  - python>={min_str},<{max_str}
  - pip
  - numpy>=1.22
  - pyyaml>=6.0
  - mdtraj>=1.9.7
  - matplotlib>=3.5
  - scikit-learn>=1.0
  - pandas>=1.4
  - python-pptx>=0.6.21
  - openmm>=8.0
  - pdbfixer
  - openmmforcefields
"""


# Constant kept for backwards compatibility with any external callers
# that imported it before the range-sync refactor.
BOOTSTRAP_ENV_YAML: str = _build_bootstrap_yaml()


class BootstrapError(Exception):
    pass


def _print(message: str, prefix: str = "INFO") -> None:
    print(f"[{prefix}] {message}")


def _run_command(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
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
        raise BootstrapError(
            f"No Miniforge installer available for this platform: {platform.system()} {platform.machine()}"
        )
    return Path(tempfile.gettempdir()) / installer_name


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _conda_executable_from_prefix(prefix: Path, tool_name: str) -> Path | None:
    if platform.system() == "Windows":
        path = prefix / "Scripts" / f"{tool_name}.exe"
    else:
        path = prefix / "bin" / tool_name
    return path if path.exists() else None


def _locate_conda_cli() -> list[str] | None:
    for tool in ("mamba", "conda"):
        if command_exists(tool):
            return [tool]
    for tool_name in ("mamba", "conda"):
        candidate = _conda_executable_from_prefix(MINIFORGE_PREFIX, tool_name)
        if candidate is not None:
            return [str(candidate)]
    return None


def _download_miniforge_installer(installer_path: Path) -> None:
    url = f"{MINIFORGE_BASE_URL}/{installer_path.name}"
    _print(f"Downloading Miniforge installer: {url}")
    try:
        urllib.request.urlretrieve(url, installer_path)
    except Exception as exc:
        raise BootstrapError(f"Failed to download Miniforge: {exc}") from exc
    if platform.system() != "Windows":
        try:
            installer_path.chmod(0o755)
        except OSError:
            pass


def _install_miniforge() -> list[str]:
    installer_path = _miniforge_installer_path()
    if not installer_path.exists():
        _download_miniforge_installer(installer_path)

    install_prefix = MINIFORGE_PREFIX
    install_prefix.mkdir(parents=True, exist_ok=True)
    system = platform.system()

    if system == "Windows":
        command = [str(installer_path), "/InstallationType=JustMe", "/RegisterPython=0", "/S", f"/D={install_prefix}"]
    else:
        command = ["/bin/bash", str(installer_path), "-b", "-p", str(install_prefix)]

    _print(f"Installing Miniforge to {install_prefix}")
    result = _run_command(command)
    if result.returncode != 0:
        raise BootstrapError(
            "Miniforge installation failed: "
            + result.stderr.strip()
            + "\nPlease install Miniforge manually from https://conda-forge.org/miniforge/."
        )
    _print("Miniforge installed successfully")
    conda_cli = _locate_conda_cli()
    if conda_cli is None:
        raise BootstrapError("Miniforge was installed, but conda/mamba could not be found afterward.")
    return conda_cli


def _ensure_conda_available() -> list[str]:
    conda_cli = _locate_conda_cli()
    if conda_cli is not None:
        return conda_cli
    return _install_miniforge()


def _write_environment_yaml() -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="fastmdxplora-env-"))
    yaml_path = temp_dir / "environment.yml"
    yaml_path.write_text(_build_bootstrap_yaml(), encoding="utf-8")
    return yaml_path


def _parse_conda_envs(conda_cli: str) -> list[str]:
    result = _run_command([conda_cli, "env", "list", "--json"])
    if result.returncode != 0:
        return []
    try:
        import json

        data = json.loads(result.stdout)
        return [Path(p).name for p in data.get("envs", []) if p]
    except json.JSONDecodeError:
        return []


def _conda_env_exists(conda_cli: str, env_name: str) -> bool:
    return env_name in _parse_conda_envs(conda_cli)


def _remove_conda_env(conda_cli: str, env_name: str) -> None:
    _print(f"Removing existing conda environment '{env_name}'")
    result = _run_command([conda_cli, "env", "remove", "-n", env_name, "-y"])
    if result.returncode != 0:
        raise BootstrapError(f"Failed to remove existing environment: {result.stderr.strip()}")


def _create_conda_env(conda_cli: str, env_name: str, yaml_path: Path) -> None:
    _print(f"Creating conda environment '{env_name}' from bundled configuration")
    result = _run_command([conda_cli, "env", "create", "-f", str(yaml_path), "-n", env_name])
    if result.returncode != 0:
        raise BootstrapError(_format_conda_error(result.stderr, env_name, create=True))
    _print(f"Conda environment '{env_name}' created successfully")


def _update_conda_env(conda_cli: str, env_name: str, yaml_path: Path) -> None:
    _print(f"Updating existing conda environment '{env_name}'")
    result = _run_command([conda_cli, "env", "update", "-f", str(yaml_path), "-n", env_name])
    if result.returncode != 0:
        raise BootstrapError(_format_conda_error(result.stderr, env_name, create=False))
    _print(f"Conda environment '{env_name}' updated successfully")


def _install_package_in_env(conda_cli: str, env_name: str, package: str, *, editable: bool = False) -> None:
    _print(f"Installing package '{package}' into '{env_name}'")
    cmd = [conda_cli, "run", "-n", env_name, sys.executable, "-m", "pip", "install", "--upgrade"]
    if editable:
        cmd.append("--editable")
    cmd.append(package)
    result = _run_command(cmd)
    if result.returncode != 0:
        raise BootstrapError(
            f"Failed to install {package} in {env_name}: {result.stderr.strip()}"
        )
    _print(f"Package '{package}' installed into '{env_name}'")


def _verify_env(conda_cli: str, env_name: str) -> None:
    _print(f"Verifying conda environment '{env_name}'")
    command = [conda_cli, "run", "-n", env_name, sys.executable, "-m", "fastmdxplora.cli.main", "info"]
    result = _run_command(command)
    if result.returncode != 0:
        raise BootstrapError(
            "Environment verification failed: "
            + result.stderr.strip()
            + "\nIf this is a package issue, rerun `fastmdx bootstrap --force` or consult the installation output."
        )
    _print("Environment verified successfully")


def _format_conda_error(stderr: str, env_name: str, create: bool) -> str:
    hint_lines = []
    if "UnsatisfiableError" in stderr:
        hint_lines.append(
            "Package resolution failed. This often means the requested environment is unavailable for the selected Python version or platform."
        )
        hint_lines.append(
            "Use Python 3.9–3.12 in the bootstrap environment and retry, or install Miniforge/conda with proper channels."
        )
    if "ResolvePackageNotFound" in stderr or "PackagesNotFoundError" in stderr:
        hint_lines.append(
            "A required package could not be found in the configured channels."
            " Ensure you have internet access and the conda-forge channel available."
        )
    if "Cannot connect" in stderr or "HTTP 000" in stderr:
        hint_lines.append(
            "Network or SSL error while fetching package metadata. Check your network or proxy settings."
        )
    hint_text = "\n".join(hint_lines)
    return (
        f"Conda env {'creation' if create else 'update'} failed for '{env_name}': {stderr.strip()}"
        + ("\n" + hint_text if hint_text else "")
        + "\nIf the environment already exists, try `fastmdx bootstrap --force`."
    )


def bootstrap_environment(
    *,
    env_name: str = DEFAULT_ENV_NAME,
    python_version: str = "3.10",
    yes: bool = False,
    force: bool = False,
    package_name: str = "fastmdxplora",
    editable: bool = False,
) -> None:
    supported = python_range_string()
    if not python_version.startswith("3."):
        raise BootstrapError(
            f"Invalid Python version {python_version!r}. FastMDXplora supports {supported}."
        )
    major_minor = tuple(int(part) for part in python_version.split(".")[:2])
    if major_minor < MIN_PYTHON or major_minor >= MAX_PYTHON:
        raise BootstrapError(
            f"Python {python_version} is outside the supported range. "
            f"FastMDXplora supports {supported} (the OpenMM/PDBFixer stack "
            f"is the bottleneck; pick 3.10 or 3.11 for the smoothest ride)."
        )

    conda_cli = _ensure_conda_available()
    if conda_cli is None:
        raise BootstrapError("Conda or mamba is required but could not be located or installed.")

    existing = _conda_env_exists(conda_cli[0], env_name)
    yaml_path = _write_environment_yaml()
    try:
        # Embed the requested Python version in the YAML before env creation.
        text = yaml_path.read_text(encoding="utf-8")
        min_str = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
        max_str = f"{MAX_PYTHON[0]}.{MAX_PYTHON[1]}"
        text = text.replace(f"python>={min_str},<{max_str}", f"python=={python_version}")
        yaml_path.write_text(text, encoding="utf-8")

        if existing and force:
            _remove_conda_env(conda_cli[0], env_name)
            existing = False

        if existing:
            _update_conda_env(conda_cli[0], env_name, yaml_path)
        else:
            _create_conda_env(conda_cli[0], env_name, yaml_path)

        _install_package_in_env(conda_cli[0], env_name, package_name, editable=editable)
        _verify_env(conda_cli[0], env_name)
    finally:
        try:
            shutil.rmtree(yaml_path.parent)
        except OSError:
            pass

    _print(
        "Bootstrap complete. Activate the environment and run your first study:",
        prefix="SUCCESS",
    )
    _print(f"  conda activate {env_name}")
    _print("  fastmdx info")
    _print("After activation, run: fastmdx explore --system 1L2Y")


def main(argv: Iterable[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Bootstrap a runnable FastMDXplora conda environment on Linux/macOS/Windows."
        )
    )
    parser.add_argument("--env-name", default=DEFAULT_ENV_NAME,
                        help="Name of the conda environment to create.")
    parser.add_argument("--python-version", default="3.10",
                        help="Python version to install into the environment (3.9-3.12).")
    parser.add_argument("--force", action="store_true",
                        help="Recreate the conda environment if it already exists.")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip prompts by assuming yes.")
    args = parser.parse_args(argv)

    try:
        bootstrap_environment(
            env_name=args.env_name,
            python_version=args.python_version,
            yes=args.yes,
            force=args.force,
        )
        return 0
    except BootstrapError as exc:
        print(f"bootstrap failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
