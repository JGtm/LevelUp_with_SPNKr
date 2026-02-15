# FAQ - Questions Fréquentes

> Réponses aux questions les plus courantes sur LevelUp.

## Installation

### Q: Quelle version de Python est requise ?

**R:** Python 3.10 ou supérieur. Nous recommandons Python 3.11 ou 3.12 pour les meilleures performances.

### Q: L'installation échoue avec une erreur pip

**R:** Essayez de mettre à jour pip :
```bash
pip install --upgrade pip
pip install -e .
```

### Q: Comment installer sur Linux/macOS ?

**R:** Le processus est identique, seule l'activation de l'environnement change :
```bash
source .venv/bin/activate
```

---

## Configuration

### Q: Comment obtenir mon XUID ?

**R:** Plusieurs méthodes :
1. Via le dashboard dans les paramètres
2. Sur des sites comme xboxgamertag.com
3. Lors de la première synchronisation

### Q: Mes tokens Azure expirent, comment les renouveler ?

**R:** Exécutez le script de récupération :
```bash
python scripts/spnkr_get_refresh_token.py
```

### Q: Comment ajouter un nouveau joueur ?

**R:** 
1. Créez le dossier : `mkdir -p data/players/NomJoueur`
2. Ajoutez le profil dans `db_profiles.json`
3. Synchronisez : `python scripts/sync.py --gamertag NomJoueur --full`

---

## Synchronisation

### Q: Quelle différence entre --delta et --full ?

**R:**
- `--delta` : Ne récupère que les nouveaux matchs depuis la dernière sync (rapide)
- `--full` : Récupère tous les matchs jusqu'à la limite spécifiée (complet)

### Q: La sync est lente, comment l'accélérer ?

**R:** 
- Utilisez `--delta` pour les syncs quotidiennes
- Limitez les matchs avec `--max-matches 100`
- Évitez `--with-assets` si pas nécessaire

### Q: Erreur "Rate limit exceeded"

**R:** L'API Halo a des limites. Attendez quelques minutes et réessayez avec un `--max-matches` plus faible.

---

## Dashboard

### Q: Le dashboard ne se lance pas

**R:** Vérifiez :
1. L'environnement virtuel est activé
2. Les dépendances sont installées
3. Essayez : `streamlit run streamlit_app.py`

### Q: Les graphiques ne s'affichent pas

**R:** Videz le cache Streamlit :
```bash
streamlit cache clear
```

### Q: Comment changer de joueur dans l'interface ?

**R:** Utilisez le sélecteur dans la sidebar, ou modifiez `is_default` dans `db_profiles.json`.

---

## Données

### Q: Où sont stockées mes données ?

**R:** Dans le dossier `data/` :
```
data/
├── players/MonGamertag/stats.duckdb  # Vos matchs
└── warehouse/metadata.duckdb         # Référentiels
```

### Q: Comment sauvegarder mes données ?

**R:** Utilisez le script de backup :
```bash
python scripts/backup_player.py --gamertag MonGamertag
```

### Q: Puis-je importer des données depuis Halo Tracker ?

**R:** Non, LevelUp utilise l'API officielle via SPNKr. Les données de sites tiers ne sont pas compatibles.

---

## Performance

### Q: Le dashboard est lent

**R:** Plusieurs optimisations possibles :
1. Vérifiez que les vues matérialisées sont à jour
2. Utilisez la pagination dans l'historique
3. Limitez les filtres de dates

### Q: Comment rafraîchir les vues matérialisées ?

**R:** Elles sont automatiquement rafraîchies après chaque sync. Sinon :
```bash
python scripts/sync.py --gamertag MonGamertag --refresh-views
```

### Q: Combien de matchs puis-je stocker ?

**R:** Il n'y a pas de limite théorique. Des joueurs avec 10 000+ matchs fonctionnent sans problème grâce au lazy loading.

---

## Migration

### Q: Je viens d'une ancienne version (SQLite), comment migrer ?

**R:** Exécutez les scripts de migration :
```bash
python scripts/migrate_metadata_to_duckdb.py
python scripts/migrate_player_to_duckdb.py --all
```

### Q: Puis-je revenir à l'ancienne version ?

**R:** Oui, les anciennes DBs SQLite sont conservées. Mais nous recommandons DuckDB pour les performances.

---

## Développement

### Q: Comment contribuer au projet ?

**R:** Voir [CONTRIBUTING.md](../CONTRIBUTING.md) pour les guidelines.

### Q: Comment lancer les tests ?

**R:**
```bash
pytest
pytest --cov=src  # Avec couverture
```

### Q: Comment reporter un bug ?

**R:** Ouvrez une issue sur GitHub avec :
1. Version de Python et OS
2. Message d'erreur complet
3. Étapes pour reproduire

---

## Divers

### Q: LevelUp collecte-t-il des données ?

**R:** Non. Toutes les données restent sur votre machine. Aucune télémétrie n'est envoyée.

### Q: Puis-je utiliser LevelUp avec Halo 5 ?

**R:** Non, LevelUp est conçu pour Halo Infinite uniquement. Les endpoints API sont différents.

### Q: Le projet est-il affilié à 343 Industries ou Microsoft ?

**R:** Non. LevelUp est un projet communautaire non-officiel.
