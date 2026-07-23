# DriftMD Workbench

DriftMD Workbench is a small Python package for staging molecular-dynamics
workflow outputs, analyzing existing trajectory/topology files, and generating
phase-aware reports.

The first version is intentionally compact. It supports local structure files,
selected workflow phases, analysis-only/report-only runs, manifest recording,
Markdown reports, slide outlines, optional PowerPoint slides, and zip bundles.

## Install for Development

```bash
cd driftmd_workbench
python -m pip install -e ".[test]"
```

Optional extras:

```bash
python -m pip install -e ".[slides]"
python -m pip install -e ".[md]"
```

## Verify

```bash
driftmd info
python -m driftmd info
python -m driftmd --help
```

Use `python -m driftmd ...` if the `driftmd` console command is not on PATH.

## Analysis-only + Report-only Mode

```bash
python -m driftmd run \
  --output runs/analysis_report \
  --include analyze report \
  --trajectory existing/trajectory.dcd \
  --topology existing/topology.pdb \
  --title "Existing Trajectory Report"
```

The generated report explicitly states that preparation and simulation were not
run in the current workflow.

## Demo Output Package

```bash
python scripts/run_drift_smoke.py \
  --output-root runs/demo_smoke \
  --continue-on-error \
  examples/tiny.pdb

mkdir -p private_reports
zip -r private_reports/driftmd_demo_outputs.zip runs/demo_smoke README.md docs
```

## Main Outputs

- `run_manifest.json`
- `analysis/drift_score.csv`
- `analysis/drift_score.png`
- `analysis/analysis_manifest.json`
- `report/report.md`
- `report/slides_outline.md`
- `report/slides.pptx` when `python-pptx` is installed
- `report/workflow_bundle.zip`
