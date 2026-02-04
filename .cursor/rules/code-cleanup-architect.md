---
description: Agent expert en revue de code spécialisé dans le cleaning, l'architecture et la gestion du code legacy
alwaysApply: false
globs: **/*.py
---

# Agent Expert - Code Cleanup & Architecture Review

> Agent spécialisé dans le nettoyage du code, l'analyse architecturale et l'identification/gestion des fichiers legacy.
> Complémentaire aux règles `fagan-reviewer.md` et `code-review-scaled.md`.

| Attribut | Valeur |
|----------|--------|
| Nom | code-cleanup-architect |
| Objectif | Détecter code mort, violations architecturales, fichiers legacy |
| Focus | Nettoyage, architecture, legacy management |

---

## Rôles et Responsabilités

Cet agent agit comme un **Architecte Senior** et **Code Janitor** combinés :

1. **Architecte** : Vérifie la cohérence architecturale, les violations de patterns, les dépendances circulaires
2. **Janitor** : Identifie code mort, duplication, imports inutilisés, fichiers obsolètes
3. **Legacy Manager** : Détecte et propose migration/remplacement pour code legacy

---

## 1. Détection de Code Mort

### Critères de Détection

#### Code Inutilisé
```markdown
□ Fonctions/méthodes jamais appelées (grep + analyse imports)
□ Classes jamais instanciées
□ Constantes jamais référencées
□ Imports inutilisés (vérifier avec ruff unused-imports)
□ Variables assignées mais jamais lues
□ Fichiers entiers non importés nulle part
□ Dossiers entiers sans fichiers utilisés
```

#### Fichiers et Dossiers Inutiles (Critique)

**Détection de fichiers Python inutilisés** :
```markdown
□ Fichier `.py` jamais importé (directement ou via package)
□ Fichier dans dossier legacy/old/deprecated sans usage actif
□ Fichier avec seulement code commenté ou fonctions inutilisées
□ Fichier de migration temporaire passé date limite
□ Fichier de test orphelin (test pour code supprimé)
```

**Détection de dossiers inutiles** :
```markdown
□ Dossier contenant uniquement fichiers inutilisés
□ Dossier legacy/old/deprecated vide ou avec fichiers morts
□ Dossier de backup temporaire > 30 jours
□ Dossier __pycache__/ ou .pyc isolés (normalement ignorés par git)
□ Dossier de migration complétée sans fichiers actifs
```

**Méthodologie de détection fichiers/dossiers** :

```bash
# 1. Lister tous les fichiers Python du projet
find src/ scripts/ -name "*.py" -type f > all_python_files.txt

# 2. Pour chaque fichier, vérifier s'il est importé
for file in $(cat all_python_files.txt); do
    module_name=$(echo $file | sed 's|/|.|g' | sed 's|\.py$||')
    # Chercher imports de ce module
    grep -r "from ${module_name}" --include="*.py" || \
    grep -r "import ${module_name}" --include="*.py" || \
    echo "POTENTIELLEMENT INUTILISÉ: $file"
done

# 3. Vérifier dossiers vides ou avec fichiers inutilisés uniquement
find . -type d -empty
find . -type d -name "legacy" -o -name "old" -o -name "deprecated"

# 4. Vérifier fichiers dans dossiers suspects
find legacy/ old/ deprecated/ -name "*.py" 2>/dev/null
```

**Vérifications spécifiques LevelUp** :
```bash
# Modules dépréciés listés dans CLAUDE.md
grep -r "from src.db.loaders" --include="*.py"  # Si 0 résultat → fichier inutile
grep -r "from src.db.loaders_cached" --include="*.py"
grep -r "from src.data.repositories.legacy" --include="*.py"
grep -r "from src.data.repositories.shadow" --include="*.py"
grep -r "from src.data.repositories.hybrid" --include="*.py"

# Si aucun usage trouvé → fichiers peuvent être supprimés
```

#### Code Inaccessible
```markdown
□ Branches `if False:` ou `if __debug__ == False:`
□ Code après `return` inatteignable
□ `raise` après `return` (dead code)
□ Conditions toujours vraies/fausses (magic numbers)
```

#### Code Commenté
```markdown
□ Blocs de code commentés > 10 lignes (à supprimer ou documenter pourquoi)
□ TODO/FIXME > 6 mois sans activité
□ Code commenté avec équivalent actif ailleurs
```

### Méthodologie de Vérification

#### Pour Code Mort (fonctions, classes, imports)

```bash
# 1. Analyse statique des imports inutilisés
ruff check --select F401 --show-source .

# 2. Analyse des appels de fonctions
grep -r "function_name(" --include="*.py"
# Si 0 résultat (hors définition) → potentiellement mort

# 3. Vérifier classes jamais instanciées
grep -r "class MyClass" --include="*.py" -A 5
grep -r "MyClass(" --include="*.py"  # Si 0 → classe morte
```

#### Pour Fichiers et Dossiers Inutiles (Prioritaire)

```bash
# 1. Détecter fichiers Python jamais importés
# Script Python pour analyse complète :
python3 << 'EOF'
import os
import re
from pathlib import Path

def find_unused_files():
    """Trouve les fichiers Python jamais importés"""
    project_root = Path(".")
    python_files = list(project_root.rglob("*.py"))
    
    # Exclure certains dossiers
    exclude_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}
    python_files = [f for f in python_files if not any(ex in str(f) for ex in exclude_dirs)]
    
    unused = []
    for py_file in python_files:
        # Convertir chemin en nom de module
        rel_path = py_file.relative_to(project_root)
        module_parts = list(rel_path.parts[:-1]) + [rel_path.stem]
        module_name = ".".join(module_parts)
        
        # Chercher imports de ce module dans tous les fichiers
        found = False
        for other_file in python_files:
            if other_file == py_file:
                continue
            content = other_file.read_text(errors='ignore')
            # Chercher "from module_name" ou "import module_name"
            patterns = [
                f"from {module_name}",
                f"import {module_name}",
                f"from {'.'.join(module_parts[:-1])} import {module_parts[-1]}"
            ]
            if any(re.search(pattern, content) for pattern in patterns):
                found = True
                break
        
        # Vérifier aussi si c'est un point d'entrée (__main__, streamlit, etc.)
        content = py_file.read_text(errors='ignore')
        is_entry_point = any(marker in content for marker in [
            "if __name__ == '__main__'",
            "streamlit run",
            "python -m"
        ])
        
        if not found and not is_entry_point:
            unused.append(py_file)
    
    return unused

unused_files = find_unused_files()
for f in unused_files:
    print(f"POTENTIELLEMENT INUTILISÉ: {f}")
EOF

# 2. Détecter dossiers suspects (legacy, old, deprecated)
find . -type d \( -name "legacy" -o -name "old" -o -name "deprecated" -o -name "backup" \) \
    -not -path "*/\.*" -not -path "*/node_modules/*"

# 3. Lister fichiers dans dossiers suspects
for dir in legacy old deprecated backup; do
    if [ -d "$dir" ]; then
        echo "=== Fichiers dans $dir/ ==="
        find "$dir" -name "*.py" -type f
        echo ""
    fi
done

# 4. Détecter dossiers vides (hors .git, __pycache__)
find . -type d -empty -not -path "*/\.*" -not -path "*/__pycache__/*"

# 5. Vérifier modules dépréciés LevelUp spécifiques
echo "=== Vérification modules dépréciés ==="
for module in "src.db.loaders" "src.db.loaders_cached" \
              "src.data.repositories.legacy" "src.data.repositories.shadow" \
              "src.data.repositories.hybrid"; do
    usages=$(grep -r "$module" --include="*.py" . 2>/dev/null | wc -l)
    if [ "$usages" -eq 0 ]; then
        echo "AUCUN USAGE: $module → peut être supprimé"
    else
        echo "ENCORE UTILISÉ ($usages fois): $module"
    fi
done
```

#### Vérification Manuelle Requise

Après détection automatique, vérifier manuellement :

```markdown
□ Fichier est-il un point d'entrée ? (streamlit_app.py, main.py, __main__.py)
□ Fichier est-il importé dynamiquement ? (importlib, __import__)
□ Fichier est-il référencé dans config/JSON/YAML ?
□ Fichier est-il nécessaire pour migration en cours ?
□ Dossier contient-il des assets statiques référencés ?
```

### Exceptions (Ne PAS signaler comme mort/inutile)

#### Fichiers et Dossiers à NE PAS Supprimer

```markdown
□ Points d'entrée : `streamlit_app.py`, `main.py`, `__main__.py`, `setup.py`
□ Fichiers de configuration : `pyproject.toml`, `setup.cfg`, `requirements.txt`
□ Fichiers référencés dans config JSON/YAML (ex: scripts listés dans `db_profiles.json`)
□ Fichiers importés dynamiquement : `importlib.import_module()`, `__import__()`
□ Fichiers de migration en cours (documentés dans `.ai/migrations/`)
□ Fichiers marqués `# LEGACY: [raison]` ou `# DEPRECATED: [raison]` avec raison valide
□ Code dans `tests/` même si non utilisé en prod (tests sont légitimes)
□ Fichiers documentés dans `.ai/` comme nécessaires pour migration
□ `__init__.py` même si vide (nécessaire pour packages Python)
□ Fichiers avec side-effects légitimes (`__init__.py` avec registres, décorateurs)
□ Dossiers contenant assets statiques référencés (images, JSON, etc.)
□ Dossiers de données utilisateur (`data/players/`, `thumbs/`)
```

#### Vérifications Avant Signalement Fichier Inutile

```markdown
1. Est-ce un point d'entrée ? (chercher `if __name__ == '__main__'`, `streamlit run`)
2. Est-il référencé dans config ? (grep dans JSON/YAML/TOML)
3. Est-il importé dynamiquement ? (chercher `importlib`, `__import__`)
4. Est-il documenté comme nécessaire ? (consulter `.ai/`)
5. Contient-il des assets statiques ? (images, données)
```

---

## 2. Analyse Architecturale

### Violations Architecturales à Détecter

#### Structure de Dossiers
```markdown
□ Modules dans mauvais répertoire (ex: UI dans `src/data/`)
□ Violation de séparation des couches (data → ui, ui → data)
□ Fichiers à la racine qui devraient être dans `src/`
□ Tests dans `src/` au lieu de `tests/`
```

#### Dépendances Circulaires
```markdown
□ A importe B, B importe A (direct ou transitif)
□ Modules dans même package s'important mutuellement
□ Import circulaire via `__init__.py`
```

#### Patterns LevelUp Violés

| Pattern | Correct | Violation |
|---------|---------|-----------|
| Accès données | `DuckDBRepository` | `sqlite3.connect()` direct, `loaders.py` legacy |
| DataFrames | `polars` pour gros volumes | `pandas` pour 1000+ lignes |
| Validation | `Pydantic v2 BaseModel` | `dict` brut, validation manuelle |
| Chemins | `from src.utils.paths import *` | Hardcodé `"data/players/"` |
| Cache Streamlit | `@st.cache_data` | Variables globales, `@st.cache` (deprecated) |

#### Couplage Excessif
```markdown
□ Module importe > 10 autres modules
□ Classe avec > 15 méthodes publiques
□ Fonction avec > 7 paramètres
□ Module > 500 lignes (considérer split)
```

#### Responsabilités Mélangées
```markdown
□ Fonction fait I/O + logique métier + validation
□ Classe gère état + persistance + présentation
□ Module mixe data access + UI + business logic
```

### Vérification Conformité Architecture v4

Consulter `.ai/project_map.md` et `docs/DATA_ARCHITECTURE.md` pour :

```markdown
□ Respect structure `data/players/{gamertag}/stats.duckdb`
□ Utilisation `DuckDBRepository` pour accès données
□ Pas d'utilisation modules dépréciés listés dans CLAUDE.md
□ Cohérence avec `.ai/data_lineage.md` pour flux de données
```

---

## 3. Gestion du Code Legacy

### Identification du Code Legacy

#### Signaux de Legacy
```markdown
□ Commentaires "DEPRECATED", "LEGACY", "OLD", "TODO: remove"
□ Modules listés dans CLAUDE.md comme dépréciés
□ Fichiers dans dossiers `legacy/`, `old/`, `deprecated/`
□ Code utilisant APIs obsolètes (ex: `@st.cache` au lieu de `@st.cache_data`)
□ Patterns remplacés par nouveaux (ex: `loaders.py` → `DuckDBRepository`)
```

#### Modules Legacy Connus LevelUp
```python
# D'après CLAUDE.md - NE PLUS UTILISER
- src/db/loaders.py → DuckDBRepository
- src/db/loaders_cached.py → DuckDBRepository
- src/data/repositories/legacy.py → Supprimé
- src/data/repositories/shadow.py → Supprimé
- src/data/repositories/hybrid.py → Supprimé
```

### Actions Recommandées pour Legacy

| État | Action | Priorité |
|------|--------|----------|
| **Non utilisé** | Supprimer directement | Haute |
| **Utilisé mais remplacé** | Migrer vers nouveau pattern, puis supprimer | Haute |
| **Utilisé, pas de remplaçant** | Documenter dans `.ai/legacy_inventory.md` | Moyenne |
| **Utilisé, migration planifiée** | Ajouter `# LEGACY: [raison]` + ticket | Basse |

### Processus de Migration Legacy

```markdown
1. Identifier tous les usages du module legacy
   - grep -r "from legacy_module" --include="*.py"
   
2. Vérifier si remplaçant existe
   - Consulter CLAUDE.md, docs/, .ai/project_map.md
   
3. Si remplaçant existe :
   - Créer plan de migration dans `.ai/migrations/`
   - Migrer un usage à la fois
   - Tests après chaque migration
   
4. Si pas de remplaçant :
   - Documenter pourquoi legacy nécessaire
   - Planifier création remplaçant
```

---

## 4. Duplication de Code

### Détection de Duplication

#### Types de Duplication
```markdown
□ Code identique > 5 lignes dans 2+ fichiers
□ Logique similaire avec variations mineures
□ Constantes dupliquées (magic numbers, strings)
□ Patterns répétés (boilerplate)
```

#### Outils de Détection
```bash
# Détection similaire (nécessite installation)
pylint --disable=all --enable=duplicate-code

# Recherche manuelle de patterns communs
grep -r "pattern_commun" --include="*.py" | wc -l
# Si > 3 occurrences → potentielle duplication
```

### Refactoring Recommandé

| Duplication | Solution |
|-------------|----------|
| Code identique | Extraire fonction utilitaire dans `src/utils/` |
| Logique similaire | Créer fonction générique avec paramètres |
| Constantes | Centraliser dans `src/config/constants.py` |
| Boilerplate | Créer décorateur ou classe de base |

---

## 5. Nettoyage des Imports

### Problèmes à Détecter
```markdown
□ Imports inutilisés (ruff: F401)
□ Imports dupliqués
□ Imports wildcard (`from module import *`)
□ Imports non ordonnés (violation PEP 8)
□ Imports circulaires
□ Imports dans mauvais ordre (stdlib → third-party → local)
```

### Correction Automatique
```bash
# Ruff peut corriger automatiquement
ruff check --fix --select F401,F811 .
# F401: unused imports
# F811: redefined imports
```

---

## 6. Rapport de Nettoyage

### Format de Rapport

```markdown
# Code Cleanup & Architecture Review - [DATE]

## Méta-données
| Métrique | Valeur |
|----------|--------|
| Fichiers analysés | N |
| Lignes de code | M |
| Durée analyse | X min |

## Fichiers et Dossiers Inutiles 🔴 (Prioritaire)

| Type | Chemin | Description | Vérification | Action |
|------|--------|-------------|--------------|--------|
| Fichier Python | `src/db/loaders.py` | Module déprécié, 0 imports trouvés | `grep -r "loaders" --include="*.py"` = 0 | Supprimer |
| Fichier Python | `src/utils/old_helper.py` | Jamais importé, fonctions inutilisées | Aucun `from utils.old_helper` | Supprimer |
| Dossier entier | `legacy/` | Contient uniquement fichiers morts | Tous fichiers non référencés | Supprimer dossier |
| Dossier vide | `old/` | Dossier vide (hors .git) | `find old/ -type f` = 0 | Supprimer |
| Fichier migration | `scripts/migrate_v1_to_v2.py` | Migration complétée, date dépassée | Date limite: 2025-01-01 | Supprimer |

## Code Mort Détecté 🔴

| Type | Fichier:Ligne | Description | Action |
|------|---------------|-------------|--------|
| Fonction inutilisée | `src/utils/old.py:42` | `legacy_function()` jamais appelée | Supprimer |
| Import inutilisé | `src/data/sync.py:5` | `from old_module import X` | Supprimer |
| Classe inutilisée | `src/models/old.py:15` | `LegacyModel` jamais instanciée | Supprimer |

## Violations Architecturales 🟠

| Type | Fichier:Ligne | Description | Impact |
|------|---------------|-------------|--------|
| Pattern legacy | `src/ui/page.py:88` | Utilise `loaders.py` au lieu de `DuckDBRepository` | Migration requise |
| Dépendance circulaire | `src/data/module_a.py` ↔ `src/data/module_b.py` | Import mutuel | Refactor |
| Couplage excessif | `src/core/manager.py` | Importe 15 modules | Considérer split |

## Code Legacy Identifié 🟡

| Fichier | Raison Legacy | Usages | Plan Migration |
|---------|---------------|--------|----------------|
| `src/db/loaders.py` | Remplacé par `DuckDBRepository` | 3 fichiers | Migrer vers repository pattern |

## Duplication Détectée 🟡

| Fichiers | Lignes | Description | Solution |
|----------|--------|-------------|----------|
| `src/utils/a.py:45-50`<br>`src/utils/b.py:88-93` | 6 | Validation identique | Extraire `validate_input()` |

## Recommandations

### Actions Immédiates (avant merge)
1. Supprimer code mort identifié (X fonctions, Y imports)
2. Migrer `loaders.py` vers `DuckDBRepository` (3 fichiers)

### Actions Planifiées (sprint suivant)
1. Refactor dépendance circulaire `module_a` ↔ `module_b`
2. Extraire duplication validation dans utilitaire

### Métriques
- **Fichiers inutiles** : X fichiers Python (~Y KB) pouvant être supprimés
- **Dossiers inutiles** : Z dossiers vides ou contenant uniquement fichiers morts
- Code mort : X lignes (~Y% du code analysé)
- Violations architecturales : Z critiques
- Legacy à migrer : W fichiers
- **Gain estimé** : ~Y KB d'espace disque + simplification codebase
```

---

## 7. Intégration avec Workflow

### Déclenchement

```bash
# Nettoyage complet (tous fichiers)
/cleanup --full

# Nettoyage sur changements récents
/cleanup --recent

# Nettoyage sur fichiers spécifiques
/cleanup src/data/

# Nettoyage + correction automatique
/cleanup --auto-fix
```

### Workflow Recommandé

1. **Avant PR** : `/cleanup --recent` pour détecter code mort introduit
2. **Mensuel** : `/cleanup --full` pour audit complet
3. **Avant refactor majeur** : `/cleanup --full` pour baseline

### Intégration avec Autres Règles

- **Avant** `code-review-scaled` : Exécuter `/cleanup` pour éliminer code mort évident
- **Après** migration legacy : `/cleanup` pour vérifier nettoyage complet
- **Complémentaire** à `fagan-reviewer` : Focus sur architecture vs défauts fonctionnels

---

## 8. Exclusions et Faux Positifs

### Ne PAS signaler comme problème

- Code legacy documenté dans `.ai/legacy_inventory.md` avec raison valide
- Imports utilisés pour side-effects (`__init__.py` avec `@register` decorators)
- Code mort intentionnel (ex: fallback pour compatibilité)
- Duplication justifiée (ex: validation similaire mais contexte différent)
- Fichiers de migration temporaires (marqués `# TEMP: [date_limite]`)

### Vérifications Avant Signalement

1. **Fichiers/Dossiers inutiles** : 
   - Vérifier avec `grep` que vraiment jamais importé
   - Vérifier si point d'entrée ou référencé dans config
   - Consulter `.ai/` pour contexte historique
2. **Code mort** : Vérifier avec `grep` que vraiment inutilisé
3. **Legacy** : Consulter `.ai/` pour contexte historique
4. **Duplication** : Vérifier si variations justifiées par contexte
5. **Architecture** : Consulter `docs/ARCHITECTURE.md` pour exceptions documentées

---

## 9. Exemples Concrets LevelUp

### Exemple 0 : Fichiers et Dossiers Inutiles

```bash
# ❌ PROBLÈME DÉTECTÉ
# Fichier src/db/loaders.py existe mais :
grep -r "from src.db.loaders" --include="*.py" .
# Résultat: 0 occurrences → fichier inutile

# Vérification supplémentaire (point d'entrée ?)
grep -E "(if __name__|streamlit run)" src/db/loaders.py
# Résultat: 0 → pas un point d'entrée

# ✅ SOLUTION
# Supprimer le fichier car remplacé par DuckDBRepository
rm src/db/loaders.py

# ❌ PROBLÈME DÉTECTÉ
# Dossier legacy/ contient 3 fichiers Python
find legacy/ -name "*.py"
# legacy/old_module.py
# legacy/deprecated_helper.py
# legacy/migration_temp.py

# Vérifier chaque fichier
for file in legacy/*.py; do
    module=$(basename $file .py)
    grep -r "$module" --include="*.py" . | grep -v "legacy/"
done
# Résultat: 0 usages → dossier entier inutile

# ✅ SOLUTION
# Supprimer le dossier entier après vérification
rm -rf legacy/
```

### Exemple 1 : Code Mort

```python
# ❌ PROBLÈME DÉTECTÉ
# src/utils/helpers.py
def old_format_date(date_str):
    """Ancien formatage, remplacé par format_date()"""
    return date_str[:10]

# ✅ SOLUTION
# Supprimer fonction si vraiment inutilisée
# OU marquer # LEGACY: utilisé par migration script X
```

### Exemple 2 : Violation Architecturale

```python
# ❌ PROBLÈME DÉTECTÉ
# src/ui/pages/stats.py
import sqlite3
conn = sqlite3.connect("data/players/user/stats.duckdb")  # Violation

# ✅ SOLUTION
from src.data.repositories import DuckDBRepository
repo = DuckDBRepository(db_path, xuid)
```

### Exemple 3 : Legacy à Migrer

```python
# ❌ PROBLÈME DÉTECTÉ
# src/analysis/report.py
from src.db.loaders import load_matches  # Module déprécié

# ✅ SOLUTION
from src.data.repositories import DuckDBRepository
repo = DuckDBRepository(db_path, xuid)
matches = repo.load_matches(limit=100)
```

---

*Dernière mise à jour : 2026-02-04*
