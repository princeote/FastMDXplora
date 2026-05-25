"""``fastmdxplorer`` has been renamed to **fastmdxplora**.

The canonical package is now ``fastmdxplora`` (Fully Automated SysTem for
Molecular Dynamics eXploration). This package is a thin redirect that installs
``fastmdxplora`` and re-exports its namespace, so existing
``pip install fastmdxplorer`` users are not broken.

Please migrate to the new name:

    pip install fastmdxplora
    import fastmdxplora
"""

import warnings

warnings.warn(
    "The 'fastmdxplorer' package has been renamed to 'fastmdxplora'. "
    "Please install and import 'fastmdxplora' instead. This redirect "
    "package will not receive further updates.",
    DeprecationWarning,
    stacklevel=2,
)

from fastmdxplora import *  # noqa: F401,F403,E402

try:
    from fastmdxplora import __version__  # noqa: F401
except Exception:  # pragma: no cover
    __version__ = "2.0.0"
