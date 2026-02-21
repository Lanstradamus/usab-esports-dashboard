# tests/test_data.py
import pytest
from data import load_games, get_player_totals, get_player_averages, get_derived_stats

SAMPLE_GAMES = {
  "games": [
    {
      "id": "game_001",
      "date": "2026-02-21",
      "screenshot": "Screenshot 2026-02-21 134108.png",
      "opponent": "Brazil",
      "score": {"us": 81, "them": 62},
      "quarters": {"us": [15, 20, 26, 20], "them": [16, 14, 20, 12]},
      "players": [
        {
          "name": "OBJ3onTwitch",
          "grade": "A",
          "pts": 21, "reb": 2, "ast": 1, "stl": 1, "blk": 0,
          "fls": 0, "to": 0,
          "fgm": 7, "fga": 12, "tpm": 3, "tpa": 8, "ftm": 4, "fta": 4,
          "confidence": {"overall": 0.95, "low_fields": []}
        }
      ]
    },
    {
      "id": "game_002",
      "date": "2026-02-21",
      "screenshot": "Screenshot 2026-02-21 134134.png",
      "opponent": "Legendary",
      "score": {"us": 71, "them": 51},
      "quarters": {"us": [9, 19, 21, 22], "them": [10, 12, 15, 14]},
      "players": [
        {
          "name": "OBJ3onTwitch",
          "grade": "B+",
          "pts": 14, "reb": 3, "ast": 2, "stl": 0, "blk": 1,
          "fls": 1, "to": 1,
          "fgm": 5, "fga": 10, "tpm": 2, "tpa": 6, "ftm": 2, "fta": 3,
          "confidence": {"overall": 0.88, "low_fields": ["reb"]}
        }
      ]
    }
  ]
}

def test_get_player_totals():
    totals = get_player_totals(SAMPLE_GAMES["games"])
    obj = totals[totals["name"] == "OBJ3onTwitch"].iloc[0]
    assert obj["pts"] == 35
    assert obj["games"] == 2
    assert obj["fgm"] == 12
    assert obj["fga"] == 22

def test_get_player_averages():
    avgs = get_player_averages(SAMPLE_GAMES["games"])
    obj = avgs[avgs["name"] == "OBJ3onTwitch"].iloc[0]
    assert obj["pts"] == 17.5
    assert obj["reb"] == 2.5
    assert obj["games"] == 2

def test_get_derived_stats():
    totals = get_player_totals(SAMPLE_GAMES["games"])
    derived = get_derived_stats(totals)
    obj = derived[derived["name"] == "OBJ3onTwitch"].iloc[0]
    assert round(obj["fg_pct"], 3) == round(12/22, 3)
    assert round(obj["tp_pct"], 3) == round(5/14, 3)
