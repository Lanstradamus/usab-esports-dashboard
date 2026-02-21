# append_game.py
import json, uuid
from datetime import date
from pathlib import Path
from data import load_games, save_games

REQUIRED_FIELDS = ["id","date","screenshot","opponent","score","quarters","players"]

def validate_game(game: dict) -> bool:
    for field in REQUIRED_FIELDS:
        if field not in game:
            raise ValueError(f"Missing required field: {field}")
    return True

def build_game_record(
    opponent: str,
    us_score: int,
    them_score: int,
    us_quarters: list,
    them_quarters: list,
    players: list,
    screenshot: str,
    game_date: str = None
) -> dict:
    return {
        "id": f"game_{uuid.uuid4().hex[:8]}",
        "date": game_date or str(date.today()),
        "screenshot": screenshot,
        "opponent": opponent,
        "score": {"us": us_score, "them": them_score},
        "quarters": {"us": us_quarters, "them": them_quarters},
        "players": players
    }

def append_game(record: dict) -> None:
    validate_game(record)
    data = load_games()
    existing = [g["screenshot"] for g in data["games"]]
    if record["screenshot"] in existing:
        print(f"[SKIP] {record['screenshot']} already imported.")
        return
    data["games"].append(record)
    save_games(data)
    print(f"[OK] Added game vs {record['opponent']} — {record['score']['us']}-{record['score']['them']}")

if __name__ == "__main__":
    import sys
    record = json.loads(sys.stdin.read())
    append_game(record)
