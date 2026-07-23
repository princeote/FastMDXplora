# Windows PowerShell Examples

Run with the module entrypoint:

```powershell
python -m driftmd info
python -m driftmd --help
```

Analysis/report-only workflow:

```powershell
python -m driftmd run `
  --output runs\analysis_report `
  --include analyze report `
  --trajectory existing\trajectory.dcd `
  --topology existing\topology.pdb `
  --title "Existing Trajectory Report"
```

Package demo outputs:

```powershell
New-Item -ItemType Directory -Force private_reports
Compress-Archive -Path runs\demo_smoke, README.md, docs -DestinationPath private_reports\driftmd_demo_outputs.zip -Force
```
