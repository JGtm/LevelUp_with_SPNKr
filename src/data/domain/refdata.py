"""Enums de référence pour Halo Infinite basés sur SPNKr refdata.py.

Ce module fournit les enums officiels de l'API Halo Infinite :
- GameVariantCategory : Catégories de modes de jeu
- PersonalScoreNameId : Décomposition du score personnel
- Outcome : Résultats de match

Source : https://github.com/acurtis166/SPNKr/blob/master/spnkr/models/refdata.py
"""

from enum import IntEnum
from typing import Final


class GameVariantCategory(IntEnum):
    """Catégories officielles de modes de jeu Halo Infinite."""

    UNKNOWN = -1
    NONE = 0
    CAMPAIGN = 1
    FORGE = 2
    ACADEMY = 3
    ACADEMY_TUTORIAL = 4
    ACADEMY_PRACTICE = 5
    MULTIPLAYER_SLAYER = 6
    MULTIPLAYER_ATTRITION = 7
    MULTIPLAYER_ELIMINATION = 8
    MULTIPLAYER_FIESTA = 9
    MULTIPLAYER_SWAT = 10
    MULTIPLAYER_STRONGHOLDS = 11
    MULTIPLAYER_BASTION = 12
    MULTIPLAYER_KING_OF_THE_HILL = 13
    MULTIPLAYER_TOTAL_CONTROL = 14
    MULTIPLAYER_CTF = 15
    MULTIPLAYER_ASSAULT = 16
    MULTIPLAYER_EXTRACTION = 17
    MULTIPLAYER_ODDBALL = 18
    MULTIPLAYER_STOCKPILE = 19
    MULTIPLAYER_JUGGERNAUT = 20
    MULTIPLAYER_REGICIDE = 21
    MULTIPLAYER_INFECTION = 22
    MULTIPLAYER_ESCORT = 23
    MULTIPLAYER_GUN_GAME = 24
    MULTIPLAYER_GRIFBALL = 25
    MULTIPLAYER_RACE = 26
    MULTIPLAYER_PROTOTYPE = 27
    TEST = 28
    TEST_ACADEMY = 29
    TEST_AUDIO = 30
    TEST_CAMPAIGN = 31
    TEST_ENGINE = 32
    TEST_FORGE = 33
    TEST_GRAPHICS = 34
    TEST_MULTIPLAYER = 35
    TEST_SANDBOX = 36
    ACADEMY_TRAINING = 37
    ACADEMY_WEAPON_DRILL = 38
    MULTIPLAYER_LAND_GRAB = 39
    MULTIPLAYER_MINIGAME = 41
    MULTIPLAYER_FIREFIGHT = 42


class PersonalScoreNameId(IntEnum):
    """Types de scores personnels avec leurs valeurs de points associées.

    Les noms sont ceux de l'API. Utilisez `display_name()` pour le nom affiché.
    Les points associés sont documentés en commentaire.
    """

    # Combat
    KILLED_PLAYER = 1024030246  # 100 pts
    BETRAYED_PLAYER = 911992497  # -100 pts
    SELF_DESTRUCTION = 249491819  # -100 pts
    ELIMINATED_PLAYER = 2408971842  # 200 pts
    REVIVED_PLAYER = 3428202435  # 100 pts
    REVIVE_DENIED = 2130209372  # 25 pts

    # Assistances
    KILL_ASSIST = 638246808  # 50 pts
    MARK_ASSIST = 152718958  # 10 pts
    SENSOR_ASSIST = 1267013266  # 10 pts
    EMP_ASSIST = 221060588  # 50 pts
    DRIVER_ASSIST = 963594075  # 50 pts

    # CTF (Capture de drapeau)
    FLAG_CAPTURED = 601966503  # 300 pts
    FLAG_STOLEN = 3002710045  # 25 pts
    FLAG_RETURNED = 22113181  # 25 pts
    FLAG_TAKEN = 2387185397  # 10 pts
    FLAG_CAPTURE_ASSIST = 555570945  # 100 pts
    RUNNER_STOPPED = 316828380  # 25 pts

    # Oddball
    BALL_CONTROL = 454168309  # 50 pts
    BALL_TAKEN = 204144695  # 10 pts
    CARRIER_STOPPED = 746397417  # 25 pts

    # King of the Hill
    HILL_CONTROL = 340198991  # 25 pts
    HILL_SCORED = 1032565232  # 100 pts

    # Strongholds / Zones
    ZONE_CAPTURED_50 = 3507884073  # 50 pts
    ZONE_CAPTURED_75 = 4026987576  # 75 pts
    ZONE_CAPTURED_100 = 757037588  # 100 pts
    ZONE_SECURED = 709346128  # 25 pts

    # Stockpile
    POWER_SEED_SECURED = 2188620691  # 100 pts
    POWER_SEED_STOLEN = 3996338664  # 50 pts
    CARRIER_KILLED = 4128329646  # 10 pts
    STOCKPILE_SCORED = 2801241965  # 150 pts

    # Extraction
    EXTRACTION_INITIATED = 1825517751  # 50 pts
    EXTRACTION_CONVERTED = 1117301492  # 50 pts
    EXTRACTION_COMPLETED = 4130011565  # 200 pts
    EXTRACTION_DENIED = 1552628741  # 25 pts

    # Infection
    CONVERSION_DENIED = 4247243561  # 25 pts

    # Last Spartan Standing
    COLLECTED_BONUS_XP = 522435689  # 300 pts

    # Hacking (Halo Infinite modes)
    HACKED_TERMINAL = 665081740  # 100 pts

    # Destruction de véhicules
    DESTROYED_BANSHEE = 597066859  # 50 pts
    DESTROYED_CHOPPER = 3472794399  # 50 pts
    DESTROYED_FALCON = 395875864  # 75 pts
    DESTROYED_GHOST = 4254982885  # 50 pts
    DESTROYED_GUNGOOSE = 2107631925  # 25 pts
    DESTROYED_MONGOOSE = 1416267372  # 25 pts
    DESTROYED_PHANTOM = 2742351765  # 100 pts
    DESTROYED_RAZORBACK = 1661163286  # 50 pts
    DESTROYED_ROCKET_WARTHOG = 2008690931  # 50 pts
    DESTROYED_SCORPION = 3454330054  # 100 pts
    DESTROYED_WARTHOG = 3107879375  # 50 pts
    DESTROYED_WASP = 2106274556  # 50 pts
    DESTROYED_WRAITH = 3243589708  # 100 pts

    # Hijacks (détournement de véhicules)
    HIJACKED_BANSHEE = 3150095814  # 25 pts
    HIJACKED_CHOPPER = 1059880024  # 25 pts
    HIJACKED_FALCON = 586857799  # 25 pts
    HIJACKED_GHOST = 1614285349  # 25 pts
    HIJACKED_GUNGOOSE = 4186766732  # 25 pts
    HIJACKED_MONGOOSE = 2191528998  # 25 pts
    HIJACKED_RAZORBACK = 2848565291  # 25 pts
    HIJACKED_ROCKET_WARTHOG = 4294405210  # 25 pts
    HIJACKED_WARTHOG = 1834653062  # 25 pts
    HIJACKED_WASP = 674964649  # 25 pts

    # Custom (scripts Forge)
    CUSTOM = 4294967295  # Variable


class Outcome(IntEnum):
    """Résultats possibles d'un match."""

    UNKNOWN = -1
    NONE = 0
    TIE = 1
    WIN = 2
    LOSS = 3
    DID_NOT_FINISH = 4
    DID_NOT_START = 5


# =============================================================================
# Mappings vers le français
# =============================================================================

CATEGORY_TO_FR: Final[dict[int, str]] = {
    GameVariantCategory.UNKNOWN: "Inconnu",
    GameVariantCategory.NONE: "Aucun",
    GameVariantCategory.CAMPAIGN: "Campagne",
    GameVariantCategory.FORGE: "Forge",
    GameVariantCategory.ACADEMY: "Académie",
    GameVariantCategory.ACADEMY_TUTORIAL: "Tutoriel",
    GameVariantCategory.ACADEMY_PRACTICE: "Entraînement",
    GameVariantCategory.MULTIPLAYER_SLAYER: "Assassin",
    GameVariantCategory.MULTIPLAYER_ATTRITION: "Attrition",
    GameVariantCategory.MULTIPLAYER_ELIMINATION: "Élimination",
    GameVariantCategory.MULTIPLAYER_FIESTA: "Fiesta",
    GameVariantCategory.MULTIPLAYER_SWAT: "SWAT",
    GameVariantCategory.MULTIPLAYER_STRONGHOLDS: "Bastions",
    GameVariantCategory.MULTIPLAYER_BASTION: "Bastion",
    GameVariantCategory.MULTIPLAYER_KING_OF_THE_HILL: "Roi de la colline",
    GameVariantCategory.MULTIPLAYER_TOTAL_CONTROL: "Contrôle total",
    GameVariantCategory.MULTIPLAYER_CTF: "Capture de drapeau",
    GameVariantCategory.MULTIPLAYER_ASSAULT: "Assaut",
    GameVariantCategory.MULTIPLAYER_EXTRACTION: "Extraction",
    GameVariantCategory.MULTIPLAYER_ODDBALL: "Balle",
    GameVariantCategory.MULTIPLAYER_STOCKPILE: "Stockpile",
    GameVariantCategory.MULTIPLAYER_JUGGERNAUT: "Juggernaut",
    GameVariantCategory.MULTIPLAYER_REGICIDE: "Régicide",
    GameVariantCategory.MULTIPLAYER_INFECTION: "Infection",
    GameVariantCategory.MULTIPLAYER_ESCORT: "Escorte",
    GameVariantCategory.MULTIPLAYER_GUN_GAME: "Gun Game",
    GameVariantCategory.MULTIPLAYER_GRIFBALL: "Grifball",
    GameVariantCategory.MULTIPLAYER_RACE: "Course",
    GameVariantCategory.MULTIPLAYER_PROTOTYPE: "Prototype",
    GameVariantCategory.MULTIPLAYER_LAND_GRAB: "Land Grab",
    GameVariantCategory.MULTIPLAYER_MINIGAME: "Mini-jeu",
    GameVariantCategory.MULTIPLAYER_FIREFIGHT: "Firefight",
}

OUTCOME_TO_FR: Final[dict[int, str]] = {
    Outcome.UNKNOWN: "Inconnu",
    Outcome.NONE: "Aucun",
    Outcome.TIE: "Égalité",
    Outcome.WIN: "Victoire",
    Outcome.LOSS: "Défaite",
    Outcome.DID_NOT_FINISH: "Non terminé",
    Outcome.DID_NOT_START: "Non commencé",
}

PERSONAL_SCORE_DISPLAY_NAMES: Final[dict[int, str]] = {
    # Combat
    PersonalScoreNameId.KILLED_PLAYER: "Joueur tué",
    PersonalScoreNameId.BETRAYED_PLAYER: "Trahison",
    PersonalScoreNameId.SELF_DESTRUCTION: "Auto-destruction",
    PersonalScoreNameId.ELIMINATED_PLAYER: "Joueur éliminé",
    PersonalScoreNameId.REVIVED_PLAYER: "Joueur réanimé",
    PersonalScoreNameId.REVIVE_DENIED: "Réanimation empêchée",
    # Assistances
    PersonalScoreNameId.KILL_ASSIST: "Assistance kill",
    PersonalScoreNameId.MARK_ASSIST: "Assistance marquage",
    PersonalScoreNameId.SENSOR_ASSIST: "Assistance capteur",
    PersonalScoreNameId.EMP_ASSIST: "Assistance EMP",
    PersonalScoreNameId.DRIVER_ASSIST: "Assistance conducteur",
    # CTF
    PersonalScoreNameId.FLAG_CAPTURED: "Drapeau capturé",
    PersonalScoreNameId.FLAG_STOLEN: "Drapeau volé",
    PersonalScoreNameId.FLAG_RETURNED: "Drapeau ramené",
    PersonalScoreNameId.FLAG_TAKEN: "Drapeau pris",
    PersonalScoreNameId.FLAG_CAPTURE_ASSIST: "Assistance capture",
    PersonalScoreNameId.RUNNER_STOPPED: "Porteur arrêté",
    # Oddball
    PersonalScoreNameId.BALL_CONTROL: "Contrôle balle",
    PersonalScoreNameId.BALL_TAKEN: "Balle prise",
    PersonalScoreNameId.CARRIER_STOPPED: "Porteur arrêté",
    # KOTH
    PersonalScoreNameId.HILL_CONTROL: "Contrôle colline",
    PersonalScoreNameId.HILL_SCORED: "Points colline",
    # Zones
    PersonalScoreNameId.ZONE_CAPTURED_50: "Zone capturée",
    PersonalScoreNameId.ZONE_CAPTURED_75: "Zone capturée",
    PersonalScoreNameId.ZONE_CAPTURED_100: "Zone capturée",
    PersonalScoreNameId.ZONE_SECURED: "Zone sécurisée",
    # Stockpile
    PersonalScoreNameId.POWER_SEED_SECURED: "Graine sécurisée",
    PersonalScoreNameId.POWER_SEED_STOLEN: "Graine volée",
    PersonalScoreNameId.CARRIER_KILLED: "Porteur tué",
    PersonalScoreNameId.STOCKPILE_SCORED: "Stockpile marqué",
    # Extraction
    PersonalScoreNameId.EXTRACTION_INITIATED: "Extraction initiée",
    PersonalScoreNameId.EXTRACTION_CONVERTED: "Extraction convertie",
    PersonalScoreNameId.EXTRACTION_COMPLETED: "Extraction complète",
    PersonalScoreNameId.EXTRACTION_DENIED: "Extraction refusée",
    # Infection
    PersonalScoreNameId.CONVERSION_DENIED: "Conversion empêchée",
    # LSS
    PersonalScoreNameId.COLLECTED_BONUS_XP: "XP bonus collecté",
    # Hacking
    PersonalScoreNameId.HACKED_TERMINAL: "Terminal piraté",
    # Custom
    PersonalScoreNameId.CUSTOM: "Personnalisé",
}

# =============================================================================
# Points par type de score
# =============================================================================

PERSONAL_SCORE_POINTS: Final[dict[int, int]] = {
    # Combat
    PersonalScoreNameId.KILLED_PLAYER: 100,
    PersonalScoreNameId.BETRAYED_PLAYER: -100,
    PersonalScoreNameId.SELF_DESTRUCTION: -100,
    PersonalScoreNameId.ELIMINATED_PLAYER: 200,
    PersonalScoreNameId.REVIVED_PLAYER: 100,
    PersonalScoreNameId.REVIVE_DENIED: 25,
    # Assistances
    PersonalScoreNameId.KILL_ASSIST: 50,
    PersonalScoreNameId.MARK_ASSIST: 10,
    PersonalScoreNameId.SENSOR_ASSIST: 10,
    PersonalScoreNameId.EMP_ASSIST: 50,
    PersonalScoreNameId.DRIVER_ASSIST: 50,
    # CTF
    PersonalScoreNameId.FLAG_CAPTURED: 300,
    PersonalScoreNameId.FLAG_STOLEN: 25,
    PersonalScoreNameId.FLAG_RETURNED: 25,
    PersonalScoreNameId.FLAG_TAKEN: 10,
    PersonalScoreNameId.FLAG_CAPTURE_ASSIST: 100,
    PersonalScoreNameId.RUNNER_STOPPED: 25,
    # Oddball
    PersonalScoreNameId.BALL_CONTROL: 50,
    PersonalScoreNameId.BALL_TAKEN: 10,
    PersonalScoreNameId.CARRIER_STOPPED: 25,
    # KOTH
    PersonalScoreNameId.HILL_CONTROL: 25,
    PersonalScoreNameId.HILL_SCORED: 100,
    # Zones
    PersonalScoreNameId.ZONE_CAPTURED_50: 50,
    PersonalScoreNameId.ZONE_CAPTURED_75: 75,
    PersonalScoreNameId.ZONE_CAPTURED_100: 100,
    PersonalScoreNameId.ZONE_SECURED: 25,
    # Stockpile
    PersonalScoreNameId.POWER_SEED_SECURED: 100,
    PersonalScoreNameId.POWER_SEED_STOLEN: 50,
    PersonalScoreNameId.CARRIER_KILLED: 10,
    PersonalScoreNameId.STOCKPILE_SCORED: 150,
    # Extraction
    PersonalScoreNameId.EXTRACTION_INITIATED: 50,
    PersonalScoreNameId.EXTRACTION_CONVERTED: 50,
    PersonalScoreNameId.EXTRACTION_COMPLETED: 200,
    PersonalScoreNameId.EXTRACTION_DENIED: 25,
    # Infection
    PersonalScoreNameId.CONVERSION_DENIED: 25,
    # LSS
    PersonalScoreNameId.COLLECTED_BONUS_XP: 300,
    # Hacking
    PersonalScoreNameId.HACKED_TERMINAL: 100,
    # Véhicules (25-100 pts selon le véhicule)
    PersonalScoreNameId.DESTROYED_BANSHEE: 50,
    PersonalScoreNameId.DESTROYED_CHOPPER: 50,
    PersonalScoreNameId.DESTROYED_FALCON: 75,
    PersonalScoreNameId.DESTROYED_GHOST: 50,
    PersonalScoreNameId.DESTROYED_GUNGOOSE: 25,
    PersonalScoreNameId.DESTROYED_MONGOOSE: 25,
    PersonalScoreNameId.DESTROYED_PHANTOM: 100,
    PersonalScoreNameId.DESTROYED_RAZORBACK: 50,
    PersonalScoreNameId.DESTROYED_ROCKET_WARTHOG: 50,
    PersonalScoreNameId.DESTROYED_SCORPION: 100,
    PersonalScoreNameId.DESTROYED_WARTHOG: 50,
    PersonalScoreNameId.DESTROYED_WASP: 50,
    PersonalScoreNameId.DESTROYED_WRAITH: 100,
    # Hijacks (tous 25 pts)
    PersonalScoreNameId.HIJACKED_BANSHEE: 25,
    PersonalScoreNameId.HIJACKED_CHOPPER: 25,
    PersonalScoreNameId.HIJACKED_FALCON: 25,
    PersonalScoreNameId.HIJACKED_GHOST: 25,
    PersonalScoreNameId.HIJACKED_GUNGOOSE: 25,
    PersonalScoreNameId.HIJACKED_MONGOOSE: 25,
    PersonalScoreNameId.HIJACKED_RAZORBACK: 25,
    PersonalScoreNameId.HIJACKED_ROCKET_WARTHOG: 25,
    PersonalScoreNameId.HIJACKED_WARTHOG: 25,
    PersonalScoreNameId.HIJACKED_WASP: 25,
    # Custom (variable, on met 0 par défaut)
    PersonalScoreNameId.CUSTOM: 0,
}

# =============================================================================
# Sets pour regroupement par type
# =============================================================================

# Scores liés aux objectifs (modes à objectifs)
OBJECTIVE_SCORES: Final[frozenset[int]] = frozenset(
    {
        # CTF
        PersonalScoreNameId.FLAG_CAPTURED,
        PersonalScoreNameId.FLAG_STOLEN,
        PersonalScoreNameId.FLAG_RETURNED,
        PersonalScoreNameId.FLAG_TAKEN,
        PersonalScoreNameId.FLAG_CAPTURE_ASSIST,
        PersonalScoreNameId.RUNNER_STOPPED,
        # Oddball
        PersonalScoreNameId.BALL_CONTROL,
        PersonalScoreNameId.BALL_TAKEN,
        PersonalScoreNameId.CARRIER_STOPPED,
        # KOTH
        PersonalScoreNameId.HILL_CONTROL,
        PersonalScoreNameId.HILL_SCORED,
        # Zones
        PersonalScoreNameId.ZONE_CAPTURED_50,
        PersonalScoreNameId.ZONE_CAPTURED_75,
        PersonalScoreNameId.ZONE_CAPTURED_100,
        PersonalScoreNameId.ZONE_SECURED,
        # Stockpile
        PersonalScoreNameId.POWER_SEED_SECURED,
        PersonalScoreNameId.POWER_SEED_STOLEN,
        PersonalScoreNameId.STOCKPILE_SCORED,
        # Extraction
        PersonalScoreNameId.EXTRACTION_INITIATED,
        PersonalScoreNameId.EXTRACTION_CONVERTED,
        PersonalScoreNameId.EXTRACTION_COMPLETED,
        PersonalScoreNameId.EXTRACTION_DENIED,
        # Hacking
        PersonalScoreNameId.HACKED_TERMINAL,
    }
)

# Scores liés aux assistances
ASSIST_SCORES: Final[frozenset[int]] = frozenset(
    {
        PersonalScoreNameId.KILL_ASSIST,
        PersonalScoreNameId.MARK_ASSIST,
        PersonalScoreNameId.SENSOR_ASSIST,
        PersonalScoreNameId.EMP_ASSIST,
        PersonalScoreNameId.DRIVER_ASSIST,
        PersonalScoreNameId.FLAG_CAPTURE_ASSIST,
    }
)

# Scores liés aux kills directs
KILL_SCORES: Final[frozenset[int]] = frozenset(
    {
        PersonalScoreNameId.KILLED_PLAYER,
        PersonalScoreNameId.ELIMINATED_PLAYER,
        PersonalScoreNameId.CARRIER_KILLED,
    }
)

# Scores négatifs (trahisons, suicides)
NEGATIVE_SCORES: Final[frozenset[int]] = frozenset(
    {
        PersonalScoreNameId.BETRAYED_PLAYER,
        PersonalScoreNameId.SELF_DESTRUCTION,
    }
)

# Scores liés aux véhicules
VEHICLE_DESTRUCTION_SCORES: Final[frozenset[int]] = frozenset(
    {
        PersonalScoreNameId.DESTROYED_BANSHEE,
        PersonalScoreNameId.DESTROYED_CHOPPER,
        PersonalScoreNameId.DESTROYED_FALCON,
        PersonalScoreNameId.DESTROYED_GHOST,
        PersonalScoreNameId.DESTROYED_GUNGOOSE,
        PersonalScoreNameId.DESTROYED_MONGOOSE,
        PersonalScoreNameId.DESTROYED_PHANTOM,
        PersonalScoreNameId.DESTROYED_RAZORBACK,
        PersonalScoreNameId.DESTROYED_ROCKET_WARTHOG,
        PersonalScoreNameId.DESTROYED_SCORPION,
        PersonalScoreNameId.DESTROYED_WARTHOG,
        PersonalScoreNameId.DESTROYED_WASP,
        PersonalScoreNameId.DESTROYED_WRAITH,
    }
)

VEHICLE_HIJACK_SCORES: Final[frozenset[int]] = frozenset(
    {
        PersonalScoreNameId.HIJACKED_BANSHEE,
        PersonalScoreNameId.HIJACKED_CHOPPER,
        PersonalScoreNameId.HIJACKED_FALCON,
        PersonalScoreNameId.HIJACKED_GHOST,
        PersonalScoreNameId.HIJACKED_GUNGOOSE,
        PersonalScoreNameId.HIJACKED_MONGOOSE,
        PersonalScoreNameId.HIJACKED_RAZORBACK,
        PersonalScoreNameId.HIJACKED_ROCKET_WARTHOG,
        PersonalScoreNameId.HIJACKED_WARTHOG,
        PersonalScoreNameId.HIJACKED_WASP,
    }
)

# =============================================================================
# Catégories de modes (groupements)
# =============================================================================

# Modes à objectifs (non-slayer)
OBJECTIVE_MODE_CATEGORIES: Final[frozenset[int]] = frozenset(
    {
        GameVariantCategory.MULTIPLAYER_CTF,
        GameVariantCategory.MULTIPLAYER_ODDBALL,
        GameVariantCategory.MULTIPLAYER_STRONGHOLDS,
        GameVariantCategory.MULTIPLAYER_KING_OF_THE_HILL,
        GameVariantCategory.MULTIPLAYER_TOTAL_CONTROL,
        GameVariantCategory.MULTIPLAYER_STOCKPILE,
        GameVariantCategory.MULTIPLAYER_ASSAULT,
        GameVariantCategory.MULTIPLAYER_EXTRACTION,
        GameVariantCategory.MULTIPLAYER_LAND_GRAB,
        GameVariantCategory.MULTIPLAYER_GRIFBALL,
    }
)

# Modes "Slayer" et variantes
SLAYER_MODE_CATEGORIES: Final[frozenset[int]] = frozenset(
    {
        GameVariantCategory.MULTIPLAYER_SLAYER,
        GameVariantCategory.MULTIPLAYER_ATTRITION,
        GameVariantCategory.MULTIPLAYER_ELIMINATION,
        GameVariantCategory.MULTIPLAYER_FIESTA,
        GameVariantCategory.MULTIPLAYER_SWAT,
        GameVariantCategory.MULTIPLAYER_GUN_GAME,
    }
)

# Modes spéciaux
SPECIAL_MODE_CATEGORIES: Final[frozenset[int]] = frozenset(
    {
        GameVariantCategory.MULTIPLAYER_INFECTION,
        GameVariantCategory.MULTIPLAYER_JUGGERNAUT,
        GameVariantCategory.MULTIPLAYER_REGICIDE,
        GameVariantCategory.MULTIPLAYER_FIREFIGHT,
        GameVariantCategory.MULTIPLAYER_RACE,
        GameVariantCategory.MULTIPLAYER_MINIGAME,
    }
)


# =============================================================================
# Fonctions utilitaires
# =============================================================================


def get_category_name_fr(category: int | GameVariantCategory) -> str:
    """Retourne le nom français d'une catégorie de mode.

    Args:
        category: Valeur de GameVariantCategory (int ou enum).

    Returns:
        Nom français de la catégorie, ou "Autre" si non trouvé.
    """
    cat_value = int(category) if isinstance(category, GameVariantCategory) else category
    return CATEGORY_TO_FR.get(cat_value, "Autre")


def get_outcome_name_fr(outcome: int | Outcome) -> str:
    """Retourne le nom français d'un résultat de match.

    Args:
        outcome: Valeur de Outcome (int ou enum).

    Returns:
        Nom français du résultat, ou "Inconnu" si non trouvé.
    """
    out_value = int(outcome) if isinstance(outcome, Outcome) else outcome
    return OUTCOME_TO_FR.get(out_value, "Inconnu")


def get_personal_score_display_name(name_id: int | PersonalScoreNameId) -> str:
    """Retourne le nom d'affichage d'un type de score personnel.

    Args:
        name_id: Valeur de PersonalScoreNameId (int ou enum).

    Returns:
        Nom d'affichage français, ou "Score" si non trouvé.
    """
    id_value = int(name_id) if isinstance(name_id, PersonalScoreNameId) else name_id
    return PERSONAL_SCORE_DISPLAY_NAMES.get(id_value, "Score")


def get_personal_score_points(name_id: int | PersonalScoreNameId) -> int:
    """Retourne les points associés à un type de score personnel.

    Args:
        name_id: Valeur de PersonalScoreNameId (int ou enum).

    Returns:
        Nombre de points, ou 0 si non trouvé.
    """
    id_value = int(name_id) if isinstance(name_id, PersonalScoreNameId) else name_id
    return PERSONAL_SCORE_POINTS.get(id_value, 0)


def is_objective_score(name_id: int | PersonalScoreNameId) -> bool:
    """Vérifie si un score est lié aux objectifs.

    Args:
        name_id: Valeur de PersonalScoreNameId.

    Returns:
        True si le score est lié aux objectifs.
    """
    id_value = int(name_id) if isinstance(name_id, PersonalScoreNameId) else name_id
    return id_value in OBJECTIVE_SCORES


def is_assist_score(name_id: int | PersonalScoreNameId) -> bool:
    """Vérifie si un score est une assistance.

    Args:
        name_id: Valeur de PersonalScoreNameId.

    Returns:
        True si le score est une assistance.
    """
    id_value = int(name_id) if isinstance(name_id, PersonalScoreNameId) else name_id
    return id_value in ASSIST_SCORES


def is_objective_mode(category: int | GameVariantCategory) -> bool:
    """Vérifie si une catégorie est un mode à objectifs.

    Args:
        category: Valeur de GameVariantCategory.

    Returns:
        True si c'est un mode à objectifs.
    """
    cat_value = int(category) if isinstance(category, GameVariantCategory) else category
    return cat_value in OBJECTIVE_MODE_CATEGORIES


def is_slayer_mode(category: int | GameVariantCategory) -> bool:
    """Vérifie si une catégorie est un mode Slayer.

    Args:
        category: Valeur de GameVariantCategory.

    Returns:
        True si c'est un mode Slayer ou variante.
    """
    cat_value = int(category) if isinstance(category, GameVariantCategory) else category
    return cat_value in SLAYER_MODE_CATEGORIES
