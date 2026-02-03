"""Module de visualisation (graphiques Plotly)."""

from src.visualization.antagonist_charts import (
    create_kd_indicator,
    get_antagonist_chart_colors,
    plot_duel_history,
    plot_kd_timeseries,
    plot_killer_victim_heatmap,
    plot_killer_victim_stacked_bars,
    plot_nemesis_victim_summary,
    plot_top_antagonists_bars,
)
from src.visualization.distributions import (
    plot_correlation_scatter,
    plot_first_event_distribution,
    plot_histogram,
    plot_kda_distribution,
    plot_matches_at_top_by_week,
    plot_medals_distribution,
    plot_outcomes_over_time,
    plot_stacked_outcomes_by_category,
    plot_top_weapons,
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
    "plot_first_event_distribution",
    "plot_top_weapons",
    "plot_map_comparison",
    "plot_map_ratio_with_winloss",
    "plot_trio_metric",
    "plot_metric_bars_by_match",
    "plot_multi_metric_bars_by_match",
    # Sprint 5: Graphiques antagonistes
    "plot_killer_victim_stacked_bars",
    "plot_kd_timeseries",
    "plot_duel_history",
    "plot_nemesis_victim_summary",
    "plot_killer_victim_heatmap",
    "plot_top_antagonists_bars",
    "get_antagonist_chart_colors",
    "create_kd_indicator",
]
