# data.py
import json
import pandas as pd
from pathlib import Path

GAMES_FILE = Path(__file__).parent / "games.json"

def load_games() -> dict:
    if not GAMES_FILE.exists():
        return {"games": []}
    with open(GAMES_FILE, "r") as f:
        return json.load(f)

def save_games(data: dict) -> None:
    with open(GAMES_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_player_totals(games: list) -> pd.DataFrame:
    rows = {}
    for game in games:
        for p in game["players"]:
            name = p["name"]
            if name not in rows:
                rows[name] = {
                    "name": name, "games": 0,
                    "pts": 0, "reb": 0, "ast": 0, "stl": 0,
                    "blk": 0, "fls": 0, "to": 0,
                    "fgm": 0, "fga": 0, "tpm": 0, "tpa": 0,
                    "ftm": 0, "fta": 0
                }
            r = rows[name]
            r["games"] += 1
            for stat in ["pts","reb","ast","stl","blk","fls","to","fgm","fga","tpm","tpa","ftm","fta"]:
                r[stat] += p.get(stat, 0)
    return pd.DataFrame(list(rows.values()))

def get_player_averages(games: list) -> pd.DataFrame:
    totals = get_player_totals(games)
    avgs = totals.copy()
    stat_cols = ["pts","reb","ast","stl","blk","fls","to","fgm","fga","tpm","tpa","ftm","fta"]
    for col in stat_cols:
        avgs[col] = (avgs[col] / avgs["games"]).round(1)
    return avgs

def get_derived_stats(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["fg_pct"] = (d["fgm"] / d["fga"].replace(0, float("nan"))).round(3)
    d["tp_pct"] = (d["tpm"] / d["tpa"].replace(0, float("nan"))).round(3)
    d["ft_pct"] = (d["ftm"] / d["fta"].replace(0, float("nan"))).round(3)
    return d
