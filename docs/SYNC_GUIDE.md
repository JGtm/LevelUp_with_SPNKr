# Guide de Synchronisation - LevelUp

> Comment synchroniser vos matchs Halo Infinite avec LevelUp.

## Architecture de Synchronisation

LevelUp utilise une architecture DuckDB unifiée où les données sont synchronisées directement depuis l'API Halo vers votre base de données locale.

```
API SPNKr (Halo Infinite)
        │
        ▼
DuckDBSyncEngine
├── api_client.py      # Wrapper API async
├── transformers.py    # JSON → DuckDB rows
└── engine.py          # Orchestrateur
        │
        ▼
data/players/{gamertag}/stats.duckdb
├── match_stats
├── player_match_stats
├── highlight_events
├── xuid_aliases
└── sync_meta
```

---

## Commandes de Base

### Sync Incrémentale (Delta)

Récupère uniquement les nouveaux matchs depuis la dernière synchronisation :

```bash
python scripts/sync.py --delta --player MonGamertag
```

**Avantages :**
- Rapide (quelques secondes)
- Idéal pour une utilisation quotidienne
- Ne surcharge pas l'API

### Sync Complète (Full)

Récupère tous les matchs jusqu'à une limite :

```bash
python scripts/sync.py --full --player MonGamertag --max-matches 500
```

**Quand utiliser :**
- Premier import
- Récupérer l'historique manquant
- Après une longue période sans sync

### Sync avec Backfill

Après la synchronisation, vous pouvez automatiquement remplir les données manquantes :

```bash
# Backfill complet (toutes les données manquantes)
python scripts/sync.py --delta --player MonGamertag --with-backfill

# Calcul uniquement des scores de performance manquants
python scripts/sync.py --delta --player MonGamertag --backfill-performance-scores
```

**Quand utiliser :**
- Après une sync pour s'assurer que tous les matchs ont leurs données complètes
- Pour calculer les scores de performance des nouveaux matchs
- Pour récupérer les médailles, events ou skill stats manquants

---

## Options Disponibles

| Option | Description | Défaut |
|--------|-------------|--------|
| `--player` | Nom du joueur à synchroniser (gamertag ou XUID) | Tous les joueurs |
| `--delta` | Mode incrémental (nouveaux matchs uniquement) | Non |
| `--full` | Mode complet (tous les matchs jusqu'à la limite) | Non |
| `--max-matches` | Nombre max de matchs | 200 (delta) / 1000 (full) |
| `--match-type` | Type de matchs (`all`, `matchmaking`, `custom`) | `matchmaking` |
| `--with-assets` | Télécharge les assets manquants (médailles, maps) | Non |
| `--with-backfill` | Effectue un backfill complet après la sync | Non |
| `--backfill-performance-scores` | Calcule les scores de performance manquants | Non |
| `--rebuild-cache` | Reconstruit le cache MatchCache | Non |
| `--apply-indexes` | Applique les index optimisés | Non |
| `--stats` | Affiche les statistiques de la DB | Non |
| `--verbose` | Mode verbeux | Non |

**Note importante :** Toutes les données sont toujours récupérées pour chaque match synchronisé :
- ✅ Stats de base (kills, deaths, assists, KDA, etc.)
- ✅ Médailles
- ✅ Personal scores
- ✅ Score de performance
- ✅ Highlight events (kills/deaths depuis les films)
- ✅ Skill/MMR (données de skill par match)
- ✅ Aliases XUID → Gamertag

---

## Synchronisation via l'Interface

### Bouton dans la Sidebar

Le dashboard affiche :
- **Dernière sync** : Date et heure
- **Matchs** : Nombre de matchs synchronisés
- **Bouton Sync** : Déclenche une sync delta
- **Bouton Full** : Déclenche une sync complète

### Sync au Lancement

```bash
# Lancer le dashboard avec sync
python openspartan_launcher.py run+refresh --player MonGamertag --delta
```

---

## Types de Données Synchronisées

**Toutes les données suivantes sont automatiquement récupérées pour chaque match synchronisé.** Il n'est pas possible de désactiver la récupération de certaines données, garantissant ainsi une base de données complète et cohérente.

### match_stats

Statistiques principales de chaque match :

| Colonne | Description |
|---------|-------------|
| `match_id` | Identifiant unique du match |
| `start_time` | Date et heure de début |
| `duration_seconds` | Durée en secondes |
| `playlist_id` | ID de la playlist |
| `map_id` | ID de la carte |
| `kills`, `deaths`, `assists` | Stats de base |
| `accuracy` | Précision (%) |
| `kda` | Ratio (kills + assists/3) / deaths |
| `outcome` | Résultat (1=Tie, 2=Win, 3=Loss, 4=Left) |

### player_match_stats

Données MMR et skill par match :

| Colonne | Description |
|---------|-------------|
| `team_mmr` | MMR de l'équipe |
| `enemy_mmr` | MMR de l'équipe adverse |
| `expected_kills` | Kills attendus (modèle) |
| `expected_deaths` | Deaths attendus (modèle) |

### highlight_events

Événements marquants du match :

| Colonne | Description |
|---------|-------------|
| `event_type` | Type (kill, death, medal) |
| `time_ms` | Timestamp en millisecondes |
| `xuid` | Joueur impliqué |
| `gamertag` | Nom du joueur |

### xuid_aliases

Correspondances XUID ↔ Gamertag :

| Colonne | Description |
|---------|-------------|
| `xuid` | Identifiant Xbox |
| `gamertag` | Dernier gamertag connu |
| `last_seen` | Dernière apparition |

---

## Vues Matérialisées

Après chaque sync, les vues matérialisées sont automatiquement rafraîchies :

| Vue | Description |
|-----|-------------|
| `mv_map_stats` | Stats agrégées par carte |
| `mv_mode_category_stats` | Stats par catégorie de mode |
| `mv_session_stats` | Stats par session de jeu |
| `mv_global_stats` | Statistiques globales |

Ces vues permettent un affichage instantané des agrégations dans le dashboard.

---

## Gestion des Erreurs

### Rate Limiting

L'API Halo a des limites de requêtes. Si vous recevez une erreur 429 :

```
Error: Rate limit exceeded
```

**Solution :**
1. Attendez quelques minutes
2. Réduisez `--max-matches`
3. Utilisez `--delta` au lieu de `--full`

### Token Expiré

```
Error: Authentication failed
```

**Solution :**
```bash
python scripts/spnkr_get_refresh_token.py
```

### Match Introuvable

Certains matchs très anciens peuvent ne plus être disponibles sur les serveurs Halo.

---

## Bonnes Pratiques

### Fréquence de Sync

| Usage | Fréquence | Commande |
|-------|-----------|----------|
| Joueur actif | Quotidienne | `--delta` |
| Joueur occasionnel | Hebdomadaire | `--delta` |
| Premier import | Une fois | `--full --max-matches 1000` |

### Avant une Session de Jeu

```bash
# Sync rapide avant de jouer
python scripts/sync.py --delta --player MonGamertag
```

### Après une Session de Jeu

```bash
# Sync pour voir les nouveaux matchs avec backfill complet
python scripts/sync.py --delta --player MonGamertag --with-backfill

# Ou seulement les scores de performance
python scripts/sync.py --delta --player MonGamertag --backfill-performance-scores
```

---

## Données Historiques

### Migrer depuis SQLite

Si vous avez des données d'une ancienne version :

```bash
# Migrer les données historiques
python scripts/migrate_all_to_duckdb.py --gamertag MonGamertag

# Vérifier la migration
python scripts/sync.py --player MonGamertag --stats
```

### Archiver les Anciens Matchs

Pour les joueurs avec beaucoup de matchs (> 5000) :

```bash
# Archiver les matchs de plus d'un an
python scripts/archive_season.py --gamertag MonGamertag --older-than-days 365
```

---

## Dépannage

### Sync Bloquée

Si la sync semble bloquée :

1. Vérifier la connexion internet
2. Vérifier les tokens Azure
3. Réessayer avec `--verbose` pour plus de détails

### Données Incohérentes

Si les stats ne correspondent pas à Halo Waypoint :

```bash
# Forcer une resync complète avec backfill
python scripts/sync.py --full --player MonGamertag --max-matches 100 --with-backfill

# Vérifier les stats
python scripts/sync.py --player MonGamertag --stats
```

### Base de Données Corrompue

En dernier recours :

```bash
# Backup
python scripts/backup_player.py --gamertag MonGamertag

# Supprimer et recréer
rm data/players/MonGamertag/stats.duckdb
python scripts/sync.py --full --player MonGamertag --with-backfill
```
