# FastMDAnalysis/src/fastmdanalysis/utils/__init__.py
from .io import load_trajectory
from .slideshow import gather_figures, slide_show
from .options import OptionsForwarder, forward_options, apply_alias_mapping

__all__ = [
    "load_trajectory",
    "gather_figures",
    "slide_show",
    "OptionsForwarder",
    "forward_options",
    "apply_alias_mapping",
]

