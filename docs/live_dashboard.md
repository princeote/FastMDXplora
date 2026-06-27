# Live simulation dashboard

FastMDXplora has two dashboard views:

- **Results Dashboard**: the static `report/dashboard.html` written after
  analysis/report. It shows completed plots, generated files, report links,
  slides, and project bundles.
- **Live Simulation**: a local-only localhost view that watches lightweight
  telemetry files while a simulation is running.

The live dashboard does not replace the static report dashboard. It adds a
separate monitoring view for progress, health messages, recent events, and
available energy/temperature samples.

## Start the local server

From a run output folder:

```bash
fastmdx dashboard serve --output local_runs/my_run
```

If the `fastmdx` console script is not on PATH, use the module entrypoint:

```bash
python -m fastmdxplora.cli.main dashboard serve --output local_runs/my_run
```

PowerShell:

```powershell
python -m fastmdxplora.cli.main dashboard serve --output local_runs\my_run
```

By default the server binds to `127.0.0.1:8765`, so it is local to your
machine:

```text
Live dashboard running at http://127.0.0.1:8765
Watching: local_runs/my_run
Press Ctrl+C to stop.
```

Use `--port` if that port is already busy:

```bash
fastmdx dashboard serve --output local_runs/my_run --port 8770
```

## Record live telemetry during simulation

Enable telemetry on simulation runs:

```bash
fastmdx explore --system protein.pdb \
  --output local_runs/my_run \
  --include setup simulation \
  --simulate-live-telemetry \
  --simulate-telemetry-interval 1000
```

The simulation phase writes:

- `simulation/live_status.json`
- `simulation/live_metrics.csv`
- `simulation/live_events.log`

Telemetry writing is intentionally lightweight and safe. If these files cannot
be written, the simulation continues and the live dashboard simply reports
unavailable data.

## What the Live Simulation tab shows

The live view polls the local output directory every few seconds and displays:

- current stage and status
- current step and planned step count when known
- frame count when known
- elapsed wall time and simulation time
- OpenMM platform
- latest checkpoint path when available
- energy/temperature trends when telemetry has those values
- recent events from `live_events.log`
- protein preview image when a topology/PDB is available
- optional local interactive 3D preview when a topology/PDB is available
- plain-language health explanations

Metrics are not invented. If a value has not been written yet, the dashboard
shows `not available`.

## Protein preview

The Live Simulation tab tries to show a protein image as soon as a usable
structure file exists. It checks common run artifacts such as
`simulation/topology.pdb`, `setup/topology.pdb`, `setup/solvated.pdb`, and
the original system path recorded in `manifest.json`.

If PyMOL is installed, FastMDXplora uses it for a cartoon/ribbon render and
adds extra camera padding so the whole protein is visible in the dashboard
frame. Install PyMOL from conda-forge:

```bash
conda install -c conda-forge pymol-open-source
```

or with micromamba:

```bash
micromamba install -c conda-forge pymol-open-source
```

Protein preview generation requires PyMOL so the static image is an actual
cartoon/ribbon render rather than a schematic placeholder. Preview files are
written to `report/dashboard_assets/protein_preview.png` when report assets
exist, or to `simulation/protein_preview.png` during setup/simulation-only
runs.

The preview panel uses a local vendored 3Dmol.js bundle for **Interactive 3D**
when a structure file exists. That tab shows a rotatable cartoon representation
with spectrum coloring and does not require a CDN or internet access. Use
**Spin** to call the real 3Dmol viewer spin control, **Reset view** to zoom back
to the full protein, and mouse controls to rotate or zoom.

The **PyMOL Preview** tab remains available whenever the PyMOL PNG exists. That
tab shows the PyMOL-rendered cartoon/ribbon image. If the bundled 3Dmol viewer
asset is unavailable, the dashboard can fall back to a schematic CA/backbone
trace, but that fallback is labeled as a schematic fallback, not as PyMOL. If no
usable structure file exists yet, the panel says that the preview is
unavailable. The panel polls for updates and includes a **Regenerate preview**
button.

The Results Dashboard tab also refreshes while the server is open. If analysis
or report artifacts are generated after the server starts, the Generated Files,
Analysis Plots, Report Artifacts, and embedded dashboard view update without
restarting the server. Use the **Refresh** button for an immediate rescan.

## Health messages

FastMDXplora classifies common live issues:

- **Numerical instability**: NaN/Inf positions or energies. Try a smaller
  timestep, lower temperature, stronger friction, the gentle preset, or check
  the input structure for clashes.
- **Energy spike**: energy changed sharply between samples. This can indicate
  bad contacts, an unstable timestep, or pressure/temperature coupling issues.
- **Temperature drift/spike**: temperature is far from the target. Try gentler
  heating, stronger friction, or a smaller timestep.
- **Stale telemetry**: no live update was seen recently. The simulation may be
  slow, paused, or crashed.

## Static dashboard behavior

Opening `report/dashboard.html` after a run still shows the completed Results
Dashboard. It now also includes a Live Simulation sidebar entry:

- If telemetry exists, it shows the last recorded status.
- If telemetry does not exist, it explains how to start
  `fastmdx dashboard serve --output ...`.

## Demo or preview output

For a small demo run, use the gentle preset and telemetry:

```bash
fastmdx explore --system local_pdbs/1L2Y.pdb \
  --output local_runs/live_demo \
  --include setup simulation analysis report \
  --simulate-preset gentle \
  --simulate-live-telemetry
```

Then serve the output:

```bash
fastmdx dashboard serve --output local_runs/live_demo
```
