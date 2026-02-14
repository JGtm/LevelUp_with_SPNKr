"""Client API SPNKr asynchrone.

Ce module encapsule HaloInfiniteClient de SPNKr avec :
- Gestion automatique des tokens (env ou refresh OAuth)
- Rate limiting configurable
- Retry avec backoff exponentiel
- Support des highlight events via spnkr.film

Usage:
    async with SPNKrAPIClient() as client:
        history = await client.get_match_history("Chocoboflor")
        for item in history:
            data = await client.get_match_data(item.match_id, xuids)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.data.sync.models import CareerRankData, MatchData, MatchHistoryItem

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration et helpers
# =============================================================================

XUID_RE = re.compile(r"(\d{12,20})")
CLEARANCE_COOKIE_RE = re.compile(r"(?:^|[;\s])343-clearance=([^;\s]+)", re.IGNORECASE)


def _load_dotenv_if_present() -> None:
    """Charge les fichiers .env.local et .env si présents."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent

    for name in (".env.local", ".env"):
        dotenv_path = repo_root / name
        if not dotenv_path.exists():
            continue
        try:
            content = dotenv_path.read_text(encoding="utf-8")
        except Exception:
            continue

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key:
                continue
            if os.environ.get(key) is None:
                os.environ[key] = value


def _normalize_token_value(raw: Any) -> str | None:
    """Normalise une valeur de token (enlève préfixes headers, etc.)."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None

    # Autorise un copier-coller depuis l'onglet réseau
    if ":" in s:
        _, after = s.split(":", 1)
        s = after.strip()

    # Autorise un copier-coller depuis un header Cookie
    m = CLEARANCE_COOKIE_RE.search(s)
    if m:
        return m.group(1).strip().strip('"').strip("'") or None

    return s or None


@dataclass(frozen=True)
class Tokens:
    """Paire de tokens SPNKr."""

    spartan_token: str
    clearance_token: str


async def get_tokens_from_env() -> Tokens:
    """Récupère les tokens depuis les variables d'environnement.

    Supporte deux modes :
    1. Tokens manuels : SPNKR_SPARTAN_TOKEN + SPNKR_CLEARANCE_TOKEN
    2. OAuth Azure : SPNKR_AZURE_CLIENT_ID + SPNKR_AZURE_CLIENT_SECRET + SPNKR_OAUTH_REFRESH_TOKEN

    Raises:
        SystemExit: Si les tokens sont manquants ou invalides.

    Returns:
        Tokens validés.
    """
    _load_dotenv_if_present()

    # Mode OAuth Azure
    azure_client_id = os.environ.get("SPNKR_AZURE_CLIENT_ID")
    azure_client_secret = os.environ.get("SPNKR_AZURE_CLIENT_SECRET")
    azure_redirect_uri = os.environ.get("SPNKR_AZURE_REDIRECT_URI", "https://localhost")
    oauth_refresh_token = os.environ.get("SPNKR_OAUTH_REFRESH_TOKEN")

    if azure_client_id and azure_client_secret and oauth_refresh_token:
        return await _get_tokens_via_oauth(
            azure_client_id,
            azure_client_secret,
            azure_redirect_uri,
            oauth_refresh_token,
        )

    # Mode tokens manuels
    spartan = _normalize_token_value(os.environ.get("SPNKR_SPARTAN_TOKEN"))
    clearance = _normalize_token_value(os.environ.get("SPNKR_CLEARANCE_TOKEN"))

    if not spartan or not clearance:
        raise ValueError(
            "Tokens SPNKr manquants. Définir soit:\n"
            "- SPNKR_SPARTAN_TOKEN + SPNKR_CLEARANCE_TOKEN,\n"
            "- ou SPNKR_AZURE_CLIENT_ID + SPNKR_AZURE_CLIENT_SECRET + SPNKR_OAUTH_REFRESH_TOKEN"
        )

    return Tokens(spartan_token=spartan, clearance_token=clearance)


async def _get_tokens_via_oauth(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    refresh_token: str,
) -> Tokens:
    """Récupère les tokens via OAuth Azure."""
    try:
        from aiohttp import ClientSession, ClientTimeout
        from spnkr import AzureApp, refresh_player_tokens
    except ImportError as e:
        raise ImportError(
            "Dépendances SPNKr manquantes. Installer: pip install spnkr aiohttp"
        ) from e

    app = AzureApp(client_id, client_secret, redirect_uri)

    async with ClientSession(timeout=ClientTimeout(total=45)) as session:
        try:
            player = await refresh_player_tokens(session, app, refresh_token)
            return Tokens(
                spartan_token=str(player.spartan_token.token),
                clearance_token=str(player.clearance_token.token),
            )
        except Exception as e:
            # Fallback pour certaines versions de SPNKr
            msg = str(e)
            if "invalid_client" not in msg:
                raise

            # Utiliser le fallback OAuth v2
            return await _get_tokens_oauth_v2_fallback(session, app, refresh_token)


async def _get_tokens_oauth_v2_fallback(
    session: Any,
    app: Any,
    refresh_token: str,
) -> Tokens:
    """Fallback OAuth v2 pour les versions anciennes de SPNKr."""
    from spnkr.auth.core import XSTS_V3_HALO_AUDIENCE, XSTS_V3_XBOX_AUDIENCE
    from spnkr.auth.halo import request_clearance_token, request_spartan_token
    from spnkr.auth.xbox import request_user_token, request_xsts_token

    # Refresh OAuth v2
    url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
    data = {
        "client_id": app.client_id,
        "client_secret": app.client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "Xboxlive.signin Xboxlive.offline_access",
    }
    resp = await session.post(url, data=data)
    payload = await resp.json()

    if resp.status >= 400:
        raise ValueError(
            f"Échec refresh OAuth v2: status={resp.status} " f"error={payload.get('error')}"
        )

    access_token = payload.get("access_token")
    if not access_token:
        raise ValueError("OAuth v2: pas de access_token")

    # Chain Xbox/XSTS/Halo
    user_token = await request_user_token(session, access_token)
    _ = await request_xsts_token(session, user_token.token, XSTS_V3_XBOX_AUDIENCE)
    halo_xsts_token = await request_xsts_token(session, user_token.token, XSTS_V3_HALO_AUDIENCE)
    spartan_token = await request_spartan_token(session, halo_xsts_token.token)
    clearance_token = await request_clearance_token(session, spartan_token.token)

    return Tokens(
        spartan_token=str(spartan_token.token),
        clearance_token=str(clearance_token.token),
    )


# =============================================================================
# Retry helper
# =============================================================================


async def request_with_retries(
    coro_factory: Callable[[], Any],
    *,
    tries: int = 4,
    base_sleep: float = 0.8,
) -> Any:
    """Exécute une coroutine avec retry et backoff exponentiel.

    Args:
        coro_factory: Factory qui retourne la coroutine à exécuter.
        tries: Nombre maximum de tentatives.
        base_sleep: Délai de base entre les tentatives (secondes).

    Returns:
        Résultat de la coroutine.

    Raises:
        Exception: Dernière exception après épuisement des tentatives.
    """
    last_err: Exception | None = None

    for i in range(tries):
        try:
            return await coro_factory()
        except Exception as e:
            # Auth invalide: inutile de retry
            try:
                from aiohttp.client_exceptions import ClientResponseError

                if isinstance(e, ClientResponseError):
                    if e.status in (401, 403):
                        raise ValueError(
                            "Requête non autorisée (401/403). "
                            "Tokens probablement invalides/expirés."
                        ) from e
                    # Assets manquants: pas de retry
                    if e.status in (400, 404, 410):
                        raise
            except ImportError:
                pass

            last_err = e
            await asyncio.sleep(base_sleep * (2**i))

    assert last_err is not None
    raise last_err


# =============================================================================
# SPNKrAPIClient
# =============================================================================


class SPNKrAPIClient:
    """Client API SPNKr asynchrone.

    Encapsule HaloInfiniteClient avec :
    - Gestion automatique des tokens
    - Rate limiting configurable
    - Support des highlight events

    Usage:
        async with SPNKrAPIClient() as client:
            history = await client.get_match_history("Chocoboflor")
    """

    def __init__(
        self,
        *,
        tokens: Tokens | None = None,
        requests_per_second: int = 5,
    ) -> None:
        """
        Args:
            tokens: Tokens pré-fournis (sinon récupérés depuis env).
            requests_per_second: Rate limiting par service.
        """
        self._tokens = tokens
        self._requests_per_second = requests_per_second
        self._session = None
        self._client = None
        self._film_mod = None

    async def __aenter__(self) -> SPNKrAPIClient:
        """Initialise la session et le client."""
        if self._tokens is None:
            self._tokens = await get_tokens_from_env()

        try:
            from aiohttp import ClientSession, ClientTimeout
            from spnkr import HaloInfiniteClient
        except ImportError as e:
            raise ImportError(
                "Dépendances SPNKr manquantes. Installer: pip install spnkr aiohttp"
            ) from e

        self._session = ClientSession(timeout=ClientTimeout(total=45))
        self._client = HaloInfiniteClient(
            session=self._session,
            spartan_token=self._tokens.spartan_token,
            clearance_token=self._tokens.clearance_token,
            requests_per_second=self._requests_per_second,
        )

        # Charger le module film pour les highlight events
        try:
            from spnkr import film as film_mod

            self._film_mod = film_mod
        except ImportError:
            self._film_mod = None

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Ferme la session."""
        if self._session:
            await self._session.close()
            self._session = None
        self._client = None

    @property
    def client(self) -> Any:
        """Retourne le HaloInfiniteClient sous-jacent."""
        if self._client is None:
            raise RuntimeError("Client non initialisé. Utiliser 'async with'.")
        return self._client

    async def get_match_history(
        self,
        player: str,
        *,
        match_type: str = "matchmaking",
        start: int = 0,
        count: int = 25,
    ) -> list[MatchHistoryItem]:
        """Récupère l'historique des matchs d'un joueur.

        Args:
            player: Gamertag ou XUID du joueur.
            match_type: Type de matchs (all, matchmaking, custom, local).
            start: Offset dans l'historique (0 = plus récent).
            count: Nombre de matchs (max 25).

        Returns:
            Liste de MatchHistoryItem.
        """

        async def _fetch():
            resp = await self.client.stats.get_match_history(
                player, start=start, count=count, match_type=match_type
            )
            return await resp.parse()

        history = await request_with_retries(_fetch)

        if not hasattr(history, "results") or not history.results:
            return []

        items = []
        for r in history.results:
            items.append(
                MatchHistoryItem(
                    match_id=str(r.match_id),
                    start_time=str(r.match_info.start_time) if hasattr(r, "match_info") else "",
                    match_type=match_type,
                )
            )

        return items

    async def get_match_stats(self, match_id: str) -> dict[str, Any] | None:
        """Récupère les stats d'un match.

        Args:
            match_id: ID du match.

        Returns:
            JSON du match ou None si erreur.
        """

        async def _fetch():
            resp = await self.client.stats.get_match_stats(match_id)
            return await resp.json()

        try:
            result = await request_with_retries(_fetch)
            return result if isinstance(result, dict) else None
        except Exception as e:
            logger.warning(f"Erreur get_match_stats({match_id}): {e}")
            return None

    async def get_skill_stats(
        self,
        match_id: str,
        xuids: list[int],
    ) -> dict[str, Any] | None:
        """Récupère les stats skill (MMR) d'un match.

        Args:
            match_id: ID du match.
            xuids: Liste des XUIDs des joueurs.

        Returns:
            JSON skill ou None si non disponible.
        """
        if not xuids:
            return None

        async def _fetch():
            resp = await self.client.skill.get_match_skill(match_id, xuids)
            return await resp.json()

        try:
            result = await request_with_retries(_fetch)
            return result if isinstance(result, dict) else None
        except Exception:
            # Non bloquant: certains matchs n'ont pas de skill
            return None

    async def get_highlight_events(self, match_id: str) -> list[Any]:
        """Récupère les highlight events (film) d'un match.

        Args:
            match_id: ID du match.

        Returns:
            Liste des events ou liste vide.
        """
        if self._film_mod is None:
            return []

        async def _fetch():
            return await self._film_mod.read_highlight_events(self.client, match_id=match_id)

        try:
            events = await request_with_retries(_fetch)
            return events if events else []
        except Exception:
            # Non bloquant: certains matchs n'ont pas de film
            return []

    async def get_match_data(
        self,
        match_id: str,
        xuids: list[int],
        *,
        with_skill: bool = True,
        with_highlight_events: bool = True,
    ) -> MatchData | None:
        """Récupère les données complètes d'un match.

        Effectue les appels en parallèle pour les performances.

        Args:
            match_id: ID du match.
            xuids: Liste des XUIDs pour l'appel skill.
            with_skill: Récupérer les données skill.
            with_highlight_events: Récupérer les highlight events.

        Returns:
            MatchData ou None si les stats sont indisponibles.
        """
        # Fetch stats (obligatoire)
        stats_json = await self.get_match_stats(match_id)
        if stats_json is None:
            return None

        # Fetch skill et events en parallèle
        skill_task = self.get_skill_stats(match_id, xuids) if with_skill else asyncio.sleep(0)
        events_task = (
            self.get_highlight_events(match_id) if with_highlight_events else asyncio.sleep(0)
        )

        skill_result, events_result = await asyncio.gather(
            skill_task,
            events_task,
            return_exceptions=True,
        )

        skill_json = skill_result if isinstance(skill_result, dict) else None
        highlight_events = events_result if isinstance(events_result, list) else []

        return MatchData(
            match_id=match_id,
            stats_json=stats_json,
            skill_json=skill_json,
            highlight_events=highlight_events,
        )

    async def get_asset(
        self,
        asset_type: str,
        asset_id: str,
        version_id: str,
    ) -> dict[str, Any] | None:
        """Récupère un asset (map, playlist, variant).

        Args:
            asset_type: Type (Maps, Playlists, PlaylistMapModePairs, GameVariants).
            asset_id: ID de l'asset.
            version_id: Version de l'asset.

        Returns:
            JSON de l'asset ou None.
        """

        async def _fetch():
            if asset_type == "Maps":
                resp = await self.client.discovery_ugc.get_map(asset_id, version_id)
            elif asset_type == "Playlists":
                resp = await self.client.discovery_ugc.get_playlist(asset_id, version_id)
            elif asset_type == "PlaylistMapModePairs":
                resp = await self.client.discovery_ugc.get_map_mode_pair(asset_id, version_id)
            elif asset_type == "GameVariants":
                resp = await self.client.discovery_ugc.get_ugc_game_variant(asset_id, version_id)
            else:
                return None
            return await resp.json()

        try:
            result = await request_with_retries(_fetch)
            return result if isinstance(result, dict) else None
        except Exception:
            # Asset manquant ou supprimé
            return None

    # =========================================================================
    # Endpoints Phase 5 : Career Rank & Stats supplémentaires
    # =========================================================================

    async def get_career_rank_progression(self, xuid: str) -> CareerRankData | None:
        """Récupère la progression du rang carrière d'un joueur.

        Args:
            xuid: XUID du joueur (format numérique).

        Returns:
            CareerRankData ou None si indisponible.
        """
        # Normaliser le XUID (enlever préfixes éventuels)
        xuid_clean = str(xuid).strip()
        if xuid_clean.startswith("xuid("):
            xuid_clean = xuid_clean[5:-1]

        async def _fetch():
            # Endpoint economy pour la progression de rang
            url = (
                f"https://economy.svc.halowaypoint.com/hi/players/"
                f"xuid({xuid_clean})/rewardtracks/careerranks/careerrank1"
            )

            if self._session is None:
                raise RuntimeError("Session non initialisée")

            headers = {
                "x-343-authorization-spartan": self._tokens.spartan_token,
                "343-clearance": self._tokens.clearance_token,
                "Accept": "application/json",
            }

            async with self._session.get(url, headers=headers) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                return await resp.json()

        try:
            json_data = await request_with_retries(_fetch)
            if json_data is None:
                return None

            career_data = self._parse_career_rank(xuid_clean, json_data)

            # Résoudre l'URL adornment via gamecms si pas déjà présente
            if career_data and not career_data.adornment_path:
                adornment_url = await self._resolve_adornment_url(career_data.current_rank)
                if adornment_url:
                    career_data = CareerRankData(
                        xuid=career_data.xuid,
                        current_rank=career_data.current_rank,
                        current_rank_name=career_data.current_rank_name,
                        current_rank_tier=career_data.current_rank_tier,
                        current_xp=career_data.current_xp,
                        xp_for_next_rank=career_data.xp_for_next_rank,
                        xp_total=career_data.xp_total,
                        is_max_rank=career_data.is_max_rank,
                        adornment_path=adornment_url,
                        spartan_id=career_data.spartan_id,
                        raw_json=career_data.raw_json,
                    )

            return career_data

        except Exception as e:
            logger.warning(f"Erreur get_career_rank_progression({xuid}): {e}")
            return None

    def _parse_career_rank(self, xuid: str, data: dict[str, Any]) -> CareerRankData:
        """Parse les données brutes de career rank en CareerRankData."""
        # Structure typique du JSON retourné par l'API
        # {
        #   "RewardTrackPath": "RewardTracks/CareerRanks/careerRank1.json",
        #   "TrackType": "CareerRank",
        #   "CurrentProgress": { "Rank": 150, "PartialProgress": 25000 },
        #   "PreviousProgress": {...}
        # }

        current = data.get("CurrentProgress", {})
        rank = current.get("Rank", 0)
        partial_xp = current.get("PartialProgress", 0)

        # Vérifier si rang max atteint (rang 272 = Hero max)
        is_max = rank >= 272

        # Récupérer les infos sur le rang depuis le track
        rank_info = self._get_rank_info(rank)

        return CareerRankData(
            xuid=xuid,
            current_rank=rank,
            current_rank_name=rank_info.get("name", f"Rank {rank}"),
            current_rank_tier=rank_info.get("tier", ""),
            current_xp=partial_xp,
            xp_for_next_rank=rank_info.get("xp_required", 0),
            xp_total=self._compute_total_xp(rank, partial_xp),
            is_max_rank=is_max,
            adornment_path=None,  # Résolu séparément via gamecms
            raw_json=data,
        )

    async def _resolve_adornment_url(self, rank: int) -> str | None:
        """Résout l'URL d'adornment via les métadonnées gamecms.

        Appelle gamecms_hacs.get_career_reward_track() pour obtenir
        le rank_adornment_icon correspondant au rang donné.

        Args:
            rank: Numéro de rang carrière (0-272).

        Returns:
            URL complète de l'adornment ou None.
        """
        try:
            if self._client is None:
                return None

            gamecms = getattr(self._client, "gamecms_hacs", None)
            if gamecms is None:
                return None

            career_track_resp = await gamecms.get_career_reward_track()
            # Compat: SPNKr peut exposer .data ou .parse()
            if hasattr(career_track_resp, "data"):
                career_track = career_track_resp.data
            elif hasattr(career_track_resp, "parse"):
                career_track = await career_track_resp.parse()
            else:
                career_track = career_track_resp

            if career_track is None:
                return None

            ranks_list = getattr(career_track, "ranks", None)
            if not ranks_list:
                return None

            # Le display_rank est rank+1 sauf pour 272 (Hero max)
            display_rank = rank if rank == 272 else rank + 1

            for rank_obj in ranks_list:
                r = getattr(rank_obj, "rank", None)
                if r == display_rank:
                    adornment_icon = getattr(rank_obj, "rank_adornment_icon", None)
                    if adornment_icon:
                        host = "https://gamecms-hacs.svc.halowaypoint.com"
                        adorn_path = str(adornment_icon).lstrip("/")
                        return f"{host}/hi/images/file/{adorn_path}"
                    break

            return None
        except Exception as e:
            logger.debug(f"Résolution adornment gamecms échouée: {e}")
            return None

    def _get_rank_info(self, rank: int) -> dict[str, Any]:
        """Retourne les infos d'un rang carrière.

        Les rangs suivent une progression par tiers :
        - Rangs 1-30: Bronze, Silver, Gold, Platinum, Diamond, Onyx (5 chacun)
        - Rangs 31-270: Répétition avec grades I à V dans chaque tier
        - Rangs 271-272: Hero
        """
        # Mapping des tiers et niveaux
        base_tiers = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Onyx"]
        hero_ranks = {271: "Hero", 272: "Hero Legend"}

        if rank in hero_ranks:
            return {
                "name": hero_ranks[rank],
                "tier": "Hero",
                "xp_required": 0,
            }

        # Calcul du tier et niveau
        # Rangs 1-30 : 5 rangs par tier, 6 tiers = 30
        if rank <= 30:
            tier_idx = (rank - 1) // 5
            level = ((rank - 1) % 5) + 1
            tier = base_tiers[tier_idx] if tier_idx < len(base_tiers) else "Unknown"
            return {
                "name": f"{tier} {level}",
                "tier": tier,
                "xp_required": 10000 + (rank * 500),  # Estimation
            }

        # Rangs 31-270 : cycles de 30 rangs
        cycle = (rank - 31) // 30
        pos_in_cycle = (rank - 31) % 30
        tier_idx = pos_in_cycle // 5
        level = (pos_in_cycle % 5) + 1
        tier = base_tiers[tier_idx] if tier_idx < len(base_tiers) else "Unknown"
        grade = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"][min(cycle, 7)]

        return {
            "name": f"{tier} {level} ({grade})",
            "tier": tier,
            "xp_required": 15000 + (cycle * 2000) + (rank * 100),  # Estimation
        }

    def _compute_total_xp(self, rank: int, partial_xp: int) -> int:
        """Calcule l'XP total basé sur le rang et l'XP partiel."""
        # Estimation simplifiée (les vrais calculs sont plus complexes)
        base_xp = 0
        for r in range(1, rank):
            info = self._get_rank_info(r)
            base_xp += info.get("xp_required", 10000)
        return base_xp + partial_xp

    async def get_match_count(self, xuid: str) -> dict[str, int] | None:
        """Récupère le nombre total de matchs d'un joueur.

        Args:
            xuid: XUID du joueur.

        Returns:
            Dict avec les compteurs de matchs ou None.
        """
        xuid_clean = str(xuid).strip()
        if xuid_clean.startswith("xuid("):
            xuid_clean = xuid_clean[5:-1]

        async def _fetch():
            url = (
                f"https://halostats.svc.halowaypoint.com/hi/players/"
                f"xuid({xuid_clean})/matches/count"
            )

            if self._session is None:
                raise RuntimeError("Session non initialisée")

            headers = {
                "x-343-authorization-spartan": self._tokens.spartan_token,
                "343-clearance": self._tokens.clearance_token,
                "Accept": "application/json",
            }

            async with self._session.get(url, headers=headers) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                return await resp.json()

        try:
            json_data = await request_with_retries(_fetch)
            if json_data is None:
                return None

            # Parser les compteurs
            return {
                "matchmaking": json_data.get("MatchmadeMatchesPlayedCount", 0),
                "custom": json_data.get("CustomMatchesPlayedCount", 0),
                "local": json_data.get("LocalMatchesPlayedCount", 0),
                "total": json_data.get("MatchesPlayedCount", 0),
            }

        except Exception as e:
            logger.warning(f"Erreur get_match_count({xuid}): {e}")
            return None

    async def get_player_customization(self, xuid: str) -> dict[str, Any] | None:
        """Récupère les données de personnalisation Spartan (armure, couleurs).

        Args:
            xuid: XUID du joueur.

        Returns:
            JSON de personnalisation ou None.
        """
        xuid_clean = str(xuid).strip()
        if xuid_clean.startswith("xuid("):
            xuid_clean = xuid_clean[5:-1]

        async def _fetch():
            resp = await self.client.economy.get_player_customization(f"xuid({xuid_clean})")
            return await resp.json()

        try:
            result = await request_with_retries(_fetch)
            return result if isinstance(result, dict) else None
        except Exception as e:
            logger.warning(f"Erreur get_player_customization({xuid}): {e}")
            return None

    async def get_spartan_token_xuid(self) -> str | None:
        """Récupère le XUID du joueur authentifié depuis le token Spartan.

        Returns:
            XUID ou None si non disponible.
        """
        if self._tokens is None:
            return None

        # Le XUID est souvent encodé dans le token ou récupérable via un appel
        # Essayer de parser le token JWT si possible
        try:
            import base64
            import json as json_module

            # Le Spartan token peut contenir le XUID
            parts = self._tokens.spartan_token.split(".")
            if len(parts) >= 2:
                # Décoder la partie payload (base64url)
                payload_b64 = parts[1]
                # Ajouter le padding si nécessaire
                padding = 4 - len(payload_b64) % 4
                if padding != 4:
                    payload_b64 += "=" * padding
                payload = base64.urlsafe_b64decode(payload_b64)
                data = json_module.loads(payload)

                # Chercher le XUID dans les claims
                xuid = data.get("xid") or data.get("xuid") or data.get("sub")
                if xuid:
                    return str(xuid)
        except Exception:
            pass

        return None


async def enrich_match_info_with_assets(client: SPNKrAPIClient, stats_json: dict[str, Any]) -> None:
    """Enrichit MatchInfo avec les PublicName depuis Discovery UGC (in-place).

    Utilisé par le moteur de sync et le script backfill pour récupérer
    les noms des playlists, maps, pairs et game variants.
    """
    match_info = stats_json.get("MatchInfo")
    if not isinstance(match_info, dict):
        return

    asset_keys = [
        ("Playlist", "Playlists"),
        ("MapVariant", "Maps"),
        ("PlaylistMapModePair", "PlaylistMapModePairs"),
        ("UgcGameVariant", "GameVariants"),
    ]

    for json_key, api_type in asset_keys:
        ref = match_info.get(json_key)
        if not isinstance(ref, dict):
            continue
        aid = ref.get("AssetId")
        vid = ref.get("VersionId")
        if not aid or not vid:
            continue

        try:
            asset = await client.get_asset(api_type, aid, vid)
            if isinstance(asset, dict):
                name = asset.get("PublicName")
                if isinstance(name, str) and name.strip():
                    ref["PublicName"] = name.strip()
        except Exception as e:
            logger.debug(f"Asset {api_type} {aid}: {e}")
