"""Sphinx configuration for FastMDAnalysis documentation."""
from __future__ import annotations

import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

project = "FastMDAnalysis"
copyright = f"{datetime.now():%Y}, Adekunle Aina"
author = "Adekunle Aina"

release = "0.1.0"
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

autosummary_generate = True
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}

autodoc_mock_imports = [
    "mdtraj",
    "numpy",
    "matplotlib",
    "matplotlib.pyplot",
    "sklearn",
    "scipy",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", {}),
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_theme_options = {
    "collapse_navigation": False,
    "navigation_depth": 4,
}
primary_domain = "py"
