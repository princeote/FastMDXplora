# The four phases

A FastMDXplora study runs as four phases in sequence. Each writes to its own
subdirectory under the project output root and records a structured manifest
of the parameters, software versions, and artifacts it produced, so every
result is traceable to the options that generated it.

```
  setup  ->  simulation  ->  analysis  ->  report
```

You can run the whole pipeline at once, or restrict it to specific phases with
`--include` / `--exclude` (CLI) or the equivalent API arguments.

## setup

Prepares a raw structure into a simulation-ready system. PDBFixer repairs the
input (missing atoms and residues, protonation at a chosen pH), then the
system is solvated in a water box and neutralized with ions. A named force
field is selected (CHARMM36 by default; AMBER variants and an OpenFF
small-molecule path are available). When a ligand is supplied, it is
parameterized with OpenFF and its bound pose is clash-checked before the run
proceeds.

Key outputs: `prepared.pdb`, `solvated.pdb`, `topology.pdb`, `system.xml`,
`setup_parameters.json`.

## simulation

Runs molecular dynamics with OpenMM: energy minimization, NVT and NPT
equilibration, then production. Integrator, thermostat/barostat, step counts,
and reporter intervals are all configurable. Optional PLUMED enhanced sampling
(metadynamics, umbrella sampling, steered MD) is applied to the production
stage, leaving equilibration unbiased.

Key outputs: `production.dcd`, `state_final.xml`, `simulation_parameters.json`
(plus `COLVAR`, `HILLS`, `plumed.dat` when PLUMED is enabled).

## analysis

Computes structural and dynamic metrics from the trajectory and renders a
figure for each. The standard suite covers RMSD, RMSF, radius of gyration,
hydrogen bonds, secondary structure, clustering, dimensionality reduction,
Q-value, and dihedrals. When a ligand is present, protein-ligand analyses run
automatically: ligand pose RMSD, protein-ligand contacts with a binding-site
fingerprint, protein-ligand hydrogen bonds, and ligand RMSF. An analysis
scope (`solute`, `protein`, `ligand`, `all`) controls which atoms each metric
considers.

Key outputs: `<analysis>/*.dat`, `<analysis>/*.png`, `analysis_manifest.json`.

## report

Assembles the results into shareable deliverables: a structured Markdown
report, a slide deck, and a self-contained project bundle.

Key outputs: `report.md`, `slides.pptx`, `project_bundle.zip`.
