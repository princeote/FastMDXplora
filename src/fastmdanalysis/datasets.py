"""
Datasets Module for FastMDAnalysis

This module provides dataset classes for example MD systems.
For each dataset (e.g., Ubiquitin, Trp-cage) it specifies the trajectory and topology file paths,
as well as additional attributes describing simulation conditions such as:
  - time_step: simulation time step (in picoseconds)
  - force_field: the force field used
  - integrator: the integration algorithm used
  - temperature: the simulation temperature (in Kelvin)
  - pressure: the simulation pressure (in atm or bar as defined)

The data directory is located within the fastmdanalysis package.
"""

import os
from pathlib import Path

def _get_data_path(filename):
    """Get path to data file using multiple fallback methods."""
    try:
        # Method 1: Try importlib.resources first (works with Hatchling)
        from importlib.resources import files
        resource_path = files('fastmdanalysis.data') / filename
        # Try to access the path - this will raise FileNotFoundError if it doesn't exist
        # but we need to check if the resource system is working
        if hasattr(resource_path, 'is_file') and resource_path.is_file():
            return str(resource_path)
        # If we get here, the file might not exist but the package structure is correct
        return str(resource_path)
    except (ImportError, AttributeError, TypeError, FileNotFoundError):
        pass
    
    # Method 2: Fallback to package directory detection
    try:
        import fastmdanalysis
        package_dir = Path(fastmdanalysis.__file__).parent
        data_path = package_dir / 'data' / filename
        if data_path.exists():
            return str(data_path)
    except:
        pass
    
    # Method 3: Development fallback - relative to current file
    current_file_dir = Path(__file__).parent
    dev_data_path = current_file_dir / 'data' / filename
    if dev_data_path.exists():
        return str(dev_data_path)
    
    # Final fallback - just return the expected relative path
    return f"data/{filename}"

class Ubiquitin:
    """
    Ubiquitin Dataset

    Attributes
    ----------
    traj : str
        Path to the ubiquitin trajectory file.
    top : str
        Path to the ubiquitin topology file.
    time_step : float
        Time step used in the simulation (picoseconds).
    force_field : str
        The force field used.
    integrator : str
        The integration method used.
    temperature : float
        Simulation temperature in Kelvin.
    pressure : float
        Simulation pressure (e.g., in atm or bar).
    md_engine : str
        Molecular dynamics simulation engine.
    """
    traj = _get_data_path("ubiquitin.dcd")
    top = _get_data_path("ubiquitin.pdb")
    time_step = 0.002
    force_field = "CHARMM36m"
    integrator = "Legenvin"
    temperature = 300
    pressure = 1.0
    md_engine = "Gromacs" 

class TrpCage:
    """
    Trp-cage Dataset

    Attributes
    ----------
    traj : str
        Path to the trp-cage trajectory file.
    top : str
        Path to the trp-cage topology file.
    time_step : float
        Time step used in the simulation (picoseconds).
    force_field : str
        The force field used.
    integrator : str
        The integration algorithm used.
    temperature : float
        Simulation temperature in Kelvin.
    pressure : float
        Simulation pressure.
    md_engine : str
        Molecular dynamics simulation engine.
    """
    traj = _get_data_path("trp_cage.dcd")
    top = _get_data_path("trp_cage.pdb")
    time_step = 0.002
    force_field = "CHARMM36m"
    integrator = "LegenvinMiddleIntegrator"
    temperature = 300
    pressure = 1.0
    md_engine = "OpenMM 8.2"  

# Convenience shortcuts for easy import.
ubiquitin = Ubiquitin
trp_cage = TrpCage