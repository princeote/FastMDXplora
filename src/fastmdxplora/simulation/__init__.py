"""MD simulation phase.

The simulation phase takes the parameterized System + initial State
produced by the setup phase and runs the canonical four-stage MD
pipeline (minimize → NVT → NPT → production), producing a DCD trajectory
plus reporters that the analysis phase consumes.

Public API
----------
- :func:`run` -- orchestrator-facing entry point
- :func:`run_simulation` -- direct programmatic interface to the runner
- :class:`SimulationResult` -- the runner's return value

OpenMM is an optional dependency installed via the ``[setup]`` extras
group; the simulation phase reuses that requirement (no separate
``[simulation]`` extra). When OpenMM isn't available, the phase
gracefully writes a manifest and skips the chemistry.
"""

from fastmdxplora.simulation.pipeline import run
from fastmdxplora.simulation.runner import SimulationResult, run_simulation

__all__ = ["SimulationResult", "run", "run_simulation"]
