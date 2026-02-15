# Guide de Migration v4 → v5

> **Date** : 2026-02-15
> **Public cible** : Utilisateurs LevelUp existants migrant depuis v4.x vers v5.0

---

## Prérequis

- **Python** : 3.12+ (recommandé 3.12.10)
- **LevelUp v4.x** fonctionnel avec données existantes
- **Espace disque** : ~500 MB disponibles pour la migration (temporaire)
- **Backup** : Obligatoire avant migration (voir ci-dessous)

---

## 1. Backup (OBLIGATOIRE)

⚠️ **La migration est irréversible sans backup.**

```bash
# Backup de tous les joueurs
python scripts/backup_player.py --gamertag MonGamertag

# Ou backup complet
cp -r data/players data/players_backup_v4
cp data/warehouse/metadata.duckdb data/warehouse/metadata_backup_v4.duckdb
```

---

## 2. Mise à jour du code

```bash
# Récupérer la version v5.0.0
git fetch origin
git checkout v5.0.0

# Mettre à jour les dépendances
pip install -e .
```

---

## 3. Créer la base partagée

```bash
# Créer shared_matches.duckdb avec le schéma v5
python scripts/migration/create_shared_matches_db.py
```

Cette commande crée `data/warehouse/shared_matches.duckdb` avec les tables :
- `match_registry` — Registre central de matchs
- `match_participants` — Stats de tous les joueurs
- `highlight_events` — Événements filmés
- `medals_earned` — Médailles
- `xuid_aliases` — Mapping xuid→gamertag
- `schema_version` — Versioning

---

## 4. Migrer chaque joueur

```bash
# Migrer un joueur à la fois
python scripts/migration/migrate_player_to_shared.py --gamertag MonGamertag

# Répéter pour chaque joueur
python scripts/migration/migrate_player_to_shared.py --gamertag AutreJoueur
```

Le script :
1. Lit les données du joueur depuis `data/players/{gamertag}/stats.duckdb`
2. Copie les matchs, participants, events et médailles vers `shared_matches.duckdb`
3. Déduplique automatiquement les matchs déjà présents (partagés avec un autre joueur)
4. Crée la table `player_match_enrichment` dans la player DB

---

## 5. Supprimer les VIEWs de compatibilité (optionnel)

Si vous aviez des VIEWs de compatibilité créées pendant la migration :

```bash
python scripts/migration/remove_compat_views.py --gamertag MonGamertag
```

---

## 6. Valider la migration

```bash
# Vérifier l'intégrité des données migrées
python scripts/validate_migration.py

# Lancer l'application pour vérifier
python openspartan_launcher.py run
```

### Points de validation

- [ ] Le dashboard se lance sans erreur
- [ ] Les stats du joueur sont identiques à la v4
- [ ] Les médailles s'affichent correctement
- [ ] Les coéquipiers sont visibles
- [ ] La synchronisation fonctionne (test avec `--delta`)

---

## 7. Backfill (optionnel)

Après migration, certaines données enrichies peuvent nécessiter un recalcul :

```bash
# Recalculer les sessions
python scripts/backfill_data.py --player MonGamertag --sessions

# Recalculer les citations
python scripts/backfill_data.py --player MonGamertag --citations

# Recalculer les shots (si manquants)
python scripts/backfill_data.py --player MonGamertag --shots
```

---

## Ce qui change pour l'utilisateur

### Sync plus rapide

La synchronisation détecte désormais les matchs déjà connus dans `shared_matches.duckdb`.
Pour un match partagé entre 4 joueurs, seul le premier joueur déclenche la sync complète.
Les suivants ne font qu'un enrichissement personnel (performance_score, session_id).

```bash
# Même commande qu'avant
python scripts/sync.py --delta --gamertag MonGamertag
```

### Aucun changement dans l'UI

L'interface Streamlit est identique. Toutes les pages fonctionnent de manière transparente
grâce à la sous-requête `_get_match_source()` qui abstrait la jointure entre les bases.

### Backup/Restore

Les commandes de backup/restore fonctionnent toujours :

```bash
python scripts/backup_player.py --gamertag MonGamertag
python scripts/restore_player.py --gamertag MonGamertag --backup ./backups/MonGamertag
```

---

## Différences techniques

| Aspect | v4 | v5 |
|--------|----|----|
| `match_stats` | Table dans player DB | Sous-requête JOIN shared |
| `medals_earned` | Table dans player DB | Table dans `shared_matches.duckdb` |
| `highlight_events` | Table dans player DB | Table dans `shared_matches.duckdb` |
| Sync d'un match connu | 3-4 appels API | 0 appel API (enrichissement local) |
| Stockage par joueur | ~200 MB | ~30 MB |

---

## Rollback

En cas de problème, restaurer les backups créés à l'étape 1 :

```bash
# Restaurer les player DBs
cp -r data/players_backup_v4/* data/players/

# Restaurer metadata
cp data/warehouse/metadata_backup_v4.duckdb data/warehouse/metadata.duckdb

# Supprimer la base partagée
rm data/warehouse/shared_matches.duckdb

# Revenir au code v4
git checkout v4.5.0
```

---

## FAQ Migration

### Q: Mes données sont-elles en sécurité ?
R: Oui, la migration ne supprime rien de la player DB. Elle copie les données vers shared_matches.duckdb.

### Q: Que se passe-t-il si je n'ai qu'un seul joueur ?
R: La migration fonctionne normalement. Vous bénéficierez des gains de sync dès que vous ajouterez un deuxième joueur partageant des matchs.

### Q: Puis-je migrer un joueur à la fois ?
R: Oui, c'est même recommandé. Le script gère la déduplication automatiquement.

### Q: L'ancienne sync v4 fonctionne-t-elle encore ?
R: Non, la v5 nécessite `shared_matches.duckdb`. Créez la base partagée (étape 3) avant toute sync.

---

## Voir aussi

- [ARCHITECTURE_V5.md](ARCHITECTURE_V5.md) — Architecture v5 détaillée
- [SHARED_MATCHES_SCHEMA.md](SHARED_MATCHES_SCHEMA.md) — Schéma DDL complet
- [SYNC_OPTIMIZATIONS_V5.md](SYNC_OPTIMIZATIONS_V5.md) — Optimisations sync
- [BACKUP_RESTORE.md](BACKUP_RESTORE.md) — Backup et restauration
