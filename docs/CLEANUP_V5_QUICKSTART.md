# Quick Start — Nettoyage Post-Migration v5

> Guide rapide pour nettoyer vos bases de données joueur après migration v5.

---

## 🎯 Objectif

Récupérer **~85% d'espace disque** en supprimant les tables redondantes après migration vers l'architecture shared_matches.

---

## ⚡ Commandes Rapides

### 1️⃣ Simuler d'abord (recommandé)

```bash
python scripts/cleanup_player_dbs_v5.py --dry-run
```

Cela vous montre :
- ✅ Quelles tables seront supprimées
- ✅ Combien d'espace vous allez récupérer
- ✅ Quelles tables seront conservées
- ❌ Aucune modification réelle

### 2️⃣ Nettoyer avec backup (sécurisé)

```bash
# Tous les joueurs avec backup automatique
python scripts/cleanup_player_dbs_v5.py --all --backup
```

Backups créés dans : `backups/v5_cleanup/{gamertag}_{timestamp}.duckdb`

### 3️⃣ Valider

```bash
# Lancer l'app pour vérifier que tout fonctionne
python openspartan_launcher.py run

# Test sync
python scripts/sync.py --delta --gamertag MonGamertag
```

---

## 📊 Exemple de Résultat

```
==============================================================
RÉSUMÉ GLOBAL
==============================================================
Joueurs traités : 4
Espace total libéré : 97,234 KB (-86.2%)
  Avant : 112,845 KB
  Après : 15,611 KB
```

---

## ⚠️ Avant de Commencer

**Vérifiez que shared_matches.duckdb existe :**

```bash
ls -lh data/warehouse/shared_matches.duckdb
```

**Si le fichier n'existe pas**, créez-le d'abord :

```bash
python scripts/migration/create_shared_matches_db.py
python scripts/migration/migrate_player_to_shared.py --all
```

---

## 🆘 En Cas de Problème

### Restaurer un backup

```bash
# Lister les backups
ls backups/v5_cleanup/

# Restaurer
cp backups/v5_cleanup/MonGamertag_20260215_143052.duckdb \
   data/players/MonGamertag/stats.duckdb
```

### Voir les détails

```bash
python scripts/cleanup_player_dbs_v5.py --gamertag MonGamertag --dry-run --verbose
```

---

## 📚 Documentation Complète

- [CLEANUP_V5.md](CLEANUP_V5.md) — Documentation complète du nettoyage
- [MIGRATION_V4_TO_V5.md](MIGRATION_V4_TO_V5.md) — Guide de migration
- [ARCHITECTURE_V5.md](ARCHITECTURE_V5.md) — Architecture v5

---

## ❓ FAQ Rapide

**Q: Est-ce obligatoire ?**  
R: Non. C'est juste pour récupérer de l'espace disque.

**Q: Puis-je annuler ?**  
R: Oui, si vous avez utilisé `--backup`.

**Q: Ça casse quelque chose ?**  
R: Non. Seules les tables redondantes sont supprimées. Les données vitales sont conservées.

**Q: Combien d'espace vais-je récupérer ?**  
R: Environ **85-90%** de la taille de chaque player DB.
