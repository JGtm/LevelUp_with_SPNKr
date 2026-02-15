# Commande /update-context

Met à jour les fichiers de contexte agentique `.ai/`.

## Fichiers à mettre à jour

### 1. `.ai/project_map.md`
Mettre à jour si :
- Nouveau module ajouté
- Dépendance ajoutée/supprimée
- Point d'entrée modifié

### 2. `.ai/thought_log.md`
Ajouter une entrée avec :
```markdown
### [YYYY-MM-DD] - [Sujet]
**Contexte** : Situation initiale
**Raisonnement** : Pourquoi cette approche
**Décision** : Ce qui a été fait
**Suivi** : Actions restantes
```

### 3. `.ai/data_lineage.md`
Mettre à jour si :
- Nouveau flux de données
- Nouvelle transformation
- Modification de schéma

## Utilisation MCP filesystem (si disponible)
Utiliser `write_file` pour mettre à jour les fichiers `.ai/*.md` directement.

## Sans MCP
Utiliser l'outil Write standard de Cursor.
