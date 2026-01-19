# TODO / Roadmap (19 janvier 2026)

Ce fichier liste les demandes + recommandations techniques après analyse du repo et de la DB OpenSpartan Workshop.

## Constats rapides (repo + DB)

- L’UI Streamlit est pilotée par `streamlit_app.py`.
- Le DataFrame principal (`load_df`) est construit uniquement depuis `MatchStats` via `src/db/loaders.py::load_matches`.
- La DB locale détectée contient (au minimum) : `MatchStats`, `PlayerMatchStats`, `GameVariants`, `EngineGameVariants`, `PlaylistCSRSnapshots`, `PlaylistMapModePairs`, `Playlists`, `Maps`, etc.

### Où sont les infos clés (confirmé sur ta DB)

- **Nom du mode (publicName)** : `MatchStats.ResponseBody.MatchInfo.UgcGameVariant.AssetId` → jointure sur `GameVariants.ResponseBody.AssetId` → `GameVariants.ResponseBody.PublicName`.
  - Exemple trouvé : `GameVariants.PublicName = "KOTH:Arena"`.
  - Si besoin du "moteur" : `GameVariants.ResponseBody.EngineGameVariantLink` peut pointer vers `EngineGameVariants`.

- **Team MMR** : dans `PlayerMatchStats` (pas dans `MatchStats`).
  - Table `PlayerMatchStats` a une colonne `MatchId`.
  - Chemins JSON repérés : `$.Value[*].Result.TeamMmr` et `$.Value[*].Result.TeamMmrs`.

- **Médailles** : dans `MatchStats`.
  - Chemin repéré : `Players[].PlayerTeamStats[].Stats.CoreStats.Medals[]`.
  - Structure typique : `{ "NameId": <int>, "Count": <int>, ... }`.
  - La DB ne semble pas fournir directement un mapping fiable `NameId -> libellé + icône` via `InventoryItems` (à confirmer / compléter côté assets externes).

---

## 1) Onglet “Dernier match” + Team MMR

### Objectif
Ajouter un onglet dédié qui résume la dernière partie (map/mode/outcome/KDA, etc.) et affiche **le MMR d’équipe**.

### Recommandation d’implémentation
- Ajouter un onglet Streamlit : `st.tabs([... , "Dernier match", ...])` dans `streamlit_app.py`.
- Déterminer le dernier match via `df.sort_values('start_time').iloc[-1]` (ou `max` sur `start_time`) et récupérer `match_id`.
- Charger les stats détaillées depuis `PlayerMatchStats` sur ce `match_id`.

### Points techniques (proposés)
- Ajouter une fonction DB :
  - `src/db/loaders.py`: `load_player_match_stats(db_path: str, match_id: str) -> dict`
  - Requête: `SELECT ResponseBody FROM PlayerMatchStats WHERE MatchId = ?`.
- Extraire pour le joueur courant (entrée `Value[]` dont `Id == f"xuid({xuid})"`) :
  - `Result.TeamId` (team du joueur)
  - `Result.TeamMmr` (MMR de son équipe)
  - `Result.TeamMmrs` (MMR des 2 équipes, utile pour comparaison)
  - Optionnel: `Result.RankRecap.{PreMatchCsr,PostMatchCsr}`.

### Comparaison “attendu vs réel” (à ajouter dans le dernier match)
- Afficher une comparaison **en français** entre :
  - **Kills attendus** (`Result.StatPerformances.Kills.Expected`) vs **kills réels** (`Result.StatPerformances.Kills.Count`)
  - **Morts attendues** (`Result.StatPerformances.Deaths.Expected`) vs **morts réelles** (`Result.StatPerformances.Deaths.Count`)
- Présenter aussi l’écart (ex: $\Delta$ kills) et idéalement l’écart normalisé si dispo (`StdDev`) :
  - `Result.StatPerformances.Kills.StdDev`, `Result.StatPerformances.Deaths.StdDev`

### UI suggérée
- KPIs (metrics) : Map / Mode / Outcome / Team MMR / Écart de MMR vs équipe adverse.
- Bloc “Match” (card) + lien Halo Waypoint (si tu as déjà le slug player et si l’URL est stable).

### Fichiers touchés (probables)
- `streamlit_app.py`
- `src/db/loaders.py`
- `src/db/queries.py` (si on formalise la requête)
- `src/models.py` (optionnel, si on crée un dataclass pour ce payload)

---

## 2) Filtrer les modes par `engineGameVariant.publicName` (via jointure)

### Objectif
Remplacer/compléter les filtres “modes” actuels (basés sur Playlist / Pair) par un filtre plus propre basé sur le **nom public du mode**.

### Recommandation (la voie qui marche sur ta DB)
- Ajouter au DataFrame (ou au modèle `MatchRow`) :
  - `game_variant_id` = `MatchInfo.UgcGameVariant.AssetId`
  - `game_variant_name` = jointure vers `GameVariants.PublicName`.

### Pourquoi c’est mieux
- `PlaylistMapModePairs` n’est pas toujours stable/expressif.
- `GameVariants.PublicName` est l’intitulé “métier” du mode (ex: KOTH, Slayer…).

### Approche “SQL-first” (recommandée)
- Construire un map `asset_id -> publicName` via une lecture de `GameVariants` (comme `load_asset_name_map`).
- Ensuite dans `load_matches` : récupérer `UgcGameVariant.AssetId` et résoudre le nom via la map.

### Fichiers touchés
- `src/db/loaders.py`
- `src/models.py` (si ajout champs)
- `streamlit_app.py` (filtres sidebar)

---

## 3) CSS / wallpaper / design inspiré Halo Waypoint UGC Browse

### Objectif
Rapprocher le look & feel de la page “Content Browser” Halo Waypoint (wallpaper hero + grille de cards avec thumbnails).

### Recommandations concrètes
- Ajouter une section “gallery grid” (cards) pour :
  - Dernier match (1 card)
  - Top médailles (grille)
  - Eventuellement “Top maps/modes” (cards)
- Ajouter un wallpaper (local) dans `static/` et l’utiliser en fond (avec overlay/blur/grain).
- Introduire des styles “cards” (bordure fine, background semi-translucide, hover).

### Fichiers touchés
- `static/styles.css`
- `src/ui/styles.py` (si on ajoute HTML helper)

---

## 4) Afficher les 25 médailles les plus remportées

### Objectif
Calculer `Top 25` sur la période/filtre courant et afficher : nom + count + icône si possible.

### Données (ce qu’on a)
- `MatchStats` contient les listes `Medals[]` avec `NameId` + `Count`.

### Problème à résoudre
- Le mapping `NameId -> libellé + image` n’est pas directement disponible via `InventoryItems` sur l’échantillon inspecté.

### Recommandation
- Implémenter d’abord un “MVP” : Top 25 **par NameId** + count (bar chart + table).
- Puis ajouter un mapping local optionnel :
  - `static/medals/medals.json` : `{ "<NameId>": {"name": "…", "icon": "…"} }`
  - `static/medals/icons/...`.
- S’inspirer des patterns et assets d’OpenSpartan Workshop (sans copier du code non buildable) : même structure de stats + affichage “tile”/grid.

### Implémentation suggérée
- Ajouter un module analyse : `src/analysis/medals.py` avec
  - `compute_top_medals(df_or_matches, top_n=25)`.
- Ajouter une section UI dans un nouvel onglet (“Médailles”) ou dans “Dernier match”.

---

## 5) S’inspirer des guides OpenSpartan pour query la DB

### Objectif
Réduire le parsing Python “full scan” et utiliser davantage `sqlite + json_extract/json_each`.

### Recommandations
- Ajouter des requêtes SQL dédiées (dans `src/db/queries.py`) :
  - “last match id” (ORDER BY StartTime desc LIMIT 1)
  - “match list” avec colonnes extraites (match_id, start_time, playlist_id, map_id, game_variant_id)
  - “medals aggregation” via `json_each`.
- Garder le JSON complet uniquement pour les écrans qui ont besoin de détails.

### Référence
- Guide OpenSpartan : https://openspartan.com/docs/workshop/guides/understanding-the-local-database/

---

## 6) Dockeriser le script (dans une nouvelle branche)

### Faisabilité
- Oui, le dashboard Streamlit est dockerisable.
- Point d’attention : la DB est générée par une app Windows, donc en Docker il faut **monter le fichier `.db`** dans le container.

### Plan de branche
- Créer une branche dédiée, ex: `feature/docker`.

### Livrables
- `Dockerfile` (python slim, install deps, expose 8501, run `streamlit run streamlit_app.py`).
- `docker-compose.yml` (optionnel) avec volume DB monté.
- `.dockerignore`.
- Section README “Docker” (commande run + comment monter la DB).

### Notes Windows
- Pour monter la DB : documenter l’équivalent de `%LOCALAPPDATA%\OpenSpartan.Workshop\data\<xuid>.db` vers `/data/<xuid>.db`.
- Prévoir une variable d’env `OPENSPARTAN_DB=/data/<xuid>.db` ou équivalent pour préremplir le champ.

---

## Questions (pour verrouiller les choix)

- “Team MMR” : tu veux afficher **MMR de ton équipe seulement**, ou **les deux équipes** (TeamMmrs) + écart ?
- Les “25 médailles” : tu veux un onglet dédié “Médailles” ou une section dans “Dernier match” ?
- Pour le filtre “mode” : on garde Playlist/Pair en plus (fallback), ou on remplace complètement ?
