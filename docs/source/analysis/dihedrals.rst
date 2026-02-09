Dihedral Angles (Phi/Psi/Omega)
===============================

This module adds backbone dihedral angle analysis using MDTraj's
``compute_phi``, ``compute_psi``, and ``compute_omega`` utilities. It computes
per-residue average dihedral angles across the trajectory using circular
statistics, then generates plots including a Ramachandran plot for the
combined phi/psi analysis.

What it computes
----------------
- **Phi (φ)**: dihedral around the N–CA bond
- **Psi (ψ)**: dihedral around the CA–C bond
- **Omega (ω)**: dihedral around the peptide bond (C–N)

Angles are computed for each frame and averaged per residue using a circular
mean to respect angle periodicity.

Outputs
-------
Each analysis writes a data table and plot into its output folder:

- ``phi_output/phi_avg.dat`` and ``phi_output/phi_avg.png``
- ``psi_output/psi_avg.dat`` and ``psi_output/psi_avg.png``
- ``omega_output/omega_avg.dat`` and ``omega_output/omega_avg.png``
- ``dihedrals_output/ramachandran.png`` (combined analysis)

API usage
---------

Compute per-residue averages and plots:

::

   from fastmdanalysis import FastMDAnalysis

   fastmda = FastMDAnalysis("traj.dcd", "top.pdb")

   phi = fastmda.phi()
   phi.plot()

   psi = fastmda.psi()
   psi.plot()

   omega = fastmda.omega()
   omega.plot()

   # Combined analysis + Ramachandran plot
   dihedrals = fastmda.dihedrals()
   dihedrals.plot()  # Ramachandran

  CLI
  ---

  ::

     fastmda phi -traj traj.dcd -top top.pdb \
       --residues 1 5 10 \
       --units degrees \
       -o phi_output

     fastmda psi -traj traj.dcd -top top.pdb \
       --residues 1 5 10 \
       --units degrees \
       -o psi_output

     fastmda omega -traj traj.dcd -top top.pdb \
       --residues 1 5 10 \
       --units degrees \
       -o omega_output

     fastmda dihedrals -traj traj.dcd -top top.pdb \
       --types phi psi omega \
       --residues 1 5 10 \
       --units degrees \
       -o dihedrals_output

Common parameters
-----------------

- ``residues``: optional residue indices (0-based) to analyze/plot
- ``units``: ``"degrees"`` (default) or ``"radians"``
- ``highlight_residues`` (plots): residues to highlight in a different color

Examples:

::

   # Plot only residues 5–10
   fastmda.phi().plot(residues=[5, 6, 7, 8, 9, 10])

   # Highlight key residues
   fastmda.psi().plot(highlight_residues=[3, 12, 17])

Ramachandran plot
-----------------

The combined analysis generates a Ramachandran plot of average psi vs. phi
angles per residue. Points are colored by residue index to help identify
outliers or region-specific conformations.

Edge cases and notes
--------------------
- Terminal residues may lack defined angles; these are handled as ``NaN`` and
  excluded from circular averaging.
- Non-protein trajectories may yield no dihedral angles; a clear error is
  raised in that case.
- Averages use circular mean to avoid artifacts around ±π/±180°.
