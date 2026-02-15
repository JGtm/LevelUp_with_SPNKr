"""Composants UI réutilisables pour le dashboard."""

from src.ui.components.checkbox_filter import (
    get_firefight_playlists,
    render_checkbox_filter,
    render_hierarchical_checkbox_filter,
)
from src.ui.components.duckdb_analytics import (
    render_analytics_section,
    render_global_stats_card,
    render_kda_trend_chart,
    render_performance_by_map,
)
from src.ui.components.kpi import (
    render_kpi_cards,
    render_top_summary,
)
from src.ui.components.media_lightbox import build_lightbox_html
from src.ui.components.media_thumbnail import (
    build_thumbnail_html,
    render_media_thumbnail,
)
from src.ui.components.performance import (
    compute_session_performance_score,
    compute_session_performance_score_v2_ui,
    get_score_color,
    get_score_label,
    render_metric_comparison_row,
    render_performance_score_card,
)

__all__ = [
    "render_checkbox_filter",
    "render_hierarchical_checkbox_filter",
    "get_firefight_playlists",
    "compute_session_performance_score",
    "compute_session_performance_score_v2_ui",
    "get_score_color",
    "get_score_label",
    "render_performance_score_card",
    "render_metric_comparison_row",
    "render_kpi_cards",
    "render_top_summary",
    # DuckDB Analytics
    "render_global_stats_card",
    "render_kda_trend_chart",
    "render_performance_by_map",
    "render_analytics_section",
    # Media (Sprint 4)
    "build_lightbox_html",
    "build_thumbnail_html",
    "render_media_thumbnail",
]
