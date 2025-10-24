# FastMDAnalysis
Fully Automated System for Molecular Dynamics Trajectory Analysis

FastMDAnalysis allows you to perform a variety of MD analyses in a single line of code.

FastMDAnalysis is designed to simplify your workflow by allowing you to load a trajectory once (with options for frame and atom selection) and then run multiple analyses without repeating input file details. 

FastMDAnalysis automatically generates publication-ready figures (with options for customization).

FastMDAnalysis provides a unified Python API as well as a command‐line interface (CLI). 


# Documentation

Full documentation with extensive usage examples can be found at https://fastmdanalysis.readthedocs.io

[![Docs](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://fastmdanalysis.readthedocs.io/en/latest/)

# Features

- **rmsd**: Calculate Root-Mean-Square Deviation relative to a reference frame.
- **rmsf**: Compute per-atom Root-Mean-Square Fluctuation.
- **rg**: Determine the Radius of Gyration for each frame.
- **hbonds**: Detect and count hydrogen bonds using the Baker-Hubbard algorithm.
- **ss**: Compute Secondary Structure (SS) assignments using DSSP with a discrete heatmap.
- **cluster**: Perform clustering on trajectory frames:
  - KMeans
  - DBSCAN
  - Hierarchical
- **sasa**: Compute Solvent Accessible Surface Area (SASA) in multiple ways:
  - Total SASA vs. frame.
  - Per-residue SASA vs. frame (heatmap).
  - Average per-residue SASA (bar plot).
- **dimred**: Perform dimensionality reduction to project high-dimensional data into 2D:
  - PCA
  - MDS
  - t-SNE

# Installation

Navigate to the root directory of the package (the directory containing `setup.py`).

For a standard installation, run:
```bash
pip install .
```

For development (editable) mode, run:
```bash
pip install -e .
```

# Usage

## Python API

Instantiate a FastMDAnalysis object with your trajectory and topology file paths. Optionally, specify frame selection and atom selection. Frame selection is provided as a tuple (start, stop, stride). Negative indices (e.g., -1 for the last frame) are supported. If no options are provided, the entire trajectory and all atoms are used by default.

### RMSD Analysis:

```python
from fastmdanalysis import FastMDAnalysis

fastmda = FastMDAnalysis("traj.dcd", "top.pdb")

# Run RMSD analysis 
rmsd_analysis = fastmda.rmsd()

```



## Command-Line Interface (CLI)
After installation, you can run FastMDAnalysis from the command line using the fastmda command. Global options allow you to specify the trajectory, topology, frame selection, and atom selection.

### RMSF Analysis:

```bash
fastmda rmsf -traj traj.dcd -top top.pdb 
```

# Contributing
Contributions are welcome. Please submit a Pull Request. 

# Citation
If you use **FastMDAnalysis** in your work, please cite:

Adekunle Aina (2025). *FastMDAnalysis: Software for Automated Molecular Dynamics Trajectory Analysis.* GitHub. https://github.com/aai-research-lab/fastmdanalysis

```bibtex
@software{FastMDAnalysis,
  author       = {Adekunle Aina},
  title        = {FastMDAnalysis: Software for Automated Molecular Dynamics Trajectory Analysis},
  year         = {2025},
  publisher    = {GitHub},
  url          = {https://github.com/aai-research-lab/fastmdanalysis}
}
```

# License

FastMDAnalysis is licensed under the MIT License. 


# Acknowledgements

FastMDAnalysis leverages MDTraj for trajectory analysis. It also relies on popular Python libraries such as NumPy, scikit-learn, and Matplotlib for data processing and visualization. Special thanks to the community for their continuous support and contributions.
