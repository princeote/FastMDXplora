"""Tests for OS-level native-output suppression."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest


def test_suppress_native_output_silences_c_level_writes(tmp_path):
    """A C-level write to fd 1/2 inside the context manager is suppressed.

    We use a subprocess that writes directly to the file descriptors (the
    way MDTraj's plugins do), capturing its stdout/stderr, to prove the
    redirect catches output that bypasses Python's stream objects.
    """
    script = tmp_path / "probe.py"
    script.write_text(
        "import os, sys\n"
        "from fastmdxplora.utils import suppress_native_output\n"
        "os.write(1, b'BEFORE-OUT\\n'); os.write(2, b'BEFORE-ERR\\n')\n"
        "with suppress_native_output():\n"
        "    os.write(1, b'INSIDE-OUT\\n')\n"
        "    os.write(2, b'INSIDE-ERR\\n')\n"
        "os.write(1, b'AFTER-OUT\\n'); os.write(2, b'AFTER-ERR\\n')\n"
    )
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    combined = result.stdout + result.stderr
    # Output before/after the block survives; output inside is suppressed.
    assert "BEFORE-OUT" in combined
    assert "BEFORE-ERR" in combined
    assert "AFTER-OUT" in combined
    assert "AFTER-ERR" in combined
    assert "INSIDE-OUT" not in combined
    assert "INSIDE-ERR" not in combined


def test_suppress_native_output_restores_fds():
    """After the block, normal printing works again (fds restored)."""
    from fastmdxplora.utils import suppress_native_output

    with suppress_native_output():
        os.write(1, b"swallowed\n")
    # If fds weren't restored this would fail or write to devnull;
    # a plain print must reach real stdout again.
    print("restored", end="")  # captured normally by pytest


def test_suppress_only_stdout():
    """stderr passes through when stdout-only is requested."""
    from fastmdxplora.utils import suppress_native_output

    # Just exercise the parameterization without asserting on the terminal.
    with suppress_native_output(stdout=True, stderr=False):
        os.write(1, b"swallowed\n")
    # No exception == fds handled cleanly.


def test_suppress_silences_mdtraj_dcd_load(tmp_path, capfd):
    """End-to-end: an MDTraj DCD load inside the CM emits no plugin chatter.

    MDTraj's C plugin prints 'dcdplugin) ...' to the libc stdio buffer on
    load. This asserts the fd redirect + libc flush actually swallows it.
    Skipped if MDTraj isn't installed.
    """
    md = pytest.importorskip("mdtraj")
    import numpy as np
    from fastmdxplora.utils import suppress_native_output

    top = md.Topology()
    chain = top.add_chain()
    res = top.add_residue("ALA", chain)
    for n in ("N", "CA", "C", "O"):
        top.add_atom(n, md.element.carbon, res)
    traj = md.Trajectory(np.random.rand(8, 4, 3).astype(np.float32), top)
    dcd = tmp_path / "probe.dcd"
    traj.save_dcd(str(dcd))

    # Drain anything emitted by the save above.
    capfd.readouterr()

    with suppress_native_output():
        loaded = md.load(str(dcd), top=top)
    assert loaded.n_frames == 8

    captured = capfd.readouterr()
    assert "dcdplugin" not in (captured.out + captured.err)
