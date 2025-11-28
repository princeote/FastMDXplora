# FastMDAnalysis/src/fastmdanalysis/utils/plotting.py

from __future__ import annotations

from typing import Dict, Optional, Sequence, Union

import numpy as np
from matplotlib.axes import Axes
from matplotlib.ticker import FixedLocator, MaxNLocator
from matplotlib.colorbar import Colorbar

NumericSeq = Optional[Union[Sequence[float], np.ndarray]]

__all__ = ["auto_ticks", "apply_slide_style", "match_colorbar_font"]


def _as_clean_array(values: NumericSeq) -> Optional[np.ndarray]:
    if values is None:
        return None
    arr = np.asarray(values, dtype=float).ravel()
    if arr.size == 0:
        return None
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None
    return arr


def _nice_step(span: float, max_ticks: int, integer: bool) -> float:
    if span <= 0 or not np.isfinite(span):
        return 1 if integer else 1.0
    raw = span / max(1, max_ticks - 1)
    if raw == 0 or not np.isfinite(raw):
        return 1 if integer else 1.0

    magnitude = 10 ** np.floor(np.log10(raw))
    residual = raw / magnitude

    if residual <= 1.5:
        nice = 1.0
    elif residual <= 3:
        nice = 2.0
    elif residual <= 7:
        nice = 5.0
    else:
        nice = 10.0

    step = nice * magnitude
    if integer:
        step = max(1, int(round(step)))
    return float(step)


def auto_ticks(
    values: NumericSeq,
    *,
    max_ticks: int = 8,
    integer: bool = False,
    include_zero: bool = False,
) -> Optional[np.ndarray]:

    arr = _as_clean_array(values)
    if arr is None:
        return None

    lo = float(np.min(arr))
    hi = float(np.max(arr))
    if np.isclose(lo, hi):
        delta = max(1.0, abs(lo) * 0.25) or 1.0
        lo -= delta
        hi += delta

    span = hi - lo
    step = _nice_step(span, max_ticks, integer)
    if step <= 0:
        return None

    start = np.floor(lo / step) * step
    stop = np.ceil(hi / step) * step

    if include_zero:
        if start > 0:
            start = 0.0
        if stop < 0:
            stop = 0.0
        if not (start <= 0 <= stop):
            if lo > 0:
                start = 0.0
            elif hi < 0:
                stop = 0.0

    ticks = np.arange(start, stop + (step * 0.5), step, dtype=float)
    if integer:
        ticks = np.unique(np.round(ticks).astype(int)).astype(float)
    return ticks


def _set_font_sizes(
    ax: Axes,
    *,
    tick_size_x: float,
    tick_size_y: float,
    label_size_x: float,
    label_size_y: float,
    title_size: float,
) -> None:
    ax.tick_params(axis="x", which="major", labelsize=tick_size_x)
    ax.tick_params(axis="y", which="major", labelsize=tick_size_y)
    ax.xaxis.label.set_fontsize(label_size_x)
    ax.yaxis.label.set_fontsize(label_size_y)
    ax.title.set_fontsize(title_size)


def _to_tick_array(data: NumericSeq) -> Optional[np.ndarray]:
    if data is None:
        return None
    arr = np.asarray(list(data), dtype=float)
    if arr.size == 0:
        return None
    return arr


def apply_slide_style(
    ax: Axes,
    *,
    x_values: NumericSeq = None,
    y_values: NumericSeq = None,
    x_ticks: NumericSeq = None,
    y_ticks: NumericSeq = None,
    x_max_ticks: int = 8,
    y_max_ticks: int = 6,
    zero_x: bool = False,
    zero_y: bool = False,
    tick_size: Optional[Union[int, float]] = None,
    label_size: Optional[Union[int, float]] = None,
    title_size: Optional[Union[int, float]] = None,
    x_tick_rotation: Optional[float] = None,
) -> Dict[str, np.ndarray]:
    applied: Dict[str, np.ndarray] = {}

    x_data = _as_clean_array(x_values)

    ticks_x = _to_tick_array(x_ticks)
    if ticks_x is None:
        ticks_x = auto_ticks(
            x_values,
            max_ticks=x_max_ticks,
            include_zero=zero_x,
        )
    if ticks_x is not None and ticks_x.size:
        ax.xaxis.set_major_locator(FixedLocator(ticks_x))
        applied["x"] = ticks_x
    else:
        ax.xaxis.set_major_locator(MaxNLocator(nbins=x_max_ticks))

    ticks_y = _to_tick_array(y_ticks)
    if ticks_y is None:
        ticks_y = auto_ticks(
            y_values,
            max_ticks=y_max_ticks,
            include_zero=zero_y,
        )
    if ticks_y is not None and ticks_y.size:
        ax.yaxis.set_major_locator(FixedLocator(ticks_y))
        applied["y"] = ticks_y
    else:
        ax.yaxis.set_major_locator(MaxNLocator(nbins=y_max_ticks))

    # Consistent font sizes
    if tick_size is None:
        tick_size_x = tick_size_y = 18.0  # Consistent tick size
    else:
        tick_size_x = tick_size_y = float(tick_size)
        
    if label_size is None:
        label_size_x = label_size_y = 20.0  # Consistent label size
    else:
        label_size_x = label_size_y = float(label_size)

    if title_size is None:
        title_size_val = 20.0  # Consistent title size
    else:
        title_size_val = float(title_size)

    _set_font_sizes(
        ax,
        tick_size_x=tick_size_x,
        tick_size_y=tick_size_y,
        label_size_x=label_size_x,
        label_size_y=label_size_y,
        title_size=title_size_val,
    )

    # Stash sizes for downstream helpers (e.g., colorbar font syncing)
    ax._fastmda_tick_size_x = tick_size_x  # type: ignore[attr-defined]
    ax._fastmda_label_size_x = label_size_x  # type: ignore[attr-defined]
    ax._fastmda_tick_size_y = tick_size_y  # type: ignore[attr-defined]
    ax._fastmda_label_size_y = label_size_y  # type: ignore[attr-defined]

    if x_tick_rotation is not None:
        for label in ax.get_xticklabels():
            label.set_rotation(x_tick_rotation)
            if x_tick_rotation and abs(x_tick_rotation) > 0:
                label.set_horizontalalignment("right")

    if x_data is not None:
        x_max_val = float(np.max(x_data))
        current_left, current_right = ax.get_xlim()
        new_left = current_left
        new_right = max(current_right, x_max_val)
        if zero_x:
            x_min_val = float(np.min(x_data))
            if x_min_val is None or x_min_val >= 0:
                span_base = x_max_val - (x_min_val if x_min_val is not None else 0.0)
                span = max(1.0, span_base)
                pad_min = max(0.5, span * 0.01)
                existing_pad = max(current_right - x_max_val, 0.0)
                pad = max(existing_pad, pad_min)
                new_left = -pad
                new_right = x_max_val + pad
            else:
                new_left = min(current_left, 0.0)
                new_right = max(new_right, x_max_val)
        if not np.isclose(new_left, current_left) or not np.isclose(new_right, current_right):
            ax.set_xlim(new_left, new_right)

    return applied


def match_colorbar_font(colorbar: Colorbar, ax: Axes) -> None:
    """Align colorbar fonts with consistent sizes."""
    # Consistent font sizes
    TICK_SIZE = 18.0
    LABEL_SIZE = 20.0
    
    axis_name = "y" if colorbar.orientation != "horizontal" else "x"
    
    # Set tick and label sizes directly
    colorbar.ax.tick_params(axis=axis_name, labelsize=TICK_SIZE)
    axis = getattr(colorbar.ax, f"{axis_name}axis")
    axis.label.set_fontsize(LABEL_SIZE)
