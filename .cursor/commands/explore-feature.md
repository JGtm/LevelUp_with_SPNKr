# Commande /explore-feature

Explore une fonctionnalité du codebase et documente les fichiers pertinents.

## Usage
`/explore-feature [nom de la feature]`

## Étapes

1. **Rechercher** les fichiers pertinents avec Grep/Glob
2. **Lire** les fichiers clés identifiés
3. **Documenter** dans `.ai/features/[feature-name].md` :
   - Fichiers impliqués
   - Flux de données
   - Points d'entrée
   - Dépendances
4. **Mettre à jour** `.ai/project_map.md` si nécessaire

## Format de sortie

```markdown
# Feature: [nom]

## Fichiers
- `path/to/file.py` : Description

## Flux
1. Entrée → Traitement → Sortie

## Notes
- Points d'attention
```
