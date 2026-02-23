# data.py
import json
import pandas as pd
from pathlib import Path

GAMES_FILE = Path(__file__).parent / "games.json"

# Canonical player names — maps OCR variants to correct spelling
NAME_ALIASES = {
    "MamalmDatMan":  "MamaImDatMan",
    "MamalmDatMan_": "MamaImDatMan",
    "MamaImDatMan_": "MamaImDatMan",
    "JohnnyRed_":    "JohhnyRed_",
}

def normalize_name(name: str) -> str:
    return NAME_ALIASES.get(name, name)

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
    pos_counts = {}  # name -> {pos: count} for picking primary position
    for game in games:
        for p in game["players"]:
            name = normalize_name(p["name"])
            pos  = p.get("pos", "")
            if name not in rows:
                rows[name] = {
                    "name": name, "pos": pos, "games": 0,
                    "pts": 0, "reb": 0, "ast": 0, "stl": 0,
                    "blk": 0, "fls": 0, "to": 0,
                    "fgm": 0, "fga": 0, "tpm": 0, "tpa": 0,
                    "ftm": 0, "fta": 0
                }
                pos_counts[name] = {}
            r = rows[name]
            r["games"] += 1
            for stat in ["pts","reb","ast","stl","blk","fls","to","fgm","fga","tpm","tpa","ftm","fta"]:
                r[stat] += p.get(stat, 0)
            pos_counts[name][pos] = pos_counts[name].get(pos, 0) + 1
    # Set primary position (most games at that pos)
    for name, r in rows.items():
        r["pos"] = max(pos_counts[name], key=pos_counts[name].get)
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

def get_advanced_stats(games: list) -> pd.DataFrame:
    """Compute per-player advanced stats across all approved games."""
    # Accumulate per-game scores and totals keyed by name only
    player_games: dict = {}  # name -> list of per-game dicts
    pos_counts: dict = {}    # name -> {pos: count} for primary pos

    for game in games:
        usa_won = game["score"]["us"] > game["score"]["them"]
        for p in game["players"]:
            name = normalize_name(p["name"])
            pos  = p.get("pos", "")
            if name not in player_games:
                player_games[name] = []
                pos_counts[name] = {}
            key = name

            pts  = p.get("pts", 0)
            fgm  = p.get("fgm", 0)
            fga  = p.get("fga", 0)
            tpm  = p.get("tpm", 0)
            ftm  = p.get("ftm", 0)
            fta  = p.get("fta", 0)
            reb  = p.get("reb", 0)
            ast  = p.get("ast", 0)
            stl  = p.get("stl", 0)
            blk  = p.get("blk", 0)
            fls  = p.get("fls", 0)
            to   = p.get("to",  0)

            # Hollinger Game Score
            gs = (pts
                  + 0.4 * fgm
                  - 0.7 * fga
                  - 0.4 * (fta - ftm)
                  + 0.7 * reb
                  + 0.3 * ast
                  + stl
                  + 0.7 * blk
                  - 0.4 * fls
                  - to)

            tpa  = p.get("tpa", 0)
            player_games[key].append({
                "gs":      gs,
                "pts":     pts,
                "fgm":     fgm,
                "fga":     fga,
                "tpm":     tpm,
                "tpa":     tpa,
                "ftm":     ftm,
                "fta":     fta,
                "ast":     ast,
                "to":      to,
                "won":     usa_won,
            })
            pos_counts[name][pos] = pos_counts[name].get(pos, 0) + 1

    rows = []
    for name, pg_list in player_games.items():
        n = len(pg_list)
        pos = max(pos_counts[name], key=pos_counts[name].get)

        # Game Score stats
        gs_values = [g["gs"] for g in pg_list]
        avg_gs = round(sum(gs_values) / n, 1)
        if n > 1:
            gs_series = pd.Series(gs_values)
            gs_std = round(float(gs_series.std()), 1)
        else:
            gs_std = None

        # Totals
        total_pts  = sum(g["pts"]  for g in pg_list)
        total_fgm  = sum(g["fgm"]  for g in pg_list)
        total_fga  = sum(g["fga"]  for g in pg_list)
        total_tpm  = sum(g["tpm"]  for g in pg_list)
        total_tpa  = sum(g["tpa"]  for g in pg_list)
        total_ftm  = sum(g["ftm"]  for g in pg_list)
        total_fta  = sum(g["fta"]  for g in pg_list)
        total_ast  = sum(g["ast"]  for g in pg_list)
        total_to   = sum(g["to"]   for g in pg_list)
        total_wins = sum(1 for g in pg_list if g["won"])

        # True Shooting %: PTS / (2 * (FGA + 0.44 * FTA))
        ts_denom = 2 * (total_fga + 0.44 * total_fta)
        ts_pct = round(total_pts / ts_denom * 100, 1) if ts_denom > 0 else None

        # Effective FG%: (FGM + 0.5 * 3PM) / FGA
        efg_pct = round((total_fgm + 0.5 * total_tpm) / total_fga * 100, 1) if total_fga > 0 else None

        # AST/TO ratio (totals)
        ast_to = round(total_ast / total_to, 2) if total_to > 0 else None

        # Scoring load: (FGA + 0.44 * FTA) / games
        scoring_load = round((total_fga + 0.44 * total_fta) / n, 1)

        # Win %
        win_pct = round(total_wins / n * 100, 1)

        # 3PT stats per game and %
        three_pm_pg   = round(total_tpm / n, 1)
        three_pa_pg   = round(total_tpa / n, 1)
        three_pct     = round(total_tpm / total_tpa * 100, 1) if total_tpa > 0 else None
        # 3PT rate: % of FGA that are 3s
        three_rate    = round(total_tpa / total_fga * 100, 1) if total_fga > 0 else None

        rows.append({
            "name":           name,
            "pos":            pos,
            "games":          n,
            "win_pct":        win_pct,
            "avg_game_score": avg_gs,
            "gs_std":         gs_std,
            "ts_pct":         ts_pct,
            "efg_pct":        efg_pct,
            "ast_to":         ast_to,
            "scoring_load":   scoring_load,
            "three_pm_pg":    three_pm_pg,
            "three_pa_pg":    three_pa_pg,
            "three_pct":      three_pct,
            "three_rate":     three_rate,
        })

    return pd.DataFrame(rows, columns=[
        "name", "pos", "games", "win_pct",
        "avg_game_score", "gs_std", "ts_pct", "efg_pct",
        "ast_to", "scoring_load",
        "three_pm_pg", "three_pa_pg", "three_pct", "three_rate",
    ])


def get_win_loss_splits(games: list) -> pd.DataFrame:
    """Per-player stats split by win vs loss games, including Hollinger Game Score averages."""
    # accumulators: (name, pos) -> {wins: {...}, losses: {...}}
    buckets: dict = {}

    for game in games:
        usa_won = game["score"]["us"] > game["score"]["them"]
        for p in game["players"]:
            name = normalize_name(p["name"])
            pos  = p.get("pos", "")
            key  = (name, pos)
            if key not in buckets:
                buckets[key] = {
                    "name": name, "pos": pos,
                    "w_pts": [], "w_reb": [], "w_ast": [], "w_gs": [],
                    "l_pts": [], "l_reb": [], "l_ast": [], "l_gs": [],
                }

            pts = p.get("pts", 0)
            fgm = p.get("fgm", 0)
            fga = p.get("fga", 0)
            ftm = p.get("ftm", 0)
            fta = p.get("fta", 0)
            reb = p.get("reb", 0)
            ast = p.get("ast", 0)
            stl = p.get("stl", 0)
            blk = p.get("blk", 0)
            fls = p.get("fls", 0)
            to  = p.get("to",  0)

            gs = (pts
                  + 0.4 * fgm
                  - 0.7 * fga
                  - 0.4 * (fta - ftm)
                  + 0.7 * reb
                  + 0.3 * ast
                  + stl
                  + 0.7 * blk
                  - 0.4 * fls
                  - to)

            b = buckets[key]
            if usa_won:
                b["w_pts"].append(pts)
                b["w_reb"].append(reb)
                b["w_ast"].append(ast)
                b["w_gs"].append(gs)
            else:
                b["l_pts"].append(pts)
                b["l_reb"].append(reb)
                b["l_ast"].append(ast)
                b["l_gs"].append(gs)

    def _avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else None

    rows = []
    for (name, pos), b in buckets.items():
        rows.append({
            "name":    name,
            "pos":     pos,
            "w_games": len(b["w_pts"]),
            "l_games": len(b["l_pts"]),
            "w_pts":   _avg(b["w_pts"]),
            "l_pts":   _avg(b["l_pts"]),
            "w_reb":   _avg(b["w_reb"]),
            "l_reb":   _avg(b["l_reb"]),
            "w_ast":   _avg(b["w_ast"]),
            "l_ast":   _avg(b["l_ast"]),
            "w_gs":    _avg(b["w_gs"]),
            "l_gs":    _avg(b["l_gs"]),
        })

    return pd.DataFrame(rows, columns=[
        "name", "pos", "w_games", "l_games",
        "w_pts", "l_pts", "w_reb", "l_reb",
        "w_ast", "l_ast", "w_gs", "l_gs",
    ])


def get_scoring_profile(games: list) -> pd.DataFrame:
    """Per-player shooting and scoring breakdown with rate statistics."""
    totals: dict = {}

    for game in games:
        for p in game["players"]:
            name = normalize_name(p["name"])
            pos  = p.get("pos", "")
            key  = (name, pos)
            if key not in totals:
                totals[key] = {
                    "name": name, "pos": pos, "games": 0,
                    "pts": 0, "fgm": 0, "fga": 0,
                    "tpm": 0, "tpa": 0,
                    "ftm": 0, "fta": 0,
                    "stl": 0, "blk": 0, "to": 0,
                }
            t = totals[key]
            t["games"] += 1
            for stat in ["pts", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "stl", "blk", "to"]:
                t[stat] += p.get(stat, 0)

    rows = []
    for (name, pos), t in totals.items():
        n        = t["games"]
        pts      = t["pts"]
        fgm      = t["fgm"]
        fga      = t["fga"]
        tpm      = t["tpm"]
        tpa      = t["tpa"]
        ftm      = t["ftm"]
        fta      = t["fta"]
        stl      = t["stl"]
        blk      = t["blk"]
        to       = t["to"]

        two_pm   = fgm - tpm
        two_pa   = fga - tpa

        two_pct          = round(two_pm / two_pa * 100, 1)       if two_pa > 0  else None
        three_rate        = round(tpa   / fga    * 100, 1)       if fga    > 0  else None
        ft_rate           = round(fta   / fga    * 100, 1)       if fga    > 0  else None
        pct_pts_from_3    = round(tpm * 3 / pts  * 100, 1)       if pts    > 0  else None
        pct_pts_from_2    = round(two_pm * 2 / pts * 100, 1)     if pts    > 0  else None
        pct_pts_from_ft   = round(ftm   / pts    * 100, 1)       if pts    > 0  else None
        stocks_per_game   = round((stl + blk) / n, 1)
        to_denom          = fga + 0.44 * fta + to
        to_rate           = round(to / to_denom * 100, 1)        if to_denom > 0 else None

        rows.append({
            "name":             name,
            "pos":              pos,
            "games":            n,
            "two_pct":          two_pct,
            "three_rate":       three_rate,
            "ft_rate":          ft_rate,
            "pct_pts_from_2":   pct_pts_from_2,
            "pct_pts_from_3":   pct_pts_from_3,
            "pct_pts_from_ft":  pct_pts_from_ft,
            "stocks_per_game":  stocks_per_game,
            "to_rate":          to_rate,
        })

    return pd.DataFrame(rows, columns=[
        "name", "pos", "games",
        "two_pct", "three_rate", "ft_rate",
        "pct_pts_from_2", "pct_pts_from_3", "pct_pts_from_ft",
        "stocks_per_game", "to_rate",
    ])


def get_scoring_shares(games: list) -> pd.DataFrame:
    """Per-player average scoring share and lead-scorer game count."""
    accum: dict = {}  # (name, pos) -> {"games": int, "shares": list, "lead_scorer": int}

    for game in games:
        usa_players = game["players"]
        team_total  = sum(p.get("pts", 0) for p in usa_players)

        if team_total == 0:
            # Register games played but skip share computation
            for p in usa_players:
                name = normalize_name(p["name"])
                pos  = p.get("pos", "")
                key  = (name, pos)
                if key not in accum:
                    accum[key] = {"name": name, "pos": pos, "games": 0, "shares": [], "lead_scorer": 0}
                accum[key]["games"] += 1
            continue

        # Determine lead scorer(s) — highest pts value in this game
        max_pts = max(p.get("pts", 0) for p in usa_players)

        for p in usa_players:
            name    = normalize_name(p["name"])
            pos     = p.get("pos", "")
            key     = (name, pos)
            if key not in accum:
                accum[key] = {"name": name, "pos": pos, "games": 0, "shares": [], "lead_scorer": 0}

            pts = p.get("pts", 0)
            accum[key]["games"] += 1
            accum[key]["shares"].append(pts / team_total * 100)
            if pts == max_pts:
                accum[key]["lead_scorer"] += 1

    rows = []
    for (name, pos), a in accum.items():
        shares = a["shares"]
        avg_share = round(sum(shares) / len(shares), 1) if shares else None
        rows.append({
            "name":              name,
            "pos":               pos,
            "games":             a["games"],
            "avg_scoring_share": avg_share,
            "lead_scorer_games": a["lead_scorer"],
        })

    return pd.DataFrame(rows, columns=[
        "name", "pos", "games", "avg_scoring_share", "lead_scorer_games",
    ])


def get_positional_matchups(games: list) -> pd.DataFrame:
    """USA vs opponent stat comparison by position index across all games."""
    POS_LABELS = ["PG", "SG", "SF", "PF", "C"]

    # pos_index (0-4) -> accumulator dict
    pos_data: dict = {i: {
        "games":      0,
        "our_pts":    0, "opp_pts":    0,
        "our_gs":     0.0, "opp_gs":  0.0,
        "our_reb":    0, "opp_reb":    0,
        "our_ast":    0, "opp_ast":    0,
        "our_stl":    0, "opp_stl":    0,
        "our_blk":    0, "opp_blk":    0,
        "usa_wins":   0,
    } for i in range(5)}

    def _gs(p):
        pts = p.get("pts", 0)
        fgm = p.get("fgm", 0)
        fga = p.get("fga", 0)
        ftm = p.get("ftm", 0)
        fta = p.get("fta", 0)
        reb = p.get("reb", 0)
        ast = p.get("ast", 0)
        stl = p.get("stl", 0)
        blk = p.get("blk", 0)
        fls = p.get("fls", 0)
        to  = p.get("to",  0)
        return (pts + 0.4*fgm - 0.7*fga - 0.4*(fta-ftm)
                + 0.7*reb + 0.3*ast + stl + 0.7*blk - 0.4*fls - to)

    for game in games:
        usa_players  = game["players"]
        opp_players  = game.get("opponent_players", [])
        for i in range(min(5, len(usa_players), len(opp_players))):
            u = usa_players[i]
            o = opp_players[i]
            d = pos_data[i]
            d["games"]    += 1
            d["our_pts"]  += u.get("pts", 0)
            d["opp_pts"]  += o.get("pts", 0)
            d["our_gs"]   += _gs(u)
            d["opp_gs"]   += _gs(o)
            d["our_reb"]  += u.get("reb", 0)
            d["opp_reb"]  += o.get("reb", 0)
            d["our_ast"]  += u.get("ast", 0)
            d["opp_ast"]  += o.get("ast", 0)
            d["our_stl"]  += u.get("stl", 0)
            d["opp_stl"]  += o.get("stl", 0)
            d["our_blk"]  += u.get("blk", 0)
            d["opp_blk"]  += o.get("blk", 0)
            if u.get("pts", 0) > o.get("pts", 0):
                d["usa_wins"] += 1

    rows = []
    for i in range(5):
        d = pos_data[i]
        g = d["games"]
        if g == 0:
            continue
        rows.append({
            "pos":              POS_LABELS[i],
            "games":            g,
            "our_avg_pts":      round(d["our_pts"]  / g, 1),
            "opp_avg_pts":      round(d["opp_pts"]  / g, 1),
            "our_avg_gs":       round(d["our_gs"]   / g, 1),
            "opp_avg_gs":       round(d["opp_gs"]   / g, 1),
            "our_reb":          round(d["our_reb"]  / g, 1),
            "opp_reb":          round(d["opp_reb"]  / g, 1),
            "our_ast":          round(d["our_ast"]  / g, 1),
            "opp_ast":          round(d["opp_ast"]  / g, 1),
            "our_stocks":       round((d["our_stl"] + d["our_blk"]) / g, 1),
            "opp_stocks":       round((d["opp_stl"] + d["opp_blk"]) / g, 1),
            "usa_wins_matchup": int(round(d["usa_wins"] / g * 100, 0)),
        })

    return pd.DataFrame(rows, columns=[
        "pos", "games",
        "our_avg_pts", "opp_avg_pts",
        "our_avg_gs",  "opp_avg_gs",
        "our_reb",     "opp_reb",
        "our_ast",     "opp_ast",
        "our_stocks",  "opp_stocks",
        "usa_wins_matchup",
    ])


def get_close_game_stats(games: list) -> pd.DataFrame:
    """Per-player performance in close games (margin <= 10) vs non-close games."""
    buckets: dict = {}

    for game in games:
        margin   = abs(game["score"]["us"] - game["score"]["them"])
        is_close = margin <= 10

        for p in game["players"]:
            name = normalize_name(p["name"])
            pos  = p.get("pos", "")
            key  = (name, pos)
            if key not in buckets:
                buckets[key] = {
                    "name": name, "pos": pos,
                    "close_gs":  [], "close_pts":  [],
                    "other_gs":  [], "other_pts":  [],
                }

            pts = p.get("pts", 0)
            fgm = p.get("fgm", 0)
            fga = p.get("fga", 0)
            ftm = p.get("ftm", 0)
            fta = p.get("fta", 0)
            reb = p.get("reb", 0)
            ast = p.get("ast", 0)
            stl = p.get("stl", 0)
            blk = p.get("blk", 0)
            fls = p.get("fls", 0)
            to  = p.get("to",  0)

            gs = (pts
                  + 0.4 * fgm
                  - 0.7 * fga
                  - 0.4 * (fta - ftm)
                  + 0.7 * reb
                  + 0.3 * ast
                  + stl
                  + 0.7 * blk
                  - 0.4 * fls
                  - to)

            b = buckets[key]
            if is_close:
                b["close_gs"].append(gs)
                b["close_pts"].append(pts)
            else:
                b["other_gs"].append(gs)
                b["other_pts"].append(pts)

    def _avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else None

    rows = []
    for (name, pos), b in buckets.items():
        rows.append({
            "name":        name,
            "pos":         pos,
            "close_games": len(b["close_gs"]),
            "close_gs":    _avg(b["close_gs"]),
            "close_pts":   _avg(b["close_pts"]),
            "other_games": len(b["other_gs"]),
            "other_gs":    _avg(b["other_gs"]),
            "other_pts":   _avg(b["other_pts"]),
        })

    return pd.DataFrame(rows, columns=[
        "name", "pos",
        "close_games", "close_gs", "close_pts",
        "other_games", "other_gs", "other_pts",
    ])


def get_usage_and_pie(games: list) -> pd.DataFrame:
    """
    Usage Rate (USG%) and Player Impact Estimate (PIE) per player.
    USG%  = 100 * (FGA + 0.44*FTA + TO) / team_possessions
    PIE   = (PTS + REB + AST + STL + BLK - FGmiss - FTmiss - TO)
            / (team_PTS + team_REB + team_AST + team_STL + team_BLK
               - team_FGmiss - team_FTmiss - team_TO)
    """
    player_acc: dict = {}
    for game in games:
        players = game["players"]
        # Team totals for this game
        t_pts  = sum(p.get("pts",0)  for p in players)
        t_reb  = sum(p.get("reb",0)  for p in players)
        t_ast  = sum(p.get("ast",0)  for p in players)
        t_stl  = sum(p.get("stl",0)  for p in players)
        t_blk  = sum(p.get("blk",0)  for p in players)
        t_fga  = sum(p.get("fga",0)  for p in players)
        t_fgm  = sum(p.get("fgm",0)  for p in players)
        t_fta  = sum(p.get("fta",0)  for p in players)
        t_ftm  = sum(p.get("ftm",0)  for p in players)
        t_to   = sum(p.get("to",0)   for p in players)
        t_fgmiss = t_fga - t_fgm
        t_ftmiss = t_fta - t_ftm
        t_poss = t_fga + 0.44 * t_fta + t_to  # team possessions proxy
        t_pie_denom = (t_pts + t_reb + t_ast + t_stl + t_blk
                       - t_fgmiss - t_ftmiss - t_to)

        for p in players:
            name = normalize_name(p["name"])
            pos  = p.get("pos", "")
            key  = (name, pos)
            if key not in player_acc:
                player_acc[key] = {"name": name, "pos": pos, "games": 0,
                                   "usg_list": [], "pie_list": []}

            pts  = p.get("pts", 0); fgm = p.get("fgm", 0); fga = p.get("fga", 0)
            ftm  = p.get("ftm", 0); fta = p.get("fta", 0)
            reb  = p.get("reb", 0); ast = p.get("ast", 0)
            stl  = p.get("stl", 0); blk = p.get("blk", 0); to  = p.get("to", 0)
            fgmiss = fga - fgm; ftmiss = fta - ftm
            p_poss = fga + 0.44 * fta + to

            usg = (p_poss / t_poss * 100) if t_poss > 0 else None
            pie_num = pts + reb + ast + stl + blk - fgmiss - ftmiss - to
            pie = (pie_num / t_pie_denom * 100) if t_pie_denom != 0 else None

            d = player_acc[key]
            d["games"] += 1
            if usg is not None: d["usg_list"].append(usg)
            if pie is not None: d["pie_list"].append(pie)

    rows = []
    for (name, pos), d in player_acc.items():
        rows.append({
            "name":    name,
            "pos":     pos,
            "games":   d["games"],
            "usg_pct": round(sum(d["usg_list"]) / len(d["usg_list"]), 1) if d["usg_list"] else None,
            "pie":     round(sum(d["pie_list"])  / len(d["pie_list"]),  1) if d["pie_list"]  else None,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("pie", ascending=False, na_position="last").reset_index(drop=True)
    return df


def get_defensive_impact(games: list) -> pd.DataFrame:
    """
    Defensive stats summary per player: STL, BLK, Stocks/G,
    Def Rating proxy (opp pts when this player plays, avg),
    Foul trouble rate.
    """
    buckets: dict = {}
    for game in games:
        opp_pts  = game["score"]["them"]
        for p in game["players"]:
            name = normalize_name(p["name"])
            pos  = p.get("pos", "")
            key  = (name, pos)
            if key not in buckets:
                buckets[key] = {"name": name, "pos": pos,
                                "games": 0, "stl": 0, "blk": 0,
                                "fls": 0, "opp_pts_list": []}
            d = buckets[key]
            d["games"]    += 1
            d["stl"]      += p.get("stl", 0)
            d["blk"]      += p.get("blk", 0)
            d["fls"]      += p.get("fls", 0)
            d["opp_pts_list"].append(opp_pts)

    rows = []
    for (name, pos), d in buckets.items():
        n = d["games"]
        rows.append({
            "name":           name,
            "pos":            pos,
            "games":          n,
            "stl_pg":         round(d["stl"] / n, 1),
            "blk_pg":         round(d["blk"] / n, 1),
            "stocks_pg":      round((d["stl"] + d["blk"]) / n, 1),
            "fls_pg":         round(d["fls"] / n, 1),
            "foul_rate":      round(d["fls"] / n / 4 * 100, 1),  # % of max 4 fouls used
            "avg_opp_pts":    round(sum(d["opp_pts_list"]) / n, 1),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("stocks_pg", ascending=False).reset_index(drop=True)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# REVOLUTIONARY ANALYTICS ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def _calc_gs(p: dict) -> float:
    """Hollinger Game Score for a single player dict."""
    pts = p.get("pts", 0); fgm = p.get("fgm", 0); fga = p.get("fga", 0)
    ftm = p.get("ftm", 0); fta = p.get("fta", 0); reb = p.get("reb", 0)
    ast = p.get("ast", 0); stl = p.get("stl", 0); blk = p.get("blk", 0)
    fls = p.get("fls", 0); to  = p.get("to",  0)
    return (pts + 0.4*fgm - 0.7*fga - 0.4*(fta - ftm)
            + 0.7*reb + 0.3*ast + stl + 0.7*blk - 0.4*fls - to)


def get_quarter_stats(games: list) -> pd.DataFrame:
    """Per-game quarter breakdown for team scoring momentum."""
    rows = []
    for game in games:
        q    = game.get("quarters", {})
        us   = q.get("us",   [0, 0, 0, 0])
        them = q.get("them", [0, 0, 0, 0])
        # pad to 4 quarters
        us   = (us   + [0, 0, 0, 0])[:4]
        them = (them + [0, 0, 0, 0])[:4]
        margin = game["score"]["us"] - game["score"]["them"]
        rows.append({
            "game_id":       game["id"],
            "date":          game["date"],
            "opponent":      game["opponent"],
            "result":        game.get("result", "W"),
            "q1_us":         us[0], "q2_us": us[1], "q3_us": us[2], "q4_us": us[3],
            "q1_them":       them[0], "q2_them": them[1], "q3_them": them[2], "q4_them": them[3],
            "final_margin":  margin,
            "best_quarter":  ["Q1", "Q2", "Q3", "Q4"][us.index(max(us))],
            "worst_quarter": ["Q1", "Q2", "Q3", "Q4"][us.index(min(us))],
        })
    return pd.DataFrame(rows)


def get_momentum_analysis(games: list) -> dict:
    """Quarter-by-quarter team momentum: avg pts scored/allowed per quarter."""
    q_us   = [[], [], [], []]
    q_them = [[], [], [], []]
    for game in games:
        q    = game.get("quarters", {})
        us   = (q.get("us",   [0, 0, 0, 0]) + [0, 0, 0, 0])[:4]
        them = (q.get("them", [0, 0, 0, 0]) + [0, 0, 0, 0])[:4]
        for i in range(4):
            q_us[i].append(us[i])
            q_them[i].append(them[i])

    def _avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else 0

    us_avgs   = [_avg(q_us[i])   for i in range(4)]
    them_avgs = [_avg(q_them[i]) for i in range(4)]
    labels    = ["Q1", "Q2", "Q3", "Q4"]

    comeback_wins = sum(
        1 for g in games
        if g.get("result", "") == "W"
        and (g.get("quarters", {}).get("us",   [0]*4) + [0]*4)[:4][2]
          < (g.get("quarters", {}).get("them", [0]*4) + [0]*4)[:4][2]
    )

    return {
        "quarters":         labels,
        "us_avg":           us_avgs,
        "them_avg":         them_avgs,
        "us_best_quarter":  labels[us_avgs.index(max(us_avgs))]  if us_avgs else "N/A",
        "us_worst_quarter": labels[us_avgs.index(min(us_avgs))]  if us_avgs else "N/A",
        "comeback_wins":    comeback_wins,
        "q_diff":           [round(us_avgs[i] - them_avgs[i], 1) for i in range(4)],
    }


def get_team_stats_by_game(games: list) -> pd.DataFrame:
    """Team-level stats per game for trend charts."""
    rows = []
    for i, game in enumerate(games):
        players     = game["players"]
        opp_players = game.get("opponent_players", [])
        us_pts   = game["score"]["us"]
        them_pts = game["score"]["them"]
        us_reb   = sum(p.get("reb", 0) for p in players)
        us_ast   = sum(p.get("ast", 0) for p in players)
        us_stl   = sum(p.get("stl", 0) for p in players)
        us_blk   = sum(p.get("blk", 0) for p in players)
        us_to    = sum(p.get("to",  0) for p in players)
        us_fga   = sum(p.get("fga", 0) for p in players)
        us_fgm   = sum(p.get("fgm", 0) for p in players)
        us_tpa   = sum(p.get("tpa", 0) for p in players)
        us_tpm   = sum(p.get("tpm", 0) for p in players)
        us_fta   = sum(p.get("fta", 0) for p in players)
        them_reb = sum(p.get("reb", 0) for p in opp_players)
        them_ast = sum(p.get("ast", 0) for p in opp_players)
        them_to  = sum(p.get("to",  0) for p in opp_players)

        pace_est  = round(us_fga + 0.44 * us_fta + us_to, 1)
        fg_pct    = round(us_fgm / us_fga * 100, 1) if us_fga > 0 else None
        three_pct = round(us_tpm / us_tpa * 100, 1) if us_tpa > 0 else None
        ts_denom  = 2 * (us_fga + 0.44 * us_fta)
        ts_pct    = round(us_pts / ts_denom * 100, 1) if ts_denom > 0 else None
        ast_to    = round(us_ast / us_to, 2) if us_to > 0 else None
        team_gs   = round(sum(_calc_gs(p) for p in players), 1)

        opp_short = game["opponent"][:10]
        rows.append({
            "game_num":     i + 1,
            "game_label":   f"G{i+1} {opp_short}",
            "game_id":      game["id"],
            "date":         game["date"],
            "opponent":     game["opponent"],
            "result":       game.get("result", "W"),
            "us_pts":       us_pts,   "them_pts":  them_pts,
            "margin":       us_pts - them_pts,
            "us_reb":       us_reb,   "them_reb":  them_reb,
            "us_ast":       us_ast,   "them_ast":  them_ast,
            "us_stl":       us_stl,
            "us_blk":       us_blk,
            "us_to":        us_to,    "them_to":   them_to,
            "us_fg_pct":    fg_pct,
            "us_three_pct": three_pct,
            "us_ts_pct":    ts_pct,
            "ast_to_ratio": ast_to,
            "pace_est":     pace_est,
            "team_gs":      team_gs,
            "reb_margin":   us_reb - them_reb,
            "to_margin":    them_to - us_to,  # positive = we force more TOs than we commit
        })
    return pd.DataFrame(rows)


def get_opponent_player_intel(games: list) -> pd.DataFrame:
    """Aggregate stats on every opponent player ever faced."""
    opp_data: dict = {}
    for game in games:
        opp_name    = game.get("opponent", "Unknown")
        opp_players = game.get("opponent_players", [])
        for p in opp_players:
            name = p.get("name", "Unknown")
            if name not in opp_data:
                opp_data[name] = {
                    "name": name, "teams": set(), "games": 0, "pos": p.get("pos", ""),
                    "pts": 0, "reb": 0, "ast": 0, "stl": 0, "blk": 0, "to": 0,
                    "fgm": 0, "fga": 0, "tpm": 0, "tpa": 0, "ftm": 0, "fta": 0,
                    "usa_wins_when_faced": 0,
                }
            d = opp_data[name]
            d["teams"].add(opp_name)
            d["games"] += 1
            if game["score"]["us"] > game["score"]["them"]:
                d["usa_wins_when_faced"] += 1
            for stat in ["pts", "reb", "ast", "stl", "blk", "to",
                         "fgm", "fga", "tpm", "tpa", "ftm", "fta"]:
                d[stat] += p.get(stat, 0)

    rows = []
    for name, d in opp_data.items():
        n   = d["games"]
        fga = d["fga"]; fgm = d["fgm"]; tpm = d["tpm"]
        tpa = d["tpa"]; ftm = d["ftm"]; fta = d["fta"]; pts = d["pts"]
        ts_denom  = 2 * (fga + 0.44 * fta)
        ts_pct    = round(pts / ts_denom * 100, 1) if ts_denom > 0 else None
        efg_pct   = round((fgm + 0.5 * tpm) / fga * 100, 1) if fga > 0 else None
        avg_pts   = round(d["pts"] / n, 1)
        avg_ast   = round(d["ast"] / n, 1)
        threat    = round(avg_pts * 0.4 + avg_ast * 0.3 + (ts_pct or 50) * 0.3, 1)
        threat_lv = ("🔴 Elite" if threat > 25 else
                     "🟠 High"  if threat > 18 else
                     "🟡 Moderate" if threat > 12 else
                     "🟢 Low")
        rows.append({
            "name":            name,
            "pos":             d["pos"],
            "teams":           ", ".join(sorted(d["teams"])),
            "games":           n,
            "avg_pts":         avg_pts,
            "avg_reb":         round(d["reb"] / n, 1),
            "avg_ast":         avg_ast,
            "avg_stl":         round(d["stl"] / n, 1),
            "avg_blk":         round(d["blk"] / n, 1),
            "avg_to":          round(d["to"]  / n, 1),
            "fg_pct":          round(fgm / fga * 100, 1) if fga > 0 else None,
            "three_pct":       round(tpm / tpa * 100, 1) if tpa > 0 else None,
            "ts_pct":          ts_pct,
            "efg_pct":         efg_pct,
            "usa_win_pct":     round(d["usa_wins_when_faced"] / n * 100, 1),
            "threat_score":    threat,
            "threat_level":    threat_lv,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("threat_score", ascending=False).reset_index(drop=True)
    return df


def get_player_impact_index(games: list) -> pd.DataFrame:
    """Composite 0-100 impact score per player (one row per player, primary position)."""
    adv   = get_advanced_stats(games)
    share = get_scoring_shares(games)
    prof  = get_scoring_profile(games)

    if adv.empty:
        return pd.DataFrame()

    # Deduplicate adv by name — keep the row with the most games played (primary position)
    adv_dedup = (adv.sort_values("games", ascending=False)
                    .drop_duplicates(subset=["name"], keep="first")
                    .reset_index(drop=True))

    # Similarly deduplicate share and prof by name
    share_dedup = (share.sort_values("games", ascending=False)
                        .drop_duplicates(subset=["name"], keep="first"))
    prof_dedup  = (prof.sort_values("games", ascending=False)
                       .drop_duplicates(subset=["name"], keep="first"))

    df = adv_dedup.merge(share_dedup[["name", "avg_scoring_share"]], on="name", how="left")
    df = df.merge(prof_dedup[["name", "stocks_per_game", "to_rate"]], on="name", how="left")

    def norm(series):
        mn, mx = series.min(), series.max()
        if mx == mn:
            return pd.Series([50.0] * len(series), index=series.index)
        return (series - mn) / (mx - mn) * 100

    df["gs_norm"]     = norm(df["avg_game_score"].fillna(0))
    df["ts_norm"]     = norm(df["ts_pct"].fillna(50))
    df["asto_norm"]   = norm(df["ast_to"].fillna(1))
    df["stocks_norm"] = norm(df["stocks_per_game"].fillna(0))
    df["share_norm"]  = norm(df["avg_scoring_share"].fillna(20))
    df["to_inv"]      = norm(100 - df["to_rate"].fillna(15))

    df["impact_score"] = (
        df["gs_norm"]     * 0.30 +
        df["ts_norm"]     * 0.20 +
        df["asto_norm"]   * 0.15 +
        df["stocks_norm"] * 0.15 +
        df["share_norm"]  * 0.10 +
        df["to_inv"]      * 0.10
    ).round(1)

    return (df[["name", "pos", "games", "avg_game_score", "ts_pct", "ast_to",
                "stocks_per_game", "avg_scoring_share", "to_rate", "impact_score"]]
            .sort_values("impact_score", ascending=False)
            .reset_index(drop=True))


def get_clutch_stats(games: list) -> pd.DataFrame:
    """Player performance in close games (margin ≤10) vs blowouts."""
    buckets: dict = {}
    for game in games:
        margin   = abs(game["score"]["us"] - game["score"]["them"])
        is_close = margin <= 10
        for p in game["players"]:
            name = normalize_name(p["name"])
            pos  = p.get("pos", "")
            key  = (name, pos)
            if key not in buckets:
                buckets[key] = {
                    "name": name, "pos": pos,
                    "clutch_pts": [], "clutch_gs": [], "clutch_wins": 0,
                    "reg_pts":    [], "reg_gs":    [],
                }
            gs = _calc_gs(p)
            pts = p.get("pts", 0)
            b   = buckets[key]
            if is_close:
                b["clutch_pts"].append(pts)
                b["clutch_gs"].append(gs)
                if game.get("result", "W") == "W":
                    b["clutch_wins"] += 1
            else:
                b["reg_pts"].append(pts)
                b["reg_gs"].append(gs)

    def _avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else None

    rows = []
    for (name, pos), b in buckets.items():
        cg           = len(b["clutch_pts"])
        cp           = _avg(b["clutch_pts"])
        rp           = _avg(b["reg_pts"])
        clutch_boost = round((cp or 0) - (rp or 0), 1) if cp is not None and rp is not None else None
        rows.append({
            "name":           name,
            "pos":            pos,
            "clutch_games":   cg,
            "clutch_pts":     cp,
            "reg_pts":        rp,
            "clutch_gs":      _avg(b["clutch_gs"]),
            "reg_gs":         _avg(b["reg_gs"]),
            "clutch_wins":    b["clutch_wins"],
            "clutch_win_pct": round(b["clutch_wins"] / cg * 100, 1) if cg > 0 else None,
            "clutch_boost":   clutch_boost,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("clutch_gs", ascending=False, na_position="last").reset_index(drop=True)
    return df


def get_hot_cold_streaks(games: list) -> dict:
    """Last 3 games rolling average vs season average per player."""
    if not games:
        return {}
    sorted_games = sorted(games, key=lambda g: g["date"])
    recent       = sorted_games[-3:]

    season_acc: dict = {}
    recent_acc: dict = {}
    gs_acc: dict     = {}

    for game in sorted_games:
        for p in game["players"]:
            n  = normalize_name(p["name"])
            gs = _calc_gs(p)
            pts = p.get("pts", 0)
            season_acc.setdefault(n, []).append(pts)
            gs_acc.setdefault(n, []).append(gs)

    for game in recent:
        for p in game["players"]:
            n   = normalize_name(p["name"])
            pts = p.get("pts", 0)
            recent_acc.setdefault(n, []).append(pts)

    result = {}
    for name in season_acc:
        s_pts = round(sum(season_acc[name]) / len(season_acc[name]), 1)
        r_pts = round(sum(recent_acc.get(name, season_acc[name])) /
                      len(recent_acc.get(name, season_acc[name])), 1)
        delta  = round(r_pts - s_pts, 1)
        s_gs   = round(sum(gs_acc.get(name, [0])) / len(gs_acc.get(name, [1])), 1)
        status = ("🔥 HOT"   if delta >= 2 else
                  "❄️ COLD"  if delta <= -2 else
                  "➡️ STEADY")
        result[name] = {
            "season_avg_pts": s_pts,
            "recent_avg_pts": r_pts,
            "delta":          delta,
            "status":         status,
            "season_avg_gs":  s_gs,
        }
    return result


def get_per_game_player_stats(games: list) -> pd.DataFrame:
    """Every individual player-game log row for timeline charts."""
    rows = []
    sorted_games = sorted(games, key=lambda g: (g["date"], g.get("id", 0)))
    for game_num, game in enumerate(sorted_games, start=1):
        opp_short = game["opponent"][:10]
        label = f"G{game_num} {opp_short}"
        for p in game["players"]:
            name = normalize_name(p["name"])
            gs   = _calc_gs(p)
            fga  = p.get("fga", 0); fgm = p.get("fgm", 0)
            tpa  = p.get("tpa", 0); tpm = p.get("tpm", 0)
            fta  = p.get("fta", 0); ftm = p.get("ftm", 0)
            pts  = p.get("pts", 0)
            ts_d = 2 * (fga + 0.44 * fta)
            rows.append({
                "game_num":   game_num,
                "game_label": label,
                "date":       game["date"],
                "opponent":   game["opponent"],
                "result":     game.get("result", "W"),
                "name":       name,
                "pos":        p.get("pos", ""),
                "pts":        pts,
                "reb":        p.get("reb", 0),
                "ast":        p.get("ast", 0),
                "stl":        p.get("stl", 0),
                "blk":        p.get("blk", 0),
                "to":         p.get("to", 0),
                "fgm":        fgm, "fga": fga,
                "tpm":        tpm, "tpa": tpa,
                "ftm":        ftm, "fta": fta,
                "fg_pct":     round(fgm / fga * 100, 1) if fga > 0 else None,
                "three_pct":  round(tpm / tpa * 100, 1) if tpa > 0 else None,
                "ts_pct":     round(pts / ts_d * 100, 1) if ts_d > 0 else None,
                "game_score": round(gs, 1),
            })
    return pd.DataFrame(rows)


def get_best_lineup_combos(games: list) -> pd.DataFrame:
    """Rank actual 5-man lineups used by game score and win rate."""
    combos: dict = {}
    for game in games:
        players    = game["players"]
        lineup_key = tuple(sorted(normalize_name(p["name"]) for p in players))
        if lineup_key not in combos:
            combos[lineup_key] = {"games": 0, "wins": 0, "team_gs": [], "team_pts": []}
        d = combos[lineup_key]
        d["games"] += 1
        if game.get("result", "W") == "W":
            d["wins"] += 1
        d["team_gs"].append(sum(_calc_gs(p) for p in players))
        d["team_pts"].append(game["score"]["us"])

    rows = []
    for lineup, d in combos.items():
        n = d["games"]
        rows.append({
            "lineup":       " | ".join(lineup),
            "games":        n,
            "win_pct":      round(d["wins"] / n * 100, 1),
            "avg_team_gs":  round(sum(d["team_gs"])  / n, 1),
            "avg_team_pts": round(sum(d["team_pts"]) / n, 1),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["win_pct", "avg_team_gs"], ascending=False).reset_index(drop=True)
    return df


def get_ai_coach_insights(games: list) -> list:
    """Rule-based AI coaching insights derived from all available data."""
    insights = []
    if not games:
        return insights

    adv      = get_advanced_stats(games)
    scoring  = get_scoring_shares(games)
    profile  = get_scoring_profile(games)
    momentum = get_momentum_analysis(games)
    streaks  = get_hot_cold_streaks(games)
    team_stats = get_team_stats_by_game(games)
    win_loss = get_win_loss_splits(games)
    impact   = get_player_impact_index(games)

    labels = ["Q1", "Q2", "Q3", "Q4"]

    # 1. Quarter momentum
    best_q  = momentum["us_best_quarter"]
    worst_q = momentum["us_worst_quarter"]
    us_avgs = momentum["us_avg"]
    them_avgs = momentum["them_avg"]
    bqi = labels.index(best_q); wqi = labels.index(worst_q)
    insights.append({
        "icon": "📈", "category": "Team Momentum",
        "title": f"Strongest quarter: {best_q} ({us_avgs[bqi]} pts avg) | Weakest: {worst_q} ({us_avgs[wqi]} pts avg)",
        "detail": (f"You outscore opponents in {best_q} by {us_avgs[bqi]-them_avgs[bqi]:+.1f} pts on average. "
                   f"In {worst_q} you're outscored by {them_avgs[wqi]-us_avgs[wqi]:.1f} pts. "
                   f"Run more half-court sets and hold transition defense in {worst_q}."),
    })

    # 2. Turnover risk
    if not profile.empty:
        to_col = profile.dropna(subset=["to_rate"])
        if not to_col.empty:
            worst_to = to_col.sort_values("to_rate", ascending=False).iloc[0]
            insights.append({
                "icon": "⚠️", "category": "Ball Security",
                "title": f"{worst_to['name']} has the highest turnover rate ({worst_to['to_rate']}%)",
                "detail": (f"For every 100 possessions, {worst_to['name']} turns it over {worst_to['to_rate']:.0f} times. "
                           f"In clutch situations, consider routing plays through your lowest TO-rate player."),
            })

    # 3. Most efficient scorer
    if not adv.empty:
        ts_sorted = adv.dropna(subset=["ts_pct"]).sort_values("ts_pct", ascending=False)
        if not ts_sorted.empty:
            best_ts = ts_sorted.iloc[0]
            insights.append({
                "icon": "🎯", "category": "Shooting Efficiency",
                "title": f"{best_ts['name']} is your most efficient scorer (TS%: {best_ts['ts_pct']}%)",
                "detail": (f"True Shooting factors in 2s, 3s, and free throws. "
                           f"{best_ts['name']} at {best_ts['ts_pct']}% means elite shot selection. "
                           f"Run late-shot-clock plays targeting this player."),
            })

    # 4. Hot/cold streaks
    hot   = [n for n, d in streaks.items() if "HOT"  in d["status"]]
    cold  = [n for n, d in streaks.items() if "COLD" in d["status"]]
    if hot:
        deltas = [streaks[n]["delta"] for n in hot]
        insights.append({
            "icon": "🔥", "category": "Form — Hot",
            "title": f"On fire right now: {', '.join(hot)}",
            "detail": (f"These players are averaging {max(deltas):+.1f} pts above their season avg "
                       f"in the last 3 games. Get them early looks."),
        })
    if cold:
        insights.append({
            "icon": "❄️", "category": "Form — Cold",
            "title": f"Cold streak: {', '.join(cold)}",
            "detail": ("Below season averages in the last 3 games. Consider extra pre-game warm-up focus "
                       "or adjusted role to rebuild confidence."),
        })

    # 5. Win correlation
    if not win_loss.empty:
        for _, row in win_loss.iterrows():
            if (row.get("w_gs") is not None and row.get("l_gs") is not None
                    and row["l_gs"] > row["w_gs"] + 2):
                insights.append({
                    "icon": "🔁", "category": "Win Correlation",
                    "title": f"{row['name']} stats spike in LOSSES — possible volume-heavy effect",
                    "detail": (f"Game Score in wins: {row['w_gs']} | In losses: {row['l_gs']}. "
                               f"High personal stats in losses can signal forced shot attempts. "
                               f"Focus on efficiency over volume."),
                })

    # 6. AST/TO leaders
    if not adv.empty and "ast_to" in adv.columns:
        asto = adv.dropna(subset=["ast_to"]).sort_values("ast_to", ascending=False)
        if not asto.empty:
            best = asto.iloc[0]
            insights.append({
                "icon": "🎶", "category": "Playmaking",
                "title": f"{best['name']} is your safest ball-handler (AST/TO: {best['ast_to']})",
                "detail": (f"Ratio of {best['ast_to']} means {best['name']} creates far more than he gives away. "
                           f"In high-pressure situations, route the ball through this player."),
            })

    # 7. Comeback wins
    if momentum["comeback_wins"] > 0:
        insights.append({
            "icon": "💪", "category": "Resilience",
            "title": f"Team has {momentum['comeback_wins']} comeback win(s) after trailing in Q3",
            "detail": ("Your squad has elite mental resilience — they don't quit when down. "
                       "Use this as a psychological edge and remind players of it pre-game."),
        })

    # 8. Impact leader
    if not impact.empty:
        top = impact.iloc[0]
        insights.append({
            "icon": "🏆", "category": "Performance Index",
            "title": f"Overall MVP: {top['name']} (Impact Score: {top['impact_score']}/100)",
            "detail": (f"Composite score across Game Score, efficiency, playmaking, and defense. "
                       f"{top['name']} is your most complete player. Build your system around him."),
        })

    # 9. Team net rating trend
    if not team_stats.empty and len(team_stats) > 1:
        avg_margin = round(team_stats["margin"].mean(), 1)
        last_margin = int(team_stats["margin"].iloc[-1])
        first_margin = int(team_stats["margin"].iloc[0])
        trend = "improving 📈" if last_margin > first_margin else "declining 📉"
        insights.append({
            "icon": "📊", "category": "Net Rating Trend",
            "title": f"Avg margin: {avg_margin:+.1f} pts | Season trajectory: {trend}",
            "detail": (f"First game margin: {first_margin:+d} pts. "
                       f"Last game margin: {last_margin:+d} pts. "
                       f"Consistent positive margins indicate sustainable team dominance."),
        })

    # 10. Rebounding edge
    if not team_stats.empty:
        avg_reb_margin = round(team_stats["reb_margin"].mean(), 1)
        reb_note = "dominating" if avg_reb_margin > 0 else "losing"
        insights.append({
            "icon": "🏀", "category": "Rebounding",
            "title": f"Rebounding margin: {avg_reb_margin:+.1f} per game ({reb_note} the glass)",
            "detail": (f"Positive rebound margin means more second-chance points and fewer opponent possessions. "
                       + ("Keep crashing the boards." if avg_reb_margin > 0
                          else "Assign box-out responsibilities more strictly.")),
        })

    return insights
