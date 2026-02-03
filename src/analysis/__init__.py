"""Module d'analyse des données."""

from src.analysis.antagonists import (
    AggregationResult,
    AntagonistEntry,
    aggregate_antagonists,
    aggregate_antagonists_from_events,
)
from src.analysis.filters import (
    build_option_map,
    build_xuid_option_map,
    is_allowed_playlist_name,
    mark_firefight,
)
from src.analysis.killer_victim import (
    AntagonistsResult,
    AntagonistsResultPolars,
    EstimatedCount,
    KVPair,
    OpponentDuel,
    compute_duel_history_polars,
    compute_kd_timeseries_by_minute_polars,
    compute_killer_victim_pairs,
    compute_personal_antagonists,
    compute_personal_antagonists_from_pairs_polars,
    killer_victim_counts_long,
    killer_victim_counts_long_polars,
    killer_victim_matrix,
    killer_victim_matrix_polars,
)
from src.analysis.maps import compute_map_breakdown
from src.analysis.objective_participation import (
    AssistBreakdownResult,
    ObjectiveParticipationResult,
    PlayerObjectiveRanking,
    compute_assist_breakdown_polars,
    compute_award_frequency_polars,
    compute_objective_participation_score_polars,
    compute_objective_summary_by_match_polars,
    get_assist_awards_with_points,
    get_objective_mode_awards,
    is_objective_mode_match,
    rank_players_by_objective_contribution_polars,
)
from src.analysis.performance_config import MIN_MATCHES_FOR_RELATIVE
from src.analysis.performance_score import (
    compute_match_performance_from_row,
    compute_performance_series,
    compute_relative_performance_score,
)
from src.analysis.sessions import (
    DEFAULT_SESSION_GAP_MINUTES,
    SESSION_CUTOFF_HOUR,
    compute_sessions,
    compute_sessions_with_context,
    is_session_potentially_active,
)
from src.analysis.stats import (
    compute_aggregated_stats,
    compute_global_ratio,
    compute_mode_category_averages,
    compute_outcome_rates,
    extract_mode_category,
)

__all__ = [
    "compute_aggregated_stats",
    "compute_outcome_rates",
    "compute_global_ratio",
    "compute_sessions",
    "compute_sessions_with_context",
    "is_session_potentially_active",
    "DEFAULT_SESSION_GAP_MINUTES",
    "SESSION_CUTOFF_HOUR",
    "compute_map_breakdown",
    "mark_firefight",
    "is_allowed_playlist_name",
    "build_option_map",
    "build_xuid_option_map",
    "KVPair",
    "compute_killer_victim_pairs",
    "compute_personal_antagonists",
    "AntagonistsResult",
    "OpponentDuel",
    "EstimatedCount",
    "killer_victim_counts_long",
    "killer_victim_matrix",
    # Sprint 3: Fonctions Polars
    "AntagonistsResultPolars",
    "compute_personal_antagonists_from_pairs_polars",
    "killer_victim_counts_long_polars",
    "compute_kd_timeseries_by_minute_polars",
    "compute_duel_history_polars",
    "killer_victim_matrix_polars",
    "compute_match_performance_from_row",
    "compute_relative_performance_score",
    "compute_performance_series",
    "MIN_MATCHES_FOR_RELATIVE",
    "extract_mode_category",
    "compute_mode_category_averages",
    # Sprint 3.2: Agrégation des antagonistes
    "aggregate_antagonists",
    "aggregate_antagonists_from_events",
    "AntagonistEntry",
    "AggregationResult",
    # Sprint 4: Participation aux objectifs avec Polars
    "ObjectiveParticipationResult",
    "AssistBreakdownResult",
    "PlayerObjectiveRanking",
    "compute_objective_participation_score_polars",
    "rank_players_by_objective_contribution_polars",
    "compute_assist_breakdown_polars",
    "compute_objective_summary_by_match_polars",
    "compute_award_frequency_polars",
    "get_objective_mode_awards",
    "get_assist_awards_with_points",
    "is_objective_mode_match",
]
