"""
Mixin pour le chargement des rosters et la résolution des gamertags.

Regroupe les méthodes d'analyse des compositions d'équipes et
de résolution XUID → Gamertag extraites de DuckDBRepository :
- load_match_rosters
- load_matches_with_teammate
- load_same_team_match_ids
- has_match_participants
- resolve_gamertag
- _extract_ascii_token
- resolve_gamertags_batch
- load_match_player_gamertags
- load_match_players_stats
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class RosterLoaderMixin:
    """Mixin fournissant le chargement des rosters et la résolution des gamertags pour DuckDBRepository."""

    def load_match_rosters(
        self,
        match_id: str,
    ) -> dict[str, Any] | None:
        """Charge les rosters d'un match depuis killer_victim_pairs ou highlight_events.

        Utilise killer_victim_pairs si disponible (source fiable), sinon
        analyse les patterns de kills dans highlight_events.

        Returns:
            None si le match n'existe pas ou si les données sont insuffisantes.
            Sinon un dict avec la structure:
            {
                "my_team_id": int,
                "my_team": [{"xuid": str, "gamertag": str|None, "team_id": int|None, "is_me": bool}],
                "enemy_team": [...],
            }
        """
        conn = self._get_connection()

        try:
            # Obtenir le team_id du joueur principal depuis match_stats
            match_info = conn.execute(
                "SELECT team_id FROM match_stats WHERE match_id = ?",
                [match_id],
            ).fetchone()

            if not match_info:
                return None

            my_team_id = match_info[0]
            if my_team_id is None:
                return None

            my_xuid_str = str(self._xuid).strip()

            # Fonction de nettoyage des gamertags
            def _clean_gamertag(value: Any) -> str | None:
                """Nettoie un gamertag en supprimant les caractères invalides."""
                if value is None:
                    return None
                try:
                    s = str(value)
                    s = s.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
                    s = s.replace("\ufffd", "")
                    s = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", s)
                    s = re.sub(r"[\ufffe\uffff]", "", s)
                    s = re.sub(r"[\s\t]+", " ", s).strip()
                    s = s.strip("\u200b\u200c\u200d\ufeff")
                    if not s or s == "?" or s.isdigit() or s.lower().startswith("xuid("):
                        return None
                    if not any(c.isprintable() for c in s):
                        return None
                    return s
                except Exception:
                    return None

            # ======================================================================
            # MÉTHODE 1 : Utiliser killer_victim_pairs si disponible (source fiable)
            # ======================================================================
            has_kvp = False
            try:
                kvp_check = conn.execute(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'main' AND table_name = 'killer_victim_pairs'"
                ).fetchone()
                has_kvp = kvp_check is not None
            except Exception:
                pass

            team_by_xuid: dict[str, int | None] = {}
            gamertag_by_xuid: dict[str, str | None] = {}

            if has_kvp:
                # Utiliser killer_victim_pairs pour déterminer les équipes
                # Logique : si je tue quelqu'un → adversaire, si quelqu'un me tue → adversaire
                # Si quelqu'un tue mes adversaires → coéquipier
                try:
                    kvp_result = conn.execute(
                        """
                        SELECT killer_xuid, killer_gamertag, victim_xuid, victim_gamertag, kill_count
                        FROM killer_victim_pairs
                        WHERE match_id = ?
                        """,
                        [match_id],
                    ).fetchall()

                    enemies: set[str] = set()
                    allies: set[str] = set()

                    for killer_xuid, killer_gt, victim_xuid, victim_gt, _ in kvp_result:
                        k_xu = str(killer_xuid or "").strip()
                        v_xu = str(victim_xuid or "").strip()

                        # Stocker les gamertags (préférer le plus long)
                        if k_xu:
                            k_gt = _clean_gamertag(killer_gt)
                            if k_gt and (
                                k_xu not in gamertag_by_xuid
                                or len(k_gt) > len(gamertag_by_xuid.get(k_xu) or "")
                            ):
                                gamertag_by_xuid[k_xu] = k_gt
                        if v_xu:
                            v_gt = _clean_gamertag(victim_gt)
                            if v_gt and (
                                v_xu not in gamertag_by_xuid
                                or len(v_gt) > len(gamertag_by_xuid.get(v_xu) or "")
                            ):
                                gamertag_by_xuid[v_xu] = v_gt

                        if not k_xu or not v_xu:
                            continue

                        # Si je suis le killer → la victime est un adversaire
                        if k_xu == my_xuid_str:
                            enemies.add(v_xu)
                        # Si je suis la victime → le killer est un adversaire
                        elif v_xu == my_xuid_str:
                            enemies.add(k_xu)

                    # Deuxième passe : si quelqu'un tue un adversaire confirmé → allié
                    # Si quelqu'un est tué par un adversaire confirmé → allié
                    for killer_xuid, _, victim_xuid, _, _ in kvp_result:
                        k_xu = str(killer_xuid or "").strip()
                        v_xu = str(victim_xuid or "").strip()
                        if not k_xu or not v_xu:
                            continue

                        # Si le killer tue un adversaire confirmé → le killer est un allié
                        if v_xu in enemies and k_xu != my_xuid_str:
                            allies.add(k_xu)
                        # Si la victime est tuée par un adversaire confirmé → la victime est un alliée
                        if k_xu in enemies and v_xu != my_xuid_str:
                            allies.add(v_xu)

                    # Assigner les équipes
                    team_by_xuid[my_xuid_str] = my_team_id
                    for xu in enemies:
                        if xu != my_xuid_str:
                            team_by_xuid[xu] = None  # Adversaire
                    for xu in allies:
                        if xu != my_xuid_str and xu not in enemies:
                            team_by_xuid[xu] = my_team_id  # Allié

                except Exception as e:
                    logger.debug(f"Erreur lecture killer_victim_pairs: {e}")

            # ======================================================================
            # Extraire tous les joueurs uniques (depuis kvp ou highlight_events)
            # ======================================================================
            all_xuids: set[str] = set(gamertag_by_xuid.keys())

            # Compléter avec highlight_events
            try:
                he_result = conn.execute(
                    """
                    SELECT xuid, gamertag
                    FROM (
                        SELECT xuid, gamertag,
                               ROW_NUMBER() OVER (
                                   PARTITION BY xuid
                                   ORDER BY LENGTH(COALESCE(gamertag, '')) DESC
                               ) as rn
                        FROM highlight_events
                        WHERE match_id = ? AND xuid IS NOT NULL AND xuid != ''
                    ) sub
                    WHERE rn = 1
                    """,
                    [match_id],
                ).fetchall()

                for xuid, gamertag in he_result:
                    xu = str(xuid).strip()
                    if xu:
                        all_xuids.add(xu)
                        # Préférer le gamertag le plus long
                        gt = _clean_gamertag(gamertag)
                        if gt and (
                            xu not in gamertag_by_xuid
                            or len(gt) > len(gamertag_by_xuid.get(xu) or "")
                        ):
                            gamertag_by_xuid[xu] = gt
            except Exception:
                pass

            if not all_xuids:
                return None

            # ======================================================================
            # MÉTHODE 2 : Fallback sur highlight_events si kvp n'a pas donné de résultats
            # ======================================================================
            if not team_by_xuid or len(team_by_xuid) <= 1:
                # Analyser les événements Kill/Death pour déterminer les équipes
                try:
                    kill_events = conn.execute(
                        """
                        SELECT event_type, xuid, raw_json
                        FROM highlight_events
                        WHERE match_id = ?
                          AND LOWER(event_type) IN ('kill', 'death')
                          AND xuid IS NOT NULL AND xuid != ''
                        """,
                        [match_id],
                    ).fetchall()

                    # Analyser les relations killer→victim depuis raw_json
                    killed_by_me: set[str] = set()
                    killed_me: set[str] = set()

                    for _event_type, xuid, raw_json in kill_events:
                        xuid_str = str(xuid).strip()
                        if not raw_json:
                            continue

                        try:
                            event_data = (
                                json.loads(raw_json) if isinstance(raw_json, str) else raw_json
                            )

                            # Extraire killer et victim
                            killer = (
                                event_data.get("killer_xuid")
                                or event_data.get("KillerXuid")
                                or str(
                                    event_data.get("Killer", {}).get("Xuid", "")
                                    if isinstance(event_data.get("Killer"), dict)
                                    else ""
                                )
                            )
                            victim = (
                                event_data.get("victim_xuid")
                                or event_data.get("VictimXuid")
                                or str(
                                    event_data.get("Victim", {}).get("Xuid", "")
                                    if isinstance(event_data.get("Victim"), dict)
                                    else ""
                                )
                            )

                            killer = str(killer).strip() if killer else ""
                            victim = str(victim).strip() if victim else ""

                            # Si je suis le killer
                            if killer == my_xuid_str and victim:
                                killed_by_me.add(victim)
                            # Si je suis la victime
                            elif victim == my_xuid_str and killer:
                                killed_me.add(killer)
                        except Exception:
                            pass

                    # Les joueurs que j'ai tués ou qui m'ont tué sont des adversaires
                    team_by_xuid[my_xuid_str] = my_team_id
                    for xu in killed_by_me | killed_me:
                        if xu != my_xuid_str:
                            team_by_xuid[xu] = None

                    # Les joueurs non classés qui ne sont pas adversaires sont probablement alliés
                    for xu in all_xuids:
                        if xu not in team_by_xuid:
                            # Par défaut, les non-classés sont considérés comme adversaires
                            # pour éviter le bug "tous dans mon équipe"
                            team_by_xuid[xu] = None

                except Exception as e:
                    logger.debug(f"Erreur analyse highlight_events: {e}")

            # ======================================================================
            # FALLBACK FINAL : Si toujours pas d'équipes, répartir 50/50
            # ======================================================================
            if not team_by_xuid or len([x for x in team_by_xuid.values() if x is None]) == 0:
                # Tous dans mon équipe → problème! Répartir aléatoirement
                others = [xu for xu in all_xuids if xu != my_xuid_str]
                team_by_xuid[my_xuid_str] = my_team_id
                # Mettre la moitié dans l'équipe adverse
                half = len(others) // 2
                for i, xu in enumerate(sorted(others)):
                    if i < half:
                        team_by_xuid[xu] = None  # Adversaire
                    else:
                        team_by_xuid[xu] = my_team_id  # Allié

            # ======================================================================
            # Construire les listes d'équipes
            # ======================================================================
            # Sprint Gamertag Roster Fix : Utiliser resolve_gamertags_batch pour
            # obtenir des gamertags propres depuis match_participants/xuid_aliases
            resolved_gamertags = self.resolve_gamertags_batch(list(all_xuids), match_id=match_id)

            my_team = []
            enemy_team = []

            for xuid_str in all_xuids:
                is_me = xuid_str == my_xuid_str
                # Priorité : gamertag résolu > gamertag extrait > XUID
                cleaned_gamertag = resolved_gamertags.get(xuid_str) or gamertag_by_xuid.get(
                    xuid_str
                )
                display_name = cleaned_gamertag if cleaned_gamertag else xuid_str
                player_team_id = team_by_xuid.get(xuid_str, None if not is_me else my_team_id)

                player_data = {
                    "xuid": xuid_str,
                    "gamertag": cleaned_gamertag,
                    "team_id": player_team_id,
                    "is_me": is_me,
                    "is_bot": False,
                    "display_name": display_name,
                }

                if player_team_id == my_team_id or is_me:
                    my_team.append(player_data)
                else:
                    enemy_team.append(player_data)

            # Trier: moi en premier, puis alphabétique
            def _sort_key(r: dict[str, Any]) -> tuple[int, str]:
                me_rank = 0 if r.get("is_me") else 1
                name = str(r.get("gamertag") or r.get("xuid") or "").strip().lower()
                return (me_rank, name)

            my_team.sort(key=_sort_key)
            enemy_team.sort(key=_sort_key)

            return {
                "my_team_id": int(my_team_id),
                "my_team_name": None,
                "my_team": my_team,
                "enemy_team": enemy_team,
                "enemy_team_ids": [],
                "enemy_team_names": [],
            }
        except Exception as e:
            logger.warning(f"Erreur lors du chargement des rosters pour {match_id}: {e}")
            return None

    def load_matches_with_teammate(
        self,
        teammate_xuid: str,
    ) -> list[str]:
        """Retourne les match_id joués avec un coéquipier.

        Utilise highlight_events pour détecter la présence dans le même match.

        Args:
            teammate_xuid: XUID du coéquipier.

        Returns:
            Liste des match_id où les deux joueurs apparaissent.
        """
        conn = self._get_connection()

        try:
            # Vérifier si highlight_events existe
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_name = 'highlight_events'"
            ).fetchall()
            if not tables:
                return []

            # Trouver les matchs où les deux joueurs apparaissent
            result = conn.execute(
                """
                SELECT DISTINCT me.match_id
                FROM highlight_events me
                INNER JOIN highlight_events tm ON me.match_id = tm.match_id
                WHERE me.xuid = ? AND tm.xuid = ?
                ORDER BY me.match_id DESC
                """,
                [self._xuid, teammate_xuid],
            )
            return [row[0] for row in result.fetchall()]
        except Exception:
            return []

    def load_same_team_match_ids(
        self,
        teammate_xuid: str,
    ) -> list[str]:
        """Retourne les match_id où les deux joueurs étaient dans la même équipe.

        Sprint Gamertag Roster Fix : Utilise match_participants si disponible
        pour une détermination précise des équipes. Sinon, fallback sur
        highlight_events.

        Args:
            teammate_xuid: XUID du coéquipier.

        Returns:
            Liste des match_id où les deux joueurs étaient dans la même équipe.
        """
        conn = self._get_connection()

        # Essayer avec match_participants d'abord (source fiable)
        if self._has_table("match_participants"):
            try:
                result = conn.execute(
                    """
                    SELECT DISTINCT me.match_id
                    FROM match_participants me
                    INNER JOIN match_participants tm
                        ON me.match_id = tm.match_id
                        AND me.team_id = tm.team_id
                    WHERE me.xuid = ? AND tm.xuid = ?
                    ORDER BY me.match_id DESC
                    """,
                    [self._xuid, teammate_xuid],
                )
                match_ids = [row[0] for row in result.fetchall()]
                if match_ids:
                    return match_ids
            except Exception as e:
                logger.debug(f"Erreur match_participants: {e}")

        # Fallback: utiliser highlight_events pour trouver les matchs communs
        # puis vérifier team_id dans match_stats (moins précis)
        try:
            result = conn.execute(
                """
                SELECT DISTINCT ms.match_id
                FROM match_stats ms
                WHERE ms.match_id IN (
                    SELECT DISTINCT match_id FROM highlight_events WHERE xuid = ?
                )
                AND ms.match_id IN (
                    SELECT DISTINCT match_id FROM highlight_events WHERE xuid = ?
                )
                ORDER BY ms.match_id DESC
                """,
                [self._xuid, teammate_xuid],
            )
            return [row[0] for row in result.fetchall()]
        except Exception:
            return []

    def has_match_participants(self) -> bool:
        """Vérifie si la table match_participants existe et contient des données."""
        conn = self._get_connection()
        try:
            count = conn.execute("SELECT COUNT(*) FROM match_participants").fetchone()[0]
            return count > 0
        except Exception:
            return False

    def resolve_gamertag(
        self,
        xuid: str,
        *,
        match_id: str | None = None,
    ) -> str | None:
        """Résout un XUID en gamertag avec cascade de sources.

        Sprint Gamertag Roster Fix : Fonction centralisée pour obtenir un
        gamertag propre à partir d'un XUID, en utilisant plusieurs sources.

        Priorité des sources:
        1. match_participants (pour ce match spécifique) - gamertags API propres
        2. xuid_aliases (source officielle API)
        3. teammates_aggregate (historique des coéquipiers)
        4. highlight_events (nettoyé avec extraction ASCII)

        Args:
            xuid: XUID du joueur à résoudre.
            match_id: ID du match (optionnel, améliore la résolution contextuelle).

        Returns:
            Gamertag propre ou None si non trouvé.
        """
        conn = self._get_connection()
        xuid = str(xuid).strip()

        # 1. match_participants (si match_id fourni et table existe)
        if match_id and self._has_table("match_participants"):
            try:
                result = conn.execute(
                    "SELECT gamertag FROM match_participants WHERE match_id = ? AND xuid = ?",
                    [match_id, xuid],
                ).fetchone()
                if result and result[0]:
                    return result[0]
            except Exception:
                pass

        # 2. xuid_aliases
        try:
            result = conn.execute(
                "SELECT gamertag FROM xuid_aliases WHERE xuid = ?",
                [xuid],
            ).fetchone()
            if result and result[0]:
                return result[0]
        except Exception:
            pass

        # 3. teammates_aggregate
        try:
            result = conn.execute(
                "SELECT teammate_gamertag FROM teammates_aggregate WHERE teammate_xuid = ?",
                [xuid],
            ).fetchone()
            if result and result[0]:
                return result[0]
        except Exception:
            pass

        # 4. highlight_events avec extraction ASCII
        if match_id:
            try:
                result = conn.execute(
                    "SELECT gamertag FROM highlight_events WHERE match_id = ? AND xuid = ? LIMIT 1",
                    [match_id, xuid],
                ).fetchone()
                if result and result[0]:
                    cleaned = self._extract_ascii_token(result[0])
                    if cleaned:
                        return cleaned
            except Exception:
                pass

        return None

    def _extract_ascii_token(self, value: str | None) -> str | None:
        """Extrait un token ASCII plausible depuis un gamertag corrompu.

        Les gamertags provenant de highlight_events peuvent contenir des
        caractères NUL et de contrôle (ex: 'juan1\\x00\\x00\\x00\\x00').
        Cette fonction extrait la partie lisible.

        Args:
            value: Gamertag potentiellement corrompu.

        Returns:
            Token ASCII nettoyé ou None si rien de plausible.
        """
        if value is None:
            return None

        try:
            # Extraire tous les tokens alphanumériques
            parts = re.findall(r"[A-Za-z0-9]+", str(value or ""))
            if not parts:
                return None

            # Prendre le plus long (probablement le gamertag)
            parts.sort(key=len, reverse=True)
            token = parts[0]

            # Minimum 3 caractères pour être un gamertag valide
            return token if len(token) >= 3 else None
        except Exception:
            return None

    def resolve_gamertags_batch(
        self,
        xuids: list[str],
        *,
        match_id: str | None = None,
    ) -> dict[str, str | None]:
        """Résout plusieurs XUIDs en gamertags en batch.

        Args:
            xuids: Liste des XUIDs à résoudre.
            match_id: ID du match (optionnel).

        Returns:
            Dict {xuid: gamertag} pour chaque XUID.
        """
        return {xuid: self.resolve_gamertag(xuid, match_id=match_id) for xuid in xuids}

    def load_match_player_gamertags(self, match_id: str) -> dict[str, str]:
        """Retourne un mapping XUID → Gamertag pour un match.

        Équivalent DuckDB de src.db.loaders.load_match_player_gamertags().

        Args:
            match_id: ID du match.

        Returns:
            Dict {xuid: gamertag}.
        """
        if not match_id:
            return {}

        conn = self._get_connection()
        result: dict[str, str] = {}

        try:
            # 1. Depuis match_participants (prioritaire)
            if self._has_table("match_participants"):
                rows = conn.execute(
                    """
                    SELECT DISTINCT xuid, gamertag
                    FROM match_participants
                    WHERE match_id = ? AND xuid IS NOT NULL AND gamertag IS NOT NULL
                    """,
                    [match_id],
                ).fetchall()
                for xuid, gt in rows:
                    if xuid and gt:
                        result[str(xuid)] = str(gt)

            # 2. Compléter depuis highlight_events
            if self._has_table("highlight_events"):
                rows = conn.execute(
                    """
                    SELECT DISTINCT xuid, gamertag
                    FROM highlight_events
                    WHERE match_id = ? AND xuid IS NOT NULL AND gamertag IS NOT NULL
                    """,
                    [match_id],
                ).fetchall()
                for xuid, gt in rows:
                    if xuid and gt and str(xuid) not in result:
                        result[str(xuid)] = str(gt)

            # 3. Compléter depuis xuid_aliases
            if self._has_table("xuid_aliases"):
                missing = [x for x in result if not result.get(x)]
                if missing:
                    placeholders = ", ".join(["?" for _ in missing])
                    rows = conn.execute(
                        f"SELECT xuid, gamertag FROM xuid_aliases WHERE xuid IN ({placeholders})",
                        missing,
                    ).fetchall()
                    for xuid, gt in rows:
                        if xuid and gt:
                            result[str(xuid)] = str(gt)

            return result
        except Exception as e:
            logger.debug(f"Erreur load_match_player_gamertags: {e}")
            return result

    def load_match_players_stats(self, match_id: str) -> list[dict[str, Any]]:
        """Charge les statistiques officielles de tous les joueurs d'un match.

        Utilisé pour valider la cohérence des frags reconstitués via les
        highlight events, et pour le tie-breaker némésis/souffre-douleur.

        Args:
            match_id: ID du match.

        Returns:
            Liste de dicts avec: xuid, gamertag, kills, deaths, assists, team_id, rank, score
        """
        if not match_id:
            return []

        conn = self._get_connection()
        try:
            if not self._has_table("match_participants"):
                return []

            # Vérifier les colonnes disponibles
            has_rank = self._has_column(conn, "match_participants", "rank")
            has_score = self._has_column(conn, "match_participants", "score")
            has_kda = (
                self._has_column(conn, "match_participants", "kills")
                and self._has_column(conn, "match_participants", "deaths")
                and self._has_column(conn, "match_participants", "assists")
            )

            # Construire la requête selon les colonnes disponibles
            columns = ["xuid", "gamertag", "team_id"]
            if has_rank:
                columns.append("rank")
            if has_score:
                columns.append("score")
            if has_kda:
                columns.extend(["kills", "deaths", "assists"])

            query = f"""
                SELECT {", ".join(columns)}
                FROM match_participants
                WHERE match_id = ?
                ORDER BY {"rank" if has_rank else "score DESC NULLS LAST"}
            """

            rows = conn.execute(query, [match_id]).fetchall()

            result = []
            for idx, row in enumerate(rows):
                d: dict[str, Any] = {
                    "xuid": str(row[0] or "").strip(),
                    "gamertag": str(row[1] or row[0] or "").strip(),
                    "team_id": int(row[2]) if row[2] is not None else None,
                    "rank": 0,
                    "score": None,
                    "kills": 0,
                    "deaths": 0,
                    "assists": 0,
                }

                col_idx = 3
                if has_rank:
                    d["rank"] = int(row[col_idx]) if row[col_idx] is not None else idx + 1
                    col_idx += 1
                else:
                    d["rank"] = idx + 1

                if has_score:
                    d["score"] = int(row[col_idx]) if row[col_idx] is not None else None
                    col_idx += 1

                if has_kda:
                    d["kills"] = int(row[col_idx]) if row[col_idx] is not None else 0
                    d["deaths"] = int(row[col_idx + 1]) if row[col_idx + 1] is not None else 0
                    d["assists"] = int(row[col_idx + 2]) if row[col_idx + 2] is not None else 0

                result.append(d)

            return result
        except Exception as e:
            logger.debug(f"Erreur load_match_players_stats: {e}")
            return []
