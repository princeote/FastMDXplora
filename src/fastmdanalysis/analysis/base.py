from __future__ import annotations
import os
from pathlib import Path
import numpy as np
from typing import Optional, Union

class AnalysisError(Exception):
    pass

class BaseAnalysis:
    def __init__(self, trajectory, output=None, **kwargs):
        self.traj = trajectory
        self.output = output or self.__class__.__name__.replace("Analysis", "").lower() + "_output"
        self.outdir = Path(self.output)
        self.outdir.mkdir(parents=True, exist_ok=True)
        self.results = {}
        self.data = None

    def _save_plot(
        self,
        fig,
        name: str,
        *,
        filename: Optional[Union[str, Path]] = None,
        dpi: Optional[int] = None,
    ) -> Path:
        """
        Save a matplotlib figure to a PNG file in the output directory.

        Parameters
        ----------
        fig : matplotlib.figure.Figure
        name : str
            Base name used when 'filename' is not provided.
        filename : str | Path | None
            Optional explicit filename or path. If relative and without suffix,
            '.png' is appended and it is placed under self.outdir.
        dpi : int | None
            Optional DPI override.

        Returns
        -------
        Path
        """
        # Ensure output dir exists (in case caller changed it)
        self.outdir.mkdir(parents=True, exist_ok=True)

        if filename is not None:
            p = Path(filename)
            if not p.suffix:
                p = p.with_suffix(".png")
            if not p.is_absolute():
                p = self.outdir / p
            p.parent.mkdir(parents=True, exist_ok=True)
            out = p
        else:
            out = self.outdir / f"{name}.png"

        save_kwargs = {"bbox_inches": "tight"}
        if dpi is not None:
            save_kwargs["dpi"] = dpi

        fig.savefig(out, **save_kwargs)
        return out

    def _save_data(self, data, filename: str, header: str | None = None, fmt: str | None = None) -> Path:
        data_path = self.outdir / f"{filename}.dat"
        if isinstance(data, np.ndarray):
            if header is None:
                if data.ndim == 2:
                    header = " ".join([f"col{i}" for i in range(data.shape[1])])
                else:
                    header = "data"
            if fmt is None:
                try:
                    if np.issubdtype(data.dtype, np.integer):
                        fmt = "%d"
                    elif np.issubdtype(data.dtype, np.floating):
                        fmt = "%.6f"
                except TypeError:
                    fmt = None
            kwargs = {"header": header}
            if fmt is not None:
                kwargs["fmt"] = fmt
            np.savetxt(data_path, data, **kwargs)
        else:
            data_path.write_text(str(data))
        return data_path

    def run(self):
        raise NotImplementedError("Subclasses must implement the run() method.")

    def plot(self):
        raise NotImplementedError("Subclasses must implement the plot() method.")

