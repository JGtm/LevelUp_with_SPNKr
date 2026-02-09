# Plan – Intégration des 14 nouvelles médailles

> Généré le 2026-02-09. À exécuter **après** validation par l’utilisateur (aucune modification de code avant accord).

---

## 1. Synthèse

- **Objectif** : Ajouter 14 médailles manquantes (labels FR/EN, icônes) et corriger 1 entrée existante (Grand Slam déjà présent, à vérifier).
- **Sources** :
  - **Labels EN** : liste fournie (noms type “Action Hero”, “Assured Destruction”, etc.).
  - **Labels FR** : [WikiHalo – Médailles de Halo Infinite](https://wiki.halo.fr/Médailles_de_Halo_Infinite) (traductions officielles quand disponibles).
  - **Descriptions** (optionnel, phase ultérieure) : WikiHalo (FR) ; [LeafApp_Infinite](https://github.com/iBotPeaches/LeafApp_Infinite) stocke les médailles en base (modèle `Medal`), pas de fichier unique avec descriptions dans le dépôt – à récupérer depuis l’app ou l’API si besoin.
- **Fichiers concernés dans l’app** :
  - `static/medals/medals_fr.json` (labels FR)
  - `static/medals/medals_en.json` (labels EN)
  - `static/medals/icons/<id>.png` (icônes)

---

## 2. Liste des médailles à ajouter (avec correction typo)

| ID         | Nom (EN)              | Référence FR WikiHalo (si trouvé) | Fichier icône source |
|------------|------------------------|-----------------------------------|------------------------|
| 2976102155 | Action Hero           | À définir / à chercher            | `Downloads/2976102155.png` |
| 1585298941 | Assured Destruction   | À définir                         | `Downloads/1585298941.png` |
| 2125906504 | Big Deal              | À définir                         | `Downloads/FHo-maHWQAYsgij.png` → renommer en `2125906504.png` |
| 590706932  | Contract Killer       | À définir                         | `Downloads/FHo-0FqXEAYC_1r.png` → renommer en `590706932.png` |
| 1254180082 | Deep Ball             | À définir                         | `Downloads/1254180082.png` |
| 4014259917 | Fast Break            | À définir                         | `Downloads/4014259917.png` |
| 3945864962 | Fast Lane             | À définir                         | `Downloads/FHo-76qXwAUbv0-.png` → renommer en `3945864962.png` |
| 3041030832 | High Value Target     | À définir                         | `Downloads/3041030832.png` |
| 1325926691 | Hang Time             | À définir                         | `Downloads/1325926691.png` |
| 2362950720 | Interception          | **Interception** (WikiHalo : mode CTF) | `Downloads/2362950720.png` |
| 1334138090 | Late Boomer           | À définir (mode Crâne)            | `Downloads/1334138090.png` |
| 2005352812 | Meganaut              | À définir                         | `Downloads/2005352812.png` |
| 420808268  | Zone Guardian         | **Garde de colline** (WikiHalo)   | `Downloads/420808268.png` |
| 1646928910 | Grand Slam            | **As du swing** (déjà en app)     | `Downloads/FHo_F-fX0A0y4sH.png` → renommer en `1646928910.png` |

**Note typo** : Dans ta liste, “Meganaut” était associé à l’ID 1334138090 ; 1334138090 = **Late Boomer**. **Meganaut = 2005352812.** Les entrées ci-dessus utilisent les bons IDs.

---

## 2b. Descriptions EN (source Leaf – [Medal Leaderboards](https://leafapp.co/leaderboards/medal), 12 pages)

Extraction faite le 2026-02-09 depuis https://leafapp.co/leaderboards/medal (pages 1 à 12). À utiliser pour les labels EN et, si l'app affiche un jour les descriptions, pour le champ description EN.

| ID         | Nom (EN)              | Description (EN – Leaf) |
|------------|------------------------|--------------------------|
| 2976102155 | Action Hero           | Disarm the enemy bomb moments before it detonates |
| 1585298941 | Assured Destruction   | Kill an enemy disarming your bomb moments before they succeed |
| 2125906504 | Big Deal              | Survive as the VIP for 2 minutes |
| 590706932  | Contract Killer        | Kill 3 enemy VIP's in a single life |
| 1254180082 | Deep Ball             | Complete a pass to a teammate from far away |
| 4014259917 | Fast Break            | Score a goal shortly after the ball is spawned without a turnover |
| 3945864962 | Fast Lane             | As VIP, visit all Scout points within X seconds |
| 3041030832 | High Value Target     | Kill a VIP that is one Scout Point away of scoring |
| 1325926691 | Hang Time             | Kill an enemy by shooting them moments after launching yourself with the Repulsor |
| 2362950720 | Interception          | Catch an enemy-thrown ball near your goal |
| 1334138090 | Late Boomer           | Plant the bomb moments before time expires |
| 2005352812 | Meganaut              | Recharge your shields 10 times as the Juggernaut |
| 420808268  | Zone Guardian         | Occupy the zone for 30 seconds without leaving in King of the Hill |
| 1646928910 | Grand Slam            | Kill 2+ enemies with a single Gravity Hammer swing |

**Clarification Interception** : Sur Leaf, **2362950720** = "Interception" (mode ballon : *Catch an enemy-thrown ball near your goal*). **3488248720** = "Stopped Short" (*Kill an enemy flag carrier who is about to score*). Deux médailles distinctes.

---

## 2c. Propositions de traductions FR (esprit Halo)

Style aligné sur l’existant : court, percutant, vocabulaire jeu (frag, bouclier, zone), parfois référence à l’annonceur ou au ton militaire. Quand une traduction officielle existe (WikiHalo), elle est reprise.

| ID         | Nom FR (proposé)      | Description FR (proposée) |
|------------|------------------------|----------------------------|
| 2976102155 | **Désamorçage**       | Désactivez la bombe ennemie juste avant qu’elle n’explose. |
| 1585298941 | **Destruction assurée** | Tuez un ennemi qui désactive votre bombe juste avant qu’il n’y parvienne. |
| 2125906504 | **Gros lot**          | Survivez en tant que VIP pendant 2 minutes. |
| 590706932  | **Chasseur de primes** | Éliminez 3 VIP ennemis en une seule vie. |
| 1254180082 | **Passe longue**      | Effectuez une passe décisive à un coéquipier depuis une longue distance. |
| 4014259917 | **Contre-attaquant**  | Marquez un but juste après l’apparition du ballon sans perdre la balle. |
| 3945864962 | **Voie express**      | En tant que VIP, atteignez tous les points de reconnaissance dans les temps. |
| 3041030832 | **Cible prioritaire** | Éliminez un VIP à un point de marquage de la victoire. |
| 1325926691 | **Tir en suspension** | Tuez un ennemi en le visant juste après vous être propulsé avec le Répulseur. |
| 2362950720 | **Interception**      | Interceptez une balle lancée par l’ennemi près de votre but. |
| 1334138090 | **Boomer de justesse** | Posez la bombe juste avant la fin du temps imparti. |
| 2005352812 | **Méganaute**         | Rechargez vos boucliers 10 fois en tant que Juggernaut. |
| 420808268  | **Garde de zone**     | Occupez la zone pendant 30 secondes sans la quitter en mode Roi de la colline. |
| 1646928910 | **As du swing**       | Tuez au moins 2 ennemis d’un seul coup de marteau antigrav. |

**Variantes possibles (noms)** :
- **Action Hero** : « Héros du dernier souffle » (plus narratif).
- **Assured Destruction** : « Trop tard » (ton annonceur).
- **Big Deal** : « Deux minutes en vue » (descriptif).
- **Late Boomer** : « À la dernière seconde » (si on évite le jeu de mots « boomer »).
- **Zone Guardian** : WikiHalo donne « Garde de colline » ; l’app a déjà **580478179** = « Garde de colline » (Hill Guardian). Pour éviter le doublon, proposition **Garde de zone** pour 420808268. Si tu préfères garder « Garde de colline » pour les deux, c’est cohérent avec le wiki.

**Descriptions** : Forme impérative (« Tuez », « Survivez »), comme sur le wiki et en jeu. Prêtes à être intégrées si tu ajoutes un champ `description` aux JSON plus tard.

---

## 3. Vérifications LeafApp_Infinite

- **Site** : Les médailles (noms + descriptions EN) sont listées sur [leafapp.co/leaderboards/medal](https://leafapp.co/leaderboards/medal) (12 pages). Extraction effectuée ; voir § 2b.
- **Config** : Pas de `config/medals.php` ; pas d’énumération PHP unique des médailles avec descriptions dans le dépôt.
- **Médailles** : Gérées via le modèle `Medal` en base, commande `RefreshMedals`, jobs `ProcessMedalAnalytic` / `ProcessMedalAnalytic.php`. Les noms/descriptions EN viennent très probablement d’une API (DotAPI / metadata) et sont en base, pas dans un fichier texte versionné.
- **Utilité pour nous** : Les labels et descriptions EN des 14 médailles sont documentés dans ce plan (§ 2b), extraits du site Leaf. Aucun code modifié.

---

## 4. Vérifications WikiHalo (FR)

D’après la page [Médailles de Halo Infinite](https://wiki.halo.fr/Médailles_de_Halo_Infinite) :

- **Zone Guardian** (420808268) : “Garde de colline” – *Occupez la colline pendant 30 secondes sans la quitter en mode Roi de la colline.*
- **Interception** (2362950720) : La page mentionne “Interception (_Stopped Short_)” pour un autre ID (3488248720). Chez nous, 3488248720 = “Stopped Short” (FR : “Interception” dans notre `medals_fr`). Donc pour **2362950720** (Interception dans ton enum), il peut s’agir d’une autre médaille (ex. interception de passe en mode ballon) ; à afficher en FR comme **“Interception”** ou à distinguer si le jeu utilise deux médailles différentes.
- **Grand Slam** (1646928910) : “As du swing” – *Tuez au moins 2 ennemis d'un seul coup de marteau antigrav.* (déjà présent dans l’app.)
- Les autres (Action Hero, Assured Destruction, Big Deal, Contract Killer, Deep Ball, Fast Break, Fast Lane, High Value Target, Hang Time, Late Boomer, Meganaut) : pas de traduction officielle évidente sur la page ; on peut utiliser une traduction littérale ou laisser le nom EN en attendant.

---

## 5. Plan d’action (sans toucher au code tant que non validé)

### Étape 1 – Fichiers d’icônes (Downloads → repo)

1. **Copier** les PNG depuis `C:\Users\Guillaume\Downloads\` vers `static/medals/icons/` :
   - Déjà nommés par ID : `2976102155.png`, `1585298941.png`, `1254180082.png`, `4014259917.png`, `3041030832.png`, `1325926691.png`, `2362950720.png`, `1334138090.png`, `2005352812.png`, `420808268.png`.
   - À **renommer** puis copier :
     - `FHo-maHWQAYsgij.png` → `2125906504.png` (Big Deal)
     - `FHo-0FqXEAYC_1r.png` → `590706932.png` (Contract Killer)
     - `FHo-76qXwAUbv0-.png` → `3945864962.png` (Fast Lane)
     - `FHo_F-fX0A0y4sH.png` → `1646928910.png` (Grand Slam – remplacement/backup si déjà présent)

2. Vérifier que chaque fichier copié est bien un PNG valide et lisible.

### Étape 2 – `medals_en.json`

- Ajouter **14 entrées** (clé = ID en chaîne, valeur = nom EN) pour les IDs listés au §2.  
- **1646928910** (Grand Slam) est déjà dans l’app ; ne pas dupliquer, uniquement s’assurer que le libellé est “Grand Slam”.

### Étape 3 – `medals_fr.json`

- Ajouter les **14 entrées** avec libellés FR :
  - **Zone Guardian** → “Garde de colline”
  - **Grand Slam** → “As du swing” (déjà présent)
  - **Interception** (2362950720) → “Interception” (ou variante si on distingue de Stopped Short)
  - Pour les autres : soit traduction littérale (ex. “Action Hero”, “Cible prioritaire” pour High Value Target), soit laisser le nom EN temporairement et documenter “à traduire” dans ce fichier ou dans le thought_log.

### Étape 4 – Optionnel (hors scope immédiat)

- **Descriptions** : Si l’app doit afficher une description sous chaque médaille, faire évoluer le format JSON (objet `{ "label": "...", "description": "..." }`) et `src/ui/medals.py` pour lire et afficher la description. Puis remplir à partir de WikiHalo (FR) et, si besoin, LeafApp/API (EN).
- **Vérification LeafApp** : En local ou via leur site (ex. [Medal Leaderboards](https://leafapp.co/leaderboards/medal)), confirmer les libellés EN pour les 14 médailles si tu veux être 100 % aligné avec eux.

### Étape 5 – Récap et tests

- **Tests automatisés** : Le fichier `tests/test_medals_labels.py` valide que les 14 médailles ont un label FR et EN et que `medal_label()` ne renvoie pas le placeholder. Après avoir mis à jour les JSON (étapes 2 et 3), exécuter :
  ```bash
  pytest tests/test_medals_labels.py -v
  ```
  Tant que les 14 entrées ne sont pas dans les JSON, ces tests échouent (comportement attendu).
- Vérifier que `load_medal_name_maps()` et `medal_icon_path()` exposent bien les 14 nouvelles médailles.
- Ouvrir une page qui affiche les médailles (ex. dernier match, grille médailles) et contrôler visuellement les nouveaux IDs (labels + icônes).

---

## 6. Résumé des fichiers à modifier/créer

| Fichier | Action |
|---------|--------|
| `static/medals/icons/<id>.png` | Copier 14 PNG depuis Downloads (4 renommés depuis FHo_*) |
| `static/medals/medals_en.json` | Ajouter 14 entrées (IDs + noms EN) |
| `static/medals/medals_fr.json` | Ajouter 14 entrées (IDs + noms FR) |
| Code | Aucun changement nécessaire pour l’affichage actuel (labels + icônes) |

---

## 7. Références

- [LeafApp_Infinite (GitHub)](https://github.com/iBotPeaches/LeafApp_Infinite)
- [WikiHalo – Médailles de Halo Infinite](https://wiki.halo.fr/Médailles_de_Halo_Infinite)
- Projet : `src/ui/medals.py` (chargement `medals_fr.json` / `medals_en.json`, priorité FR ; icônes dans `static/medals/icons/` ou cache OpenSpartan).
- Tests : `tests/test_medals_labels.py` (validation des 14 labels ; exécution : `pytest tests/test_medals_labels.py -v`).

Une fois ce plan validé, les étapes 1 à 3 (et 5) peuvent être exécutées ; l’étape 4 reste optionnelle pour une phase suivante.
