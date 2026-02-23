# pending.py
import json
from pathlib import Path
from data import load_games, save_games

PENDING_FILE = Path(__file__).parent / "pending_games.json"

def load_pending() -> dict:
    if not PENDING_FILE.exists():
        return {"pending": []}
    with open(PENDING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_pending(data: dict) -> None:
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def add_to_pending(record: dict) -> None:
    data = load_pending()
    existing = [g["screenshot"] for g in data["pending"]]
    if record["screenshot"] in existing:
        print(f"[SKIP] Already pending: {record['screenshot']}")
        return
    approved = load_games()
    if record["screenshot"] in [g["screenshot"] for g in approved["games"]]:
        print(f"[SKIP] Already approved: {record['screenshot']}")
        return
    data["pending"].append(record)
    save_pending(data)
    print(f"[PENDING] Queued: {record['opponent']} {record['score']['us']}-{record['score']['them']}")

def approve_game(game_id: str, updated_players: list = None, updated_opponent_players: list = None) -> bool:
    pending_data = load_pending()
    game = next((g for g in pending_data["pending"] if g["id"] == game_id), None)
    if not game:
        return False
    if updated_players is not None:
        game["players"] = updated_players
    if updated_opponent_players is not None:
        game["opponent_players"] = updated_opponent_players
    approved = load_games()
    approved["games"].append(game)
    save_games(approved)
    pending_data["pending"] = [g for g in pending_data["pending"] if g["id"] != game_id]
    save_pending(pending_data)
    return True

def reject_game(game_id: str) -> bool:
    pending_data = load_pending()
    before = len(pending_data["pending"])
    pending_data["pending"] = [g for g in pending_data["pending"] if g["id"] != game_id]
    save_pending(pending_data)
    return len(pending_data["pending"]) < before
