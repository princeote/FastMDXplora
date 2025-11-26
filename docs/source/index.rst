FastMDAnalysis documentation
============================

FastMDAnalysis is a Python toolkit for automated molecular dynamics (MD)
trajectory analysis. It wraps the trajectory I/O strengths of MDTraj and the
machine-learning primitives of scikit-learn in a coherent API and command-line
interface so that routine structural metrics, clustering tasks, and embeddings
can be executed without bespoke scripts. The guides collected here translate
the accompanying research manuscript into practical instructions for installing
the package, running analyses, and extending the code base.

Highlights
----------

* **All-in-one analyses.** Built-in modules cover RMSD, RMSF, radius of
   gyration, hydrogen bonds, secondary structure, SASA, clustering, and
   dimensionality reduction – the same portfolio described in the paper.
* **Publication-ready figures by default.** A shared styling toolkit trims
   ticks, balances fonts, pads zero-based axes, and keeps colorbars synced so
   the PNGs that ship with each analysis are usable directly in manuscripts and
   slide decks.
* **One trajectory load.** ``FastMDAnalysis.FastMDAnalysis`` caches the
   trajectory once, applies optional frame and atom selections, and reuses those
   slices across analyses to avoid redundant I/O.
* **Consistent outputs.** Every analysis writes numeric ``.dat`` files,
   publication-ready PNGs, and a timestamped log inside ``<analysis>_output`` by
   default, promoting reproducibility.
* **Friendly interfaces.** Choose the Python API for scripted workflows or the
   ``fastmda`` CLI for batch runs; both routes share the same analysis classes
   and plotting options.

Workflow at a glance
--------------------

1. Install the package (editable or standard) and optional doc requirements.
2. Load a trajectory plus topology through the API or provide them to the CLI.
3. Run analyses directly (``fastmda.<analysis>()`` or ``fastmda analyze``), or
   compose new modules using the base-class pattern; generated plots inherit
   the publication-focused styling defaults automatically.
4. Regenerate these docs locally with Sphinx or publish to Read the Docs using
    the supplied configuration.

The sections below map to that journey: start with quickstart material, explore
analysis-specific references, and finish with contribution guidelines and API
details.


.. toctree::
   :maxdepth: 2
   :caption: Guides

   getting-started
   usage/api
   usage/cli
   usage/plotting
   usage/outputs
   datasets
   contributing

.. toctree::
   :maxdepth: 2
   :caption: Analyses

   analysis/index

.. toctree::
   :maxdepth: 1
   :caption: API

   api/index
