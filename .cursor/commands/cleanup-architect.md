# Commande /cleanup-architect

Agent expert en revue de code spécialisé dans le cleaning, l'architecture et la gestion du code legacy.

**Protocole complet** : `.cursor/rules/code-cleanup-architect.md`

## Usage

```bash
/cleanup-architect                    # Analyse fichiers modifiés récemment
/cleanup-architect --full             # Audit complet de tous les fichiers
/cleanup-architect src/data/          # Analyse répertoire spécifique
/cleanup-architect --auto-fix         # Détection + correction automatique
/cleanup-architect --legacy           # Focus sur code legacy uniquement
/cleanup-architect --dead-code        # Focus sur code mort uniquement
```

## Domaines d'Expertise

### 1. Fichiers et Dossiers Inutiles (Prioritaire)
- **Fichiers Python jamais importés** (analyse complète des imports)
- **Dossiers entiers inutiles** (vides ou contenant uniquement fichiers morts)
- **Fichiers dans dossiers legacy/old/deprecated** sans usage actif
- **Fichiers de migration temporaires** passés date limite
- **Modules dépréciés** listés dans CLAUDE.md avec 0 usages

### 2. Code Mort
- Fonctions/méthodes jamais appelées
- Classes jamais instanciées
- Imports inutilisés
- Code inaccessible (après return, conditions toujours fausses)
- Constantes jamais référencées

### 2. Architecture
- Violations de structure de dossiers
- Dépendances circulaires
- Couplage excessif
- Non-respect patterns LevelUp (DuckDBRepository, Polars, etc.)

### 3. Code Legacy
- Modules dépréciés (loaders.py, etc.)
- Code marqué LEGACY/DEPRECATED
- Patterns obsolètes à migrer

### 4. Duplication
- Code identique dans plusieurs fichiers
- Constantes dupliquées
- Patterns répétés

## Étapes d'Analyse

### 1. Collecte du Contexte
```bash
# Lire fichiers de référence
- CLAUDE.md
- .ai/project_map.md
- .ai/data_lineage.md
- docs/DATA_ARCHITECTURE.md
- .cursor/rules/code-cleanup-architect.md
```

### 2. Détection Fichiers et Dossiers Inutiles (Prioritaire)
```bash
# Pour chaque fichier Python, vérifier s'il est importé
# Script d'analyse complète (voir règles pour détails)

# Détecter dossiers suspects
find . -type d \( -name "legacy" -o -name "old" -o -name "deprecated" \)

# Vérifier modules dépréciés LevelUp
grep -r "from src.db.loaders" --include="*.py"  # Si 0 → fichier inutile
```

### 3. Détection Code Mort
```bash
# Analyse statique
grep -r "function_name(" --include="*.py" | grep -v "def function_name"
ruff check --select F401  # Imports inutilisés
```

### 4. Analyse Architecturale
- Vérifier structure dossiers vs `.ai/project_map.md`
- Détecter dépendances circulaires
- Vérifier conformité patterns LevelUp

### 5. Identification Legacy
- Chercher modules listés dans CLAUDE.md comme dépréciés
- Détecter usages de patterns obsolètes
- Vérifier fichiers dans dossiers legacy/

### 6. Détection Duplication
- Rechercher code identique > 5 lignes
- Identifier constantes dupliquées

## Rapport de Sortie

Générer `.ai/cleanup_report.md` avec format structuré :

```markdown
# Code Cleanup & Architecture Review - [DATE]

## Fichiers et Dossiers Inutiles 🔴 (Prioritaire)
- [fichier/dossier] Description + Vérification + Action (Supprimer)

## Code Mort Détecté 🔴
- [fichier:ligne] Description + Action recommandée

## Violations Architecturales 🟠
- [fichier:ligne] Description + Impact

## Code Legacy Identifié 🟡
- [fichier] Raison + Plan migration

## Duplication Détectée 🟡
- [fichiers] Description + Solution

## Recommandations
- Actions immédiates (suppression fichiers/dossiers inutiles)
- Actions planifiées
- Métriques (fichiers/dossiers, code mort, etc.)
```

## Intégration avec Autres Commandes

- **Avant** `/review` : Exécuter `/cleanup-architect` pour nettoyer code mort évident
- **Après** migration : `/cleanup-architect --legacy` pour vérifier nettoyage
- **Mensuel** : `/cleanup-architect --full` pour audit complet

## Checklist de Sortie

- [ ] Contexte architectural lu (project_map, data_lineage)
- [ ] **Fichiers et dossiers inutiles identifiés** avec preuves (analyse imports)
- [ ] Code mort identifié avec preuves (grep)
- [ ] Violations architecturales documentées
- [ ] Legacy catalogué avec plan migration
- [ ] Duplication détectée avec solution
- [ ] Rapport généré dans `.ai/cleanup_report.md`
- [ ] Actions prioritaires identifiées (suppression fichiers/dossiers en premier)

---

## Exemples Concrets

### Détection Fichiers/Dossiers Inutiles

```bash
# ❌ PROBLÈME DÉTECTÉ
# Fichier src/db/loaders.py existe mais :
grep -r "from src.db.loaders" --include="*.py" .
# Résultat: 0 occurrences → fichier inutile

# ✅ SOLUTION
# Supprimer le fichier car remplacé par DuckDBRepository
rm src/db/loaders.py

# ❌ PROBLÈME DÉTECTÉ
# Dossier legacy/ contient uniquement fichiers non référencés
find legacy/ -name "*.py" -exec basename {} \;
# Vérifier chaque fichier → tous inutilisés

# ✅ SOLUTION
# Supprimer le dossier entier après vérification
rm -rf legacy/
```

### Détection Code Mort
```python
# ❌ PROBLÈME
def old_helper():
    return "deprecated"

# ✅ SOLUTION
# Supprimer si vraiment inutilisé
# OU marquer # LEGACY: utilisé par script X
```

### Violation Architecturale
```python
# ❌ PROBLÈME
import sqlite3
conn = sqlite3.connect("data/players/user/stats.duckdb")

# ✅ SOLUTION
from src.data.repositories import DuckDBRepository
repo = DuckDBRepository(db_path, xuid)
```

### Legacy à Migrer
```python
# ❌ PROBLÈME
from src.db.loaders import load_matches  # Déprécié

# ✅ SOLUTION
from src.data.repositories import DuckDBRepository
repo = DuckDBRepository(db_path, xuid)
matches = repo.load_matches(limit=100)
```
