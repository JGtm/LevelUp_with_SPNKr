# Commandes Utiles — LevelUp

> Aide-mémoire des commandes les plus fréquentes.

---

## 🚀 Lancement

```bash
# Lancer le dashboard
python openspartan_launcher.py run

# Lancer en mode debug
streamlit run streamlit_app.py --server.runOnSave true
```

---

## 🔄 Synchronisation

```bash
# Sync delta (nouveaux matchs uniquement)
python scripts/sync.py --delta --gamertag MonGamertag

# Sync complète (tous les matchs)
python scripts/sync.py --full --gamertag MonGamertag

# Sync limitée (100 derniers matchs)
python scripts/sync.py --full --gamertag MonGamertag --max-matches 100

# Sync tous les joueurs
python scripts/sync.py --all
```

---

## 🗄️ Migration v4 → v5

```bash
# 1. Créer la base partagée
python scripts/migration/create_shared_matches_db.py

# 2. Migrer un joueur
python scripts/migration/migrate_player_to_shared.py --gamertag MonGamertag

# 3. Migrer tous les joueurs
python scripts/migration/migrate_player_to_shared.py --all

# 4. Valider la migration
python scripts/validate_migration.py
```

---

## 🧹 Nettoyage post-migration v5

```bash
# Simuler d'abord (recommandé)
python scripts/cleanup_player_dbs_v5.py --dry-run

# Nettoyer un joueur avec backup
python scripts/cleanup_player_dbs_v5.py --gamertag MonGamertag --backup

# Nettoyer tous les joueurs avec backup
python scripts/cleanup_player_dbs_v5.py --all --backup

# Supprimer aussi les views de compatibilité
python scripts/cleanup_player_dbs_v5.py --all --backup --remove-compat-views

# Voir les détails
python scripts/cleanup_player_dbs_v5.py --gamertag MonGamertag --dry-run --verbose
```

**Gain typique** : -85% de taille par player DB

---

## 🔧 Backfill

```bash
# Recalculer les sessions
python scripts/backfill_data.py --player MonGamertag --sessions

# Recalculer les citations
python scripts/backfill_data.py --player MonGamertag --citations

# Recalculer les shots (si manquants)
python scripts/backfill_data.py --player MonGamertag --shots

# Backfill tous les joueurs
python scripts/backfill_data.py --all --sessions --citations
```

---

## 💾 Backup & Restore

```bash
# Backup d'un joueur
python scripts/backup_player.py --gamertag MonGamertag

# Backup de tous les joueurs
python scripts/backup_player.py --all

# Restore depuis un backup
python scripts/restore_player.py --gamertag MonGamertag --backup ./backups/MonGamertag_20260215.tar.gz
```

---

## 🧪 Tests

```bash
# Suite complète
python -m pytest

# Suite stable (recommandé)
python -m pytest -q --ignore=tests/integration

# Avec couverture
python -m pytest --cov=src --cov-report=html

# Tests spécifiques
python -m pytest tests/test_duckdb_repository.py -v

# E2E navigateur (optionnel)
python -m pytest tests/e2e/test_streamlit_browser_e2e.py -v --run-e2e-browser
```

---

## 🔍 Diagnostic

```bash
# Vérifier l'environnement Python
python scripts/check_env.py

# Diagnostiquer une player DB
python scripts/diagnose_player_db.py --gamertag MonGamertag

# Diagnostiquer les citations
python scripts/diagnose_citations.py --gamertag MonGamertag

# Auditer les données actuelles
python scripts/audit_current_data.py
```

---

## 📊 Analyse

```bash
# Analyser les overlaps de matchs entre joueurs
python scripts/analyze_match_overlap.py

# Compter les citations affichées
python scripts/count_displayed_citations.py --gamertag MonGamertag

# Benchmark des pages UI
python scripts/benchmark_pages.py
```

---

## 🛠️ Maintenance

```bash
# Nettoyer les rank dans player assets (legacy)
python scripts/cleanup_rank_from_player_assets.py

# Exporter les schémas SQL
python scripts/export_schemas.py

# Générer les thumbnails médias
python scripts/generate_thumbnails.py --gamertag MonGamertag

# Indexer les médias
python scripts/index_media.py --gamertag MonGamertag
```

---

## 🗂️ Chemins Importants

```
data/
├── warehouse/
│   ├── metadata.duckdb            # Référentiels (maps, playlists, medals)
│   └── shared_matches.duckdb      # Base partagée (v5)
├── players/
│   └── {gamertag}/
│       ├── stats.duckdb           # Stats personnelles
│       └── archive/               # Archives Parquet
└── cache/                         # Thumbnails

db_profiles.json                   # Profils joueurs
app_settings.json                  # Paramètres app
.env.local                         # Tokens Azure
```

---

## 📚 Documentation

| Document | Lien |
|----------|------|
| Installation | [docs/INSTALL.md](docs/INSTALL.md) |
| Architecture v5 | [docs/ARCHITECTURE_V5.md](docs/ARCHITECTURE_V5.md) |
| Migration v5 | [docs/MIGRATION_V4_TO_V5.md](docs/MIGRATION_V4_TO_V5.md) |
| Nettoyage v5 | [docs/CLEANUP_V5.md](docs/CLEANUP_V5.md) |
| Synchronisation | [docs/SYNC_GUIDE.md](docs/SYNC_GUIDE.md) |
| Backup/Restore | [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md) |
| FAQ | [docs/FAQ.md](docs/FAQ.md) |

---

## 🆘 En Cas de Problème

1. **Vérifier l'environnement** : `python scripts/check_env.py`
2. **Consulter les logs** : `tail -f logs/levelup.log`
3. **Restaurer un backup** : `python scripts/restore_player.py ...`
4. **Lire la FAQ** : [docs/FAQ.md](docs/FAQ.md)
5. **Ouvrir une issue** : [GitHub Issues](https://github.com/JGtm/LevelUp_with_SPNKr/issues)
