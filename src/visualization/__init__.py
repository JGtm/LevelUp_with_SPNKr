"""Module de visualisation (graphiques Plotly)."""

from src.visualization.distributions import (
    plot_correlation_scatter,
    plot_histogram,
    plot_kda_distribution,
    plot_matches_at_top_by_week,
    plot_medals_distribution,
    plot_outcomes_over_time,
    plot_stacked_outcomes_by_category,
    plot_win_ratio_heatmap,
)
from src.visualization.maps import (
    plot_map_comparison,
    plot_map_ratio_with_winloss,
)
from src.visualization.match_bars import (
    plot_metric_bars_by_match,
    plot_multi_metric_bars_by_match,
)
from src.visualization.theme import apply_halo_plot_style
from src.visualization.timeseries import (
    plot_accuracy_last_n,
    plot_assists_timeseries,
    plot_average_life,
    plot_per_minute_timeseries,
    plot_performance_timeseries,
    plot_spree_headshots_accuracy,
    plot_timeseries,
)
from src.visualization.trio import plot_trio_metric

__all__ = [
    "apply_halo_plot_style",
    "plot_timeseries",
    "plot_assists_timeseries",
    "plot_per_minute_timeseries",
    "plot_accuracy_last_n",
    "plot_average_life",
    "plot_spree_headshots_accuracy",
    "plot_performance_timeseries",
    "plot_kda_distribution",
    "plot_outcomes_over_time",
    "plot_stacked_outcomes_by_category",
    "plot_win_ratio_heatmap",
    "plot_histogram",
    "plot_medals_distribution",
    "plot_correlation_scatter",
    "plot_matches_at_top_by_week",
    "plot_map_comparison",
    "plot_map_ratio_with_winloss",
    "plot_trio_metric",
    "plot_metric_bars_by_match",
    "plot_multi_metric_bars_by_match",
]
