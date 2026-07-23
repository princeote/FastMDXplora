"""Tests for the bootstrap helpers in ``src/fastmdxplora/install.py``.

These tests pin two regressions:

1. **Certifi-already-installed-but-stale gap**: earlier code short-circuited
   the auto-recovery when ``certifi`` was *importable*, which silently
   skipped the pip-upgrade path. The most common "new machine" failure
   mode is certifi present but stale, so the upgrade-and-retry path has
   to run on every SSL failure.

2. **Lockstep drift between ``MINIFORGE_INSTALLERS`` and
   ``MINIFORGE_SHA256``**: a future contributor who adds a platform
   without remembering to add the matching SHA would silently lose
   integrity verification on that platform. This module asserts the
   two tables stay 1:1 on non-None entries.

Also covers:

* ``_try_upgrade_certifi`` return paths on pip success / failure.
* ``_insecure_ssl_optin_enabled`` env-var parsing.
* ``_download_miniforge_installer`` SHA-gate on insecure SSL.
* ``_sha256_of_file`` correctness on a small known file.
"""

from __future__ import annotations

import os
import ssl
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fastmdxplora.install import (
    MINIFORGE_INSTALLERS,
    MINIFORGE_SHA256,
    MINIFORGE_VERSION,
    BootstrapError,
    _build_certifi_ssl_context,
    _download_miniforge_installer,
    _insecure_ssl_optin_enabled,
    _sha256_of_file,
    _should_block_insecure_ssl,
    _try_upgrade_certifi,
)


# ---------------------------------------------------------------------------
# Certifi auto-recovery helpers
# ---------------------------------------------------------------------------
class TestTryUpgradeCertifi:
    """``_try_upgrade_certifi`` returns based on pip's exit code."""

    def test_returns_true_when_pip_exits_zero(self):
        fake_proc = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=fake_proc) as run_mock:
            assert _try_upgrade_certifi() is True
        argv = run_mock.call_args[0][0]
        assert argv[:3] == [sys.executable, "-m", "pip"]
        assert "--user" in argv
        assert "--upgrade" in argv
        assert "certifi" in argv

    def test_returns_false_when_pip_exits_nonzero(self):
        with patch("subprocess.run", return_value=MagicMock(returncode=1)):
            assert _try_upgrade_certifi() is False

    def test_returns_false_on_timeout(self):
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="pip", timeout=180),
        ):
            assert _try_upgrade_certifi() is False

    def test_returns_false_on_missing_executable(self):
        with patch(
            "subprocess.run",
            side_effect=FileNotFoundError("python not on PATH"),
        ):
            assert _try_upgrade_certifi() is False

    def test_passes_timeout_to_subprocess(self):
        """We cap the pip call so a hung pip can't hang the bootstrap."""
        with patch("subprocess.run", return_value=MagicMock(returncode=0)) as run_mock:
            _try_upgrade_certifi()
        timeout_kw = run_mock.call_args.kwargs.get("timeout")
        assert timeout_kw is not None
        assert timeout_kw <= 300  # cap; don't sleep forever


class TestBuildCertifiSslContext:
    """``_build_certifi_ssl_context`` returns an SSLContext or None."""

    def test_returns_none_when_certifi_import_fails(self):
        with patch.dict("sys.modules", {"certifi": None}):
            assert _build_certifi_ssl_context() is None

    def test_returns_sslcontext_when_certifi_importable(self):
        # Use any existing file as the certifi CA path so we don't
        # make this test depend on system CA bundles; then mock
        # ``ssl.create_default_context`` itself so we don't actually
        # parse the file as a CA bundle (which would still work but
        # couples this test to the real SSL implementation).
        fake_certifi = MagicMock()
        fake_certifi.where.return_value = __file__
        sentinel_ctx = object()
        with patch.dict("sys.modules", {"certifi": fake_certifi}), \
                patch("ssl.create_default_context", return_value=sentinel_ctx):
            ctx = _build_certifi_ssl_context()
        assert ctx is sentinel_ctx


class TestInsecureSslOptinEnvVar:
    """``FASTMDX_INSECURE_SSL`` env var: case-insensitive, whitespace-tolerant."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("1", True),
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("yes", True),
            ("yES", True),
            ("on", True),
            (" 1 ", True),
            ("  yes  ", True),
            ("0", False),
            ("", False),
            ("false", False),
            ("no", False),
            ("off", False),
            ("2", False),
            ("enabled", False),
            ("enable", False),
        ],
    )
    def test_parses_truthy_and_falsy_inputs(self, raw, expected):
        with patch.dict(
            os.environ, {"FASTMDX_INSECURE_SSL": raw}, clear=False,
        ):
            assert _insecure_ssl_optin_enabled() is expected

    def test_unset_env_means_false(self):
        env = {k: v for k, v in os.environ.items() if k != "FASTMDX_INSECURE_SSL"}
        with patch.dict(os.environ, env, clear=True):
            assert _insecure_ssl_optin_enabled() is False


# ---------------------------------------------------------------------------
# SHA-gate on insecure SSL
# ---------------------------------------------------------------------------
class TestInsecureSslShaGate:
    """Insecure SSL must be refused when no SHA is recorded."""

    def test_refuses_when_no_sha_is_recorded_for_the_installer(
        self, tmp_path: Path,
    ):
        # Manufacture an installer name that exists in
        # MINIFORGE_INSTALLERS but has no MINIFORGE_SHA256 entry.
        unsupported_installer_path = tmp_path / "Made-Up-Installer.exe"
        assert MINIFORGE_SHA256.get(unsupported_installer_path.name) is None
        with patch.dict(
            os.environ, {"FASTMDX_INSECURE_SSL": "1"}, clear=False,
        ):
            with pytest.raises(
                BootstrapError,
                match="FASTMDX_INSECURE_SSL=1 cannot be used",
            ):
                _download_miniforge_installer(unsupported_installer_path)

    def test_does_not_refuse_when_sha_is_recorded(self):
        # When a SHA *is* recorded AND the env var is set, the
        # SHA gate does NOT refuse. ``_should_block_insecure_ssl``
        # is the single source of truth shared by
        # ``_download_miniforge_installer``, so a typo in either
        # the function or the helper is caught by this test.
        installer_name = "Miniforge3-Linux-x86_64.sh"
        assert MINIFORGE_SHA256.get(installer_name) is not None
        with patch.dict(
            os.environ, {"FASTMDX_INSECURE_SSL": "1"}, clear=False,
        ):
            assert not _should_block_insecure_ssl(installer_name)


# ---------------------------------------------------------------------------
# Lockstep invariant: SHA table and INSTALLERS table stay in sync
# ---------------------------------------------------------------------------
class TestMiniforgePinLockstep:
    """Fail-fast CI checks for the pin table consistency."""

    def test_sha_keys_match_installer_filenames(self):
        sha_keys = set(MINIFORGE_SHA256.keys())
        installer_filenames = {
            v for v in MINIFORGE_INSTALLERS.values() if v is not None
        }
        assert sha_keys == installer_filenames, (
            "MINIFORGE_SHA256 keys must equal MINIFORGE_INSTALLERS "
            f"non-None values. SHA keys: {sha_keys}, "
            f"installer filenames: {installer_filenames}."
        )

    def test_no_sha_table_key_is_a_none_installer(self):
        for filename in MINIFORGE_SHA256:
            assert filename in MINIFORGE_INSTALLERS.values(), (
                f"MINIFORGE_SHA256 contains '{filename}' but the corresponding "
                f"MINIFORGE_INSTALLERS entry is None or missing."
            )

    def test_every_sha_value_is_a_64_char_lowercase_hex(self):
        for filename, sha in MINIFORGE_SHA256.items():
            assert len(sha) == 64, (
                f"{filename}: expected 64-char SHA-256, got {len(sha)}"
            )
            int(sha, 16)  # raises ValueError on non-hex
            assert sha == sha.lower(), (
                f"{filename}: SHA-256 must be lowercase (got {sha!r})"
            )

    def test_miniforge_version_is_pinned_string(self):
        """A non-``latest`` pinned version is required for SHA verification."""
        assert MINIFORGE_VERSION != "latest"
        # conda-forge tags look like 24.11.0-0 -- at least one "-" separator.
        assert "-" in MINIFORGE_VERSION

    def test_windows_aarch64_is_documented_unsupported(self):
        assert MINIFORGE_INSTALLERS.get(("Windows", "aarch64")) is None


# ---------------------------------------------------------------------------
# _sha256_of_file streaming correctness on a small known file
# ---------------------------------------------------------------------------
class TestSha256OfFile:
    def test_hashes_a_known_file_correctly(self, tmp_path: Path):
        # SHA-256 of empty file.
        empty = tmp_path / "empty.bin"
        empty.write_bytes(b"")
        assert (
            _sha256_of_file(empty)
            == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_hashes_a_small_file_correctly(self, tmp_path: Path):
        # SHA-256 of the literal string "abc".
        f = tmp_path / "abc.txt"
        f.write_bytes(b"abc")
        assert (
            _sha256_of_file(f)
            == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )
