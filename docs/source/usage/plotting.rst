Plot Styling Reference
=======================

FastMDAnalysis centralises all figure layout tweaks in
``fastmdanalysis.utils.plotting`` so CLI and API runs ship with consistent,
publication-ready PNGs. This page summarises the helpers and shows how to
customise them via ``options`` dictionaries or CLI ``--options`` files.

Core helpers
------------

``auto_ticks(values, max_ticks=8, integer=False, include_zero=False)``
    Computes evenly spaced tick candidates given sample values. Integer mode
    snaps to whole numbers and enforces monotonic spacing (see
    ``tests/test_utils_plotting.py``).

``apply_slide_style(ax, ...)``
    Annotates an axis with fonts, tick density, rotations, and optional
    zero padding. Common keyword arguments:

    * ``x_values`` / ``y_values`` – raw data to derive density for auto ticks.
    * ``x_ticks`` / ``y_ticks`` – explicit tick lists (auto detection is skipped).
    * ``integer_x`` – request integer-only ticks on the x-axis (e.g., residue IDs).
    * ``tick_size`` / ``label_size`` / ``title_size`` – fonts in points.
    * ``zero_x`` – pad the left limit slightly below zero for positive-only data.
    * ``x_tick_rotation`` – manual rotation to prevent overlap.

    The helper stores the chosen tick and label sizes on the axis object so other
    utilities (like match_colorbar_font) can reuse them.

``match_colorbar_font(colorbar, axes)``
    Syncs colorbar tick/label fonts with the parent axes. Falls back to whichever
    axis still has visible ticks (``x`` or ``y``) so heatmaps remain legible even
    when one axis is hidden.

Connecting to CLI/API options
-----------------------------

Every analysis accepts a dictionary of plotting keywords that bubble down into
``apply_slide_style``. Examples:

.. code-block:: yaml

    # CLI options file
    sasa:
      tick_step_avg: 5          # thins average SASA residue ticks
      color_total: "#2c3e50"
    rmsf:
      tick_step: 4
      rotate: 45
    dimred:
      title_pca: "PCA (Publication)"
      max_ticks: 6

.. code-block:: python

    fastmda.analyze(
        include=["sasa", "rmsf"],
        options={
            "sasa": {"tick_step_avg": 5, "zero_x": True},
            "rmsf": {"tick_step": 4, "rotate": 45},
        },
    )

Most ``tick_step*`` arguments ultimately constrain the ``x_ticks`` fed into
``apply_slide_style``. Colorbar-specific tweaks are available under each module's
API (see ``docs/source/analysis`` pages for module-specific keywords).

Testing the helpers
-------------------

Unit tests under ``tests/test_utils_plotting.py`` validate integer tick spacing,
font scaling, zero-padding, and colorbar inheritance. If you change the helper
behaviour, run:

.. code-block:: bash

    pytest tests/test_utils_plotting.py

For end-to-end regressions, ``tests/test_analysis_plotting_styles.py`` exercises
multiple analyses to ensure CLI/API options still propagate correctly.
