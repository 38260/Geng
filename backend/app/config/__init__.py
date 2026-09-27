"""Configuration package: runtime settings + analytics thresholds + logging."""

from .algorithms import (
    ANALYSIS_DEFAULTS,
    ANALYTICS_CONFIG,
    CATCHUP_EMOJI,
    CATCHUP_LABELS,
    CATCHUP_THRESHOLDS,
    HOME_FILTERS,
    HOME_FILTER_LABELS,
    HOTNESS_REFERENCE,
    HOTNESS_WEIGHTS,
    LIFECYCLE_EMOJI,
    LIFECYCLE_LABELS,
    LIFECYCLE_STAGES,
    LIFECYCLE_THRESHOLDS,
    LOW_SAMPLE_DAMPING,
    MIN_SAMPLE_VIDEOS,
    RELEVANCE_THRESHOLD,
    RELEVANCE_WEIGHTS,
)
from .logging import configure_logging, get_logger
from .settings import Settings, get_settings, settings

__all__ = [
    "Settings",
    "get_settings",
    "settings",
    "configure_logging",
    "get_logger",
    "ANALYTICS_CONFIG",
    "ANALYSIS_DEFAULTS",
    "RELEVANCE_WEIGHTS",
    "RELEVANCE_THRESHOLD",
    "HOTNESS_WEIGHTS",
    "HOTNESS_REFERENCE",
    "MIN_SAMPLE_VIDEOS",
    "LOW_SAMPLE_DAMPING",
    "LIFECYCLE_STAGES",
    "LIFECYCLE_LABELS",
    "LIFECYCLE_EMOJI",
    "LIFECYCLE_THRESHOLDS",
    "CATCHUP_THRESHOLDS",
    "CATCHUP_LABELS",
    "CATCHUP_EMOJI",
    "HOME_FILTERS",
    "HOME_FILTER_LABELS",
]
