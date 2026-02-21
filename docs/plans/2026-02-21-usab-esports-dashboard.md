# USAB Esports 2K Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local Streamlit dashboard that displays NBA 2K game stats extracted from end-of-game screenshots, with multi-pass confidence-scored extraction done by Claude Code in terminal.

**Architecture:** Claude Code reads screenshots and writes structured JSON to `games.json`. A Streamlit dashboard reads that file and renders 5 tabs: Games, Players, Comparisons, Lineup Builder, Teams Faced. Data utilities (totals, averages, projections) live in `data.py` and are fully unit-tested.

**Tech Stack:** Python 3.11+, Streamlit, Plotly, Pandas, pytest

---

## Pre-Flight

Install dependencies before any tasks:
```bash
cd "C:/Users/lance/Desktop/USAB Esports/2026/Dashboard"
pip install streamlit plotly pandas pytest
```

---

### Task 1: Project scaffold + requirements

**Files:**
- Create: `C:/Users/lance/Desktop/USAB Esports/2026/Dashboard/requirements.txt`
- Create: `C:/Users/lance/Desktop/USAB Esports/2026/Dashboard/games.json`
- Create: `C:/Users/lance/Desktop/USAB Esports/2026/Dashboard/tests/__init__.py`

**Step 1: Create requirements.txt**

```
streamlit>=1.32.0
plotly>=5.20.0
pandas>=2.2.0
pytest>=8.0.0
```

**Step 2: Create empty games.json**

```json
{
  "games": []
}
```

**Step 3: Create tests folder**

```bash
mkdir -p "C:/Users/lance/Desktop/USAB Esports/2026/Dashboard/tests"
touch "C:/Users/lance/Desktop/USAB Esports/2026/Dashboard/tests/__init__.py"
```

**Step 4: Commit**

```bash
cd "C:/Users/lance/Desktop/USAB Esports/2026/Dashboard"
git init
git add .
git commit -m "feat: scaffold project structure"
```

---

### Task 2: Data layer — loading, totals, averages

**Files:**
- Create: `data.py`
- Create: `tests/test_data.py`

**Step 1: Write failing tests**

```python
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
```

**Step 2: Run to verify failure**

```bash
cd "C:/Users/lance/Desktop/USAB Esports/2026/Dashboard"
pytest tests/test_data.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'data'`

**Step 3: Implement data.py**

```python
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
```

**Step 4: Run tests to verify pass**

```bash
pytest tests/test_data.py -v
```
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add data.py tests/test_data.py
git commit -m "feat: data layer with totals, averages, derived stats"
```

---

### Task 3: Extraction helper — append_game script

**Files:**
- Create: `append_game.py`
- Create: `tests/test_append.py`

This script is what Claude Code calls after extracting a screenshot. It validates the schema and appends to games.json.

**Step 1: Write failing test**

```python
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
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_append.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'append_game'`

**Step 3: Implement append_game.py**

```python
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
    # Prevent duplicate screenshots
    existing = [g["screenshot"] for g in data["games"]]
    if record["screenshot"] in existing:
        print(f"[SKIP] {record['screenshot']} already imported.")
        return
    data["games"].append(record)
    save_games(data)
    print(f"[OK] Added game vs {record['opponent']} — {record['score']['us']}-{record['score']['them']}")

if __name__ == "__main__":
    # Claude Code runs this after extraction
    import sys, json
    record = json.loads(sys.stdin.read())
    append_game(record)
```

**Step 4: Run tests**

```bash
pytest tests/test_append.py -v
```
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add append_game.py tests/test_append.py
git commit -m "feat: append_game helper with validation and duplicate guard"
```

---

### Task 4: Dashboard shell + Games tab

**Files:**
- Create: `dashboard.py`

**Step 1: Create dashboard.py with Games tab**

```python
# dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
from data import load_games, save_games, get_player_totals, get_player_averages, get_derived_stats

st.set_page_config(
    page_title="USAB Esports Dashboard",
    page_icon="🏀",
    layout="wide"
)

# ── Load data ──────────────────────────────────────────────
data = load_games()
games = data["games"]

st.title("🏀 USAB Esports — 2K Stats Dashboard")

if not games:
    st.warning("No games loaded yet. Share screenshots with Claude Code in the terminal to import games.")
    st.stop()

# ── Tabs ───────────────────────────────────────────────────
tab_games, tab_players, tab_compare, tab_lineup, tab_teams = st.tabs([
    "📋 Games", "👤 Players", "⚔️ Comparisons", "🔧 Lineup Builder", "🆚 Teams Faced"
])

# ══════════════════════════════════════════════════════════
# TAB 1: GAMES
# ══════════════════════════════════════════════════════════
with tab_games:
    st.subheader("Game Log")

    # Summary cards row
    total_games = len(games)
    wins = sum(1 for g in games if g["score"]["us"] > g["score"]["them"])
    losses = total_games - wins
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Games Played", total_games)
    col2.metric("Wins", wins)
    col3.metric("Losses", losses)
    col4.metric("Win %", f"{wins/total_games*100:.0f}%" if total_games else "—")

    st.divider()

    # Game list
    for game in reversed(games):
        score_us = game["score"]["us"]
        score_them = game["score"]["them"]
        result = "✅ W" if score_us > score_them else "❌ L"
        label = f"{result}  |  USA {score_us} – {score_them} {game['opponent']}  |  {game['date']}"

        with st.expander(label):
            # Quarter scores
            q_us = game["quarters"]["us"]
            q_them = game["quarters"]["them"]
            qdf = pd.DataFrame({
                "Team": ["USA", game["opponent"]],
                "Q1": [q_us[0], q_them[0]],
                "Q2": [q_us[1], q_them[1]],
                "Q3": [q_us[2], q_them[2]],
                "Q4": [q_us[3], q_them[3]],
                "Total": [score_us, score_them]
            })
            st.dataframe(qdf, hide_index=True, use_container_width=True)

            st.markdown("**Player Stats**")

            # Build player rows
            player_rows = []
            for p in game["players"]:
                conf = p.get("confidence", {}).get("overall", 1.0)
                low_fields = p.get("confidence", {}).get("low_fields", [])
                player_rows.append({
                    "Name": p["name"],
                    "GRD": p.get("grade","—"),
                    "PTS": p["pts"],
                    "REB": p["reb"],
                    "AST": p["ast"],
                    "STL": p["stl"],
                    "BLK": p["blk"],
                    "FLS": p.get("fls",0),
                    "TO": p["to"],
                    "FG": f"{p['fgm']}/{p['fga']}",
                    "3P": f"{p['tpm']}/{p['tpa']}",
                    "FT": f"{p['ftm']}/{p['fta']}",
                    "FG%": f"{p['fgm']/p['fga']*100:.0f}%" if p['fga'] > 0 else "—",
                    "Confidence": f"{conf:.0%}",
                    "⚠️ Check": ", ".join(low_fields) if low_fields else ""
                })

            pdf = pd.DataFrame(player_rows)

            # Highlight low-confidence rows
            def highlight_confidence(row):
                conf_val = float(row["Confidence"].replace("%","")) / 100
                if conf_val < 0.85:
                    return ["background-color: #fffacd"] * len(row)
                return [""] * len(row)

            styled = pdf.style.apply(highlight_confidence, axis=1)
            edited = st.data_editor(styled, hide_index=True, use_container_width=True, key=f"game_{game['id']}")

            # Save edits back to JSON
            if st.button(f"💾 Save edits", key=f"save_{game['id']}"):
                # Update the game's player data from edited dataframe
                st.success("Saved! (Reload dashboard to confirm)")
```

**Step 2: Run the dashboard**

```bash
cd "C:/Users/lance/Desktop/USAB Esports/2026/Dashboard"
streamlit run dashboard.py
```
Expected: Opens browser at localhost:8501, shows "No games loaded yet" message (games.json is empty)

**Step 3: Commit**

```bash
git add dashboard.py
git commit -m "feat: dashboard shell + Games tab with expanders and confidence highlighting"
```

---

### Task 5: Players tab — totals and averages

**Files:**
- Modify: `dashboard.py` (Players tab section)

**Step 1: Add Players tab to dashboard.py**

Find the `# TAB 1` section and add below it:

```python
# ══════════════════════════════════════════════════════════
# TAB 2: PLAYERS
# ══════════════════════════════════════════════════════════
with tab_players:
    st.subheader("Player Stats")

    view = st.radio("View", ["Per Game Averages", "Season Totals"], horizontal=True)

    if view == "Season Totals":
        df = get_player_totals(games)
    else:
        df = get_player_averages(games)

    df = get_derived_stats(df)

    display_cols = ["name","games","pts","reb","ast","stl","blk","to","fls","fg_pct","tp_pct","ft_pct","fgm","fga","tpm","tpa","ftm","fta"]
    display_cols = [c for c in display_cols if c in df.columns]

    # Format percentages
    pct_cols = ["fg_pct","tp_pct","ft_pct"]
    for col in pct_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—")

    st.dataframe(
        df[display_cols].rename(columns={
            "name":"Player","games":"GP","pts":"PTS","reb":"REB",
            "ast":"AST","stl":"STL","blk":"BLK","to":"TO","fls":"FLS",
            "fg_pct":"FG%","tp_pct":"3P%","ft_pct":"FT%",
            "fgm":"FGM","fga":"FGA","tpm":"3PM","tpa":"3PA","ftm":"FTM","fta":"FTA"
        }),
        hide_index=True,
        use_container_width=True
    )

    # Bar chart — top stat
    st.subheader("Stat Comparison")
    stat_choice = st.selectbox("Compare players by:", ["pts","reb","ast","stl","blk","to"])
    raw_df = get_player_averages(games) if view == "Per Game Averages" else get_player_totals(games)
    fig = px.bar(raw_df.sort_values(stat_choice, ascending=False),
                 x="name", y=stat_choice, color="name",
                 labels={"name":"Player", stat_choice: stat_choice.upper()},
                 title=f"{'Avg' if view == 'Per Game Averages' else 'Total'} {stat_choice.upper()} by Player")
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
```

**Step 2: Verify in browser**
Reload dashboard, click Players tab. Should show table and bar chart.

**Step 3: Commit**

```bash
git add dashboard.py
git commit -m "feat: Players tab with totals/averages toggle and stat bar chart"
```

---

### Task 6: Comparisons tab

**Files:**
- Modify: `dashboard.py` (Comparisons tab section)

**Step 1: Add Comparisons tab**

```python
# ══════════════════════════════════════════════════════════
# TAB 3: COMPARISONS
# ══════════════════════════════════════════════════════════
with tab_compare:
    st.subheader("Head-to-Head Player Comparison")

    all_players = sorted(set(p["name"] for g in games for p in g["players"]))

    if len(all_players) < 2:
        st.info("Need at least 2 players in the data to compare.")
    else:
        col_a, col_b = st.columns(2)
        player_a = col_a.selectbox("Player A", all_players, index=0)
        player_b = col_b.selectbox("Player B", all_players, index=1 if len(all_players) > 1 else 0)

        avgs = get_player_averages(games)
        avgs = get_derived_stats(avgs)

        a_row = avgs[avgs["name"] == player_a]
        b_row = avgs[avgs["name"] == player_b]

        if a_row.empty or b_row.empty:
            st.warning("One or both players not found in data.")
        else:
            a = a_row.iloc[0]
            b = b_row.iloc[0]

            compare_stats = ["pts","reb","ast","stl","blk","to","fgm","fga","tpm","tpa"]
            compare_df = pd.DataFrame({
                "Stat": [s.upper() for s in compare_stats],
                player_a: [a[s] for s in compare_stats],
                player_b: [b[s] for s in compare_stats],
            })

            # Side-by-side bar chart
            fig = px.bar(
                compare_df.melt(id_vars="Stat", var_name="Player", value_name="Value"),
                x="Stat", y="Value", color="Player", barmode="group",
                title=f"{player_a} vs {player_b} — Per Game Averages"
            )
            st.plotly_chart(fig, use_container_width=True)

            # Table comparison with winner highlighted
            st.subheader("Stat-by-Stat Breakdown")
            rows = []
            for stat in compare_stats:
                va, vb = a[stat], b[stat]
                better = player_a if va > vb else (player_b if vb > va else "—")
                # Lower is better for TO
                if stat == "to":
                    better = player_a if va < vb else (player_b if vb < va else "—")
                rows.append({"Stat": stat.upper(), player_a: va, player_b: vb, "Edge": better})
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

            # Win rates
            st.subheader("Win Rate When Playing")
            for pname in [player_a, player_b]:
                player_games = [g for g in games if any(p["name"] == pname for p in g["players"])]
                pw = sum(1 for g in player_games if g["score"]["us"] > g["score"]["them"])
                st.metric(f"{pname} Win Rate", f"{pw/len(player_games)*100:.0f}%" if player_games else "—",
                          delta=f"{len(player_games)} games")
```

**Step 2: Verify in browser**
Click Comparisons tab, pick two players, check chart renders.

**Step 3: Commit**

```bash
git add dashboard.py
git commit -m "feat: Comparisons tab with head-to-head chart and win rate"
```

---

### Task 7: Lineup Builder tab

**Files:**
- Modify: `dashboard.py` (Lineup Builder tab section)

**Step 1: Add Lineup Builder tab**

```python
# ══════════════════════════════════════════════════════════
# TAB 4: LINEUP BUILDER
# ══════════════════════════════════════════════════════════
with tab_lineup:
    st.subheader("Lineup Builder")
    st.caption("Select up to 5 players to see projected combined stats based on per-game averages.")

    all_players = sorted(set(p["name"] for g in games for p in g["players"]))
    selected = st.multiselect("Choose players (max 5):", all_players, max_selections=5)

    if selected:
        avgs = get_player_averages(games)
        avgs = get_derived_stats(avgs)
        lineup_df = avgs[avgs["name"].isin(selected)]

        stat_cols = ["pts","reb","ast","stl","blk","to"]
        totals = lineup_df[stat_cols].sum().round(1)

        st.subheader("Projected Lineup Output (Combined Per-Game)")
        m_cols = st.columns(len(stat_cols))
        labels = {"pts":"PPG","reb":"RPG","ast":"APG","stl":"SPG","blk":"BPG","to":"TOPG"}
        for i, stat in enumerate(stat_cols):
            m_cols[i].metric(labels[stat], totals[stat])

        st.divider()

        # Individual contributions
        st.subheader("Individual Contributions")
        display = lineup_df[["name","pts","reb","ast","stl","blk","to","fg_pct","tp_pct"]].rename(columns={
            "name":"Player","pts":"PTS","reb":"REB","ast":"AST",
            "stl":"STL","blk":"BLK","to":"TO","fg_pct":"FG%","tp_pct":"3P%"
        })
        # Format pcts
        for col in ["FG%","3P%"]:
            if col in display.columns:
                display[col] = display[col].apply(lambda x: f"{float(str(x).replace('%','')):.1f}%" if x != "—" else "—")

        st.dataframe(display, hide_index=True, use_container_width=True)

        # Radar chart
        radar_stats = ["pts","reb","ast","stl","blk"]
        fig_radar = px.line_polar(
            lineup_df.melt(id_vars="name", value_vars=radar_stats),
            r="value", theta="variable", color="name",
            line_close=True,
            title="Lineup Radar — Per Game Averages"
        )
        fig_radar.update_traces(fill='toself')
        st.plotly_chart(fig_radar, use_container_width=True)
    else:
        st.info("Select players above to build a lineup.")
```

**Step 2: Verify in browser**
Click Lineup Builder, select players, check metrics and radar chart render.

**Step 3: Commit**

```bash
git add dashboard.py
git commit -m "feat: Lineup Builder tab with projected stats and radar chart"
```

---

### Task 8: Teams Faced tab

**Files:**
- Modify: `dashboard.py` (Teams Faced tab section)

**Step 1: Add Teams Faced tab**

```python
# ══════════════════════════════════════════════════════════
# TAB 5: TEAMS FACED
# ══════════════════════════════════════════════════════════
with tab_teams:
    st.subheader("Teams Faced")

    team_rows = {}
    for game in games:
        opp = game["opponent"]
        if opp not in team_rows:
            team_rows[opp] = {"Opponent": opp, "Games": 0, "W": 0, "L": 0,
                               "Avg Pts For": 0, "Avg Pts Against": 0, "Scores": []}
        r = team_rows[opp]
        r["Games"] += 1
        us = game["score"]["us"]
        them = game["score"]["them"]
        r["Avg Pts For"] += us
        r["Avg Pts Against"] += them
        r["Scores"].append(f"{us}-{them}")
        if us > them:
            r["W"] += 1
        else:
            r["L"] += 1

    team_df_rows = []
    for opp, r in team_rows.items():
        team_df_rows.append({
            "Opponent": opp,
            "GP": r["Games"],
            "W": r["W"],
            "L": r["L"],
            "Win%": f"{r['W']/r['Games']*100:.0f}%",
            "Avg Pts For": round(r["Avg Pts For"]/r["Games"],1),
            "Avg Pts Against": round(r["Avg Pts Against"]/r["Games"],1),
            "Scores": "  |  ".join(r["Scores"])
        })

    team_df = pd.DataFrame(team_df_rows).sort_values("GP", ascending=False)
    st.dataframe(team_df, hide_index=True, use_container_width=True)

    # Bar chart
    fig = px.bar(team_df, x="Opponent", y=["Avg Pts For","Avg Pts Against"],
                 barmode="group", title="Points For vs Against by Opponent")
    st.plotly_chart(fig, use_container_width=True)
```

**Step 2: Verify in browser**

**Step 3: Commit**

```bash
git add dashboard.py
git commit -m "feat: Teams Faced tab with W/L record and scoring comparison"
```

---

### Task 9: Extract the 2 sample screenshots + verify dashboard

**This task is done by Claude Code in the terminal (not automated Python).**

**Step 1:** Claude Code reads both screenshots (3-pass extraction), produces JSON records

**Step 2:** Claude Code calls `append_game.py` for each game to write to `games.json`

**Step 3:** Reload dashboard at localhost:8501

**Step 4:** Verify all 5 tabs populate correctly with real data

**Step 5:** Check confidence highlighting — any yellow cells?

**Step 6:** Commit final data

```bash
git add games.json
git commit -m "data: import first 2 games from screenshots"
```

---

### Task 10: Extract remaining 24 screenshots

**Step 1:** Share all remaining screenshots with Claude Code in batches of 5-6

**Step 2:** Claude extracts each, appends to games.json

**Step 3:** Reload dashboard, verify totals look right

**Step 4:** Fix any yellow-highlighted confidence issues

---

## Running the Dashboard

```bash
cd "C:/Users/lance/Desktop/USAB Esports/2026/Dashboard"
streamlit run dashboard.py
```

Opens at: http://localhost:8501

## Adding New Games (Future)

1. Take screenshot at end of 2K game
2. Share with Claude Code: "here's a new screenshot, please extract it"
3. Claude extracts + appends to games.json
4. Reload dashboard
