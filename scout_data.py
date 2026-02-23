# scout_data.py
# Handles all scouting data — completely separate from games.json
import json
import pandas as pd
from pathlib import Path

SCOUT_FILE = Path(__file__).parent / "scouting.json"


def load_scouting() -> dict:
    if not SCOUT_FILE.exists():
        return {"scout_team": "Puerto Rico", "games": [], "pending": []}
    with open(SCOUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_scouting(data: dict) -> None:
    with open(SCOUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def approve_scout_game(game_id: int) -> bool:
    data = load_scouting()
    pending = data.get("pending", [])
    match = next((g for g in pending if g.get("id") == game_id), None)
    if not match:
        return False
    data["pending"] = [g for g in pending if g.get("id") != game_id]
    data.setdefault("games", []).append(match)
    save_scouting(data)
    return True


def reject_scout_game(game_id: int) -> bool:
    data = load_scouting()
    before = len(data.get("pending", []))
    data["pending"] = [g for g in data.get("pending", []) if g.get("id") != game_id]
    save_scouting(data)
    return len(data["pending"]) < before


def get_scout_player_profiles(games: list) -> pd.DataFrame:
    """Aggregate scouted opponent players across all approved scouting games."""
    players: dict = {}
    for game in games:
        for p in game.get("players", []):
            name = p.get("name", "Unknown")
            if name not in players:
                players[name] = {
                    "name": name, "pos": p.get("pos", ""), "games": 0,
                    "pts": 0, "reb": 0, "ast": 0, "stl": 0, "blk": 0,
                    "to": 0, "fgm": 0, "fga": 0, "tpm": 0, "tpa": 0,
                    "ftm": 0, "fta": 0, "wins": 0,
                }
            d = players[name]
            d["games"] += 1
            won = game.get("scout_team_won", False)
            if won:
                d["wins"] += 1
            for stat in ["pts","reb","ast","stl","blk","to","fgm","fga","tpm","tpa","ftm","fta"]:
                d[stat] += p.get(stat, 0)

    rows = []
    for name, d in players.items():
        n   = d["games"]
        fga = d["fga"]; fgm = d["fgm"]
        tpa = d["tpa"]; tpm = d["tpm"]
        fta = d["fta"]; ftm = d["ftm"]
        pts = d["pts"]
        ts_denom  = 2 * (fga + 0.44 * fta)
        ts_pct    = round(pts / ts_denom * 100, 1)      if ts_denom > 0 else None
        fg_pct    = round(fgm / fga * 100, 1)           if fga > 0     else None
        three_pct = round(tpm / tpa * 100, 1)           if tpa > 0     else None
        three_rate = round(tpa / fga * 100, 1)          if fga > 0     else None
        ast_to    = round(d["ast"] / d["to"], 2)        if d["to"] > 0 else None
        poss      = fga + 0.44 * fta + d["to"]
        off_rtg   = round(pts / poss * 100, 1)          if poss > 0    else None
        # Hollinger game score avg
        gs_total  = sum(
            p.get("pts",0) + 0.4*p.get("fgm",0) - 0.7*p.get("fga",0)
            - 0.4*(p.get("fta",0)-p.get("ftm",0)) + 0.7*p.get("reb",0)
            + 0.3*p.get("ast",0) + p.get("stl",0) + 0.7*p.get("blk",0)
            - 0.4*p.get("fls",0) - p.get("to",0)
            for game in games for p in game.get("players",[]) if p.get("name") == name
        )
        avg_gs = round(gs_total / n, 1)

        # Threat level
        threat_score = round(
            (pts/n) * 0.4 + (ts_pct or 50) * 0.2 +
            (d["ast"]/n) * 0.15 + ((d["stl"]+d["blk"])/n) * 0.1 +
            avg_gs * 0.15, 1
        )
        if threat_score >= 25:   threat = "🔴 Elite"
        elif threat_score >= 18: threat = "🟠 High"
        elif threat_score >= 12: threat = "🟡 Moderate"
        else:                    threat = "🟢 Low"

        rows.append({
            "name":        name,
            "pos":         d["pos"],
            "games":       n,
            "win_pct":     round(d["wins"] / n * 100, 1),
            "ppg":         round(pts / n, 1),
            "rpg":         round(d["reb"] / n, 1),
            "apg":         round(d["ast"] / n, 1),
            "spg":         round(d["stl"] / n, 1),
            "bpg":         round(d["blk"] / n, 1),
            "topg":        round(d["to"]  / n, 1),
            "fg_pct":      fg_pct,
            "three_pct":   three_pct,
            "three_rate":  three_rate,
            "ts_pct":      ts_pct,
            "ast_to":      ast_to,
            "off_rtg":     off_rtg,
            "avg_gs":      avg_gs,
            "threat_score": threat_score,
            "threat":      threat,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("ppg", ascending=False).reset_index(drop=True)
    return df


def get_scout_team_tendencies(games: list) -> dict:
    """Team-level tendencies for the scouted team across all their games."""
    if not games:
        return {}

    n = len(games)
    wins   = sum(1 for g in games if g.get("scout_team_won", False))
    pts_f  = [sum(p.get("pts",0) for p in g.get("players",[])) for g in games]
    pts_a  = [g.get("opp_score", 0) for g in games]
    fga_l  = [sum(p.get("fga",0) for p in g.get("players",[])) for g in games]
    fta_l  = [sum(p.get("fta",0) for p in g.get("players",[])) for g in games]
    tpa_l  = [sum(p.get("tpa",0) for p in g.get("players",[])) for g in games]
    tpm_l  = [sum(p.get("tpm",0) for p in g.get("players",[])) for g in games]
    fgm_l  = [sum(p.get("fgm",0) for p in g.get("players",[])) for g in games]
    to_l   = [sum(p.get("to",0)  for p in g.get("players",[])) for g in games]
    ast_l  = [sum(p.get("ast",0) for p in g.get("players",[])) for g in games]
    reb_l  = [sum(p.get("reb",0) for p in g.get("players",[])) for g in games]

    total_fga = sum(fga_l); total_fgm = sum(fgm_l)
    total_fta = sum(fta_l); total_tpa = sum(tpa_l); total_tpm = sum(tpm_l)
    total_to  = sum(to_l);  total_pts = sum(pts_f)

    poss_per_game = [fga_l[i] + 0.44 * fta_l[i] + to_l[i] for i in range(n)]
    avg_poss  = round(sum(poss_per_game) / n, 1)
    off_rtg   = round(total_pts / sum(poss_per_game) * 100, 1) if sum(poss_per_game) > 0 else None
    fg_pct    = round(total_fgm / total_fga * 100, 1)          if total_fga > 0 else None
    three_pct = round(total_tpm / total_tpa * 100, 1)          if total_tpa > 0 else None
    three_rate = round(total_tpa / total_fga * 100, 1)         if total_fga > 0 else None
    ts_denom  = 2 * (total_fga + 0.44 * total_fta)
    ts_pct    = round(total_pts / ts_denom * 100, 1)            if ts_denom > 0 else None
    ast_to    = round(sum(ast_l) / total_to, 2)                 if total_to > 0 else None

    return {
        "games":          n,
        "record":         f"{wins}W-{n-wins}L",
        "win_pct":        round(wins / n * 100, 1),
        "avg_pts_for":    round(sum(pts_f) / n, 1),
        "avg_pts_against": round(sum(pts_a) / n, 1) if any(pts_a) else None,
        "avg_poss":       avg_poss,
        "off_rtg":        off_rtg,
        "fg_pct":         fg_pct,
        "three_pct":      three_pct,
        "three_rate":     three_rate,
        "ts_pct":         ts_pct,
        "ast_to":         ast_to,
        "avg_ast":        round(sum(ast_l) / n, 1),
        "avg_reb":        round(sum(reb_l) / n, 1),
        "avg_to":         round(sum(to_l)  / n, 1),
    }
