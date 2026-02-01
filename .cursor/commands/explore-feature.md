# Commande /explore-feature

Explore une fonctionnalité du codebase et documente les fichiers pertinents.

## Usage
`/explore-feature [nom de la feature]`

## Étapes

### 0. Consulter le RAG (si MCP halo-rag activé)

Avant de chercher dans le code, interroger la base de connaissances :

```
CallMcpTool("halo-rag", "search_knowledge", {
    "query": "[nom de la feature]",
    "top_k": 5
})
```

Cela permet de :
- Trouver de la documentation existante
- Identifier des patterns similaires dans le projet ou Grunt
- Avoir du contexte sur l'API Halo si pertinent

### 1. Rechercher les fichiers pertinents avec Grep/Glob
### 2. Lire les fichiers clés identifiés
### 3. Documenter dans `.ai/features/[feature-name].md` :
   - Fichiers impliqués
   - Flux de données
   - Points d'entrée
   - Dépendances
   - **Références RAG** (si trouvées)
### 4. Mettre à jour `.ai/project_map.md` si nécessaire

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
