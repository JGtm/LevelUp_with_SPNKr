"""Modèles de données pour le module de synchronisation.

Contient les dataclasses et modèles Pydantic pour :
- Options de synchronisation (SyncOptions)
- Résultats de synchronisation (SyncResult)
- Données de match intermédiaires (MatchData, MatchHistoryItem)
- Lignes DuckDB (MatchStatsRow, PlayerMatchStatsRow, HighlightEventRow)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# =============================================================================
# Options et résultats de synchronisation
# =============================================================================


@dataclass
class SyncOptions:
    """Options de synchronisation.

    Attributes:
        match_type: Type de matchs (all, matchmaking, custom, local).
        max_matches: Nombre maximum de matchs à récupérer.
        with_highlight_events: Récupérer les highlight events (kills/deaths).
        with_skill: Récupérer les données MMR/skill.
        with_aliases: Mettre à jour les aliases XUID → Gamertag.
        with_participants: Extraire les participants de chaque match (roster complet).
        with_assets: Récupérer les assets (maps, playlists).
        requests_per_second: Rate limiting API (requêtes/seconde).
        parallel_matches: Nombre de matchs traités en parallèle.
    """

    match_type: str = "matchmaking"
    max_matches: int = 200
    with_highlight_events: bool = True
    with_skill: bool = True
    with_aliases: bool = True
    with_participants: bool = True  # Sprint Gamertag Roster Fix
    with_assets: bool = True
    requests_per_second: int = 5
    parallel_matches: int = 3


@dataclass
class SyncResult:
    """Résultat d'une synchronisation.

    Contient les compteurs et erreurs pour le rapport final.
    """

    matches_inserted: int = 0
    matches_updated: int = 0
    matches_skipped: int = 0
    highlight_events_inserted: int = 0
    skill_records_inserted: int = 0
    aliases_updated: int = 0
    assets_imported: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def success(self) -> bool:
        """True si la sync a réussi (même partiellement)."""
        # Succès si au moins un match inséré ou aucune erreur fatale
        return self.matches_inserted > 0 or len(self.errors) == 0

    @property
    def total_matches_processed(self) -> int:
        """Nombre total de matchs traités (insérés + mis à jour + skippés)."""
        return self.matches_inserted + self.matches_updated + self.matches_skipped

    def to_message(self) -> str:
        """Message de résumé pour l'UI."""
        if not self.success:
            error_preview = ", ".join(self.errors[:2])
            return f"❌ Sync échouée: {error_preview}"

        parts = []
        if self.matches_inserted > 0:
            parts.append(f"{self.matches_inserted} nouveaux matchs")
        if self.matches_updated > 0:
            parts.append(f"{self.matches_updated} mis à jour")
        if self.highlight_events_inserted > 0:
            parts.append(f"{self.highlight_events_inserted} events")
        if self.aliases_updated > 0:
            parts.append(f"{self.aliases_updated} aliases")

        if not parts:
            parts.append("Déjà à jour")

        duration_str = ""
        if self.duration_seconds > 0:
            duration_str = f" ({self.duration_seconds:.1f}s)"

        return f"✅ {', '.join(parts)}{duration_str}"

    def to_dict(self) -> dict[str, Any]:
        """Convertit en dict pour sérialisation JSON."""
        return {
            "success": self.success,
            "matches_inserted": self.matches_inserted,
            "matches_updated": self.matches_updated,
            "matches_skipped": self.matches_skipped,
            "highlight_events_inserted": self.highlight_events_inserted,
            "skill_records_inserted": self.skill_records_inserted,
            "aliases_updated": self.aliases_updated,
            "assets_imported": self.assets_imported,
            "errors": self.errors,
            "warnings": self.warnings,
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


# =============================================================================
# Données de match intermédiaires (API → Transformer)
# =============================================================================


@dataclass
class MatchHistoryItem:
    """Item de l'historique des matchs (résultat léger).

    Contient uniquement les informations minimales pour décider
    si on doit récupérer les détails du match.
    """

    match_id: str
    start_time: str
    match_type: str | None = None
    playlist_id: str | None = None
    map_id: str | None = None


@dataclass
class MatchData:
    """Données complètes d'un match (stats + skill + events).

    Contient les JSON bruts de l'API avant transformation.
    """

    match_id: str
    stats_json: dict[str, Any]
    skill_json: dict[str, Any] | None = None
    highlight_events: list[dict[str, Any]] = field(default_factory=list)


# =============================================================================
# Lignes DuckDB (résultat des transformers)
# =============================================================================


@dataclass
class MatchStatsRow:
    """Ligne pour la table match_stats.

    Correspond exactement aux colonnes de match_stats dans DuckDB.
    """

    match_id: str
    start_time: datetime | None = None
    end_time: datetime | None = None  # start_time + time_played_seconds
    playlist_id: str | None = None
    playlist_name: str | None = None
    map_id: str | None = None
    map_name: str | None = None
    pair_id: str | None = None
    pair_name: str | None = None
    game_variant_id: str | None = None
    game_variant_name: str | None = None
    outcome: int | None = None
    team_id: int | None = None
    rank: int | None = None
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    kda: float | None = None
    accuracy: float | None = None
    headshot_kills: int | None = None
    max_killing_spree: int | None = None
    time_played_seconds: int | None = None
    avg_life_seconds: float | None = None
    my_team_score: int | None = None
    enemy_team_score: int | None = None
    team_mmr: float | None = None
    enemy_mmr: float | None = None
    damage_dealt: float | None = None
    damage_taken: float | None = None
    shots_fired: int | None = None
    shots_hit: int | None = None
    grenade_kills: int | None = None
    melee_kills: int | None = None
    power_weapon_kills: int | None = None
    score: int | None = None
    personal_score: int | None = None
    mode_category: str | None = None
    game_variant_category: int | None = (
        None  # Sprint 2: GameVariantCategory API (6=Slayer, 15=CTF, etc.)
    )
    is_ranked: bool = False
    is_firefight: bool = False
    left_early: bool = False
    teammates_signature: str | None = None


@dataclass
class PlayerMatchStatsRow:
    """Ligne pour la table player_match_stats (MMR/skill)."""

    match_id: str
    xuid: str
    team_id: int | None = None
    team_mmr: float | None = None
    enemy_mmr: float | None = None
    kills_expected: float | None = None
    kills_stddev: float | None = None
    deaths_expected: float | None = None
    deaths_stddev: float | None = None
    assists_expected: float | None = None
    assists_stddev: float | None = None


@dataclass
class HighlightEventRow:
    """Ligne pour la table highlight_events."""

    match_id: str
    event_type: str
    time_ms: int
    xuid: str | None = None
    gamertag: str | None = None
    type_hint: int | None = None
    raw_json: str = "{}"


@dataclass
class XuidAliasRow:
    """Ligne pour la table xuid_aliases."""

    xuid: str
    gamertag: str
    last_seen: datetime | None = None
    source: str = "sync"


@dataclass
class MedalEarnedRow:
    """Ligne pour la table medals_earned."""

    match_id: str
    medal_name_id: int
    count: int


# =============================================================================
# Sprint 8 : Nouvelles tables pour backfill
# =============================================================================


@dataclass
class KillerVictimPairRow:
    """Ligne pour la table killer_victim_pairs.

    Stocke les paires killer→victim calculées depuis highlight_events.
    Permet des requêtes rapides pour némésis/souffre-douleur.
    """

    match_id: str
    killer_xuid: str
    victim_xuid: str
    killer_gamertag: str | None = None
    victim_gamertag: str | None = None
    kill_count: int = 1
    time_ms: int | None = None
    is_validated: bool = False


@dataclass
class PersonalScoreAwardRow:
    """Ligne pour la table personal_score_awards.

    Stocke les awards individuels contribuant au PersonalScore.
    Catégories : objective, assist, kill, medal, etc.
    """

    match_id: str
    xuid: str
    award_name: str
    award_category: str | None = None
    award_count: int = 1
    award_score: int = 0


@dataclass
class MatchParticipantRow:
    """Ligne pour la table match_participants.

    Stocke TOUS les joueurs d'un match avec leurs informations d'équipe.
    Source : MatchStats.Players[] (API propre, pas les films corrompus).

    Permet de :
    - Reconstruire le roster complet d'un match
    - Identifier les coéquipiers et adversaires
    - Avoir des gamertags propres (vs highlight_events corrompus)
    """

    match_id: str
    xuid: str
    team_id: int | None = None
    outcome: int | None = None
    gamertag: str | None = None


# =============================================================================
# Données Career Rank (Phase 5)
# =============================================================================


@dataclass
class CareerRankData:
    """Données de progression du rang carrière.

    Correspond à l'endpoint economy/rewardtracks/careerranks.
    """

    xuid: str
    current_rank: int = 0
    current_rank_name: str = ""
    current_rank_tier: str = ""
    current_xp: int = 0
    xp_for_next_rank: int = 0
    xp_total: int = 0
    is_max_rank: bool = False
    adornment_path: str | None = None
    spartan_id: str | None = None
    raw_json: dict[str, Any] = field(default_factory=dict)

    @property
    def progress_to_next_rank(self) -> float:
        """Pourcentage de progression vers le prochain rang (0-100)."""
        if self.is_max_rank or self.xp_for_next_rank == 0:
            return 100.0
        return min(100.0, (self.current_xp / self.xp_for_next_rank) * 100)


@dataclass
class CareerRankRow:
    """Ligne pour la table career_progression dans DuckDB."""

    xuid: str
    rank: int
    rank_name: str
    rank_tier: str
    current_xp: int
    xp_for_next_rank: int
    xp_total: int
    is_max_rank: bool
    adornment_path: str | None = None
    recorded_at: datetime | None = None
