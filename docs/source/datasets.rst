Datasets
========

FastMDAnalysis ships with a curated Trp-cage molecular dynamics dataset that
underpins the manuscript examples and tutorials. It lives in ``data/`` and is
exposed through ``fastmdanalysis.datasets`` (``TrpCage`` class plus the
``trp_cage`` shortcut).

Attributes available on the dataset helper:

``traj`` / ``top``
	Absolute paths to trajectory (``.dcd``) and topology (``.pdb``) files. Paths
	are resolved via :func:`fastmdanalysis.datasets._get_data_path`, so installs
from PyPI and editable checkouts behave the same.

``time_step``
	Simulation timestep in picoseconds.

``force_field`` / ``integrator`` / ``md_engine``
	Metadata copied from the original simulations; useful for reporting or
	selecting analysis parameters.

``temperature`` / ``pressure``
	Nominal ensemble settings (Kelvin, atm/bar).

Trp-cage
--------

* **Files:** ``data/trp_cage.dcd``, ``data/trp_cage.pdb``
* **Frames:** 1 000 snapshots sampled every 10 ps (10 ns total)
* **Force field / engine:** CHARMM36m, OpenMM 8.2
* **Use cases:** Quickstart notebooks, CLI examples, hydrogen-bond and SASA
	tutorials

The helper attributes ``trp_cage.traj`` and ``trp_cage.top`` resolve to absolute
paths, making it easy to run tutorials from any working directory::

	 from fastmdanalysis.datasets import trp_cage
	 fastmda = FastMDAnalysis(trp_cage.traj, trp_cage.top)

Best practices
--------------


* Call ``traj.topology.create_standard_bonds()`` when an analysis needs bond
	definitions (hydrogen bonds, secondary structure).
* Use the ``--frames`` CLI option or the ``frames`` constructor argument to
	subsample long trajectories without editing the source files.
* Treat this dataset as a smoke test; real research trajectories can be passed
	via single paths, comma-separated strings, lists, or glob patterns thanks to
	:func:`FastMDAnalysis.utils.load_trajectory`.
