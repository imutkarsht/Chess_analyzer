"""
Chart creation functions for metrics dashboard.
Uses matplotlib to create chart figures.
"""

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..styles import Styles


def create_donut_figure(
    sizes: list,
    colors: list,
    center_text: str = "",
    figsize: tuple = (2.5, 2.5),
    dpi: int = 100,
    text_color: str | None = None,
) -> Figure:
    """
    Creates a donut chart figure.

    Args:
        sizes: List of numeric values for each wedge
        colors: List of colors for each wedge
        center_text: Text to display in the center
        figsize: Figure size in inches
        dpi: Dots per inch
        text_color: Optional override for center text color (defaults to Styles.COLOR_TEXT_PRIMARY)

    Returns:
        matplotlib Figure object
    """
    fig = Figure(figsize=figsize, dpi=dpi, facecolor="none")
    fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)
    ax = fig.add_subplot(111)
    ax.set_facecolor("none")

    if sizes and any(s > 0 for s in sizes):
        # Filter zeros
        valid_sizes = []
        valid_colors = []
        for i, size in enumerate(sizes):
            if size > 0:
                valid_sizes.append(size)
                valid_colors.append(colors[i])

        wedges, texts = ax.pie(
            valid_sizes,
            labels=None,
            startangle=90,
            colors=valid_colors,
            wedgeprops=dict(width=0.35, edgecolor="none"),
        )

        # Center text - large and bold
        if center_text:
            text_c = text_color or Styles.COLOR_TEXT_PRIMARY
            font_sz = 15 if "\n" in center_text else 18
            ax.text(
                0,
                0,
                center_text,
                ha="center",
                va="center",
                fontsize=font_sz,
                color=text_c,
                weight="bold",
            )
    else:
        empty_c = text_color or Styles.COLOR_TEXT_SECONDARY
        ax.text(
            0,
            0,
            "No Data",
            ha="center",
            va="center",
            fontsize=12,
            color=empty_c,
        )

    ax.set_aspect("equal")
    return fig


def create_line_chart_figure(
    values: list, figsize: tuple = (5, 3), dpi: int = 100, ylim: tuple = (0, 100), fill: bool = True
) -> Figure:
    """
    Creates a line chart figure with optional fill.

    Args:
        values: List of y-values
        figsize: Figure size in inches
        dpi: Dots per inch
        ylim: Y-axis limits
        fill: Whether to fill under the line

    Returns:
        matplotlib Figure object
    """
    fig = Figure(figsize=figsize, dpi=dpi, facecolor="none")
    ax = fig.add_subplot(111)
    ax.set_facecolor("none")

    if values:
        x = range(len(values))
        ax.plot(x, values, color=Styles.COLOR_ACCENT, marker="o", linewidth=2, markersize=6)

        if fill:
            ax.fill_between(x, values, alpha=0.1, color=Styles.COLOR_ACCENT)

        ax.set_ylim(ylim)
        ax.grid(True, color="#444", linestyle=":", alpha=0.3)

        # Remove spines
        for spine in ["top", "right", "left", "bottom"]:
            ax.spines[spine].set_visible(False)

    ax.tick_params(colors=Styles.COLOR_TEXT_SECONDARY, which="both", length=0)

    return fig


def create_accuracy_trend_figure(
    accuracies: list[float],
    figsize: tuple = (4.0, 1.8),
    dpi: int = 100,
    baseline_acc: float | None = None,
    text_color: str | None = None,
) -> Figure:
    """
    Creates an interactive, modern line chart figure showing game-by-game accuracy,
    rolling moving average trend, and baseline accuracy level.
    """
    fig = Figure(figsize=figsize, dpi=dpi, facecolor="none")
    fig.subplots_adjust(left=0.10, right=0.96, top=0.92, bottom=0.20)
    ax = fig.add_subplot(111)
    ax.set_facecolor("none")

    text_c = text_color or Styles.COLOR_TEXT_SECONDARY
    primary_c = Styles.COLOR_TEXT_PRIMARY

    if not accuracies:
        ax.text(
            0.5,
            0.5,
            "No Accuracy Data",
            ha="center",
            va="center",
            fontsize=11,
            color=text_c,
            transform=ax.transAxes,
        )
        for spine in ["top", "right", "left", "bottom"]:
            ax.spines[spine].set_visible(False)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        return fig

    n = len(accuracies)
    x = list(range(n))

    # Y limits: ensure dynamic breathing room without squashing
    min_val = min(accuracies)

    if min_val >= 80:
        y_min = 70.0
    elif min_val >= 65:
        y_min = 50.0
    elif min_val >= 50:
        y_min = 40.0
    else:
        y_min = max(0.0, float(int(min_val // 10) * 10 - 5))

    y_max = 100.0
    ax.set_ylim(y_min, y_max)
    ax.set_xlim(-0.4, n - 0.6 if n > 1 else 0.4)

    # 1. Subtle horizontal gridlines only
    ax.grid(True, axis="y", color=Styles.COLOR_BORDER, linestyle=":", alpha=0.35, linewidth=0.8)

    # 2. Baseline reference line (Overall average)
    if baseline_acc is not None and y_min < baseline_acc < y_max:
        ax.axhline(
            baseline_acc,
            color=Styles.COLOR_TEXT_MUTED,
            linestyle="--",
            linewidth=1.0,
            alpha=0.45,
            zorder=1,
        )

    # 3. Rolling Moving Average trendline (if >= 4 games)
    if n >= 4:
        window_size = 3 if n < 12 else 5
        ma = [
            sum(accuracies[max(0, i - window_size + 1) : i + 1])
            / len(accuracies[max(0, i - window_size + 1) : i + 1])
            for i in range(n)
        ]
        ax.plot(
            x,
            ma,
            color=primary_c,
            linestyle="--",
            linewidth=1.4,
            alpha=0.55,
            zorder=2,
            label="Trend",
        )

    # 4. Main Accuracy curve
    ax.plot(
        x,
        accuracies,
        color=Styles.COLOR_ACCENT,
        linewidth=2.0,
        zorder=3,
    )
    ax.fill_between(
        x,
        accuracies,
        y_min,
        alpha=0.12,
        color=Styles.COLOR_ACCENT,
        zorder=2,
    )

    # 5. Scatter points
    ax.scatter(
        x,
        accuracies,
        color=Styles.COLOR_ACCENT,
        s=20,
        zorder=4,
    )

    # 6. Highlight Best (peak) game
    best_idx = int(max(range(n), key=lambda i: accuracies[i]))
    ax.scatter(
        [best_idx],
        [accuracies[best_idx]],
        color=Styles.COLOR_BEST,
        edgecolors=Styles.COLOR_SURFACE,
        linewidths=1.5,
        s=55,
        zorder=5,
    )

    # 7. Highlight Lowest game if distinct
    lowest_idx = int(min(range(n), key=lambda i: accuracies[i]))
    if lowest_idx != best_idx and n > 2:
        ax.scatter(
            [lowest_idx],
            [accuracies[lowest_idx]],
            color=Styles.COLOR_TEXT_MUTED,
            edgecolors=Styles.COLOR_SURFACE,
            linewidths=1.0,
            s=30,
            zorder=5,
        )

    # Spines
    for spine in ["top", "right", "left", "bottom"]:
        ax.spines[spine].set_visible(False)

    # Y-Ticks
    y_ticks = [int(y_min), int((y_min + y_max) / 2), 100]
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([f"{t}%" for t in y_ticks], fontsize=8, color=text_c)

    # X-Ticks
    if n <= 1:
        ax.set_xticks([0])
        ax.set_xticklabels(["G1"], fontsize=8, color=text_c)
    elif n <= 6:
        ax.set_xticks(x)
        ax.set_xticklabels([f"G{i + 1}" for i in x], fontsize=8, color=text_c)
    elif n <= 12:
        step = 2
        ax.set_xticks(x[::step])
        ax.set_xticklabels([f"G{i + 1}" for i in x[::step]], fontsize=8, color=text_c)
    else:
        ticks = [0, n // 2, n - 1]
        ax.set_xticks(ticks)
        ax.set_xticklabels(["G1", f"G{n // 2 + 1}", f"G{n}"], fontsize=8, color=text_c)

    ax.tick_params(colors=text_c, which="both", length=0, labelsize=8)

    return fig


def fig_to_pixmap(fig: Figure) -> QPixmap:
    """
    Converts a matplotlib figure to a QPixmap.

    Args:
        fig: matplotlib Figure

    Returns:
        QPixmap
    """
    canvas = FigureCanvasQTAgg(fig)
    canvas.draw()

    width = int(fig.get_figwidth() * fig.get_dpi())
    height = int(fig.get_figheight() * fig.get_dpi())

    buf = canvas.buffer_rgba()
    qimg = QImage(buf, width, height, QImage.Format.Format_ARGB32)

    return QPixmap.fromImage(qimg)


def fig_to_label(fig: Figure) -> QLabel:
    """
    Converts a matplotlib figure to a QLabel with the chart as pixmap.

    Args:
        fig: matplotlib Figure

    Returns:
        QLabel with chart
    """
    pixmap = fig_to_pixmap(fig)
    lbl = QLabel()
    lbl.setPixmap(pixmap)
    lbl.setStyleSheet(Styles.get_transparent_label_style())
    return lbl


def fig_to_canvas(fig: Figure) -> FigureCanvasQTAgg:
    """
    Wraps a matplotlib figure in a canvas widget.

    Args:
        fig: matplotlib Figure

    Returns:
        FigureCanvasQTAgg widget
    """
    canvas = FigureCanvasQTAgg(fig)
    canvas.setStyleSheet("background: transparent;")
    return canvas


def create_legend_widget(labels: list, colors: list, values: list = None) -> QWidget:
    """
    Creates a legend widget for charts.

    Args:
        labels: List of label strings
        colors: List of colors corresponding to labels
        values: Optional list of values to display

    Returns:
        QWidget containing the legend
    """
    legend_widget = QWidget()
    legend_widget.setStyleSheet("background: transparent;")
    legend_layout = QVBoxLayout(legend_widget)
    legend_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
    legend_layout.setSpacing(8)

    for i, label in enumerate(labels):
        row = QHBoxLayout()
        row.setSpacing(8)

        # Dot
        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {colors[i]}; font-size: 16px; border: none; background: transparent;"
        )
        row.addWidget(dot)

        # Label
        lbl_name = QLabel(label)
        lbl_name.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent;"
        )
        row.addWidget(lbl_name)

        # Value
        if values:
            lbl_val = QLabel(str(values[i]))
            lbl_val.setStyleSheet(
                f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: bold; font-size: 12px; border: none; background: transparent;"
            )
            row.addWidget(lbl_val)

        row.addStretch()
        legend_layout.addLayout(row)

    return legend_widget
