# Plan : Récupération des dommages (damage_dealt/damage_taken) pour les participants

> Date : 2026-02-09  
> Statut : 📋 Planification  
> Objectif : Ajouter `damage_dealt` et `damage_taken` à la table `match_participants` pour tous les joueurs d'un match

---

## Contexte

Actuellement, les données `damage_dealt` et `damage_taken` sont :
- ✅ **Récupérées** pour le joueur principal dans `match_stats` (via `transform_match_stats`)
- ❌ **Non récupérées** pour les autres participants dans `match_participants`

L'API SPNKr fournit ces données dans `Players[].PlayerTeamStats[].Stats.CoreStats.DamageDealt` et `DamageTaken` pour chaque joueur.

---

## Architecture

### 1. Modèle de données (`src/data/sync/models.py`)

**Fichier** : `src/data/sync/models.py`  
**Classe** : `MatchParticipantRow` (ligne ~302)

**Modifications** :
- Ajouter `damage_dealt: float | None = None` après `shots_hit`
- Ajouter `damage_taken: float | None = None` après `damage_dealt`
- Mettre à jour la docstring pour mentionner les dommages

**Référence** : Voir `MatchStatsRow` (ligne ~195-196) pour le type (`float | None`)

---

### 2. Extraction des données (`src/data/sync/transformers.py`)

**Fichier** : `src/data/sync/transformers.py`  
**Fonction** : `extract_participants` (ligne ~1095)

**Modifications** :
- Après l'extraction de `shots_fired` et `shots_hit` (ligne ~1162-1164)
- Ajouter l'extraction de `damage_dealt` et `damage_taken` depuis `stats_dict` :
  ```python
  damage_dealt_val = _safe_float(stats_dict.get("DamageDealt")) if stats_dict else None
  damage_taken_val = _safe_float(stats_dict.get("DamageTaken")) if stats_dict else None
  ```
- Ajouter ces valeurs à `MatchParticipantRow` lors de la création (ligne ~1166-1181)

**Référence** : Voir `transform_match_stats` (ligne ~500-501) pour l'extraction similaire

---

### 3. Schéma de base de données (`src/data/sync/engine.py`)

**Fichier** : `src/data/sync/engine.py`

#### 3.1. Schéma DDL (ligne ~146)

**Modifications** :
- Dans `SYNC_SCHEMA_DDL`, ajouter les colonnes dans le `CREATE TABLE IF NOT EXISTS match_participants` :
  ```sql
  damage_dealt FLOAT,
  damage_taken FLOAT,
  ```
- Placer après `shots_hit INTEGER` (ligne ~158)

#### 3.2. Migration des colonnes (ligne ~425)

**Fonction** : `_ensure_match_participants_rank_score` (à renommer ou créer une nouvelle fonction)

**Modifications** :
- Ajouter la vérification et création des colonnes `damage_dealt` et `damage_taken` :
  ```python
  if "damage_dealt" not in col_names:
      conn.execute("ALTER TABLE match_participants ADD COLUMN damage_dealt FLOAT")
  if "damage_taken" not in col_names:
      conn.execute("ALTER TABLE match_participants ADD COLUMN damage_taken FLOAT")
  ```
- Placer après la vérification de `shots_hit` (ligne ~448-449)

**Note** : Cette fonction est appelée automatiquement lors du sync et du backfill.

---

### 4. Insertion des participants lors du sync (`src/data/sync/engine.py`)

**Fichier** : `src/data/sync/engine.py`  
**Fonction** : `_insert_participant_rows` (ligne ~1101)

**Modifications** :
- Ajouter `damage_dealt` et `damage_taken` dans la liste des colonnes de l'`INSERT OR REPLACE` (ligne ~1115-1117) :
  ```sql
  match_id, xuid, team_id, outcome, gamertag, rank, score,
  kills, deaths, assists, shots_fired, shots_hit, damage_dealt, damage_taken
  ```
- Ajouter les valeurs correspondantes dans les paramètres (ligne ~1119-1132) :
  ```python
  getattr(row, "damage_dealt", None),
  getattr(row, "damage_taken", None),
  ```
- Utiliser `getattr()` pour compatibilité avec les anciennes instances de `MatchParticipantRow` qui n'auraient pas encore ces attributs
- Mettre à jour la docstring pour mentionner les dommages

**Référence** : Voir `_insert_participant_rows` dans `backfill_data.py` (ligne ~354-356) pour le pattern similaire

---

### 5. Script de backfill (`scripts/backfill_data.py`)

**Fichier** : `scripts/backfill_data.py`

#### 5.1. Fonction `_ensure_match_participants_columns` (ligne ~295)

**Modifications** :
- Ajouter la vérification et création des colonnes `damage_dealt` et `damage_taken` :
  ```python
  if "damage_dealt" not in col_names:
      conn.execute("ALTER TABLE match_participants ADD COLUMN damage_dealt FLOAT")
  if "damage_taken" not in col_names:
      conn.execute("ALTER TABLE match_participants ADD COLUMN damage_taken FLOAT")
  ```
- Placer après `shots_hit` (ligne ~315-316)

#### 5.2. Fonction `_insert_participant_rows` (ligne ~321)

**Modifications** :
- Ajouter `damage_dealt` et `damage_taken` dans la liste des colonnes de l'`INSERT OR REPLACE` (ligne ~354-356)
- Ajouter les valeurs correspondantes dans les paramètres (ligne ~357-370) :
  ```python
  getattr(row, "damage_dealt", None),
  getattr(row, "damage_taken", None),
  ```

#### 5.3. Fonction `_find_matches_missing_data` (ligne ~727)

**Modifications** :
- Ajouter un nouveau paramètre `participants_damage: bool = False` (ligne ~743)
- Ajouter un nouveau paramètre `force_participants_damage: bool = False` (ligne ~744)
- Dans la logique de détection (après `participants_shots`, ligne ~938) :
  ```python
  if participants_damage:
      if force_participants_damage:
          conditions.append("1=1")  # Tous les matchs pour forcer damage des participants
      else:
          try:
              table_ok = conn.execute(
                  "SELECT COUNT(*) FROM information_schema.tables "
                  "WHERE table_schema = 'main' AND table_name = 'match_participants'"
              ).fetchone()
              damage_ok = conn.execute(
                  "SELECT COUNT(*) FROM information_schema.columns "
                  "WHERE table_schema = 'main' AND table_name = 'match_participants' AND column_name = 'damage_dealt'"
              ).fetchone()
              if table_ok and table_ok[0] and damage_ok and damage_ok[0]:
                  conditions.append("""
                      ms.match_id IN (
                          SELECT match_id FROM match_participants
                          WHERE damage_dealt IS NULL OR damage_taken IS NULL
                      )
                  """)
              else:
                  conditions.append("1=1")
          except Exception:
              conditions.append("1=1")
  ```

#### 5.4. Fonction `backfill_player_data` (ligne ~982)

**Modifications** :
- Ajouter les paramètres `participants_damage: bool = False` (ligne ~1000)
- Ajouter les paramètres `force_participants_damage: bool = False` (ligne ~1010)
- **IMPORTANT** : Dans le bloc `if all_data:` (ligne ~1035), ajouter `participants_damage = True` après `participants_shots = True` (ligne ~1049)
  ```python
  if all_data:
      # ... autres options ...
      participants_shots = True  # shots_fired/shots_hit des participants
      participants_damage = True  # damage_dealt/damage_taken des participants
      killer_victim = True
      # ...
  ```
- Dans la vérification des options activées (ligne ~1081), ajouter `participants_damage`
- Dans le dict de retour par défaut (ligne ~1106), ajouter `"participants_damage_updated": 0`
- Dans le dict de retour d'erreur XUID (ligne ~1218), ajouter `"participants_damage_updated": 0`
- Dans le dict de retour d'erreur DB (ligne ~1158), ajouter `"participants_damage_updated": 0`
- Dans le dict de retour dry-run (ligne ~1362), ajouter `"participants_damage_updated": 0`
- Dans le dict de retour "pas de matchs" (ligne ~1395), ajouter `"participants_damage_updated": 0`
- Dans le dict de retour "pas de matchs API" (ligne ~1461), ajouter `"participants_damage_updated": 0`
- Dans le dict de retour "tokens non disponibles" (ligne ~1487), ajouter `"participants_damage_updated": 0`
- Initialiser `total_participants_damage_updated = 0` (ligne ~1523)
- Dans l'appel à `_find_matches_missing_data` (ligne ~1331), ajouter :
  ```python
  participants_damage=participants_damage,
  force_participants_damage=force_participants_damage,
  ```
- Dans la section de traitement des participants (ligne ~1545), ajouter :
  ```python
  participants_damage_this_match = 0
  ```
- Après l'extraction des participants (ligne ~1548), ajouter la mise à jour des dommages :
  ```python
  if participants_damage:
      _ensure_match_participants_columns(conn)
      participant_rows = extract_participants(stats_json)
      for row in participant_rows:
          try:
              if force_participants_damage or (
                  row.damage_dealt is not None or row.damage_taken is not None
              ):
                  conn.execute(
                      """UPDATE match_participants
                         SET damage_dealt = ?, damage_taken = ?
                         WHERE match_id = ? AND xuid = ?""",
                      (
                          row.damage_dealt,
                          row.damage_taken,
                          row.match_id,
                          row.xuid,
                      ),
                  )
                  participants_damage_this_match += 1
          except Exception as e:
              logger.debug(f"Update participant damage {row.xuid}: {e}")
      if participant_rows:
          total_participants_damage_updated += participants_damage_this_match
  ```
- Dans `inserted_this_match` (ligne ~1611), ajouter `"participants_damage": participants_damage_this_match`
- Dans le log des insertions (ligne ~1796), ajouter :
  ```python
  if inserted_this_match.get("participants_damage", 0) > 0:
      parts.append(
          f"{inserted_this_match['participants_damage']} damage participant(s)"
      )
  ```
- Dans le dict de retour final (ligne ~1887), ajouter `"participants_damage_updated": total_participants_damage_updated`

#### 5.5. Fonction `backfill_all_players` (ligne ~1913)

**Modifications** :
- Ajouter les paramètres `participants_damage: bool = False` (ligne ~1930)
- Ajouter les paramètres `force_participants_damage: bool = False` (ligne ~1945)
- Dans `total_results` (ligne ~1956), ajouter `"participants_damage_updated": 0`
- Dans l'appel à `backfill_player_data` (ligne ~1983), ajouter :
  ```python
  participants_damage=participants_damage,
  force_participants_damage=force_participants_damage,
  ```

#### 5.6. Fonction `main` (ligne ~2028)

**Modifications** :
- Ajouter l'argument `--participants-damage` (après `--participants-shots`, ligne ~2195) :
  ```python
  parser.add_argument(
      "--participants-damage",
      action="store_true",
      help="Backfill damage_dealt/damage_taken des participants (matchs où damage manquants)",
  )
  ```
- Ajouter l'argument `--force-participants-damage` (après `--force-participants-shots`, ligne ~2201) :
  ```python
  parser.add_argument(
      "--force-participants-damage",
      action="store_true",
      help="Force la mise à jour de damage_dealt/damage_taken pour tous les participants de tous les matchs",
  )
  ```
- Dans l'appel à `backfill_all_players` (ligne ~2246), ajouter :
  ```python
  participants_damage=args.participants_damage,
  force_participants_damage=args.force_participants_damage,
  ```
- Dans l'appel à `backfill_player_data` (ligne ~2324), ajouter :
  ```python
  participants_damage=args.participants_damage,
  force_participants_damage=args.force_participants_damage,
  ```
- Dans le résumé global (ligne ~2282), ajouter :
  ```python
  if args.participants_damage:
      logger.info(
          f"Damage participants mis à jour: {totals['participants_damage_updated']}"
      )
  ```
- Dans le résumé joueur unique (ligne ~2361), ajouter :
  ```python
  if args.participants_damage:
      logger.info(
          f"Damage participants mis à jour: {result['participants_damage_updated']}"
      )
  ```

#### 5.7. Documentation en-tête (ligne ~1)

**Modifications** :
- Ajouter des exemples d'usage dans la docstring (après la ligne ~52, avant `# Backfill paires killer/victim`) :
  ```python
  # Backfill damage_dealt/damage_taken des participants (matchs où damage manquants)
  python scripts/backfill_data.py --player JGtm --participants-damage

  # Forcer damage pour tous les participants de tous les matchs
  python scripts/backfill_data.py --player JGtm --participants-damage --force-participants-damage
  ```
- Mettre à jour la description de `--all-data` (ligne ~2110) pour inclure `--participants-damage` dans la liste :
  ```python
  parser.add_argument(
      "--all-data",
      action="store_true",
      help="Backfill toutes les données (équivalent à --medals --events --skill --personal-scores --performance-scores --aliases --accuracy --enemy-mmr --assets --participants --shots --participants-scores --participants-kda --participants-shots --participants-damage --killer-victim --end-time --sessions)",
  )
  ```

---

## Ordre d'implémentation recommandé

1. **Modèle de données** (`models.py`) - Base pour tout le reste
2. **Extraction** (`transformers.py`) - Récupération depuis l'API
3. **Schéma DB** (`engine.py`) - Création et migration des colonnes
4. **Insertion sync** (`engine.py`) - Enregistrement lors des syncs
5. **Backfill** (`backfill_data.py`) - Mise à jour des matchs existants

---

## Tests à effectuer

### Test 1 : Extraction depuis l'API
- Vérifier que `extract_participants` retourne bien `damage_dealt` et `damage_taken` pour chaque participant
- Vérifier que les valeurs sont correctement extraites depuis `CoreStats.DamageDealt` et `DamageTaken`

### Test 2 : Création de colonnes
- Vérifier que les colonnes sont créées lors du premier sync
- Vérifier que la migration fonctionne pour les tables existantes

### Test 3 : Insertion lors du sync
- Faire un sync d'un nouveau match et vérifier que les dommages sont enregistrés pour tous les participants

### Test 4 : Backfill
- Tester `--participants-damage` sur un joueur avec des matchs existants
- Vérifier que seuls les matchs avec `damage_dealt IS NULL OR damage_taken IS NULL` sont traités
- Tester `--force-participants-damage` pour forcer la mise à jour de tous les matchs
- Vérifier les logs dans le terminal pour confirmer que les dommages sont bien récupérés et inscrits

### Test 5 : Option `--all`
- Tester `python scripts/backfill_data.py --all --participants-damage`
- Vérifier que tous les joueurs DuckDB v4 sont traités
- Vérifier le résumé global affiche bien les dommages mis à jour

---

## Points d'attention

1. **Compatibilité** : Utiliser `getattr(row, "damage_dealt", None)` pour éviter les erreurs si le modèle n'a pas encore été mis à jour
2. **Type de données** : Utiliser `FLOAT` (comme pour `match_stats`) et non `DOUBLE` ou `INTEGER`
3. **Valeurs NULL** : Gérer correctement les cas où `DamageDealt` ou `DamageTaken` ne sont pas présents dans l'API
4. **Logs** : S'assurer que les logs indiquent clairement le nombre de participants avec dommages mis à jour
5. **Performance** : Le backfill peut être long si beaucoup de matchs, utiliser `--max-matches` pour tester
6. **Option `--all-data`** : ⚠️ **CRITIQUE** - S'assurer que `participants_damage = True` est bien ajouté dans le bloc `if all_data:` (ligne ~1035) pour que `--all-data` inclue automatiquement le backfill des dommages des participants

---

## Références

- Extraction pour le joueur principal : `src/data/sync/transformers.py` ligne ~500-501
- Modèle pour le joueur principal : `src/data/sync/models.py` ligne ~195-196
- Pattern de backfill similaire : `scripts/backfill_data.py` ligne ~938-961 (`participants_shots`)
- Documentation API : `.ai/research/API_REFDATA_FIELDS.md` ligne ~163-164
