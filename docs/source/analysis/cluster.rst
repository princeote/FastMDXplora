.. currentmodule:: FastMDAnalysis.analysis.cluster

Clustering
==========

The :class:`ClusterAnalysis` module groups trajectory frames into discrete
states using the algorithms summarised in Section 3.7 of the manuscript. It
supports DBSCAN on precomputed RMSD distances as well as KMeans and hierarchical
clustering on flattened coordinates.

Feature Construction
--------------------

- **Distance matrix** — For DBSCAN the module computes an :math:`N \times N`
  symmetric RMSD matrix (nanometres) using the selected atoms.
- **Coordinate matrix** — For KMeans and hierarchical clustering it reshapes
  the selected atomic coordinates into a 2D feature matrix of shape
  ``(n_frames, n_atoms * 3)``.

Available Methods
-----------------

- ``dbscan`` — Density-based clustering using ``eps`` (nm) and
  ``min_samples``.
- ``kmeans`` — Lloyd’s algorithm, requires ``n_clusters``.
- ``hierarchical`` — Ward linkage with ``n_clusters`` controlling the final cut.

Implementation Highlights
-------------------------

- Accepts a single method string or list; ``methods=["dbscan","kmeans"]``
  will run both and return a combined results dictionary.
- Automatically generates plots for each method, including population bars,
  trajectory histograms/scatters, and (where relevant) distance matrices or
  dendrograms.
- Labels are shifted to one-based indexing for consistency with the manuscript
  figures.

Usage
-----

**API**

.. code-block:: python

   from FastMDAnalysis import FastMDAnalysis

   fastmda = FastMDAnalysis("traj.dcd", "top.pdb", atoms="protein and name CA")
   cluster = fastmda.cluster(methods=["dbscan", "kmeans"], eps=0.45, min_samples=10, n_clusters=4)
   results = cluster.run()
   dbscan_plots = results["dbscan"]["trajectory_histogram"]

**CLI**

.. code-block:: bash

   fastmda cluster -traj traj.dcd -top top.pdb --atoms "protein and name CA" \
      --methods dbscan kmeans --eps 0.45 --min_samples 10 --n_clusters 4 -o analysis/cluster

Outputs
-------

Each requested method populates a key within ``cluster_output``:

- ``<method>_pop.png`` — bar plot of cluster populations.
- ``<method>_traj_hist.png`` and ``<method>_traj_scatter.png`` — frame-wise
  cluster assignments.
- ``dbscan_distance_matrix.png`` — RMSD heatmap (DBSCAN only).
- ``hierarchical_dendrogram.png`` — Ward dendrogram (hierarchical only).
- ``cluster.log`` — aggregated log file with parameter values.

Interpretation Tips
-------------------

- Use DBSCAN to detect rare conformations without predefining cluster counts; a
  label of zero indicates noise frames that failed density thresholds.
- Compare population plots across methods to ensure the chosen ``n_clusters``
  reflects the intrinsic dimensionality of the data.

Troubleshooting
---------------

- ``AnalysisError: ... n_clusters must be provided`` means you invoked KMeans or
  hierarchical clustering without specifying ``n_clusters``.
- If DBSCAN reports a single cluster, decrease ``eps`` or increase
  ``min_samples`` until the density threshold separates distinct states.
- Hierarchical clustering scales as :math:`O(N^2)`; use frame sub-sampling for
  very long trajectories to avoid memory issues.
