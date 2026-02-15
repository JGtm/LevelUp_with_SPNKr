"""Tests unitaires pour compute_teammates_signature et fonctions liées."""

from __future__ import annotations

from src.data.sync.transformers import compute_teammates_signature


def test_compute_teammates_signature_basic():
    """Signature avec plusieurs coéquipiers."""
    match_json = {
        "Players": [
            {"PlayerId": "xuid(2533274823110022)", "LastTeamId": 0},
            {"PlayerId": "xuid(2533274858283686)", "LastTeamId": 0},
            {"PlayerId": "xuid(2533274883457349)", "LastTeamId": 0},
            {"PlayerId": "xuid(9999999999999999)", "LastTeamId": 1},
        ],
    }
    sig = compute_teammates_signature(match_json, "2533274823110022", 0)
    assert sig is not None
    assert "2533274858283686" in sig
    assert "2533274883457349" in sig
    assert "2533274823110022" not in sig
    assert "9999999999999999" not in sig
    xuids = sig.split(",")
    assert xuids == sorted(xuids)


def test_compute_teammates_signature_single_teammate():
    """Un seul coéquipier."""
    match_json = {
        "Players": [
            {"PlayerId": "xuid(2533274823110022)", "LastTeamId": 0},
            {"PlayerId": "xuid(2533274858283686)", "LastTeamId": 0},
        ],
    }
    sig = compute_teammates_signature(match_json, "2533274823110022", 0)
    assert sig == "2533274858283686"


def test_compute_teammates_signature_no_teammates():
    """Aucun coéquipier (solo)."""
    match_json = {
        "Players": [
            {"PlayerId": "xuid(2533274823110022)", "LastTeamId": 0},
        ],
    }
    sig = compute_teammates_signature(match_json, "2533274823110022", 0)
    assert sig is None


def test_compute_teammates_signature_no_team_id():
    """team_id None."""
    match_json = {
        "Players": [
            {"PlayerId": "xuid(2533274823110022)", "LastTeamId": 0},
            {"PlayerId": "xuid(2533274858283686)", "LastTeamId": 0},
        ],
    }
    sig = compute_teammates_signature(match_json, "2533274823110022", None)
    assert sig is None


def test_compute_teammates_signature_empty_players():
    """Players vide."""
    match_json = {"Players": []}
    sig = compute_teammates_signature(match_json, "2533274823110022", 0)
    assert sig is None


def test_compute_teammates_signature_no_players_key():
    """Clé Players absente."""
    match_json = {}
    sig = compute_teammates_signature(match_json, "2533274823110022", 0)
    assert sig is None


def test_compute_teammates_signature_xuid_in_dict():
    """PlayerId peut être un dict avec Xuid."""
    match_json = {
        "Players": [
            {"PlayerId": {"Xuid": "2533274823110022"}, "LastTeamId": 0},
            {"PlayerId": {"Xuid": "2533274858283686"}, "LastTeamId": 0},
        ],
    }
    sig = compute_teammates_signature(match_json, "2533274823110022", 0)
    assert sig == "2533274858283686"


def test_compute_teammates_signature_sorted_output():
    """La sortie doit être triée par XUID."""
    match_json = {
        "Players": [
            {"PlayerId": "xuid(2533274883457349)", "LastTeamId": 0},
            {"PlayerId": "xuid(2533274823110022)", "LastTeamId": 0},
            {"PlayerId": "xuid(2533274858283686)", "LastTeamId": 0},
        ],
    }
    sig = compute_teammates_signature(match_json, "2533274858283686", 0)
    assert sig is not None
    assert sig == "2533274823110022,2533274883457349"
