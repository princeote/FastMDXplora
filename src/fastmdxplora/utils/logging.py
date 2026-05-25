"""Console and file logging for FastMDXplora.

This module establishes a consistent visual identity across the FastMDXplora
toolchain (FastMDXplora, FastMDXplora-Analysis, FastMDXplora-Simulation).
It provides a consistent logging design so that users
who run the three tools side-by-side see uniform output.

Two styles are offered:

  - ``pretty`` (default) -- compact, human-friendly, colored when stderr is
    a TTY. One line per record with timestamp, level icon, and message.
  - ``plain``            -- ISO-like ``YYYY-MM-DD HH:MM:SS,mmm - LEVEL - message``
    suitable for log files, grep, and audit trails. Default for file
    handlers.

Environment overrides:

  - ``FASTMDX_LOG_STYLE``  -- ``pretty`` | ``plain`` (overrides API-supplied style)
  - ``FASTMDX_LOGLEVEL``   -- ``DEBUG`` | ``INFO`` | ``WARNING`` | ``ERROR`` | ``CRITICAL``
  - ``NO_COLOR``           -- if set, disables color even on a TTY (industry convention)

Public API:

  :func:`setup_console`     -- initialize the colored console logger
  :func:`attach_file_logger` -- add a project-level file logger
  :func:`get_logger`        -- get the package logger or a namespaced child
  :func:`set_level`         -- change the log level for all handlers

The shared package logger is rooted at ``"fastmdx"`` so all modules in
``fastmdxplora.*`` flow through one configuration.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Union

# ---------------------------------------------------------------------------
# Colors & icons for pretty console output
# ---------------------------------------------------------------------------
_COLOR = {
    "DEBUG": "\x1b[38;5;244m",
    "INFO": "\x1b[38;5;33m",
    "WARNING": "\x1b[38;5;214m",
    "ERROR": "\x1b[38;5;196m",
    "CRITICAL": "\x1b[48;5;196m\x1b[97m",
    "RESET": "\x1b[0m",
}
_ICON = {"DEBUG": "·", "INFO": "✓", "WARNING": "⚠", "ERROR": "✗", "CRITICAL": "‼"}


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------
class _PrettyFormatter(logging.Formatter):
    """Compact, human-friendly formatter. Color only when stderr is a TTY."""

    def __init__(self, use_color: bool):
        super().__init__()
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        lvl = record.levelname
        icon = _ICON.get(lvl, "·")
        msg = record.getMessage()
        if self.use_color:
            c, r = _COLOR.get(lvl, ""), _COLOR["RESET"]
            return f"{ts} {c}{icon} {lvl:<8}{r} {msg}"
        return f"{ts} {icon} {lvl:<8} {msg}"


class _PlainISOFormatter(logging.Formatter):
    """ISO-like formatter for file/audit logs.

    Produces ``YYYY-MM-DD HH:MM:SS,mmm - LEVEL - message`` matching the
    default look used by the rest of the FastMDXplora toolchain.
    """

    def __init__(self):
        fmt = "%(asctime)s - %(levelname)s - %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        s = super().format(record)
        msec = f",{int(record.msecs):03d}"
        # Append milliseconds after the seconds component (best-effort,
        # tolerant of locale/format variations).
        if " - " in s:
            left, rest = s.split(" - ", 1)
            if "," not in left[-4:]:
                left = left + msec
            s = " - ".join([left, rest])
        return s


# ---------------------------------------------------------------------------
# Module-level handler bookkeeping
# ---------------------------------------------------------------------------
_console_handler: logging.Handler | None = None
_file_handler: logging.Handler | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_level(val: Union[int, str, None]) -> int:
    """Coerce a level specifier (int, str, None) to a numeric logging level."""
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        try:
            return getattr(logging, val.upper())
        except AttributeError:
            pass
    return logging.INFO


def _resolve_style(default: str | None = None, *, env_wins: bool = True) -> str:
    """Return ``'pretty'`` or ``'plain'``.

    Resolution order:
      - If ``env_wins`` is True (the default) and ``FASTMDX_LOG_STYLE`` is
        set to a valid value, use it.
      - Otherwise prefer the API-supplied ``default``.
      - Otherwise fall back to ``"pretty"``.

    The console uses ``env_wins=True`` so users can override their CLI's
    appearance via the environment. The file logger uses ``env_wins=False``
    when its caller passes an explicit style (since file logs are
    audit-oriented and should stay plain even when a user customizes the
    console).
    """
    if env_wins:
        env = os.getenv("FASTMDX_LOG_STYLE", "").strip().lower()
        if env in ("pretty", "plain"):
            return env
    return default or "pretty"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def setup_console(
    level: int | str = logging.INFO,
    style: str | None = None,
) -> logging.Logger:
    """Initialize console logging for the ``fastmdx`` logger.

    Parameters
    ----------
    level : int or str, default INFO
        Initial log level. Overridden by ``FASTMDX_LOGLEVEL`` if set.
    style : str, optional
        ``"pretty"`` (default) or ``"plain"``. Overridden by ``FASTMDX_LOG_STYLE``
        if set.

    Notes
    -----
    Safe to call multiple times; the second call updates the level on the
    existing handler instead of adding a duplicate.

    Returns
    -------
    logging.Logger
        The package logger, already configured.
    """
    global _console_handler
    base = logging.getLogger("fastmdx")
    base.propagate = False

    env_level = os.getenv("FASTMDX_LOGLEVEL")
    base.setLevel(_to_level(env_level) if env_level else _to_level(level))

    style = _resolve_style(style)

    if _console_handler is None:
        handler = logging.StreamHandler(sys.stdout)
        if style == "plain":
            fmt: logging.Formatter = _PlainISOFormatter()
        else:
            use_color = sys.stdout.isatty() and not os.getenv("NO_COLOR")
            fmt = _PrettyFormatter(use_color)
        handler.setFormatter(fmt)
        handler.setLevel(base.level)
        base.addHandler(handler)
        _console_handler = handler
    else:
        _console_handler.setLevel(base.level)
    return base


def attach_file_logger(
    path: str | os.PathLike,
    level: int | str = logging.INFO,
    style: str | None = "plain",
) -> logging.Logger:
    """Attach (or replace) a per-project file logger.

    Parameters
    ----------
    path : path
        Path to the log file. Parent directories are created if needed.
    level : int or str, default INFO
        File log level. Overridden by ``FASTMDX_LOGLEVEL`` if set.
    style : str, default ``"plain"``
        Default ``"plain"`` since file logs are typically used for audit
        and grep; pass ``"pretty"`` to write the colored format.

    Returns
    -------
    logging.Logger
        The package logger, now with the file handler attached. The
        previous file handler (if any) is detached and closed.
    """
    global _file_handler
    base = logging.getLogger("fastmdx")
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    # Replace any prior file handler. This lets each new FastMDXplora
    # session redirect its file log without leaking handlers.
    if _file_handler is not None:
        try:
            base.removeHandler(_file_handler)
            _file_handler.close()
        except Exception:  # noqa: BLE001 -- cleanup must never raise
            pass
        _file_handler = None

    handler = logging.FileHandler(path, mode="a", encoding="utf-8")

    # File logs are audit-oriented: when an explicit style is supplied
    # (the typical case from the project orchestrator), respect it and
    # ignore the env override that's intended for the console.
    resolved_style = _resolve_style(style, env_wins=style is None)
    if resolved_style == "plain":
        fmt: logging.Formatter = _PlainISOFormatter()
    else:
        fmt = _PrettyFormatter(use_color=False)
    handler.setFormatter(fmt)

    env_level = os.getenv("FASTMDX_LOGLEVEL")
    handler.setLevel(_to_level(env_level) if env_level else _to_level(level))
    base.addHandler(handler)
    _file_handler = handler
    return base


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the package logger or a namespaced child.

    Examples
    --------
    >>> log = get_logger()
    >>> log.info("hello")              # logged as 'fastmdx'

    >>> log = get_logger("analysis.rmsd")
    >>> log.info("computed")            # logged as 'fastmdx.analysis.rmsd'
    """
    base = logging.getLogger("fastmdx")
    return base if name is None else base.getChild(name)


def set_level(level: int | str) -> None:
    """Programmatically change the log level for the package and all handlers."""
    lvl = _to_level(level)
    base = logging.getLogger("fastmdx")
    base.setLevel(lvl)
    for h in list(base.handlers):
        try:
            h.setLevel(lvl)
        except Exception:  # noqa: BLE001 -- best-effort
            pass
