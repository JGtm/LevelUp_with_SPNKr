# Plan : Stockage des sessions en base (session_id figé)

> **Date** : 2026-02-07  
> **Objectif** : Figer les sessions avec des paramètres fixes, les stocker en base, supprimer le slider, prévoir un backfill pour recalculer, et exclure les matchs < 4h du stockage (calcul à la volée pour ceux-ci).

---

## 0. Règle des 4 heures (sécurité des sessions)

**Problème** : Une session est "ouverte" tant qu'un match peut encore s'y rattacher (gap < 120 min). Stocker `session_id` trop tôt risque de le rendre obsolète si le joueur enchaîne.

**Règle** :
- **Matchs ≥ 4h** : `session_id` et `session_label` stockés en base (session considérée stable)
- **Matchs < 4h** : `session_id` = NULL en base, calcul à la volée à chaque lecture

**Justification** : 4h = 2× le gap (120 min), seuil conservateur pour considérer une session terminée.

**Comportement lecture** :
- Lire `session_id` depuis la DB pour les matchs qui l'ont
- Pour les matchs avec NULL (ou < 4h), recalculer à la volée sur la fenêtre concernée et fusionner avec les sessions stockées (association préliminaire logique et safe)

---

## 1. Récapitulatif de la logique de session actuelle

### 1.1 Paramètres utilisés

| Paramètre | Source actuelle | Valeur figée proposée |
|-----------|-----------------|------------------------|
| **gap_minutes** | Slider sidebar (15–240, défaut 120) | **120** (SESSION_CONFIG.advanced_gap_minutes) |
| **friends_xuids** | `.streamlit/friends_defaults.json` ou top 2 coéquipiers | **friends_defaults.json** au moment du backfill |

### 1.2 Logique legacy V3 (mode jeu avec amis)

**Règle 1 – Gap temporel**
- Nouvelle session si : `(start_time_match_N - start_time_match_N-1) > 120 minutes`

**Règle 2 – Changement de coéquipiers (amis uniquement)**
- `prev_friends = prev_teammates ∩ friends_xuids`
- `curr_friends = curr_teammates ∩ friends_xuids`
- Nouvelle session si :
  - Passage à solo : `curr_friends vide ET prev_friends non vide`
  - Un ami rejoint : `curr_friends - prev_friends ≠ ∅`
- Même session si :
  - Un ami part (sauf passage à solo)
  - Seuls les randoms changent (matchmaking)

**Format teammates_signature** : XUIDs triés, séparés par virgule, ex. `"2533274823110022,2533274858283686"`

### 1.3 Liste d'amis – config actuelle

**Fichier** : `.streamlit/friends_defaults.json`  
**Format** : `{ "xuid_joueur": ["gamertag_ami1", "gamertag_ami2", ...] }`

**Contenu actuel** :
```
2533274823110022 (JGtm)         → Madina97294, Chocoboflor, XxDaemonGamerxX
2533274858283686 (Madina97294)  → JGtm, Chocoboflor, XxDaemonGamerxX
2535469190789936 (Chocoboflor)  → JGtm, Madina97294, XxDaemonGamerxX
2533274833178266 (XxDaemonGamerxX) → JGtm, Madina97294, Chocoboflor
```

Les gamertags sont résolus en XUID via `build_xuid_option_map` / `display_name_from_xuid` au moment du chargement.

### 1.4 Fallback si pas d'amis

Si `friends_defaults.json` n'a pas d'entrée pour le joueur : **top 2 coéquipiers** (depuis `cached_list_top_teammates`).  
Si aucun ami : comportement **gap seul** (tout changement de teammates_signature = nouvelle session).

---

## 2. Plan détaillé d'implémentation

### Phase 1 : Schéma et colonnes

**Table** : `match_stats` (DuckDB v4, une DB par joueur)

**Colonnes à ajouter** :
| Colonne | Type | Description |
|---------|------|-------------|
| `session_id` | INTEGER | ID de session (0, 1, 2, … par ordre chronologique inverse) |
| `session_label` | VARCHAR | Label lisible, ex. `"07/02/2026 14:30–16:45 (5)"` |

**Notes** :
- `session_id` doit être unique et stable pour un match donné
- Les sessions sont calculées avec les paramètres figés au moment du backfill

### Phase 2 : Configuration figée pour le backfill

**Constantes** (ex. dans `src/config.py` ou nouveau module `src/config/sessions_storage.py`) :
```python
STORED_SESSION_GAP_MINUTES = 120
# friends_xuids : chargés depuis .streamlit/friends_defaults.json au moment du backfill
```

**Contrainte** : Le backfill doit être exécutable sans environnement Streamlit (pas de `st.session_state`). La fonction `get_friends_xuids_for_sessions` dépend de `build_friends_opts_map` qui utilise des caches Streamlit. Il faudra une version standalone pour le backfill :
- Lire `.streamlit/friends_defaults.json` directement
- Résoudre gamertags → XUID via la DB (xuid_aliases, teammates_aggregate)

### Phase 3 : Script de backfill des sessions

**Nouveau script** : `scripts/backfill_sessions.py`

**Constante** : `SESSION_STABILITY_HOURS = 4` (seuil en heures)

**Options** :
```
--gamertag GAMERTAG   Joueur à traiter
--all                 Tous les joueurs DuckDB v4
--force               Recalculer même si session_id déjà rempli
--include-recent      Inclure les matchs < 4h (stockage pour tous, sinon seulement ≥ 4h)
--dry-run             Simulation sans UPDATE
--gap-minutes N       Override du gap (défaut: 120)
```

**Algorithme** :
1. Charger `friends_xuids` pour le joueur (friends_defaults.json ou top 2)
2. Charger `match_stats` (match_id, start_time, teammates_signature) trié par start_time
3. Exécuter `compute_sessions_with_context_polars(df, gap_minutes=120, friends_xuids=friends_set)`
4. Pour chaque match :
   - Si `start_time >= now - 4h` ET non `--include-recent` : **ne pas UPDATE** (session_id reste NULL)
   - Sinon : UPDATE match_stats SET session_id = ?, session_label = ? WHERE match_id = ?

**Sync** : lors de l'insertion de nouveaux matchs, ne pas écrire `session_id` (NULL par défaut). Le backfill (manuel ou périodique) remplira les matchs ≥ 4h.

**Dépendances** : `teammates_signature` doit être rempli (déjà le cas ou via `backfill_teammates_signature.py --force`)

### Phase 4 : Adaptation de l'UI

**4.1 Suppression du slider**
- Fichiers : `src/app/filters_render.py`, `src/app/filters.py`
- Supprimer le `st.slider("Écart max entre parties (minutes)", ...)`
- Supprimer `gap_minutes` du `FilterState` (ou le garder en interne avec valeur fixe 120 pour compatibilité)

**4.2 Lecture des sessions (hybride stocké + calcul à la volée)**

**Logique** :
1. SELECT match_stats (match_id, start_time, teammates_signature, session_id, session_label)
2. **Cas A** : Tous les matchs ont session_id non NULL et sont ≥ 4h → utiliser les valeurs stockées directement (aucun calcul)
3. **Cas B** : Au moins un match a session_id NULL ou est < 4h → calcul à la volée sur **l'ensemble des matchs** via `compute_sessions_with_context_polars`
   - Garantit la cohérence : les matchs récents et leurs voisins (même session possible) ont des session_id alignés
   - Association préliminaire pour les récents, safe car calcul complet

**4.3 Filtres et préférences**
- `filter_state.gap_minutes` : supprimer de la persistance (ou fixer à 120)
- `FilterPreferences` dans `filter_state.py` : retirer gap_minutes ou le laisser optionnel

### Phase 5 : Points d'appel à adapter

| Fichier | Modification |
|---------|--------------|
| `src/ui/cache.py` | `cached_compute_sessions_db` : d'abord SELECT session_id, session_label depuis match_stats ; si NULL, fallback calcul |
| `src/app/filters_render.py` | Supprimer slider, passer gap_minutes=120 en dur |
| `src/app/filters.py` | Idem si utilisé |
| `src/app/page_router.py` | Utiliser gap_minutes=120 (ou le retirer du passage de paramètres) |
| `src/ui/pages/teammates.py` | Remplacer `st.session_state.get("gap_minutes", 120)` par 120 |
| `streamlit_app.py` | Retirer "gap_minutes" des clés à clear au changement de joueur |
| `src/ui/filter_state.py` | gap_minutes optionnel ou supprimé |

### Phase 6 : Migration des DB existantes

**Option A** : Colonnes nullable, backfill manuel
- ALTER TABLE match_stats ADD COLUMN session_id INTEGER;
- ALTER TABLE match_stats ADD COLUMN session_label VARCHAR;
- L'utilisateur exécute `python scripts/backfill_sessions.py --all`

**Option B** : Backfill automatique à la première ouverture
- Détecter si des matchs ont session_id NULL
- Lancer le backfill en tâche de fond ou au prochain sync

**Recommandation** : Option A (explicite, l'utilisateur contrôle)

---

## 3. Décomposition en sprints

### Sprint 1 : Schéma et constante
| # | Tâche | Détail |
|---|-------|--------|
| 1.1 | Ajouter colonnes à match_stats | ALTER TABLE match_stats ADD COLUMN session_id INTEGER ; ADD COLUMN session_label VARCHAR |
| 1.2 | Constante SESSION_STABILITY_HOURS | 4 dans src/config.py ou sessions_storage |
| 1.3 | Mettre à jour sync engine | S'assurer que l'INSERT de nouveaux matchs laisse session_id, session_label à NULL (pas d'écriture) |

### Sprint 2 : Backfill standalone
| # | Tâche | Détail |
|---|-------|--------|
| 2.1 | get_friends_xuids_for_backfill | Fonction sans Streamlit : lire friends_defaults.json, résoudre gamertags → XUID via xuid_aliases/teammates |
| 2.2 | Script backfill_sessions.py | Options --gamertag, --all, --force, --include-recent, --dry-run, --gap-minutes |
| 2.3 | Règle 4h dans backfill | Ne pas UPDATE les matchs avec start_time >= now - 4h sauf si --include-recent |
| 2.4 | Tests du script | dry-run, vérifier exclusion des matchs récents |

### Sprint 3 : Lecture hybride (cache)
| # | Tâche | Détail |
|---|-------|--------|
| 3.1 | Lire depuis match_stats | SELECT match_id, start_time, teammates_signature, session_id, session_label |
| 3.2 | Cas A (tout stable) | Si tous ont session_id non NULL et start_time ≥ now-4h → retourner tel quel |
| 3.3 | Cas B (présence de récents) | Si au moins un session_id NULL ou start_time < now-4h → calcul complet à la volée |
| 3.4 | Calcul à la volée | compute_sessions_with_context_polars sur tout le DataFrame, mêmes paramètres figés |

### Sprint 4 : Suppression slider et UI
| # | Tâche | Détail |
|---|-------|--------|
| 4.1 | Supprimer slider | filters_render.py, filters.py : st.slider("Écart max...") |
| 4.2 | Fixer gap_minutes à 120 | Partout où c'était dynamique : 120 en dur |
| 4.3 | FilterState / FilterPreferences | Retirer ou figer gap_minutes |
| 4.4 | Autres appels | page_router, teammates.py, streamlit_app : adapter |

### Sprint 5 : Migration et doc
| # | Tâche | Détail |
|---|-------|--------|
| 5.1 | Migration schéma | Script ou instructions ALTER pour DB existantes |
| 5.2 | Backfill initial | python scripts/backfill_sessions.py --all |
| 5.3 | Documentation | CLAUDE.md, DATA_SESSIONS.md, SESSIONS_STOCKAGE_PLAN.md |

---

## 4. Ordre d'exécution recommandé

1. Sprint 1 (schéma)
2. Sprint 2 (backfill script)
3. Sprint 3 (lecture hybride)
4. Sprint 4 (suppression slider)
5. Sprint 5 (migration + doc)

---

## 6. Recalcul ultérieur (changement de config)

Si l'utilisateur modifie `friends_defaults.json` ou souhaite un autre gap :
```bash
python scripts/backfill_sessions.py --all --force
# ou
python scripts/backfill_sessions.py --gamertag JGtm --force --gap-minutes 90
```

Le `--force` force le recalcul pour tous les matchs, même ceux qui ont déjà un session_id.

---

## 7. Fichiers de référence

| Fichier | Rôle |
|---------|------|
| `src/analysis/sessions.py` | `compute_sessions_with_context_polars`, `_should_start_new_session_on_teammate_change` |
| `src/app/filters.py` | `get_friends_xuids_for_sessions`, `_load_local_friends_defaults` |
| `src/app/filters_render.py` | `_render_session_filter`, `FilterState`, `apply_filters` |
| `src/data/sessions_backfill.py` | `get_friends_xuids_for_backfill` (standalone, sans Streamlit) |
| `src/ui/cache.py` | `cached_compute_sessions_db` (lecture hybride) |
| `scripts/backfill_data.py` | Backfill session_id, session_label (option --sessions) |
| `.streamlit/friends_defaults.json` | Config amis par joueur |
| `scripts/_obsolete/migrate_to_cache.py` | Référence legacy `should_start_new_session_on_teammate_change` |
| `.ai/archive/.../LOGIC_LEGACY_SESSIONS.md` | Documentation détaillée de la logique |

---

## 8. Implémentation terminée (2026-02-07)

Tous les sprints ont été implémentés. Pour appliquer le backfill initial :

```bash
python scripts/backfill_data.py --all --sessions
```

---

*Document créé le 2026-02-07*
