"""
Shared GUI components module.
"""
from src.gui.components.controls.button import Button, ButtonSize, ButtonVariant
from src.gui.components.controls.checkbox import Checkbox, CheckboxVariant
from src.gui.components.controls.date_picker import DatePicker
from src.gui.components.controls.filter_chip import FilterChip
from src.gui.components.controls.form_field import FormField
from src.gui.components.controls.input import (
    TEXT_INPUT_TYPES,
    DecimalInput,
    Input,
    InputSize,
    InputVariant,
    NumberInput,
    TextArea,
    TextAreaVariant,
)
from src.gui.components.controls.path_field import PathField
from src.gui.components.controls.radio_group import RadioChoice
from src.gui.components.controls.segmented_bar import SegmentedBar
from src.gui.components.controls.segmented_control import SegmentedControl
from src.gui.components.controls.select import Select, SelectOption, SelectSize
from src.gui.components.controls.slider_counter import SliderCounter
from src.gui.components.controls.star_rating_widget import StarRatingWidget
from src.gui.components.controls.tabs import TabAppearance, Tabs, TabVariant
from src.gui.components.dialogs import (
    confirm_dialog,
    open_feedback_dialog,
    open_llm_settings,
    show_error_dialog,
)
from src.gui.components.display.avatar import Avatar
from src.gui.components.display.chip_label import ChipLabel
from src.gui.components.display.circular_accuracy import CircularAccuracyWidget
from src.gui.components.display.clock_label import ClockLabel
from src.gui.components.display.color_label import ColorLabel
from src.gui.components.display.elided_label import ElidedLabel
from src.gui.components.display.graph_widget import GraphWidget
from src.gui.components.display.icon_label import IconLabel
from src.gui.components.display.label import Label
from src.gui.components.display.mini_bar import MiniBar
from src.gui.components.display.rich_text import LinkLabel, RichTextLabel
from src.gui.components.display.stat_card import SimpleStatCard, StatCard
from src.gui.components.feedback.empty_state import EmptyState
from src.gui.components.feedback.engine_score_badge import EngineScoreBadge
from src.gui.components.feedback.loading_widget import LoadingOverlay
from src.gui.components.feedback.progress_bar import ProgressBar, ProgressBarVariant
from src.gui.components.feedback.pulsing_skeleton import PulsingSkeleton
from src.gui.components.feedback.status_badge import BadgeVariant, StatusBadge
from src.gui.components.feedback.toast import (
    Toast,
    ToastHandle,
    ToastManager,
    ToastOptions,
    ToastPosition,
    ToastVariant,
)
from src.gui.components.feedback.tooltip import (
    Tooltip,
    TooltipKind,
    TooltipManager,
    attach_tooltip,
    detach_tooltip,
    format_action,
    format_disabled,
    format_explanation,
    format_navigation,
    format_shortcut,
    format_state,
    tooltip_for,
)
from src.gui.components.layout.masonry_layout import MasonryLayout
from src.gui.components.layout.sidebar import Sidebar
from src.gui.components.layout.stats_layout import StatsLayout
from src.gui.components.layout.tour_manager import TourManager, TourStep
from src.gui.components.layout.tour_overlay import TourOverlay
from src.gui.components.layout.transition_stack import FadedStackedWidget
from src.gui.components.layout.welcome_panel import WelcomePanel
from src.gui.components.lists.legend_list import LegendList
from src.gui.components.lists.list_view import ListView
from src.gui.components.lists.pagination_bar import (
    PaginationBar,
    PaginationSize,
    PaginationState,
    PaginationStyle,
)
from src.gui.components.lists.sortable_item_list import SortableItem, SortableItemList
from src.gui.theme.typography import TextRole, TextTone
from src.gui.utils.smooth_scroll import SmoothScroll, install_smooth_scrolling

_LAZY_EXPORTS = {"GameListItemWidget", "GameListWidget"}


def __getattr__(name: str):
    """Resolve list widgets lazily to avoid the board <-> facade import cycle."""
    if name in _LAZY_EXPORTS:
        from src.gui.components.lists.game_list_item_widget import GameListItemWidget
        from src.gui.components.lists.game_list_widget import GameListWidget

        return {
            "GameListItemWidget": GameListItemWidget,
            "GameListWidget": GameListWidget,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'Avatar',
    'Button',
    'ButtonSize',
    'ButtonVariant',
    'BadgeVariant',
    'Checkbox',
    'CheckboxVariant',
    'ChipLabel',
    'ClockLabel',
    'ColorLabel',
    'confirm_dialog',
    'ElidedLabel',
    'EmptyState',
    'EngineScoreBadge',
    'FadedStackedWidget',
    'FilterChip',
    'FormField',
    'GameListItemWidget',
    'GameListWidget',
    'GraphWidget',
    'IconLabel',
    'Input',
    'Label',
    'LinkLabel',
    'RichTextLabel',
    'TextRole',
    'TextTone',
    'InputSize',
    'InputVariant',
    'NumberInput',
    'DecimalInput',
    'TextArea',
    'TextAreaVariant',
    'TEXT_INPUT_TYPES',
    'PathField',
    'RadioChoice',
    'SliderCounter',
    'LegendList',
    'ListView',
    'LoadingOverlay',
    'MiniBar',
    'open_feedback_dialog',
    'open_llm_settings',
    'PaginationBar',
    'PaginationSize',
    'PaginationState',
    'PaginationStyle',
    'ProgressBar',
    'ProgressBarVariant',
    'SegmentedBar',
    'SegmentedControl',
    'Select',
    'SelectOption',
    'SelectSize',
    'show_error_dialog',
    'Sidebar',
    'SmoothScroll',
    'install_smooth_scrolling',
    'StatCard',
    'SimpleStatCard',
    'StarRatingWidget',
    'StatusBadge',
    'MasonryLayout',
    'StatsLayout',
    'CircularAccuracyWidget',
    'DatePicker',
    'PulsingSkeleton',
    'SortableItem',
    'SortableItemList',
    'TabAppearance',
    'TabVariant',
    'Tabs',
    'Toast',
    'ToastHandle',
    'ToastManager',
    'ToastOptions',
    'ToastPosition',
    'ToastVariant',
    'Tooltip',
    'TooltipKind',
    'TooltipManager',
    'attach_tooltip',
    'detach_tooltip',
    'format_action',
    'format_disabled',
    'format_explanation',
    'format_navigation',
    'format_shortcut',
    'format_state',
    'tooltip_for',
    'TourManager',
    'TourOverlay',
    'TourStep',
    'WelcomePanel',
]
