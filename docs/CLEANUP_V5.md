# Guide de Nettoyage Post-Migration v5

> **Date** : 2026-02-15
> **Version** : v5.0.0
> **Script** : `scripts/cleanup_player_dbs_v5.py`

---

## Contexte

Après la migration vers l'architecture v5 (shared matches), certaines données dans les bases de données joueurs (`data/players/{gamertag}/stats.duckdb`) sont **redondantes** car elles existent maintenant dans `shared_matches.duckdb`.

Le script `cleanup_player_dbs_v5.py` vous permet de **récupérer l'espace disque** en supprimant ces tables dupliquées tout en conservant les données personnelles.

### Gains attendus

| Métrique | Avant nettoyage | Après nettoyage | Gain |
|----------|----------------|-----------------|------|
| Taille player DB | ~30 MB | ~2-5 MB | **-85%** |
| Tables par joueur | 12-15 tables | 6-8 tables | **-50%** |

---

## Tables Supprimées vs Conservées

### ❌ Tables SUPPRIMÉES (maintenant dans `shared_matches.duckdb`)

| Table | Raison |
|-------|--------|
| `match_stats` | Remplacée par la sous-requête `_get_match_source()` qui fait un JOIN avec `shared.match_registry` + `shared.match_participants` |
| `match_participants` | Tous les participants sont dans `shared.match_participants` |
| `highlight_events` | Tous les événements sont dans `shared.highlight_events` |
| `medals_earned` | Toutes les médailles sont dans `shared.medals_earned` |

### ✅ Tables CONSERVÉES (données personnelles)

| Table | Raison |
|-------|--------|
| `player_match_enrichment` | Données calculées personnelles : `performance_score`, `session_id`, `is_with_friends` |
| `teammates_aggregate` | Stats coéquipiers du point de vue du joueur |
| `antagonists` | Rivalités (top killers/victimes) |
| `match_citations` | Citations calculées par match |
| `career_progression` | Historique des rangs |
| `media_files` | Fichiers médias du joueur |
| `media_match_associations` | Associations média↔match |
| `sync_meta` | Métadonnées de synchronisation |
| `mv_*` | Vues matérialisées |

### 👁️ Views de Compatibilité (optionnelles)

Pendant la migration, des views de compatibilité ont pu être créées :
- `v_match_stats`
- `v_match_participants`
- `v_highlight_events`
- `v_medals_earned`

Ces views redirigent vers `shared_matches.duckdb`. Elles ne consomment pas d'espace disque mais peuvent être supprimées avec l'option `--remove-compat-views` si vous utilisez déjà `DuckDBRepository` partout.

---

## Prérequis

⚠️ **Avant de nettoyer, assurez-vous que :**

1. ✅ La migration v4 → v5 est complète (voir [MIGRATION_V4_TO_V5.md](MIGRATION_V4_TO_V5.md))
2. ✅ `shared_matches.duckdb` existe et contient vos matchs
3. ✅ Vous avez validé que l'application fonctionne correctement avec v5
4. ✅ (Recommandé) Vous avez un backup récent de vos données

### Vérifier que shared_matches.duckdb existe

```bash
# Vérifier l'existence
ls -lh data/warehouse/shared_matches.duckdb

# Vérifier le contenu
python -c "import duckdb; conn = duckdb.connect('data/warehouse/shared_matches.duckdb'); print(f\"Matchs : {conn.execute('SELECT COUNT(*) FROM match_registry').fetchone()[0]}\"); conn.close()"
```

Si `shared_matches.duckdb` n'existe pas ou est vide, **ne nettoyez pas encore** :

```bash
# Créer la base partagée
python scripts/migration/create_shared_matches_db.py

# Migrer chaque joueur
python scripts/migration/migrate_player_to_shared.py --all
```

---

## Utilisation

### 1. Mode Dry-Run (Recommandé en premier)

**Simuler** le nettoyage sans rien modifier pour voir ce qui serait supprimé :

```bash
# Pour tous les joueurs
python scripts/cleanup_player_dbs_v5.py --all --dry-run

# Ou pour un joueur spécifique
python scripts/cleanup_player_dbs_v5.py --gamertag MonGamertag --dry-run
```

Exemple de sortie :

```
==============================================================
NETTOYAGE PLAYER DBs v5 (DRY-RUN)
==============================================================
Joueurs à traiter : 4
Backup avant nettoyage : Non
Supprimer views compatibilité : Non
==============================================================

📊 Chocoboflor
------------------------------------------------------------
  📁 Taille : 28,456 KB
  📋 Tables à supprimer :
     • match_stats (1243 lignes)
     • match_participants (18645 lignes)
     • highlight_events (8734 lignes)
     • medals_earned (32156 lignes)
  ✓ Tables conservées (8) :
     • player_match_enrichment (1243 lignes)
     • teammates_aggregate (156 lignes)
     • antagonists (45 lignes)
     • match_citations (1243 lignes)
     • career_progression (23 lignes)
  ✓ Tables supprimées : 4
  💾 Espace libéré : 24,321 KB (-85.5%)

[...]

==============================================================
RÉSUMÉ GLOBAL
==============================================================
Joueurs traités : 4
Espace total libéré : 97,234 KB (-86.2%)
  Avant : 112,845 KB
  Après : 15,611 KB

💡 Mode DRY-RUN : aucune modification effectuée
   Pour nettoyer réellement, relancez sans --dry-run
```

### 2. Nettoyer UN joueur spécifique

```bash
# Avec backup (recommandé)
python scripts/cleanup_player_dbs_v5.py --gamertag MonGamertag --backup

# Sans backup (si vous avez déjà sauvegardé)
python scripts/cleanup_player_dbs_v5.py --gamertag MonGamertag
```

### 3. Nettoyer TOUS les joueurs

```bash
# Avec backup de chaque joueur (recommandé)
python scripts/cleanup_player_dbs_v5.py --all --backup

# Sans backup (si vous êtes sûr)
python scripts/cleanup_player_dbs_v5.py --all

# Avec suppression des views de compatibilité
python scripts/cleanup_player_dbs_v5.py --all --backup --remove-compat-views

# Mode verbeux pour voir les détails
python scripts/cleanup_player_dbs_v5.py --all --backup --verbose
```

### 4. Options avancées

```bash
# Analyser un joueur sans nettoyer
python scripts/cleanup_player_dbs_v5.py --gamertag MonGamertag --dry-run --verbose

# Nettoyer avec chemin custom vers shared_matches
python scripts/cleanup_player_dbs_v5.py --all --shared-db /custom/path/shared_matches.duckdb
```

---

## Options du Script

| Option | Description |
|--------|-------------|
| `--gamertag GT` | Nettoyer un joueur spécifique |
| `--all` | Nettoyer tous les joueurs de `db_profiles.json` |
| `--backup` | Créer un backup avant nettoyage (dans `backups/v5_cleanup/`) |
| `--remove-compat-views` | Supprimer aussi les views `v_*` de compatibilité |
| `--dry-run` | Simuler sans modifier les DBs |
| `--verbose`, `-v` | Afficher les détails de chaque DB |
| `--shared-db PATH` | Chemin custom vers `shared_matches.duckdb` |

---

## Vérifications de Sécurité

Le script effectue plusieurs vérifications automatiques :

1. ✅ **Existence de `shared_matches.duckdb`** : Le script refuse de nettoyer si la base partagée n'existe pas
2. ✅ **Validation du contenu** : Vérifie que `shared_matches.duckdb` contient au moins 1 match
3. ✅ **Backup optionnel** : Avec `--backup`, sauvegarde chaque DB dans `backups/v5_cleanup/` avant modification
4. ✅ **Mode dry-run** : Permet de simuler d'abord
5. ✅ **VACUUM automatique** : Récupère l'espace disque après suppression des tables

---

## Que Faire Après le Nettoyage

### 1. Valider l'Application

```bash
# Lancer l'application
python openspartan_launcher.py run
```

Vérifier que :
- [ ] Les stats s'affichent correctement
- [ ] Les graphiques fonctionnent
- [ ] Les médailles sont visibles
- [ ] Les coéquipiers apparaissent
- [ ] Aucune erreur dans les logs

### 2. Tester la Synchronisation

```bash
# Sync delta pour vérifier que tout fonctionne
python scripts/sync.py --delta --gamertag MonGamertag
```

### 3. Nettoyer les Backups (Optionnel)

Si tout fonctionne bien après quelques jours, vous pouvez supprimer les backups :

```bash
# Lister les backups créés
ls -lh backups/v5_cleanup/

# Supprimer un backup spécifique
rm backups/v5_cleanup/MonGamertag_20260215_143052.duckdb

# Supprimer tous les backups v5_cleanup (attention !)
rm -r backups/v5_cleanup/
```

---

## Rollback

Si vous avez utilisé `--backup` et que quelque chose ne fonctionne pas :

```bash
# Lister les backups disponibles
ls -lh backups/v5_cleanup/

# Restaurer un joueur
cp backups/v5_cleanup/MonGamertag_20260215_143052.duckdb data/players/MonGamertag/stats.duckdb
```

Sans backup, vous pouvez restaurer depuis :
1. Un backup global créé avant migration (voir [BACKUP_RESTORE.md](BACKUP_RESTORE.md))
2. Les archives Parquet (si elles existent) — nécessite une réimportation complète

---

## FAQ

### Q: Est-ce obligatoire de nettoyer ?

**R:** Non. Le fonctionnement de l'application n'est pas affecté par les tables redondantes. Le nettoyage sert uniquement à **récupérer de l'espace disque**.

Si vous avez assez d'espace, vous pouvez garder ces tables indéfiniment.

---

### Q: Puis-je nettoyer un joueur à la fois ?

**R:** Oui, c'est même recommandé pour tester :

```bash
# Nettoyer le premier joueur avec backup
python scripts/cleanup_player_dbs_v5.py --gamertag Joueur1 --backup

# Valider que tout fonctionne
python openspartan_launcher.py run

# Nettoyer les autres
python scripts/cleanup_player_dbs_v5.py --all --backup
```

---

### Q: Les views `v_*` sont-elles utiles ?

**R:** Non, si vous utilisez exclusivement `DuckDBRepository` (cas normal depuis v5). Ces views ont été créées pendant la migration pour la compatibilité transitoire.

Vous pouvez les supprimer avec `--remove-compat-views`.

---

### Q: Que se passe-t-il si je nettoie avant d'avoir migré ?

**R:** Le script refuse de s'exécuter si `shared_matches.duckdb` n'existe pas ou est vide :

```
❌ shared_matches.duckdb introuvable : data/warehouse/shared_matches.duckdb
   Vous devez d'abord créer la base partagée avec :
   python scripts/migration/create_shared_matches_db.py
```

---

### Q: Combien d'espace vais-je récupérer ?

**R:** Environ **85-90%** de la taille de chaque player DB. Exemple :

| Joueur | Avant | Après | Gain |
|--------|-------|-------|------|
| Chocoboflor | 28 MB | 3 MB | -89% |
| JGtm | 32 MB | 4 MB | -87% |
| Madina97294 | 25 MB | 3 MB | -88% |
| XxDaemonGamerxX | 2 MB | 0.5 MB | -75% |

**Total** : -86% en moyenne.

---

### Q: Puis-je re-créer les tables supprimées ?

**R:** Non. Les tables `match_stats`, `match_participants`, etc. ne sont plus utilisées en v5. Si vous avez besoin de ces données, elles sont dans `shared_matches.duckdb` et accessibles via `DuckDBRepository`.

Si vous avez supprimé par erreur, restaurez depuis un backup.

---

### Q: Le nettoyage affecte-t-il `shared_matches.duckdb` ?

**R:** **Non**. Le script ne touche **jamais** à `shared_matches.duckdb`, uniquement aux bases joueurs individuelles.

---

## Voir Aussi

- [MIGRATION_V4_TO_V5.md](MIGRATION_V4_TO_V5.md) — Guide de migration complet
- [ARCHITECTURE_V5.md](ARCHITECTURE_V5.md) — Architecture v5 détaillée
- [BACKUP_RESTORE.md](BACKUP_RESTORE.md) — Backup et restauration
- [SHARED_MATCHES_SCHEMA.md](SHARED_MATCHES_SCHEMA.md) — Schéma de `shared_matches.duckdb`

---

## Support

En cas de problème :

1. **Vérifier les logs** : Le script affiche des messages détaillés
2. **Utiliser `--dry-run --verbose`** : Pour diagnostiquer
3. **Restaurer un backup** : Si quelque chose ne fonctionne plus
4. **Consulter les docs** : Voir section "Voir Aussi" ci-dessus

**Important** : Si vous avez un doute, utilisez **toujours** `--backup` ou faites un backup manuel avant de nettoyer.
