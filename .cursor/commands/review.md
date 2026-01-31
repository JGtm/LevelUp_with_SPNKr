# Commande /review

Effectue une revue de code systématique avec critères de qualité.

## Usage
`/review [fichier ou dossier à revoir]`
`/review --staged` (fichiers git staged)
`/review --recent` (derniers fichiers modifiés)

## Critères de Revue

### 1. Qualité du Code
```
□ Nommage clair et cohérent (snake_case, PascalCase)
□ Fonctions courtes (< 50 lignes idéalement)
□ Pas de code dupliqué (DRY)
□ Commentaires utiles (pas évidents)
□ Docstrings sur fonctions publiques
```

### 2. Architecture
```
□ Respect de la séparation des responsabilités
□ Pas d'imports circulaires
□ Dépendances injectées vs hardcodées
□ Cohérence avec l'architecture existante (.ai/project_map.md)
```

### 3. Sécurité
```
□ Pas de secrets hardcodés
□ Validation des entrées utilisateur
□ Gestion des erreurs appropriée
□ Pas de SQL injection (requêtes paramétrées)
```

### 4. Performance
```
□ Pas de boucles N+1 (requêtes DB)
□ Utilisation appropriée de Polars vs Pandas
□ Lazy evaluation quand possible
□ Cache utilisé si pertinent
```

### 5. Testabilité
```
□ Fonctions pures quand possible
□ Dépendances mockables
□ Pas d'effets de bord cachés
```

## Étapes

### 1. Collecte des fichiers
```bash
# Fichiers staged
git diff --cached --name-only

# Fichiers modifiés récemment
git diff --name-only HEAD~5
```

### 2. Analyse automatique
```bash
# Linting
ruff check [fichiers]

# Complexité
ruff check --select C901 [fichiers]

# Sécurité
bandit -r [fichiers] 2>/dev/null || echo "bandit non installé"
```

### 3. Revue manuelle
Pour chaque fichier :
1. Lire le code en entier
2. Vérifier les critères ci-dessus
3. Noter les problèmes par sévérité

### 4. Rapport

```markdown
## Revue de Code - [date]

### Fichiers analysés
- `path/to/file.py`

### Problèmes Critiques 🔴
- [fichier:ligne] Description

### Améliorations Suggérées 🟡
- [fichier:ligne] Description

### Points Positifs 🟢
- Bonne utilisation de X

### Actions Recommandées
1. Corriger les problèmes critiques
2. Considérer les améliorations
```

## Checklist de sortie

- [ ] Tous les fichiers analysés
- [ ] Problèmes critiques identifiés
- [ ] Suggestions d'amélioration listées
- [ ] Rapport généré
