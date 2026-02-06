"""Analyse killer → victime à partir des highlight events (film).

Les highlight events (SPNKr) fournissent typiquement des events 'kill' et 'death'
avec un timestamp en ms depuis le début du match, mais sans lien direct
killer→victim. L'approche consiste à joindre:
- chaque kill event (t)
- avec un death event (t')
avec |t - t'| <= tolérance.

Référence: discussions den.dev / SPNKr (jointure kill/death ~ 5ms).

Sprint 3.1 - Améliorations:
- Validation par totaux officiels (kills/deaths depuis MatchStats)
- Tie-breaker par rang dans le match (meilleur classement = priorité)
- Flag de confiance sur les résultats
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from src.db.loaders import MatchPlayerStats


@dataclass(frozen=True)
class KVPair:
    killer_xuid: str
    killer_gamertag: str
    victim_xuid: str
    victim_gamertag: str
    time_ms: int


@dataclass(frozen=True)
class EstimatedCount:
    """Compteur avec séparation certain/estimé.

    Note: "estimé" signifie qu'il y avait ambiguïté (plusieurs candidats).
    """

    certain: int = 0
    estimated: int = 0

    @property
    def total(self) -> int:
        return int(self.certain) + int(self.estimated)

    @property
    def has_estimated(self) -> bool:
        return int(self.estimated) > 0


@dataclass(frozen=True)
class OpponentDuel:
    """Résumé d'un duel moi <-> adversaire."""

    xuid: str
    gamertag: str
    opponent_killed_me: EstimatedCount
    me_killed_opponent: EstimatedCount


@dataclass(frozen=True)
class ValidationResult:
    """Résultat de validation des paires killer→victim.

    Contient les écarts entre les totaux reconstitués et officiels.
    """

    xuid: str
    kills_reconstituted: int
    kills_official: int
    deaths_reconstituted: int
    deaths_official: int

    @property
    def kills_diff(self) -> int:
        """Écart entre kills reconstitués et officiels."""
        return self.kills_reconstituted - self.kills_official

    @property
    def deaths_diff(self) -> int:
        """Écart entre deaths reconstituées et officielles."""
        return self.deaths_reconstituted - self.deaths_official

    @property
    def is_consistent(self) -> bool:
        """Retourne True si les totaux sont cohérents."""
        return self.kills_diff == 0 and self.deaths_diff == 0


@dataclass(frozen=True)
class AntagonistsResult:
    """Résultat Némésis / Souffre-douleur pour un match."""

    nemesis: OpponentDuel | None
    bully: OpponentDuel | None
    my_deaths_total: int
    my_deaths_assigned_certain: int
    my_deaths_assigned_total: int
    my_kills_total: int
    my_kills_assigned_certain: int
    my_kills_assigned_total: int
    # Sprint 3.1: Ajout du flag de confiance
    is_validated: bool = False
    validation_notes: str = ""


def _coerce_int(v: Any) -> int | None:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        return int(v)
    except Exception:
        return None


def _coerce_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def validate_and_adjust_pairs(
    pairs: list[KVPair],
    official_stats: list[MatchPlayerStats],
) -> tuple[list[ValidationResult], bool]:
    """Valide la cohérence des paires killer→victim avec les stats officielles.

    Stratégie:
    1. Pour chaque joueur du match, compter les kills/deaths reconstitués
    2. Comparer avec les kills/deaths officiels depuis MatchStats
    3. Retourner les écarts et un flag de cohérence globale

    Args:
        pairs: Liste des paires killer→victim reconstituées.
        official_stats: Stats officielles de chaque joueur (depuis load_match_players_stats).

    Returns:
        Tuple (liste de ValidationResult, is_globally_consistent)
    """
    if not official_stats:
        return [], True  # Pas de validation possible, on considère OK

    # Construire un mapping xuid → stats officielles
    stats_by_xuid: dict[str, MatchPlayerStats] = {s.xuid: s for s in official_stats}

    # Compter les kills/deaths reconstitués par joueur
    kills_reconstituted: dict[str, int] = Counter()
    deaths_reconstituted: dict[str, int] = Counter()

    for p in pairs:
        if p.killer_xuid:
            kills_reconstituted[p.killer_xuid] += 1
        if p.victim_xuid:
            deaths_reconstituted[p.victim_xuid] += 1

    # Générer les résultats de validation
    results: list[ValidationResult] = []
    all_xuids = (
        set(stats_by_xuid.keys())
        | set(kills_reconstituted.keys())
        | set(deaths_reconstituted.keys())
    )

    for xuid in all_xuids:
        official = stats_by_xuid.get(xuid)
        results.append(
            ValidationResult(
                xuid=xuid,
                kills_reconstituted=kills_reconstituted.get(xuid, 0),
                kills_official=official.kills if official else 0,
                deaths_reconstituted=deaths_reconstituted.get(xuid, 0),
                deaths_official=official.deaths if official else 0,
            )
        )

    # Vérifier la cohérence globale
    is_globally_consistent = all(r.is_consistent for r in results)

    return results, is_globally_consistent


def get_player_rank(xuid: str, official_stats: list[MatchPlayerStats]) -> int:
    """Retourne le rang d'un joueur dans le match (1 = meilleur).

    Utilisé comme tie-breaker pour les cas ambigus.

    Args:
        xuid: XUID du joueur.
        official_stats: Stats officielles avec rangs.

    Returns:
        Rang du joueur (1 = meilleur), ou 999 si non trouvé.
    """
    for s in official_stats:
        if s.xuid == xuid:
            return s.rank
    return 999  # Non trouvé → rang très bas


def _infer_event_type(event: dict[str, Any]) -> str | None:
    et = _coerce_str(event.get("event_type"))
    if et:
        return et.lower()

    # Fallback: type_hint (blog den.dev)
    th = _coerce_int(event.get("type_hint"))
    if th == 50:
        return "kill"
    if th == 20:
        return "death"
    if th == 10:
        return "mode"
    return None


def compute_killer_victim_pairs(
    events: Iterable[dict[str, Any]],
    *,
    tolerance_ms: int = 5,
) -> list[KVPair]:
    """Construit les paires killer→victim à partir des highlight events.

    Stratégie:
    - sépare les kills et deaths
    - trie les deaths par time_ms
    - pour chaque kill, cherche les deaths dans [t-tol, t+tol]
      et choisit le death le plus proche (en évitant de réutiliser le même death)

    Args:
        events: liste de dicts (un event par entrée)
        tolerance_ms: fenêtre de jointure en millisecondes

    Returns:
        Liste de KVPair (killer, victim, time_ms).
    """

    if tolerance_ms < 0:
        tolerance_ms = 0

    kills: list[tuple[int, dict[str, Any]]] = []
    deaths: list[tuple[int, dict[str, Any]]] = []

    for e in events:
        if not isinstance(e, dict):
            continue
        et = _infer_event_type(e)
        t = _coerce_int(e.get("time_ms"))
        if t is None:
            continue
        if et == "kill":
            kills.append((t, e))
        elif et == "death":
            deaths.append((t, e))

    if not kills or not deaths:
        return []

    kills.sort(key=lambda x: x[0])
    deaths.sort(key=lambda x: x[0])

    death_times = [t for t, _ in deaths]
    used_death_idx: set[int] = set()

    out: list[KVPair] = []

    for t_kill, kill_event in kills:
        lo = bisect_left(death_times, t_kill - tolerance_ms)
        hi = bisect_right(death_times, t_kill + tolerance_ms)
        if lo >= hi:
            continue

        best_idx: int | None = None
        best_delta: int | None = None
        for idx in range(lo, hi):
            if idx in used_death_idx:
                continue
            delta = abs(death_times[idx] - t_kill)
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_idx = idx

        if best_idx is None:
            continue

        used_death_idx.add(best_idx)
        victim_event = deaths[best_idx][1]

        killer_xuid = _coerce_str(kill_event.get("xuid")) or ""
        victim_xuid = _coerce_str(victim_event.get("xuid")) or ""
        killer_gt = _coerce_str(kill_event.get("gamertag")) or killer_xuid or "?"
        victim_gt = _coerce_str(victim_event.get("gamertag")) or victim_xuid or "?"

        if not killer_xuid or not victim_xuid:
            # On garde quand même la paire si les gamertags existent.
            pass

        out.append(
            KVPair(
                killer_xuid=killer_xuid,
                killer_gamertag=killer_gt,
                victim_xuid=victim_xuid,
                victim_gamertag=victim_gt,
                time_ms=int(t_kill),
            )
        )

    return out


def compute_personal_antagonists(
    events: Iterable[dict[str, Any]],
    *,
    me_xuid: str,
    tolerance_ms: int = 5,
    official_stats: list[MatchPlayerStats] | None = None,
) -> AntagonistsResult:
    """Calcule Némésis et Souffre-douleur à partir des highlight events.

    Stratégie hybride (A+B) avec validation (Sprint 3.1):
    - Pass 1: on attribue uniquement les duels non ambigus (1 seul candidat).
    - Pass 2: on attribue les cas ambigus via une heuristique déterministe:
        1) privilégie l'adversaire déjà le plus fréquent en "certain" (Pass 1)
        2) NEW: tie-breaker par rang dans le match (meilleur classement = priorité)
        3) sinon, fallback stable: plus petit XUID (numérique si possible)

    Cette approche évite les résultats "aléatoires" tout en conservant
    une transparence: chaque compteur sépare certain vs estimé.

    Args:
        events: highlight events bruts (dicts) du match.
        me_xuid: XUID du joueur (digits recommandés, ou "xuid(...)" accepté).
        tolerance_ms: fenêtre de jointure en millisecondes.
        official_stats: Stats officielles des joueurs du match (pour validation et tie-breaker).

    Returns:
        AntagonistsResult avec flag de validation.
    """

    if tolerance_ms < 0:
        tolerance_ms = 0

    me = _coerce_str(me_xuid) or ""
    if not me:
        return AntagonistsResult(
            nemesis=None,
            bully=None,
            my_deaths_total=0,
            my_deaths_assigned_certain=0,
            my_deaths_assigned_total=0,
            my_kills_total=0,
            my_kills_assigned_certain=0,
            my_kills_assigned_total=0,
            is_validated=False,
            validation_notes="XUID manquant",
        )

    # Construire un mapping xuid → rang (pour tie-breaker)
    rank_by_xuid: dict[str, int] = {}
    if official_stats:
        for s in official_stats:
            rank_by_xuid[s.xuid] = s.rank

    kills: list[tuple[int, str, str]] = []
    deaths: list[tuple[int, str, str]] = []
    # Map xuid -> last known gamertag (from events)
    gt_by_xuid: dict[str, str] = {}

    for e in events:
        if not isinstance(e, dict):
            continue
        et = _infer_event_type(e)
        t = _coerce_int(e.get("time_ms"))
        if t is None:
            continue
        xu = _coerce_str(e.get("xuid")) or ""
        gt = _coerce_str(e.get("gamertag")) or ""
        if xu and gt:
            gt_by_xuid[xu] = gt
        if et == "kill":
            kills.append((int(t), xu, gt))
        elif et == "death":
            deaths.append((int(t), xu, gt))

    kills.sort(key=lambda x: x[0])
    deaths.sort(key=lambda x: x[0])

    kill_times = [t for t, _xu, _gt in kills]
    death_times = [t for t, _xu, _gt in deaths]

    def _xuid_sort_key(xuid_value: str) -> tuple[int, str]:
        s = str(xuid_value or "").strip()
        try:
            return (0, f"{int(s):020d}")
        except Exception:
            return (1, s)

    def _choose_best(candidates: list[str], prefer: dict[str, int]) -> str:
        """Choisit le meilleur candidat parmi les ambigus.

        Heuristiques (dans l'ordre):
        1. Privilégie l'adversaire déjà le plus fréquent en "certain" (Pass 1)
        2. Tie-breaker par rang dans le match (meilleur classement = priorité)
        3. Fallback stable: plus petit XUID numérique

        Sprint 3.1: Ajout du tie-breaker par rang.
        """
        if not candidates:
            return ""

        # heuristique 1: privilégier ceux déjà fréquents en certain
        best_score = None
        best = None
        for c in candidates:
            score = int(prefer.get(c, 0))
            if best_score is None or score > best_score:
                best_score = score
                best = c

        if best is None:
            return ""

        # si plusieurs candidats ont le même score "certain"
        top_score = int(best_score or 0)
        tied = [c for c in candidates if int(prefer.get(c, 0)) == top_score]

        if len(tied) == 1:
            return tied[0]

        # Sprint 3.1: Tie-breaker par rang dans le match
        # Meilleur rang (plus petit numéro) = priorité
        if rank_by_xuid:
            tied.sort(key=lambda x: (rank_by_xuid.get(x, 999), _xuid_sort_key(x)))
        else:
            # Fallback: plus petit xuid (stable)
            tied.sort(key=_xuid_sort_key)

        return tied[0]

    # -----------------
    # Némésis: qui m'a le plus tué (killer -> me)
    # -----------------
    my_deaths = [(t, vx, vgt) for (t, vx, vgt) in deaths if str(vx) == str(me)]
    my_deaths_total = len(my_deaths)
    used_kill_idx: set[int] = set()

    nem_certain: dict[str, int] = {}
    nem_est: dict[str, int] = {}

    pending_deaths: list[tuple[int, str, str, list[int]]] = []

    for t_death, _vx, _vgt in my_deaths:
        lo = bisect_left(kill_times, t_death - tolerance_ms)
        hi = bisect_right(kill_times, t_death + tolerance_ms)
        cand_idx = [i for i in range(lo, hi) if i not in used_kill_idx]
        if len(cand_idx) == 1:
            i = cand_idx[0]
            used_kill_idx.add(i)
            kx = str(kills[i][1] or "").strip()
            if kx:
                nem_certain[kx] = int(nem_certain.get(kx, 0)) + 1
        elif len(cand_idx) > 1:
            pending_deaths.append((t_death, _vx, _vgt, cand_idx))

    # Pass 2: assignation estimée
    for _t_death, _vx, _vgt, cand_idx in pending_deaths:
        cand_idx2 = [i for i in cand_idx if i not in used_kill_idx]
        if not cand_idx2:
            continue
        candidates = [str(kills[i][1] or "").strip() for i in cand_idx2]
        candidates = [c for c in candidates if c]
        if not candidates:
            continue
        chosen = _choose_best(candidates, nem_certain)
        if not chosen:
            continue
        # on consomme un kill event correspondant au chosen (stable)
        chosen_idxs = [i for i in cand_idx2 if str(kills[i][1] or "").strip() == chosen]
        if not chosen_idxs:
            continue
        used_kill_idx.add(min(chosen_idxs))
        nem_est[chosen] = int(nem_est.get(chosen, 0)) + 1

    my_deaths_assigned_certain = sum(nem_certain.values())
    my_deaths_assigned_total = my_deaths_assigned_certain + sum(nem_est.values())

    # -----------------
    # Souffre-douleur: qui j'ai le plus tué (me -> victim)
    # -----------------
    my_kills = [(t, kx, kgt) for (t, kx, kgt) in kills if str(kx) == str(me)]
    my_kills_total = len(my_kills)
    used_death_idx: set[int] = set()

    bully_certain: dict[str, int] = {}
    bully_est: dict[str, int] = {}
    pending_kills: list[tuple[int, str, str, list[int]]] = []

    for t_kill, _kx, _kgt in my_kills:
        lo = bisect_left(death_times, t_kill - tolerance_ms)
        hi = bisect_right(death_times, t_kill + tolerance_ms)
        cand_idx = [i for i in range(lo, hi) if i not in used_death_idx]
        if len(cand_idx) == 1:
            i = cand_idx[0]
            used_death_idx.add(i)
            vx = str(deaths[i][1] or "").strip()
            if vx and vx != str(me):
                bully_certain[vx] = int(bully_certain.get(vx, 0)) + 1
        elif len(cand_idx) > 1:
            pending_kills.append((t_kill, _kx, _kgt, cand_idx))

    for _t_kill, _kx, _kgt, cand_idx in pending_kills:
        cand_idx2 = [i for i in cand_idx if i not in used_death_idx]
        if not cand_idx2:
            continue
        candidates = [str(deaths[i][1] or "").strip() for i in cand_idx2]
        candidates = [c for c in candidates if c and c != str(me)]
        if not candidates:
            continue
        chosen = _choose_best(candidates, bully_certain)
        if not chosen:
            continue
        chosen_idxs = [i for i in cand_idx2 if str(deaths[i][1] or "").strip() == chosen]
        if not chosen_idxs:
            continue
        used_death_idx.add(min(chosen_idxs))
        bully_est[chosen] = int(bully_est.get(chosen, 0)) + 1

    my_kills_assigned_certain = sum(bully_certain.values())
    my_kills_assigned_total = my_kills_assigned_certain + sum(bully_est.values())

    # -----------------
    # Sélection top nemesis / bully + construction du duel (inclut les 2 sens)
    # -----------------
    def _top_xuid(certain_map: dict[str, int], est_map: dict[str, int]) -> str | None:
        keys = set(certain_map.keys()) | set(est_map.keys())
        if not keys:
            return None
        # max sur total/certain; tie-break xuid asc
        best = None
        best_tuple = None
        for x in keys:
            t = (
                int(certain_map.get(x, 0)) + int(est_map.get(x, 0)),
                int(certain_map.get(x, 0)),
                _xuid_sort_key(x),
            )
            if (
                best_tuple is None
                or t[0] > best_tuple[0]
                or (
                    t[0] == best_tuple[0]
                    and (t[1] > best_tuple[1] or (t[1] == best_tuple[1] and t[2] < best_tuple[2]))
                )
            ):
                best_tuple = t
                best = x
        return best

    nem_xu = _top_xuid(nem_certain, nem_est)
    bully_xu = _top_xuid(bully_certain, bully_est)

    # cross counts (me<->opponent) via the already computed per-direction counters
    def _ec(map_c: dict[str, int], map_e: dict[str, int], key: str | None) -> EstimatedCount:
        if not key:
            return EstimatedCount(0, 0)
        return EstimatedCount(int(map_c.get(key, 0)), int(map_e.get(key, 0)))

    # me killed opponent counters are bully_certain/bully_est (victims)
    def _build_duel(
        op_xu: str | None, *, killed_me_c: dict[str, int], killed_me_e: dict[str, int]
    ) -> OpponentDuel | None:
        if not op_xu:
            return None
        op_gt = gt_by_xuid.get(op_xu, "")
        return OpponentDuel(
            xuid=op_xu,
            gamertag=op_gt,
            opponent_killed_me=_ec(killed_me_c, killed_me_e, op_xu),
            me_killed_opponent=_ec(bully_certain, bully_est, op_xu),
        )

    nemesis = _build_duel(nem_xu, killed_me_c=nem_certain, killed_me_e=nem_est)
    bully = _build_duel(bully_xu, killed_me_c=nem_certain, killed_me_e=nem_est)

    # Sprint 3.1: Validation avec les stats officielles
    is_validated = False
    validation_notes = ""

    if official_stats:
        # Trouver mes stats officielles
        my_official = next((s for s in official_stats if s.xuid == me), None)
        if my_official:
            # Comparer mes kills/deaths reconstitués vs officiels
            kills_diff = my_kills_assigned_total - my_official.kills
            deaths_diff = my_deaths_assigned_total - my_official.deaths

            if kills_diff == 0 and deaths_diff == 0:
                is_validated = True
                validation_notes = "Cohérent avec stats officielles"
            else:
                notes = []
                if kills_diff != 0:
                    notes.append(
                        f"kills: {my_kills_assigned_total} vs {my_official.kills} ({kills_diff:+d})"
                    )
                if deaths_diff != 0:
                    notes.append(
                        f"deaths: {my_deaths_assigned_total} vs {my_official.deaths} ({deaths_diff:+d})"
                    )
                validation_notes = "Écarts: " + ", ".join(notes)
        else:
            validation_notes = "Stats officielles du joueur non trouvées"
    else:
        validation_notes = "Pas de stats officielles pour validation"

    return AntagonistsResult(
        nemesis=nemesis,
        bully=bully,
        my_deaths_total=int(my_deaths_total),
        my_deaths_assigned_certain=int(my_deaths_assigned_certain),
        my_deaths_assigned_total=int(my_deaths_assigned_total),
        my_kills_total=int(my_kills_total),
        my_kills_assigned_certain=int(my_kills_assigned_certain),
        my_kills_assigned_total=int(my_kills_assigned_total),
        is_validated=is_validated,
        validation_notes=validation_notes,
    )


def killer_victim_counts_long(pairs: Iterable[KVPair]) -> pd.DataFrame:
    """Retourne un DF long: killer, victim, count (agrégé).

    ⚠️ DÉPRÉCIÉ : Utiliser killer_victim_counts_long_polars() avec un DataFrame Polars.
    Cette fonction sera supprimée dans une future version.
    """

    counter = Counter(
        (p.killer_xuid, p.killer_gamertag, p.victim_xuid, p.victim_gamertag) for p in pairs
    )
    rows = [
        {
            "killer_xuid": kx,
            "killer_gamertag": kgt,
            "victim_xuid": vx,
            "victim_gamertag": vgt,
            "count": int(cnt),
        }
        for (kx, kgt, vx, vgt), cnt in counter.items()
    ]

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(
        ["count", "killer_gamertag", "victim_gamertag"], ascending=[False, True, True]
    )


def killer_victim_matrix(pairs: Iterable[KVPair]) -> pd.DataFrame:
    """Retourne un DF matrice: index=killer, colonnes=victim, valeurs=count.

    ⚠️ DÉPRÉCIÉ : Utiliser killer_victim_matrix_polars() avec un DataFrame Polars.
    Cette fonction sera supprimée dans une future version.
    """

    df = killer_victim_counts_long(pairs)
    if df.empty:
        return df

    pivot = df.pivot_table(
        index="killer_gamertag",
        columns="victim_gamertag",
        values="count",
        aggfunc="sum",
        fill_value=0,
    )

    # Tri stable: killers/victims les plus "actifs" d'abord
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]
    pivot = pivot[pivot.sum(axis=0).sort_values(ascending=False).index]
    return pivot


# =============================================================================
# Sprint 3 : Fonctions d'analyse Polars
# =============================================================================

try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None  # type: ignore


@dataclass(frozen=True)
class AntagonistsResultPolars:
    """Résultat Némésis / Souffre-douleur calculé avec Polars.

    Version simplifiée pour les données provenant de killer_victim_pairs DuckDB.
    """

    nemesis_xuid: str | None
    nemesis_gamertag: str | None
    nemesis_times_killed_by: int
    victim_xuid: str | None
    victim_gamertag: str | None
    victim_times_killed: int
    total_deaths: int
    total_kills: int


def compute_personal_antagonists_from_pairs_polars(
    pairs_df: pl.DataFrame,
    me_xuid: str,
) -> AntagonistsResultPolars:
    """Calcule antagonistes (némésis/souffre-douleur) avec Polars.

    Cette fonction utilise les données de killer_victim_pairs stockées en DuckDB.
    Plus simple que compute_personal_antagonists() car les paires sont déjà établies.

    Args:
        pairs_df: DataFrame Polars avec colonnes killer_xuid, killer_gamertag,
                  victim_xuid, victim_gamertag, kill_count.
        me_xuid: XUID du joueur principal.

    Returns:
        AntagonistsResultPolars avec némésis et souffre-douleur.
    """
    if not POLARS_AVAILABLE:
        raise ImportError("Polars n'est pas installé. Installez-le avec: pip install polars")

    if pairs_df.is_empty():
        return AntagonistsResultPolars(
            nemesis_xuid=None,
            nemesis_gamertag=None,
            nemesis_times_killed_by=0,
            victim_xuid=None,
            victim_gamertag=None,
            victim_times_killed=0,
            total_deaths=0,
            total_kills=0,
        )

    # Némésis : qui m'a le plus tué (je suis la victime)
    nemesis_df = (
        pairs_df.filter(pl.col("victim_xuid") == me_xuid)
        .group_by("killer_xuid", "killer_gamertag")
        .agg(pl.col("kill_count").sum().alias("times_killed_by"))
        .sort("times_killed_by", descending=True)
        .head(1)
    )

    # Souffre-douleur : qui j'ai le plus tué (je suis le tueur)
    victim_df = (
        pairs_df.filter(pl.col("killer_xuid") == me_xuid)
        .group_by("victim_xuid", "victim_gamertag")
        .agg(pl.col("kill_count").sum().alias("times_killed"))
        .sort("times_killed", descending=True)
        .head(1)
    )

    # Totaux
    total_deaths = (
        pairs_df.filter(pl.col("victim_xuid") == me_xuid).select(pl.col("kill_count").sum()).item()
    ) or 0

    total_kills = (
        pairs_df.filter(pl.col("killer_xuid") == me_xuid).select(pl.col("kill_count").sum()).item()
    ) or 0

    # Extraire les résultats
    nemesis_xuid = None
    nemesis_gamertag = None
    nemesis_times_killed_by = 0
    if len(nemesis_df) > 0:
        row = nemesis_df.row(0, named=True)
        nemesis_xuid = row["killer_xuid"]
        nemesis_gamertag = row["killer_gamertag"]
        nemesis_times_killed_by = row["times_killed_by"]

    victim_xuid = None
    victim_gamertag = None
    victim_times_killed = 0
    if len(victim_df) > 0:
        row = victim_df.row(0, named=True)
        victim_xuid = row["victim_xuid"]
        victim_gamertag = row["victim_gamertag"]
        victim_times_killed = row["times_killed"]

    return AntagonistsResultPolars(
        nemesis_xuid=nemesis_xuid,
        nemesis_gamertag=nemesis_gamertag,
        nemesis_times_killed_by=nemesis_times_killed_by,
        victim_xuid=victim_xuid,
        victim_gamertag=victim_gamertag,
        victim_times_killed=victim_times_killed,
        total_deaths=total_deaths,
        total_kills=total_kills,
    )


def killer_victim_counts_long_polars(pairs_df: pl.DataFrame) -> pl.DataFrame:
    """Retourne un DataFrame Polars agrégé: killer, victim, count.

    Équivalent Polars de killer_victim_counts_long() pour les paires KVPair.

    Args:
        pairs_df: DataFrame Polars avec colonnes killer_xuid, killer_gamertag,
                  victim_xuid, victim_gamertag, kill_count.

    Returns:
        DataFrame Polars avec colonnes killer_xuid, killer_gamertag,
        victim_xuid, victim_gamertag, count, trié par count desc.
    """
    if not POLARS_AVAILABLE:
        raise ImportError("Polars n'est pas installé. Installez-le avec: pip install polars")

    if pairs_df.is_empty():
        return pairs_df

    return (
        pairs_df.group_by("killer_xuid", "killer_gamertag", "victim_xuid", "victim_gamertag")
        .agg(pl.col("kill_count").sum().alias("count"))
        .sort(["count", "killer_gamertag", "victim_gamertag"], descending=[True, False, False])
    )


def compute_kd_timeseries_by_minute_polars(
    pairs_df: pl.DataFrame,
    me_xuid: str,
    *,
    match_duration_ms: int | None = None,
) -> pl.DataFrame:
    """Calcule le K/D cumulé par minute avec Polars.

    Utile pour visualiser la progression du K/D au cours d'un match.

    Args:
        pairs_df: DataFrame Polars avec colonnes killer_xuid, victim_xuid, time_ms.
        me_xuid: XUID du joueur principal.
        match_duration_ms: Durée du match en ms (optionnel, pour compléter les minutes vides).

    Returns:
        DataFrame Polars avec colonnes minute, kills, deaths, net_kd, cumulative_net_kd.
    """
    if not POLARS_AVAILABLE:
        raise ImportError("Polars n'est pas installé. Installez-le avec: pip install polars")

    if pairs_df.is_empty():
        return pl.DataFrame(
            {
                "minute": [],
                "kills": [],
                "deaths": [],
                "net_kd": [],
                "cumulative_net_kd": [],
            }
        )

    # Mes kills par minute
    my_kills = (
        pairs_df.filter(pl.col("killer_xuid") == me_xuid)
        .with_columns((pl.col("time_ms") // 60000).alias("minute"))
        .group_by("minute")
        .agg(pl.col("kill_count").sum().alias("kills"))
    )

    # Mes deaths par minute
    my_deaths = (
        pairs_df.filter(pl.col("victim_xuid") == me_xuid)
        .with_columns((pl.col("time_ms") // 60000).alias("minute"))
        .group_by("minute")
        .agg(pl.col("kill_count").sum().alias("deaths"))
    )

    # Déterminer la plage de minutes
    all_minutes = set()
    if len(my_kills) > 0:
        all_minutes.update(my_kills["minute"].to_list())
    if len(my_deaths) > 0:
        all_minutes.update(my_deaths["minute"].to_list())

    if match_duration_ms:
        max_minute = match_duration_ms // 60000
        all_minutes.update(range(max_minute + 1))

    if not all_minutes:
        return pl.DataFrame(
            {
                "minute": [],
                "kills": [],
                "deaths": [],
                "net_kd": [],
                "cumulative_net_kd": [],
            }
        )

    # Créer un DataFrame avec toutes les minutes
    minutes_df = pl.DataFrame({"minute": sorted(all_minutes)})

    # Joindre kills et deaths
    result = (
        minutes_df.join(my_kills, on="minute", how="left")
        .join(my_deaths, on="minute", how="left")
        .with_columns(
            [
                pl.col("kills").fill_null(0),
                pl.col("deaths").fill_null(0),
            ]
        )
        .with_columns((pl.col("kills") - pl.col("deaths")).alias("net_kd"))
        .with_columns(pl.col("net_kd").cum_sum().alias("cumulative_net_kd"))
        .sort("minute")
    )

    return result


def compute_duel_history_polars(
    pairs_df: pl.DataFrame,
    me_xuid: str,
    opponent_xuid: str,
) -> pl.DataFrame:
    """Calcule l'historique des duels entre deux joueurs avec Polars.

    Args:
        pairs_df: DataFrame Polars avec colonnes match_id, killer_xuid, victim_xuid, time_ms.
        me_xuid: XUID du joueur principal.
        opponent_xuid: XUID de l'adversaire.

    Returns:
        DataFrame Polars avec colonnes match_id, my_kills, opponent_kills, net.
    """
    if not POLARS_AVAILABLE:
        raise ImportError("Polars n'est pas installé. Installez-le avec: pip install polars")

    if pairs_df.is_empty():
        return pl.DataFrame(
            {
                "match_id": [],
                "my_kills": [],
                "opponent_kills": [],
                "net": [],
            }
        )

    # Mes kills sur l'adversaire
    my_kills = (
        pairs_df.filter(
            (pl.col("killer_xuid") == me_xuid) & (pl.col("victim_xuid") == opponent_xuid)
        )
        .group_by("match_id")
        .agg(pl.col("kill_count").sum().alias("my_kills"))
    )

    # Kills de l'adversaire sur moi
    opponent_kills = (
        pairs_df.filter(
            (pl.col("killer_xuid") == opponent_xuid) & (pl.col("victim_xuid") == me_xuid)
        )
        .group_by("match_id")
        .agg(pl.col("kill_count").sum().alias("opponent_kills"))
    )

    # Combiner
    all_matches = set()
    if len(my_kills) > 0:
        all_matches.update(my_kills["match_id"].to_list())
    if len(opponent_kills) > 0:
        all_matches.update(opponent_kills["match_id"].to_list())

    if not all_matches:
        return pl.DataFrame(
            {
                "match_id": [],
                "my_kills": [],
                "opponent_kills": [],
                "net": [],
            }
        )

    matches_df = pl.DataFrame({"match_id": list(all_matches)})

    result = (
        matches_df.join(my_kills, on="match_id", how="left")
        .join(opponent_kills, on="match_id", how="left")
        .with_columns(
            [
                pl.col("my_kills").fill_null(0),
                pl.col("opponent_kills").fill_null(0),
            ]
        )
        .with_columns((pl.col("my_kills") - pl.col("opponent_kills")).alias("net"))
    )

    return result


def killer_victim_matrix_polars(pairs_df: pl.DataFrame) -> pl.DataFrame:
    """Retourne une matrice killer/victim en format pivot avec Polars.

    Args:
        pairs_df: DataFrame Polars avec colonnes killer_gamertag, victim_gamertag, kill_count.

    Returns:
        DataFrame Polars pivotée avec gamertags en lignes et colonnes.
    """
    if not POLARS_AVAILABLE:
        raise ImportError("Polars n'est pas installé. Installez-le avec: pip install polars")

    if pairs_df.is_empty():
        return pairs_df

    # Agréger les counts
    aggregated = pairs_df.group_by("killer_gamertag", "victim_gamertag").agg(
        pl.col("kill_count").sum().alias("count")
    )

    # Créer la matrice pivot
    return aggregated.pivot(
        values="count",
        index="killer_gamertag",
        on="victim_gamertag",
        aggregate_function="sum",
    ).fill_null(0)
