"""
Mapping des Weapon IDs extraits des chunks de film Halo Infinite.

Structure validée (2026-02-02):
- Gamertag en UTF-16 LE
- Event type: [00 TYPE 00] où TYPE = 0x32 (kill), 0x14 (death)
- Timestamp: 2 bytes LE en CENTISECONDES (÷100 = secondes)
- Weapon ID: après prefix [00 00], 2 bytes LE

Validé sur match 7f1bbf06 avec données de référence utilisateur.

Source: .ai/research/BINARY_CHUNK_ANALYSIS_PLAN.md
"""

from __future__ import annotations

# Mapping confirmé
# Sources: matchs Quick Play, Fiesta, BTB + validation manuelle
WEAPON_IDS: dict[int, str] = {
    0xE02E: "Sidekick",  # 57390 - Pistolet de départ
    0x7017: "MA40 AR",  # 28695 - Fusil d'assaut
}

# Le préfixe avant le weapon ID peut avoir deux valeurs :
# - 0x00 : kill standard
# - 0x80 : possiblement un flag (headshot? à investiguer)
WEAPON_PREFIX_FLAGS = {
    0x00: "standard",
    0x80: "flag (headshot?)",
}

# IDs non confirmés (peuvent être du bruit)
UNCONFIRMED_WEAPON_IDS: dict[int, str] = {}

# Constantes pour la conversion de timestamp
# Les timestamps dans les events sont en CENTISECONDES
CENTISEC_PER_SECOND = 100


def get_weapon_name(weapon_id: int) -> str | None:
    """
    Retourne le nom de l'arme pour un weapon_id donné.

    Args:
        weapon_id: ID de l'arme (uint16)

    Returns:
        Nom de l'arme ou None si inconnu
    """
    return WEAPON_IDS.get(weapon_id)


def centisec_to_seconds(centisec: int) -> float:
    """
    Convertit les centisecondes en secondes.

    Args:
        centisec: Timestamp en centisecondes (2 bytes LE)

    Returns:
        Timestamp en secondes
    """
    return centisec / CENTISEC_PER_SECOND


def extract_timestamp(ts_bytes: bytes | list[int]) -> float:
    """
    Extrait le timestamp depuis 2 bytes (little-endian, centisecondes).

    Args:
        ts_bytes: 2 bytes du timestamp

    Returns:
        Timestamp en secondes
    """
    if len(ts_bytes) < 2:
        return 0.0
    centisec = ts_bytes[0] + ts_bytes[1] * 256
    return centisec_to_seconds(centisec)


def extract_weapon_id_from_area(weapon_area: bytes | list[int]) -> int | None:
    """
    Extrait le weapon_id depuis une zone de bytes.

    Cherche le pattern [00 00 WID_LO WID_HI] où WID est le weapon ID.

    Args:
        weapon_area: Zone de bytes où chercher le weapon ID

    Returns:
        Weapon ID ou None si non trouvé
    """
    # Chercher le pattern 00 00 suivi de 2 bytes (weapon ID)
    for i in range(len(weapon_area) - 3):
        if weapon_area[i] == 0 and weapon_area[i + 1] == 0:
            wid = weapon_area[i + 2] + weapon_area[i + 3] * 256
            # Filtrer les weapon IDs connus ou plausibles
            if wid in WEAPON_IDS or 0x1000 < wid < 0xF000:
                return wid
    return None


def is_valid_event(
    timestamp_sec: float,
    max_match_duration_sec: float = 1800.0,
) -> bool:
    """
    Vérifie si un event semble valide (pas du bruit).

    Critères:
    - Timestamp > 10s et < durée max du match

    Args:
        timestamp_sec: Timestamp en secondes
        max_match_duration_sec: Durée max d'un match en secondes (défaut: 30 min)

    Returns:
        True si l'event semble valide
    """
    return 10.0 < timestamp_sec < max_match_duration_sec


# Alias pour compatibilité
def ticks_to_seconds(ticks: int) -> float:
    """DEPRECATED: Utiliser centisec_to_seconds ou extract_timestamp."""
    return ticks / 10_000_000  # Ancien format (ticks Windows)
