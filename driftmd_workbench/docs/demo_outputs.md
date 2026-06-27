# Demo Output Generation

The smoke runner processes small local PDB files and writes CSV/JSON summaries.
It does not run heavy MD.

```bash
python scripts/run_drift_smoke.py \
  --output-root runs/demo_smoke \
  --continue-on-error \
  examples/tiny.pdb
```

Review outputs:

```bash
find runs/demo_smoke -maxdepth 4 -type f | sort
cat runs/demo_smoke/summary.csv
```

Create a package:

```bash
mkdir -p private_reports
zip -r private_reports/driftmd_demo_outputs.zip runs/demo_smoke README.md docs
```
