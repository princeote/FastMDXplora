# Migrating to FastMDXplora

**FastMDAnalysis is now FastMDXplora** (Fully Automated SysTem for Molecular
Dynamics eXploration). FastMDXplora 2.0 is the direct successor to
FastMDAnalysis — the same automated, reproducibility-by-design philosophy,
now covering the *entire* molecular dynamics study rather than analysis alone.

If you previously used `fastmdanalysis` (or the interim `fastmdxplorer`
package), this guide covers everything you need to switch.

## What changed

| | Before | Now |
|---|---|---|
| Package name | `fastmdanalysis` / `fastmdxplorer` | `fastmdxplora` |
| Install | `pip install fastmdanalysis` | `pip install fastmdxplora` |
| Import | `import fastmdanalysis` / `import fastmdxplorer` | `import fastmdxplora` |
| CLI command | (various) | `fastmdx` (unchanged from the interim releases) |

The CLI command remains **`fastmdx`** — no change to your command-line usage.

## Installation

```bash
pip install fastmdxplora
# optional extras:
pip install "fastmdxplora[ligand]"   # OpenFF small-molecule parameterization
pip install "fastmdxplora[plumed]"   # PLUMED enhanced sampling
```

## Updating your code

The only required change is the import name:

```python
# Before
import fastmdanalysis          # or: import fastmdxplorer

# Now
import fastmdxplora
```

The public API surface is preserved. If you prefer a short alias in code:

```python
import fastmdxplora as fastmdx
```

## Your old installs still work (for now)

To avoid breaking existing environments, the former names remain on PyPI as
**redirect packages** that install `fastmdxplora` and re-export its namespace:

- `pip install fastmdanalysis` → installs `fastmdxplora`, emits a deprecation notice
- `pip install fastmdxplorer` → installs `fastmdxplora`, emits a deprecation notice
- `pip install fastmdx` → installs `fastmdxplora` (this remains a supported short alias, not deprecated)

These redirects will not receive further updates. Please migrate to
`fastmdxplora` at your convenience.

## What's new in 2.0 (beyond FastMDAnalysis)

FastMDXplora extends the original trajectory-analysis scope to a full,
single-command MD pipeline:

- **Setup** — PDBFixer preparation, named force fields, OpenFF ligand
  parameterization with a pose clash check
- **Simulation** — OpenMM with selectable integrators/barostat, and optional
  **PLUMED enhanced sampling** (metadynamics, umbrella sampling, …) on the
  production stage
- **Analysis** — the full FastMDAnalysis suite (RMSD, RMSF, Rg, SASA, SS,
  Q-value, H-bonds, dihedrals, clustering, dimensionality reduction) plus
  **protein-ligand analyses** (ligand pose RMSD, protein-ligand contacts and
  binding-site fingerprint, protein-ligand H-bonds, ligand RMSF), auto-detected
  for complexes
- **Report** — automated Markdown report, slide deck, and project bundle

## Citation

The foundational work remains:

> Aina, A.; Kwan, D. *FastMDAnalysis: Software for Automated Analysis of
> Molecular Dynamics Trajectories.* J. Comput. Chem. **2026**, 47, e70350.
> DOI: [10.1002/jcc.70350](https://doi.org/10.1002/jcc.70350)
