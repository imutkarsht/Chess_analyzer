"""Canonical classification buckets shared by metrics, reports, and the GUI."""

from src.backend.analysis.metrics.constants import QUALITY_NAMES
from src.constants import CLASSIFICATION_ORDER, zero_classification_counts


def test_quality_names_alias_the_display_order():
    assert QUALITY_NAMES is CLASSIFICATION_ORDER


def test_zero_classification_counts_covers_each_bucket_once():
    counts = zero_classification_counts()

    assert tuple(counts) == CLASSIFICATION_ORDER
    assert set(counts.values()) == {0}
