# Plan : Enregistrement en BDD des tirs (shots_fired / shots_hit) et backfill

> Planification uniquement — pas de modification de code dans ce document.  
> Date : 2026-02-07

---

## Contexte

- **API** : L’API Halo fournit `ShotsFired` et `ShotsHit` pour **chaque joueur** dans `MatchStats.Players[]` (CoreStats).
- **Actuellement** : Les champs sont extraits dans `MatchStatsRow` (transformers) et les colonnes existent dans `match_stats`, mais **l’INSERT dans engine.py ne les écrit pas**. Pour les autres joueurs, on ne stocke rien (pas de shots dans `match_participants`).
- **Objectif** : Persister shots_fired et shots_hit pour le joueur propriétaire **et** pour tous les participants, et prévoir les options de backfill dans `backfill_data.py`.

---

## 1. Périmètre des données

| Cible | Table | Portée | Source API |
|-------|--------|--------|------------|
| Joueur propriétaire (token) | `match_stats` | 1 ligne / match | `Players[]` où `PlayerId` = xuid du joueur |
| Tous les joueurs du match | `match_participants` | 1 ligne / (match_id, xuid) | `Players[]` (chaque entrée a ses CoreStats) |

---

## 2. Modifications à prévoir (sans toucher au code ici)

### 2.1 Table `match_stats`

- **Colonnes** : Déjà présentes (`shots_fired INTEGER`, `shots_hit INTEGER`).
- **À faire** :
  - Inclure `shots_fired` et `shots_hit` dans l’INSERT de `_insert_match_row` (engine.py), avec les autres colonnes optionnelles déjà prévues (damage_dealt, damage_taken, etc. si souhaité).
- **Sync** : Lors de l’ingestion d’un nouveau match, la ligne insérée contiendra déjà shots_fired / shots_hit (déjà fournis par `transform_match_stats`).

### 2.2 Table `match_participants`

- **Colonnes à ajouter** (migration) :
  - `shots_fired INTEGER` (nullable)
  - `shots_hit INTEGER` (nullable)
- **Modèle** : Étendre `MatchParticipantRow` (models.py) avec `shots_fired` et `shots_hit`.
- **Extraction** : Dans `extract_participants`, pour chaque `player` dans `Players[]`, récupérer `ShotsFired` et `ShotsHit` depuis le même CoreStats que Kills/Deaths/Assists (`_find_core_stats_dict(player)`), et les ajouter à chaque `MatchParticipantRow`.
- **Sync** : Lors de l’écriture des participants (engine), inclure shots_fired et shots_hit dans l’INSERT/REPLACE de `match_participants`. S’assurer que la création/migration de table ajoute ces colonnes (comme pour rank/score/kda).

---

## 3. Options backfill à anticiper dans `backfill_data.py`

Convention : même logique que `--accuracy` / `--participants-kda` (identifier les matchs à mettre à jour, re-télécharger le JSON match, extraire, UPDATE ou INSERT/REPLACE).

### 3.1 Backfill pour le joueur propriétaire (`match_stats`)

- **Option** : `--shots` (ou `--match-stats-shots`)
  - **Comportement** : Pour chaque match où `match_stats.shots_fired` ou `match_stats.shots_hit` est NULL, re-télécharger le match via l’API, appeler `transform_match_stats`, puis mettre à jour (UPDATE) ou remplacer la ligne (INSERT OR REPLACE) avec les valeurs shots_fired / shots_hit.
  - **Sélection des matchs** : `SELECT match_id FROM match_stats WHERE shots_fired IS NULL OR shots_hit IS NULL`.
- **Option** : `--force-shots`
  - **Comportement** : Comme `--force-accuracy` : traiter **tous** les matchs de la BDD, pas seulement ceux avec shots NULL. Utile après correction de l’INSERT pour remplir l’historique.
- **Compteur de rapport** : Ex. `shots_updated` ou `match_stats_shots_updated` (nombre de matchs mis à jour).

### 3.2 Backfill pour tous les participants (`match_participants`)

- **Option** : `--participants-shots`
  - **Comportement** : Pour les matchs où au moins un participant a `shots_fired IS NULL` ou `shots_hit IS NULL` (ou où la table n’a pas encore les colonnes et on remplit tout), re-télécharger le match, appeler `extract_participants` (avec la nouvelle extraction ShotsFired/ShotsHit), puis UPDATE ou INSERT OR REPLACE des lignes `match_participants` pour ce match (tous les participants).
  - **Sélection** : Soit par match (liste des match_id ayant des participants sans shots), soit “tous les matchs qui ont des participants” si les colonnes viennent d’être ajoutées et sont encore vides.
- **Option** : `--force-participants-shots`
  - **Comportement** : Forcer la ré-extraction et mise à jour des shots pour **tous** les participants de **tous** les matchs (utile après ajout des colonnes ou correction de l’extraction).
- **Compteur** : Ex. `participants_shots_updated` (nombre de lignes participants mises à jour).

### 3.3 Intégration dans la CLI et le flux

- **Arguments** : Ajouter `--shots`, `--force-shots`, `--participants-shots`, `--force-participants-shots` au parser argparse.
- **Propagation** : Passer ces flags dans la fonction qui décide quels matchs récupérer et quelles mises à jour faire (comme pour `participants_kda` / `participants_scores`).
- **Ordre d’exécution** : Dans une même passe backfill, on peut faire d’abord match_stats (--shots), puis match_participants (--participants-shots), en réutilisant le même `stats_json` téléchargé par match pour limiter les appels API.
- **Dry-run** : En mode `--dry-run`, lister les match_id qui seraient traités pour --shots et pour --participants-shots, sans rien écrire.

### 3.4 Exemples d’usage à documenter (docstring / README)

```text
# Backfill shots pour le joueur propriétaire (matchs où shots manquants)
python scripts/backfill_data.py --player JGtm --shots

# Forcer shots pour tous les matchs (match_stats)
python scripts/backfill_data.py --player JGtm --shots --force-shots

# Backfill shots pour tous les participants (match_participants)
python scripts/backfill_data.py --player JGtm --participants-shots

# Forcer shots pour tous les participants de tous les matchs
python scripts/backfill_data.py --player JGtm --participants-shots --force-participants-shots

# Combiner avec --all
python scripts/backfill_data.py --all --shots --participants-shots
```

---

## 4. Sprints précis

**Gate avant livraison (tous les sprints)** : Avant toute livraison de sprint, l’exécution des **tests nouveaux et des tests mis à jour** est **obligatoire**. Tous les tests concernés doivent passer (ex. `pytest tests/ -v`). Aucune livraison ne peut être considérée faite si cette condition n’est pas remplie.

---

### Sprint 1 — Shots joueur propriétaire (match_stats)

**Objectif** : Persister shots_fired / shots_hit pour le joueur dont on sync la BDD et permettre le backfill.

| # | Tâche | Livrable | Critère d’acceptation |
|---|--------|----------|------------------------|
| 1.1 | Inclure shots_fired et shots_hit dans l’INSERT | `engine.py` : `_insert_match_row` modifié | Les nouvelles sync écrivent shots_fired/shots_hit en base pour chaque match. |
| 1.2 | Backfill match_stats : sélection des matchs | Dans backfill_data.py : requête matchs où shots_fired IS NULL OR shots_hit IS NULL | Liste de match_id à traiter pour --shots. |
| 1.3 | Backfill match_stats : mise à jour | Re-télécharger match, transform_match_stats, UPDATE ou INSERT OR REPLACE avec shots | Les lignes match_stats sont mises à jour avec les valeurs extraites. |
| 1.4 | Options CLI --shots et --force-shots | argparse + propagation dans le flux backfill | --shots ne traite que les matchs avec shots NULL ; --force-shots traite tous les matchs. |
| 1.5 | Compteur et logs | shots_updated (ou match_stats_shots_updated) dans le rapport final + logs | L’utilisateur voit combien de matchs ont été mis à jour. |
| 1.6 | Dry-run | En --dry-run, lister les match_id qui seraient traités pour --shots | Aucune écriture ; liste uniquement. |
| 1.7 | Tests | Nouveaux tests (shots dans match_stats, backfill --shots) ; mise à jour des tests existants impactés (ex. sync engine, transformers) ; exécution complète | `pytest tests/ -v` vert avant livraison. |

**Livrables de sprint** : Sync qui remplit shots en match_stats ; backfill --shots / --force-shots opérationnel ; docstring backfill_data.py mise à jour pour ces options.

**Gate avant livraison** : Exécution des tests (nouveaux + mis à jour) obligatoire ; tous les tests passent.

**Durée indicative** : 1 sprint court.

---

### Sprint 2 — Shots tous les participants (match_participants)

**Objectif** : Stocker shots_fired / shots_hit pour tous les joueurs de chaque match et permettre le backfill participants.

| # | Tâche | Livrable | Critère d’acceptation |
|---|--------|----------|------------------------|
| 2.1 | Migration schéma match_participants | Colonnes shots_fired INTEGER, shots_hit INTEGER (ALTER ou création) | Table match_participants contient shots_fired et shots_hit (nullable). |
| 2.2 | Modèle MatchParticipantRow | models.py : champs shots_fired, shots_hit | Dataclass aligné avec la table. |
| 2.3 | Extraction dans extract_participants | ShotsFired / ShotsHit depuis _find_core_stats_dict(player) par joueur | Chaque MatchParticipantRow retourné contient shots_fired et shots_hit. |
| 2.4 | Sync : écriture participants | engine : INSERT/REPLACE match_participants inclut shots_fired, shots_hit | Lors de l’ingestion d’un match, tous les participants sont enregistrés avec leurs shots. |
| 2.5 | Backfill participants : sélection | Matchs où au moins un participant a shots_fired IS NULL ou shots_hit IS NULL (ou tous si colonnes neuves) | Liste de match_id pour --participants-shots. |
| 2.6 | Backfill participants : mise à jour | Re-télécharger match, extract_participants, UPDATE ou REPLACE des lignes match_participants pour ce match | Tous les participants du match ont shots_fired/shots_hit remplis. |
| 2.7 | Options CLI --participants-shots et --force-participants-shots | argparse + propagation | --participants-shots : matchs avec participants sans shots ; --force-participants-shots : tous les matchs. |
| 2.8 | Réutilisation du JSON par match | Lors d’une même passe, réutiliser stats_json pour --shots et --participants-shots si les deux sont demandés | Un seul appel API get_match_stats par match. |
| 2.9 | Compteur et dry-run | participants_shots_updated + dry-run liste pour --participants-shots | Rapport et dry-run cohérents. |
| 2.10 | Tests | Nouveaux tests (shots dans match_participants, extract_participants, backfill --participants-shots) ; mise à jour des tests existants impactés (engine, modèles) ; exécution complète | `pytest tests/ -v` vert avant livraison. |

**Livrables de sprint** : match_participants contient shots pour tous les participants ; sync et backfill --participants-shots / --force-participants-shots opérationnels.

**Gate avant livraison** : Exécution des tests (nouveaux + mis à jour) obligatoire ; tous les tests passent.

**Dépendance** : Sprint 1 terminé (optionnel pour la logique, mais cohérent pour réutiliser le même JSON dans une passe backfill combinée).

**Durée indicative** : 1 sprint.

---

### Sprint 3 — Documentation et traçabilité

**Objectif** : Finaliser la doc et la traçabilité données.

| # | Tâche | Livrable | Critère d’acceptation |
|---|--------|----------|------------------------|
| 3.1 | Docstring backfill_data.py | Exemples --shots, --force-shots, --participants-shots, --force-participants-shots et combinaison avec --all | En tête du script, tous les usages shots sont documentés. |
| 3.2 | Référence projet | CLAUDE.md ou thought_log : mention des options backfill shots | Les agents / devs trouvent les options sans chercher. |
| 3.3 | Ligne de données | data_lineage.md et/ou ARCHITECTURE_ROADMAP : origine shots_fired / shots_hit (match_stats + match_participants) | Traçabilité claire : API → tables. |
| 3.4 | Tests | Vérifier que la suite complète passe après les changements de doc ; corriger ou mettre à jour tout test impacté par les références modifiées | `pytest tests/ -v` vert avant livraison. |

**Livrables de sprint** : Doc à jour ; data lineage / roadmap alignés.

**Gate avant livraison** : Exécution des tests (nouveaux + mis à jour) obligatoire ; tous les tests passent.

**Dépendance** : Sprints 1 et 2 livrés.

**Durée indicative** : 0,5 sprint (peut être fusionné avec la fin du Sprint 2).

---

## 5. Ordre recommandé des tâches (implémentation future)

1. **Sprint 1** — match_stats (INSERT + backfill --shots / --force-shots).
2. **Sprint 2** — match_participants (migration, modèle, extraction, sync, backfill --participants-shots / --force-participants-shots).
3. **Sprint 3** — Documentation et traçabilité (docstring, CLAUDE/thought_log, data_lineage/ARCHITECTURE_ROADMAP).

---

## 6. Points d’attention

- **Tests avant livraison** : Avant chaque livraison de sprint, exécution obligatoire des tests nouveaux et mis à jour ; `pytest tests/ -v` doit être vert.
- **API** : Un seul appel `get_match_stats(match_id)` fournit déjà tous les joueurs et leurs CoreStats ; pas besoin d’appel supplémentaire pour les shots.
- **Cohérence** : Utiliser les mêmes helpers d’extraction (_find_core_stats_dict, _safe_int) que pour match_stats pour éviter les incohérences.
- **Polars / Pandas** : Rester en Polars côté analyse/requêtes ; backfill peut rester en SQL DuckDB + transformers existants.
- **Règle backfill** : Tout backfill reste dans `scripts/backfill_data.py` (pas de script dédié) — ajout d’options uniquement.

---

## 7. Résumé

| Élément | Action planifiée |
|---------|------------------|
| **match_stats** | Inclure shots_fired, shots_hit dans l’INSERT ; backfill `--shots` + `--force-shots` |
| **match_participants** | Ajouter colonnes shots_fired, shots_hit ; étendre modèle et extract_participants ; backfill `--participants-shots` + `--force-participants-shots` |
| **backfill_data.py** | Nouveaux flags, sélection des matchs, mise à jour, compteurs, dry-run, docstring et exemples |
| **Livraison** | Exécution des tests (nouveaux + mis à jour) obligatoire avant chaque livraison de sprint ; `pytest tests/ -v` vert. |

Ce document sert de référence pour l’implémentation sans modifier le code ici.
