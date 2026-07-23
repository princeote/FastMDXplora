# Quickstart

Prepare a local structure:

```bash
python -m driftmd prepare --structure examples/tiny.pdb --output runs/prepared
```

Analyze an existing trajectory/topology pair:

```bash
python -m driftmd analyze \
  --trajectory existing/trajectory.dcd \
  --topology existing/topology.pdb \
  --output runs/analyzed
```

Build a report from an output directory:

```bash
python -m driftmd report --output runs/analyzed --title "Trajectory Review"
```

Run selected phases together:

```bash
python -m driftmd run \
  --output runs/analysis_report \
  --include analyze report \
  --trajectory existing/trajectory.dcd \
  --topology existing/topology.pdb
```

Real OpenMM simulation requires the optional `md` extra and is not part of the
normal fast test suite.
