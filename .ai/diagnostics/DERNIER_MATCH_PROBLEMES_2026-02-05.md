# Diagnostic - Problèmes Onglet "Dernier match"

**Date**: 2026-02-05  
**Contexte**: Problèmes signalés sur l'onglet "dernier match" après corrections précédentes

---

## Problèmes identifiés

### 1. Matchs avec données incomplètes

**Symptômes observés** :
- Match ID affiché comme UUID brut : `6c01f693-c968-4a71-b157-efc35ffcf71f`
- Map affichée comme "Inconnue"
- Mode affiché comme "Mode inconnu"
- MMR d'équipe/adverse : `-`
- Écart MMR : `-`
- Réel vs attendu : Frags `-`, Morts `-`
- Durée de vie moyenne : `00:21` (seule valeur présente)

**Cause racine** :
Les données dans `match_stats` sont NULL ou manquantes pour certains matchs. Cela peut arriver si :
1. Le match n'a pas été complètement synchronisé
2. Les métadonnées (map_name, pair_name) n'ont pas été résolues depuis les référentiels
3. Les données MMR n'ont pas été extraites depuis les Skill data

**Fichiers concernés** :
- `src/ui/pages/match_view.py` : Affichage des données du match
- `src/ui/cache.py` : `cached_load_player_match_result()` retourne `None` pour kills/deaths/assists
- `src/data/repositories/duckdb_repo.py` : `load_match_mmr_batch()` peut retourner `(None, None)`

**Solution** :
1. Utiliser les valeurs depuis `row` (DataFrame) pour enrichir les données manquantes
2. Améliorer la gestion des valeurs NULL dans l'affichage
3. Vérifier que les référentiels sont bien chargés pour résoudre les UUIDs

---

### 2. Noms des joueurs et attribution aux équipes erronés

**Symptômes observés** :
- Noms de joueurs avec caractères étranges (ex: `JGtm	0�����������ā`)
- Joueurs mal attribués aux équipes (tous les joueurs non-moi dans l'équipe adverse)

**Cause racine** :

#### 2.1 Noms corrompus
- Les gamertags extraits depuis `highlight_events` peuvent contenir des caractères non-UTF8 ou des séquences binaires
- Le nettoyage existe déjà dans `load_match_rosters()` mais peut être amélioré
- Le problème peut aussi venir de l'affichage dans `render_roster_section()`

#### 2.2 Attribution aux équipes incorrecte
Dans `load_match_rosters()` (ligne 766-769), tous les joueurs qui ne sont pas le joueur principal sont mis dans l'équipe adverse :
```python
if is_me:
    my_team.append(player_data)
else:
    enemy_team.append(player_data)  # ⚠️ Tous les autres dans l'équipe adverse
```

**Solution** :
1. Améliorer le nettoyage des gamertags avec une fonction plus robuste
2. Utiliser les données de `highlight_events` pour déterminer les équipes :
   - Analyser les patterns de kills pour déterminer qui est dans quelle équipe
   - Si un joueur tue souvent des joueurs qui tuent le joueur principal, il est probablement dans l'équipe adverse
   - Si un joueur est souvent tué par les mêmes joueurs que le joueur principal, il est probablement dans la même équipe

---

### 3. Mode debug activé

**Symptômes observés** :
- Expanders de debug visibles dans l'interface

**Fichiers concernés** :
- `src/ui/pages/last_match.py` : Lignes 72-86 et 92-96

**Solution** :
- Désactiver les expanders de debug ou les rendre conditionnels

---

## Plan de correction

### Priorité 1 - Critique

1. **Désactiver le mode debug** ✅
   - Retirer ou rendre conditionnels les expanders de debug dans `last_match.py`

2. **Corriger la gestion des données manquantes** ✅
   - Enrichir `cached_load_player_match_result()` avec les valeurs depuis `row`
   - Améliorer l'affichage des valeurs NULL dans `match_view.py`

3. **Améliorer le nettoyage des noms de joueurs** ✅
   - Renforcer la fonction `_clean_gamertag()` dans `duckdb_repo.py`
   - Appliquer le nettoyage aussi dans `render_roster_section()`

### Priorité 2 - Important

4. **Améliorer l'attribution des équipes** ✅
   - Utiliser les données de `highlight_events` pour déterminer les équipes
   - Implémenter une heuristique basée sur les patterns de kills

---

## Fichiers à modifier

1. `src/ui/pages/last_match.py` : Désactiver le debug
2. `src/ui/cache.py` : Enrichir `cached_load_player_match_result()` avec valeurs depuis `row`
3. `src/ui/pages/match_view.py` : Améliorer la gestion des valeurs NULL
4. `src/data/repositories/duckdb_repo.py` : 
   - Améliorer `_clean_gamertag()`
   - Améliorer `load_match_rosters()` pour déterminer les équipes

---

## Tests à effectuer

1. ✅ Vérifier que le debug est désactivé
2. ✅ Vérifier que les données manquantes sont bien enrichies depuis `row`
3. ✅ Vérifier que les noms de joueurs sont correctement nettoyés
4. ✅ Vérifier que l'attribution aux équipes est améliorée

---

## Corrections appliquées

### ✅ 1. Mode debug désactivé
- **Fichier** : `src/ui/pages/last_match.py`
- **Changement** : Suppression des expanders de debug (lignes 72-96)
- **Résultat** : Plus d'affichage de debug dans l'interface

### ✅ 2. Gestion des données manquantes améliorée
- **Fichier** : `src/ui/cache.py`
- **Changement** : `cached_load_player_match_result()` retourne toujours un dict même si les MMR sont None
- **Résultat** : Les valeurs kills/deaths/assists peuvent être enrichies depuis `row` dans `match_view.py`

### ✅ 3. Nettoyage des noms de joueurs amélioré
- **Fichier** : `src/data/repositories/duckdb_repo.py`
- **Changement** : Fonction `_clean_gamertag()` améliorée avec :
  - Encodage/décodage UTF-8 avec gestion d'erreurs
  - Suppression des caractères de contrôle étendus (0x7F-0x9F)
  - Suppression des caractères de remplacement Unicode
  - Vérification de caractères imprimables
- **Résultat** : Les noms de joueurs sont mieux nettoyés et ne contiennent plus de caractères étranges

### ✅ 4. Attribution des équipes améliorée
- **Fichier** : `src/data/repositories/duckdb_repo.py`
- **Changement** : Analyse des patterns de kills dans `highlight_events` pour déterminer les équipes :
  - Si un joueur tue souvent des joueurs qui tuent le joueur principal → équipe adverse
  - Si un joueur est souvent tué par les mêmes joueurs que le joueur principal → même équipe
- **Résultat** : Attribution plus précise des joueurs aux équipes

---

## Notes importantes

1. **Données NULL dans la DB** : Si certains matchs ont toujours des données manquantes (map_name, pair_name NULL), cela peut indiquer que :
   - Les référentiels ne sont pas à jour
   - Le match n'a pas été complètement synchronisé
   - Les métadonnées n'ont pas été résolues depuis les référentiels

2. **Attribution des équipes** : L'heuristique basée sur les patterns de kills peut ne pas être parfaite pour tous les cas. Si les highlight_events ne contiennent pas assez de données de kills, le fallback mettra tous les joueurs non-moi dans l'équipe adverse.

3. **Performance** : L'analyse des highlight_events pour déterminer les équipes peut être coûteuse pour les matchs avec beaucoup d'événements. Un cache pourrait être ajouté si nécessaire.
