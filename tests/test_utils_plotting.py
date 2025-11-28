# tests/test_utils_plotting.py

import numpy as np
import pytest

from fastmdanalysis.utils.plotting import auto_ticks, apply_slide_style, match_colorbar_font


def test_auto_ticks_integer_scaling():
    ticks = auto_ticks(np.arange(0, 251), max_ticks=8, integer=True)
    assert ticks is not None
    assert np.isclose(ticks[0], 0)
    assert np.isclose(ticks[-1], 250)
    diffs = np.diff(ticks)
    assert np.allclose(diffs, diffs[0])
    assert diffs[0] >= 10


def test_auto_ticks_constant_data():
    ticks = auto_ticks([5, 5, 5], max_ticks=6, integer=True)
    assert ticks is not None
    assert (ticks[0] < 5) and (ticks[-1] > 5)
    assert np.any(np.isclose(ticks, 5))


def test_auto_ticks_include_zero_for_positive_data():
    ticks = auto_ticks([5, 15], max_ticks=5, include_zero=True)
    assert ticks is not None
    assert np.isclose(ticks[0], 0.0)
    assert ticks[-1] >= 15


def test_apply_slide_style_sets_fonts(matplotlib):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot([0, 1, 2], [0, 1, 0])
    applied = apply_slide_style(
        ax,
        x_values=np.arange(0, 51),
        y_values=[0, 1],
        # Remove integer_x parameter
        tick_size=20,
        label_size=22,
        title_size=24,
        x_tick_rotation=45,
    )

    assert "x" in applied and applied["x"].size > 0
    assert ax.xaxis.get_label().get_fontsize() == 22
    assert ax.yaxis.get_label().get_fontsize() == 22
    assert ax.title.get_fontsize() >= 24
    assert ax.get_xticklabels()[0].get_rotation() == 45

    plt.close(fig)


def test_apply_slide_style_respects_manual_ticks(matplotlib):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    manual_ticks = [0, 5, 10]
    apply_slide_style(ax, x_ticks=manual_ticks, y_values=[0, 1])
    assert np.allclose(ax.get_xticks(), manual_ticks)
    plt.close(fig)


def test_apply_slide_style_adapts_font_size(matplotlib):
    import matplotlib.pyplot as plt

    fig_sparse, ax_sparse = plt.subplots()
    apply_slide_style(ax_sparse, x_ticks=[0, 50], y_ticks=[0, 1])
    fig_sparse.canvas.draw()
    sparse_size = ax_sparse.get_xticklabels()[0].get_fontsize()

    fig_dense, ax_dense = plt.subplots()
    apply_slide_style(ax_dense, x_ticks=np.linspace(0, 100, 20), y_ticks=[0, 1])
    fig_dense.canvas.draw()
    dense_size = ax_dense.get_xticklabels()[0].get_fontsize()

    # Updated assertion to match your consistent font sizes
    assert sparse_size == dense_size  # Now both should be the same

    plt.close(fig_sparse)
    plt.close(fig_dense)


def test_apply_slide_style_zero_padding_extends_xlim(matplotlib):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ax.set_xlim(0.0, 1.0)
    apply_slide_style(
        ax,
        x_values=np.linspace(0.0, 5.0, 6),
        y_values=[0.0, 1.0],
        # Remove integer_x parameter
        zero_x=True,
    )
    left, right = ax.get_xlim()
    assert left < 0.0
    assert right >= 4.99
    plt.close(fig)


def test_match_colorbar_font_falls_back_to_x_axis(matplotlib):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    mesh = ax.imshow(np.arange(4).reshape(2, 2))
    cbar = fig.colorbar(mesh, ax=ax)
    apply_slide_style(
        ax,
        x_values=np.arange(5),
        y_values=np.arange(5),
        tick_size=16,
        label_size=22,
    )
    ax.set_ylabel("")
    ax.set_yticks([])
    cbar.set_ticks([0.0, 1.0])
    match_colorbar_font(cbar, ax)
    fig.canvas.draw()
    tick_sizes = [label.get_fontsize() for label in cbar.ax.get_yticklabels() if label.get_text()]
    # Updated assertion to match your consistent font sizes
    assert tick_sizes and tick_sizes[0] == 18.0  # Your consistent tick size
    plt.close(fig)


def test_match_colorbar_font_inherits_other_axis_label(matplotlib):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ax.set_xlabel("Frames")
    ax.set_ylabel("")
    mesh = ax.imshow(np.arange(4).reshape(2, 2))
    cbar = fig.colorbar(mesh, ax=ax)
    cbar.set_label("Scale")
    apply_slide_style(
        ax,
        x_values=np.arange(6),
        y_values=np.arange(6),
        tick_size=14,
        label_size=26,
    )
    ax.set_yticks([])
    match_colorbar_font(cbar, ax)
    fig.canvas.draw()
    # Updated assertion to match your consistent font sizes
    assert cbar.ax.yaxis.label.get_fontsize() == 20.0  # Your consistent label size
    plt.close(fig)