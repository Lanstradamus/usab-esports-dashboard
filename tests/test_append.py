# tests/test_append.py
import json, pytest
from pathlib import Path
from append_game import validate_game, build_game_record

def test_validate_game_passes_valid():
    game = {
        "id": "game_001",
        "date": "2026-02-21",
        "screenshot": "test.png",
        "opponent": "Brazil",
        "score": {"us": 81, "them": 62},
        "quarters": {"us": [15,20,26,20], "them": [16,14,20,12]},
        "players": []
    }
    assert validate_game(game) == True

def test_validate_game_fails_missing_field():
    game = {"id": "game_001", "opponent": "Brazil"}
    with pytest.raises(ValueError):
        validate_game(game)

def test_build_game_record_sets_id():
    record = build_game_record("Brazil", 81, 62, [15,20,26,20], [16,14,20,12], [], "test.png", "2026-02-21")
    assert record["opponent"] == "Brazil"
    assert record["score"]["us"] == 81
    assert len(record["id"]) > 0
