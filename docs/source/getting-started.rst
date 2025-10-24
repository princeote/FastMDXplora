Getting Started
===============

This guide distills the practical setup instructions discussed in the
FastMDAnalysis manuscript. It walks through installation options, describes the
bundled benchmark datasets, and demonstrates one-minute API and CLI workflows.

Prerequisites
-------------

FastMDAnalysis targets Python 3.8 or newer and depends on
``mdtraj``, ``numpy``, ``matplotlib``, and ``scikit-learn``. The optional
documentation toolchain requires Sphinx and the Read the Docs theme. GPU
hardware is **not** required; all analyses run on a standard laptop.

Installation
------------

From a cloned repository, choose one of the following modes:

**Standard install** (locks files in ``site-packages``)::

   python -m pip install .

**Editable install** (preferred during development)::

   python -m pip install -e .

The editable mode mirrors the workflow used in the manuscript: it keeps the
package importable while allowing you to modify source files in-place.

Optional documentation dependencies – useful if you want to rebuild the Read
the Docs site locally – live in ``docs/requirements.txt``::

   python -m pip install -r docs/requirements.txt

Sample data
-----------

Small trajectories for ubiquitin and Trp-cage ship with the project under
``data/``. The helper objects ``FastMDAnalysis.datasets.ubiquitin`` and
``FastMDAnalysis.datasets.trp_cage`` expose absolute paths to these files so
tests and tutorials run without extra downloads.

Quick start (Python API)
------------------------

.. code-block:: python

   from FastMDAnalysis import FastMDAnalysis
   from FastMDAnalysis.datasets import trp_cage

   fastmda = FastMDAnalysis(trp_cage.traj, trp_cage.top,
                             frames=(0, -1, 10), atoms="protein")
   rmsd = fastmda.rmsd(reference_frame=0)
   print(rmsd.data[:5])  

The call caches the trajectory (honouring the frame stride and atom selection),
computes RMSD relative to frame 0, stores the results in ``rmsd.data`` and saves
``rmsd_output/rmsd.dat`` plus ``rmsd_output/rmsd.png``.

Quick start (CLI)
-----------------

After installation, the ``fastmda`` entry point exposes the same analyses. This
command mirrors the API example above::

   fastmda rmsd \
      --trajectory "data/trp_cage.dcd" \
      --topology "data/trp_cage.pdb" \
      --frames "0,-1,10" \
      --atoms "protein" \
      --reference-frame 0

Logs land in ``rmsd_output/rmsd.log`` and document the parameter set, library
versions, and timing – part of the reproducibility focus highlighted in the
paper.

Where to next
-------------

* Read :doc:`datasets` for metadata about the bundled trajectories.
* Follow :doc:`usage/api` and :doc:`usage/cli` for deeper walkthroughs.
* Explore :doc:`analysis/index` to understand how each analysis module is
  implemented and which figures it produces.
