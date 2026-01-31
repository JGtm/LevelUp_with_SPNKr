# .ai/features/ - Base de Connaissances Technique

Ce dossier contient les spécifications techniques extraites automatiquement du projet par la commande `/investigate`.

## Structure

Chaque fichier `.md` représente un module majeur du projet :

| Fichier | Module |
|---------|--------|
| `spnkr_integration.md` | Intégration API SPNKr |
| `data_storage.md` | Architecture de stockage (SQLite/Parquet) |
| `stats_engine.md` | Moteur de calculs statistiques |
| `ui_components.md` | Composants Streamlit |
| ... | ... |

## Format Standard

Chaque fiche doit suivre ce template :

```markdown
# Nom du Module

## Résumé
[Description en 2-3 phrases]

## Inputs
- [Type et source des données entrantes]

## Outputs  
- [Type et destination des données sortantes]

## Dépendances
- [Modules internes et packages externes]

## Logique Métier
[Algorithmes et règles importantes]

## Points d'Attention
[Bugs connus, limitations, TODOs]
```

## Usage

Ces fichiers sont lus par la commande `/plan` pour générer un plan d'implémentation structuré.

---
*Généré automatiquement - Ne pas modifier manuellement*
