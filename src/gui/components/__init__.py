"""
Shared GUI components module.
"""
from src.gui.theme.typography import TextRole, TextTone

from ..utils.smooth_scroll import SmoothScroll, install_smooth_scrolling
from .controls.button import Button, ButtonSize, ButtonVariant
from .controls.date_picker import DatePicker
from .controls.form_field import FormField
from .controls.input import (
    TEXT_INPUT_TYPES,
    DecimalInput,
    Input,
    InputSize,
    InputVariant,
    NumberInput,
    TextArea,
    TextAreaVariant,
)
from .controls.segmented_bar import SegmentedBar
from .controls.segmented_control import SegmentedControl
from .controls.select import Select, SelectOption, SelectSize
from .controls.tabs import TabAppearance, Tabs, TabVariant
from .display.avatar import Avatar
from .display.chip_label import ChipLabel
from .display.circular_accuracy import CircularAccuracyWidget
from .display.clock_label import ClockLabel
from .display.color_label import ColorLabel
from .display.icon_label import IconLabel
from .display.label import Label
from .display.mini_bar import MiniBar
from .display.rich_text import LinkLabel, RichTextLabel
from .display.stat_card import SimpleStatCard, StatCard
from .feedback.empty_state import EmptyState
from .feedback.engine_score_badge import EngineScoreBadge
from .feedback.pulsing_skeleton import PulsingSkeleton
from .feedback.status_badge import BadgeVariant, StatusBadge
from .feedback.toast import (
    Toast,
    ToastHandle,
    ToastManager,
    ToastOptions,
    ToastPosition,
    ToastVariant,
)
from .layout.masonry_layout import MasonryLayout
from .layout.stats_layout import StatsLayout
from .layout.welcome_panel import WelcomePanel
from .lists.legend_list import LegendList
from .lists.pagination_bar import (
    PaginationBar,
    PaginationSize,
    PaginationState,
    PaginationStyle,
)
from .lists.sortable_item_list import SortableItem, SortableItemList

__all__ = [
    'Avatar',
    'Button',
    'ButtonSize',
    'ButtonVariant',
    'BadgeVariant',
    'ChipLabel',
    'ClockLabel',
    'ColorLabel',
    'EmptyState',
    'EngineScoreBadge',
    'FormField',
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
    'LegendList',
    'MiniBar',
    'PaginationBar',
    'PaginationSize',
    'PaginationState',
    'PaginationStyle',
    'SegmentedBar',
    'SegmentedControl',
    'Select',
    'SelectOption',
    'SelectSize',
    'SmoothScroll',
    'install_smooth_scrolling',
    'StatCard',
    'SimpleStatCard',
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
    'WelcomePanel',
]
