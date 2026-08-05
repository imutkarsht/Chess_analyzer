"""
Chart creation functions for metrics dashboard.
Uses matplotlib to create chart figures.
"""
import matplotlib
import matplotlib.patches
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage, QPainter
from ..styles import Styles


def create_donut_figure(
    sizes: list,
    colors: list,
    center_text: str = "",
    figsize: tuple = (2.5, 2.5),
    dpi: int = 100
) -> Figure:
    """
    Creates a donut chart figure.
    
    Args:
        sizes: List of numeric values for each wedge
        colors: List of colors for each wedge
        center_text: Text to display in the center
        figsize: Figure size in inches
        dpi: Dots per inch
        
    Returns:
        matplotlib Figure object
    """
    fig = Figure(figsize=figsize, dpi=dpi, facecolor='none')
    fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)
    ax = fig.add_subplot(111)
    ax.set_facecolor('none')
    
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
            wedgeprops=dict(width=0.35, edgecolor='none')
        )
        
        # Center text - large and bold
        if center_text:
            ax.text(0, 0, center_text, ha='center', va='center', 
                    fontsize=18, color='white', weight='bold')
    else:
        ax.text(0, 0, "No Data", ha='center', va='center', 
                fontsize=12, color=Styles.COLOR_TEXT_SECONDARY)
    
    ax.set_aspect('equal')
    return fig


def create_line_chart_figure(
    values: list,
    figsize: tuple = (5, 3),
    dpi: int = 100,
    ylim: tuple = (0, 100),
    fill: bool = True,
    labels: list = None,
    title: str = "",
    color: str = None,
) -> Figure:
    """
    Creates a line chart figure with optional fill.

    Args:
        values: List of y-values
        figsize: Figure size in inches
        dpi: Dots per inch
        ylim: Y-axis limits
        fill: Whether to fill under the line
        labels: Optional x-axis tick labels (must match len(values))
        title: Optional chart title
        color: Optional line color (defaults to accent)

    Returns:
        matplotlib Figure object
    """
    line_color = color or Styles.COLOR_ACCENT
    fig = Figure(figsize=figsize, dpi=dpi, facecolor=Styles.COLOR_SURFACE)
    ax = fig.add_subplot(111)
    ax.set_facecolor(Styles.COLOR_SURFACE)
    
    if values:
        x = range(len(values))
        ax.plot(x, values, color=line_color, marker='o', linewidth=2, markersize=6)
        
        if fill:
            ax.fill_between(x, values, alpha=0.1, color=line_color)
        
        ax.set_ylim(ylim)
        ax.grid(True, color='#444', linestyle=':', alpha=0.3)
        
        # Remove spines
        for spine in ['top', 'right', 'left', 'bottom']:
            ax.spines[spine].set_visible(False)

        if labels:
            ax.set_xticks(list(x))
            ax.set_xticklabels(labels, fontsize=8)

        if title:
            ax.set_title(title, color=Styles.COLOR_TEXT_SECONDARY, fontsize=11, pad=8)
    
    ax.tick_params(colors=Styles.COLOR_TEXT_SECONDARY, which='both', length=0)
    
    return fig


def create_stacked_bar_figure(
    rows: list,
    row_labels: list,
    figsize: tuple = (6, 3),
    dpi: int = 100,
    center_text: str = "",
) -> Figure:
    """
    Creates a horizontal stacked bar figure from multiple segment rows.

    Args:
        rows: List of rows; each row is a list of (value, color, label) segments.
        row_labels: List of labels for each row.
        figsize: Figure size in inches
        dpi: Dots per inch
        center_text: Optional text rendered as a centered legend-style hint

    Returns:
        matplotlib Figure object
    """
    fig = Figure(figsize=figsize, dpi=dpi, facecolor=Styles.COLOR_SURFACE)

    # Reserve left space for the row labels so they are never clipped.
    max_chars = max((len(lbl) for lbl in row_labels), default=0)
    left_space = max(0.10, min(0.45, 0.06 + 0.022 * max_chars))
    bottom_space = 0.18 if center_text else 0.06
    fig.subplots_adjust(left=left_space, right=0.98, top=0.94, bottom=bottom_space)

    ax = fig.add_subplot(111)
    ax.set_facecolor(Styles.COLOR_SURFACE)

    max_total = 0
    for row in rows:
        row_total = sum(v for v, _, _ in row)
        max_total = max(max_total, row_total)

    for i, (row, label) in enumerate(zip(rows, row_labels)):
        y = len(rows) - i - 1
        left = 0.0
        for value, color, _ in row:
            if value > 0:
                width = value if max_total else 0
                ax.barh(y, width, left=left, color=color, height=0.6,
                        edgecolor='none')
                left += width
        ax.text(0, y, label, ha='right', va='center', clip_on=False,
                color=Styles.COLOR_TEXT_PRIMARY, fontsize=11, fontweight='bold')

    ax.set_yticks([])
    for spine in ['top', 'right', 'left', 'bottom']:
        ax.spines[spine].set_visible(False)
    ax.set_xlim(0, max_total if max_total else 1)
    ax.set_xticks([])

    if center_text:
        ax.text(max_total, -0.55, center_text, ha='right', va='top', clip_on=False,
                color=Styles.COLOR_TEXT_MUTED, fontsize=9)

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
    legend_layout = QVBoxLayout(legend_widget)
    legend_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
    legend_layout.setSpacing(8)
    
    for i, label in enumerate(labels):
        row = QHBoxLayout()
        row.setSpacing(8)
        
        # Dot
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {colors[i]}; font-size: 16px; border: none; background: transparent;")
        row.addWidget(dot)
        
        # Label
        lbl_name = QLabel(label)
        lbl_name.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent;")
        row.addWidget(lbl_name)
        
        # Value
        if values:
            lbl_val = QLabel(str(values[i]))
            lbl_val.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: bold; font-size: 12px; border: none; background: transparent;")
            row.addWidget(lbl_val)
        
        row.addStretch()
        legend_layout.addLayout(row)
    
    return legend_widget
