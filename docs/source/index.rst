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
* **One trajectory load.** ``FastMDAnalysis.FastMDAnalysis`` caches the
   trajectory once, applies optional frame and atom selections, and reuses those
   slices across analyses to avoid redundant I/O.
* **Consistent outputs.** Every analysis writes numeric ``.dat`` files,
   publication-ready PNGs, and a timestamped log inside ``<analysis>_output`` by
   default, promoting reproducibility.
* **Friendly interfaces.** Choose the Python API for scripted workflows or the
   ``fastmda`` CLI for quick batch runs; both routes exercise the same analysis
   classes.

Workflow at a glance
--------------------

1. Install the package (editable or standard) and optional doc requirements.
2. Load a trajectory plus topology through the API or provide them to the CLI.
3. Run analyses, inspect the saved artifacts, or compose new ones using the
    base-class pattern.
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
