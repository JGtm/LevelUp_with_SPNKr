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
from src.visualization.objective_charts import (
    get_objective_chart_colors,
    plot_assist_breakdown_pie,
    plot_objective_breakdown_bars,
    plot_objective_ratio_gauge,
    plot_objective_trend_over_time,
    plot_objective_vs_kills_scatter,
    plot_top_players_objective_bars,
)
from src.visualization.participation_charts import (
    aggregate_participation_for_radar,
    compute_participation_percentages,
    create_participation_indicator,
    get_participation_colors,
    plot_participation_bars,
    plot_participation_by_match,
    plot_participation_pie,
    plot_participation_sunburst,
)
from src.visualization.participation_radar import (
    RADAR_AXIS_LINES,
    RADAR_THRESHOLDS,
    compute_global_radar_thresholds,
    compute_participation_profile,
    get_radar_thresholds,
)
from src.visualization.performance import (
    create_cumulative_metrics_indicator,
    get_performance_colors,
    plot_cumulative_comparison,
    plot_cumulative_kd,
    plot_cumulative_net_score,
    plot_rolling_kd,
    plot_session_trend,
)
from src.visualization.theme import apply_halo_plot_style
from src.visualization.timeseries import (
    plot_accuracy_last_n,
    plot_assists_timeseries,
    plot_average_life,
    plot_damage_dealt_taken,
    plot_per_minute_timeseries,
    plot_performance_timeseries,
    plot_rank_score,
    plot_shots_accuracy,
    plot_spree_headshots_accuracy,
    plot_streak_chart,
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
    # Sprint 7: Nouvelles visualisations V/D + Stats
    "plot_streak_chart",
    "plot_damage_dealt_taken",
    "plot_shots_accuracy",
    "plot_rank_score",
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
    # Sprint 6: Performance cumulée
    "plot_cumulative_net_score",
    "plot_cumulative_kd",
    "plot_rolling_kd",
    "plot_session_trend",
    "plot_cumulative_comparison",
    "create_cumulative_metrics_indicator",
    "get_performance_colors",
    # Sprint 7: Graphiques objectifs
    "plot_objective_vs_kills_scatter",
    "plot_objective_breakdown_bars",
    "plot_top_players_objective_bars",
    "plot_objective_ratio_gauge",
    "plot_assist_breakdown_pie",
    "plot_objective_trend_over_time",
    "get_objective_chart_colors",
    # Sprint 8.2: Graphiques participation (PersonalScores)
    "plot_participation_pie",
    "plot_participation_bars",
    "plot_participation_by_match",
    "create_participation_indicator",
    "plot_participation_sunburst",
    "get_participation_colors",
    "aggregate_participation_for_radar",
    "compute_participation_percentages",
    # Radar participation unifié (6 axes)
    "RADAR_AXIS_LINES",
    "RADAR_THRESHOLDS",
    "compute_participation_profile",
    "compute_global_radar_thresholds",
    "get_radar_thresholds",
]
