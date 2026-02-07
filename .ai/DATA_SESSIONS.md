# Logique Sessions et teammates_signature

> **Date** : 2026-02-06  
> **Sprint 2** : Logique Sessions (teammates_signature)

---

## Vue d'ensemble

La détection des sessions de jeu combine **trois critères** :

1. **Gap temporel** : Nouvelle session si l'écart entre deux matchs dépasse `gap_minutes` (défaut : 120 min)
2. **Changement de coéquipiers** : Nouvelle session si `teammates_signature` change entre deux matchs consécutifs
3. **Heure de coupure** : Utilisée pour les sessions "en cours" (matchs avant 8h regroupés avec la veille)

---

## Colonne `teammates_signature`

### Format

Chaîne de caractères : XUIDs des coéquipiers (même équipe, excluant le joueur principal), **triés par ordre croissant**, séparés par des virgules.

```
"2533274858283686,2533274883457349"
```

### Calcul

- **Source** : JSON du match (`Players`, `LastTeamId`)
- **Fonction** : `compute_teammates_signature(match_json, my_xuid, my_team_id)` dans `src/data/sync/transformers.py`
- **Règles** :
  - Extraire les joueurs avec `LastTeamId == my_team_id` et `xuid != my_xuid`
  - Trier les XUIDs
  - Joindre par virgule

### Valeurs spéciales

| Valeur | Signification |
|--------|---------------|
| `NULL` | Pas de coéquipiers (solo) ou info indisponible |
| `""` | Équipe vide (non utilisé en pratique) |

### Gestion des NULL dans les sessions

Les valeurs `NULL` sont traitées comme une **valeur distincte** pour la détection de rupture :

- `"xuid1"` → `NULL` → nouvelle session
- `NULL` → `"xuid2"` → nouvelle session
- `NULL` → `NULL` (consecutifs) → même session (pas de rupture)

---

## Fonctions de calcul

### `compute_sessions_with_context()` (Pandas)

- **Fichier** : `src/analysis/sessions.py`
- **Entrée** : `pd.DataFrame` avec `start_time` et optionnellement `teammates_signature`
- **Sortie** : DataFrame avec `session_id` et `session_label`

### `compute_sessions_with_context_polars()` (Polars)

- **Fichier** : `src/analysis/sessions.py`
- **Entrée** : `pl.DataFrame` avec `start_time` et optionnellement `teammates_signature`
- **Sortie** : DataFrame avec `session_id` et `session_label`
- **Préféré** : Utiliser la version Polars (règle projet Pandas proscrit)

---

## Backfill teammates_signature

### Script

```bash
# Un joueur
python scripts/backfill_teammates_signature.py --gamertag MonGT

# Tous les joueurs
python scripts/backfill_teammates_signature.py --all

# Limiter
python scripts/backfill_teammates_signature.py --gamertag MonGT --limit 100

# Forcer le recalcul
python scripts/backfill_teammates_signature.py --gamertag MonGT --force

# Simulation (dry-run)
python scripts/backfill_teammates_signature.py --gamertag MonGT --dry-run
```

### Source des données

Le backfill récupère le JSON de chaque match depuis l'API SPNKr (`get_match_stats`), puis calcule `teammates_signature` via `compute_teammates_signature()`.

---

## Stockage session_id / session_label (match_stats)

### Colonnes ajoutées

| Colonne | Type | Description |
|---------|------|-------------|
| `session_id` | VARCHAR | Identifiant unique de la session |
| `session_label` | VARCHAR | Libellé affiché (ex. « Session 1 », « Session du 07/02 ») |

### Règle de stabilité (4 h)

Les sessions ne sont **pas** stockées pour les matchs de moins de 4 h. Pour ces matchs, le calcul reste à la volée dans `cached_compute_sessions_db`.

### Lecture hybride

`cached_compute_sessions_db` :
- **Cas A** : Tous les matchs ont `session_id` et sont ≥ 4 h → retour des données stockées
- **Cas B** : Au moins un match récent ou sans `session_id` → recalcul complet à la volée

### Backfill sessions

```bash
# Un joueur
python scripts/backfill_data.py --player MonGT --sessions

# Tous les joueurs
python scripts/backfill_data.py --all --sessions

# Forcer le recalcul même si session_id déjà rempli
python scripts/backfill_data.py --all --sessions --force-sessions

# Simuler (dry-run)
python scripts/backfill_data.py --player MonGT --sessions --dry-run
```

**Paramètres** : `gap_minutes=120` fixe ; amis via `friends_defaults.json` ou top 2 coéquipiers.

### Plan détaillé

Voir `.ai/features/SESSIONS_STOCKAGE_PLAN.md`.

---

## Utilisation dans l'UI

- **Cache** : `src/ui/cache.py` utilise `compute_sessions_with_context_polars()` quand `teammates_signature` est disponible
- **Fallback** : Si la colonne est absente, utilisation de la logique gap seul (comportement legacy)

---

## Tests

| Fichier | Contenu |
|---------|---------|
| `tests/test_sessions_advanced.py` | Tests généraux (gap, changement, NULL, premier match) |
| `tests/test_sessions_teammates.py` | Scénarios coéquipiers (solo/squad, un part, un rejoint) |
| `tests/test_transformers_teammates.py` | Tests unitaires `compute_teammates_signature` |

---

## Références

- `.ai/archive/plans_treated_2026-02/sprints/LOGIC_LEGACY_SESSIONS.md` : Logique legacy détaillée
- `.ai/CONSOLIDATED_AUDITS_AND_ROADMAP.md` : Sprint 2
