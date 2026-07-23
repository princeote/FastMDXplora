# Analysis-only Reporting

DriftMD can analyze existing files without running preparation or simulation.
Use this when trajectory/topology files already exist:

```bash
python -m driftmd run \
  --output runs/existing_trajectory_report \
  --include analyze report \
  --trajectory data/trajectory.dcd \
  --topology data/topology.pdb \
  --title "Existing Trajectory Report"
```

The manifest records only the phases that ran. The report and slide outline
state that preparation and simulation were not run in the current workflow.
