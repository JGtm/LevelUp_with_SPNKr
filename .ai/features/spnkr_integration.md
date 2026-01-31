# SPNKr Integration - Client API Halo Infinite

## Résumé
Module d'intégration avec l'API Halo Waypoint via la bibliothèque SPNKr. Gère l'authentification Xbox Live/Azure, la récupération des profils joueurs, des appearances (emblems, backdrops, nameplates), des Career Ranks, et la résolution XUID ↔ Gamertag.

## Inputs
- **XUID** : Identifiant Xbox unique du joueur (string de 16 chiffres)
- **Gamertag** : Pseudo Xbox du joueur
- **Tokens d'authentification** :
  - `SPNKR_SPARTAN_TOKEN` : Token Spartan (cache court terme)
  - `SPNKR_CLEARANCE_TOKEN` : Token Clearance (cache court terme)
  - `SPNKR_AZURE_CLIENT_ID` + `SPNKR_AZURE_CLIENT_SECRET` + `SPNKR_OAUTH_REFRESH_TOKEN` : Authentification Azure (régénération automatique)

## Outputs
- **ProfileAppearance** (Pydantic dataclass) :
  - `service_tag` : Tag de service (4 caractères)
  - `emblem_image_url` : URL de l'emblème PNG
  - `backdrop_image_url` : URL du backdrop PNG  
  - `nameplate_image_url` : URL de la nameplate PNG
  - `rank_label` : Label du Career Rank (ex: "Caporal Argent III")
  - `rank_subtitle` : Progression XP (ex: "XP 1500/2000")
  - `rank_image_url` : URL de l'icône du rang

## Dépendances
- **Packages externes** :
  - `spnkr` : Client Python pour Halo Infinite API
  - `aiohttp` : Requêtes HTTP asynchrones
  - `asyncio` : Gestion asynchrone
- **Modules internes** :
  - `src.ui.profile_api_cache` : Cache disque des profils
  - `src.ui.profile_api_urls` : Construction des URLs Waypoint
  - `src.ui.profile_api_tokens` : Gestion des tokens
  - `src.ui.career_ranks` : Traduction des Career Ranks

## Logique Métier

### Flux d'authentification
```
1. Vérifier tokens en cache (SPNKR_SPARTAN_TOKEN, SPNKR_CLEARANCE_TOKEN)
2. Si expirés/absents → Régénérer via Azure OAuth (refresh token)
3. Si échec → Lever une exception avec message explicatif
```

### Flux de récupération profil
```
1. Vérifier cache disque (JSON, TTL configurable)
2. Si cache valide → Retourner ProfileAppearance
3. Si enabled=False → Retourner None
4. Appeler HaloInfiniteClient.economy.get_player_customization()
5. Résoudre URLs des assets (emblem, backdrop, nameplate)
6. Appeler Career Rank API pour progression
7. Construire ProfileAppearance
8. Sauvegarder en cache
```

### Endpoints utilisés
| Endpoint | Usage |
|----------|-------|
| `economy.get_player_customization` | Apparence joueur |
| `gamecms_hacs.get_career_reward_track` | Métadonnées des rangs |
| `profile.get_user_by_gamertag` | Résolution XUID |
| `GET /hi/players/xuid({XUID})/rewardtracks/careerranks/careerrank1` | Progression Career Rank |

## Points d'Attention
- **Rate limiting** : `requests_per_second` configurable (défaut: 3)
- **Timeout** : `timeout_seconds` configurable (défaut: 12)
- **Erreurs d'auth** : Détection automatique et retry avec nouveaux tokens
- **Cache** : Stocké dans `data/cache/profile_api/`
- **Asyncio** : Gestion des event loops existantes (Streamlit)

## Fichiers Clés
| Fichier | Rôle |
|---------|------|
| `src/ui/profile_api.py` | Point d'entrée principal |
| `src/ui/profile_api_cache.py` | Gestion du cache disque |
| `src/ui/profile_api_urls.py` | Construction URLs Waypoint |
| `src/ui/profile_api_tokens.py` | Authentification Azure/tokens |
| `scripts/spnkr_get_refresh_token.py` | Obtention du refresh token initial |
| `scripts/spnkr_import_db.py` | Import des matchs depuis SPNKr |
