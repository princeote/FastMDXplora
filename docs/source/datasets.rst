Datasets
========

FastMDAnalysis ships with two curated molecular dynamics datasets that underpin
the manuscript examples and unit tests. They live in ``data/`` and are exposed
through ``FastMDAnalysis.datasets`` for convenience.

Ubiquitin
---------

* **Files:** ``data/ubiquitin.dcd`` (trajectory), ``data/ubiquitin.pdb``
	(topology)
* **Frames:** 10 000 snapshots sampled every 10 ps (100 ns total)
* **Force field / engine:** CHARMM36m, GROMACS
* **Use cases:** Full regression test suite, clustering benchmarks, RMSD/RMSF
	demonstrations

Example usage::

	 from fastmdanalysis.datasets import ubiquitin
	 print(ubiquitin.traj)
	 print(ubiquitin.top)

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
* Treat these datasets as smoke tests; real research trajectories can be passed
	via single paths, comma-separated strings, lists, or glob patterns thanks to
	:func:`FastMDAnalysis.utils.load_trajectory`.
