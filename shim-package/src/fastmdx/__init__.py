"""`fastmdx` is the PyPI alias for FastMDXplora.

The canonical package is `fastmdxplora`. This alias exists so that
`pip install fastmdx` works for users who type the shorter name.

Recommended usage in code:

    import fastmdxplora as fastmdx       # preferred

The bare `import fastmdx` form also works and re-exports the
`fastmdxplora` namespace.
"""

import warnings

# Re-export the canonical package's public surface.
from fastmdxplora import *  # noqa: F401,F403
from fastmdxplora import (  # noqa: F401
    FastMDXplora,
    __author__,
    __citation__,
    __doi__,
    __expansion__,
    __license__,
    __version__,
)

# Friendly notice when the alias is imported directly.
warnings.warn(
    "Importing 'fastmdx' is supported as a PyPI/import alias for "
    "'fastmdxplora'. The recommended idiom is "
    "`import fastmdxplora as fastmdx`. The CLI command is also `fastmdx`.",
    stacklevel=2,
)
