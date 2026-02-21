# USAB Esports 2K Dashboard — Design Doc
**Date:** 2026-02-21
**Status:** Approved
**Built for:** Coach / Analyst use — local machine only

---

## Overview

A local Streamlit dashboard that displays NBA 2K game stats extracted from end-of-game screenshots. Claude Code handles all image extraction (multi-pass, confidence-scored). The dashboard reads from a single `games.json` file and provides game logs, player totals/averages, comparisons, and a lineup builder.

---

## Tech Stack

| Layer | Tool |
|-------|------|
| Dashboard | Streamlit (Python) |
| Charts | Plotly |
| Data processing | Pandas |
| Data storage | `games.json` (local file) |
| Image extraction | Claude Code (in terminal, multi-pass) |

**Run command:** `streamlit run dashboard.py`
**Location:** `C:\Users\lance\Desktop\USAB Esports\2026\Dashboard\`

---

## Data Flow

```
Screenshots → Claude Code (3-pass extraction) → games.json → Streamlit Dashboard
```

1. User shares screenshot(s) in Claude Code terminal
2. Claude does 3-pass extraction with confidence scoring
3. Data saved/appended to `games.json`
4. Dashboard reads `games.json` on load
5. Low-confidence stats highlighted yellow → user edits inline

---

## Data Schema

### games.json structure
```json
{
  "games": [
    {
      "id": "game_001",
      "date": "2026-02-21",
      "screenshot": "Screenshot 2026-02-21 134108.png",
      "opponent": "Brazil",
      "opponent_logo": "brazil",
      "score": { "us": 81, "them": 62 },
      "quarters": {
        "us": [15, 20, 26, 20],
        "them": [16, 14, 20, 12]
      },
      "players": [
        {
          "name": "OBJ3onTwitch",
          "grade": "A",
          "pts": 21,
          "reb": 0,
          "ast": 1,
          "stl": 1,
          "blk": 0,
          "fls": 0,
          "to": 0,
          "fgm": 7, "fga": 12,
          "tpm": 3, "tpa": 8,
          "ftm": 0, "fta": 0,
          "confidence": {
            "overall": 0.94,
            "low_fields": ["reb", "blk"]
          }
        }
      ]
    }
  ]
}
```

---

## Dashboard Tabs

### Tab 1: Games
- List of all games, newest first
- Each game card shows: opponent, score, Q1-Q4, W/L
- Expand game → full box score for all 5 players
- Low-confidence cells highlighted yellow, inline editable
- Derived stats auto-calculated: FG%, 3P%, FT%, +/-

### Tab 2: Players
- One row per unique player seen across all games
- Columns: Games Played, PTS, REB, AST, STL, BLK, TO, FG%, 3P%, FT%
- Toggle: **Totals** vs **Per Game Averages**
- Sort by any column
- Grade distribution shown as letter badges (A/B+/B/C+/C/D)

### Tab 3: Comparisons
- Dropdown: Pick Player A vs Player B
- Side-by-side bar chart for every stat
- Win rate when each player plays
- Table of all shared games

### Tab 4: Lineup Builder
- Select up to 5 players via checkboxes
- Shows projected combined stats (based on per-game averages)
- Projected PPG, RPG, APG, STL, BLK, TO, FG%, 3P%
- Comparison against actual lineups from game data

### Tab 5: Teams Faced
- One row per opponent
- Stats: W/L, avg score, avg points allowed, close games
- Filterable

---

## Multi-Pass Extraction

When Claude Code processes a screenshot:

1. **Pass 1** — Full read of all visible stats for all 10 players
2. **Pass 2** — Re-examine any stat that seemed unclear (low contrast, cut off, etc.)
3. **Pass 3** — Math cross-check:
   - PTS ≈ (FGM - 3PM) × 2 + 3PM × 3 + FTM
   - FG% = FGM / FGA
   - Any mismatch → flag as low confidence

Confidence score = 0.0–1.0 per player stat
Threshold: < 0.85 → highlight yellow in dashboard

---

## File Structure

```
Dashboard/
├── dashboard.py          # Main Streamlit app
├── games.json            # All extracted game data
├── requirements.txt      # pip dependencies
├── docs/
│   └── plans/
│       └── 2026-02-21-usab-esports-dashboard-design.md
└── screenshots/          # Optional: copies of source screenshots
```

---

## Future (Not in v1)
- AI analysis tab (ask Claude about a player's tendencies)
- Export to PDF report
- Opponent scouting notes
