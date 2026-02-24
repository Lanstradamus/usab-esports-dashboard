# USAB Esports — Screenshot Stat Extraction Process

This document describes the exact process for extracting game stats from 2K screenshots and adding them to the review queue.

---

## Overview

When new game screenshots are added to the Screenshots folder, Claude reads each image, extracts all stats for **both USA eFIBA and the opponent**, and places them into the `pending` array in `games.json` for manual approval on the Review Queue tab.

**Screenshots folder:** `C:\Users\lance\Desktop\USAB Esports\2026\Screenshots\`
**Approved games file:** `C:\Users\lance\Desktop\USAB Esports\2026\Dashboard\games.json`
**Pending queue file:** `C:\Users\lance\Desktop\USAB Esports\2026\Dashboard\pending_games.json`
**Pending module:** `pending.py` → `load_pending()`, `approve_game()`, `reject_game()`

---

## Step-by-Step Process

### Step 1: Read Original Screenshots
Use the `Read` tool to load all PNG files from the Screenshots folder.

### Step 2: Crop & Upscale for Precision
The original screenshots are ~1618×676px — too small to read individual numbers reliably. Use Python + Pillow to:
- Crop the **right 55%** of each image → full stats columns (PTS, REB, AST, STL, BLK, FOULS, TO, FGM/FGA, 3PM/3PA, FTM/FTA)
- Crop the **left 60%** of each image → team names, scores, quarter scores, player names, grades
- **3× upscale** both crops using `Image.LANCZOS`
- Save as temp PNG files, read them with the `Read` tool for clear vision

```python
from PIL import Image
img = Image.open(screenshot_path)
w, h = img.size
# Stats columns (right side)
right = img.crop((int(w*0.45), 0, w, h))
right_big = right.resize((right.width*3, right.height*3), Image.LANCZOS)
right_big.save('crop_temp_right.png')
# Names + scores (left side)
left = img.crop((0, 0, int(w*0.60), h))
left_big = left.resize((left.width*3, left.height*3), Image.LANCZOS)
left_big.save('crop_temp_left.png')
```

### Step 3: Extract Stats
Read each cropped image carefully. For each game extract:

**Game-level fields:**
- `opponent` — team name shown in the box score header (top team label)
- `score` — `{"us": X, "them": Y}` — USA score is always the USA eFIBA team
- `result` — `"W"` if `us > them`, `"L"` if `us < them`
- `quarters` — `{"us": [Q1,Q2,Q3,Q4], "them": [Q1,Q2,Q3,Q4]}`
- `date` — from the screenshot filename (format: `Screenshot YYYY-MM-DD HHMMSS.png`)
- `screenshot` — exact filename

**Per-player fields (both teams):**
| Field | Description |
|-------|-------------|
| `name` | Gamertag exactly as shown |
| `grade` | Letter grade shown (A+, A, A-, B+, B, B-, C+, C, C-, D) |
| `pos` | Position — infer from grade column suffix or known roster |
| `pts` | Points |
| `reb` | Rebounds |
| `ast` | Assists |
| `stl` | Steals |
| `blk` | Blocks |
| `fls` | Fouls (FOULS column) |
| `to` | Turnovers |
| `fgm` | Field goals made (first number in FGM/FGA) |
| `fga` | Field goals attempted (second number in FGM/FGA) |
| `tpm` | 3-pointers made (first number in 3PM/3PA) |
| `tpa` | 3-pointers attempted (second number in 3PM/3PA) |
| `ftm` | Free throws made (first number in FTM/FTA) |
| `fta` | Free throws attempted (second number in FTM/FTA) |

### Step 4: Identify USA vs Opponent
- USA eFIBA always shows the **US flag** logo on the left side panel
- USA players are: CB13onTwitch, JohhnyRed_, MamaImDatMan, daws6x/dawb6x, SuperSeese, JOEMORNING, and any other known USA roster members
- USA team is in `"players"` array; opponent team is in `"opponent_players"` array

### Step 5: Write to Pending Queue
Use a Python script to append all extracted games to `data["pending"]` in `games.json`:

```python
import json, uuid

with open("games.json", "r") as f:
    data = json.load(f)

if "pending" not in data:
    data["pending"] = []

game = {
    "id": "game_" + uuid.uuid4().hex[:8],
    "date": "YYYY-MM-DD",
    "screenshot": "Screenshot YYYY-MM-DD HHMMSS.png",
    "opponent": "Opponent Name",
    "score": {"us": 0, "them": 0},
    "result": "W",  # or "L"
    "quarters": {"us": [0,0,0,0], "them": [0,0,0,0]},
    "players": [
        {
            "name": "CB13onTwitch", "grade": "A", "pos": "PG",
            "pts": 0, "reb": 0, "ast": 0, "stl": 0, "blk": 0, "fls": 0, "to": 0,
            "fgm": 0, "fga": 0, "tpm": 0, "tpa": 0, "ftm": 0, "fta": 0
        }
        # ... more USA players
    ],
    "opponent_players": [
        {
            "name": "OpponentName", "grade": "A-", "pos": "SG",
            "pts": 0, "reb": 0, "ast": 0, "stl": 0, "blk": 0, "fls": 0, "to": 0,
            "fgm": 0, "fga": 0, "tpm": 0, "tpa": 0, "ftm": 0, "fta": 0
        }
        # ... more opponent players
    ]
}

data["pending"].append(game)
with open("pending_games.json", "w") as f:
    json.dump(data, f, indent=2)
```

### Step 6: Clean Up Temp Files
Delete the cropped PNG files after extraction is complete.

### Step 7: User Approves on Dashboard
The user opens the **Review Queue** tab in the dashboard (`localhost:8505`) and clicks **Approve** or **Reject** for each pending game.

---

## USA eFIBA Known Roster

| Name | Typical Position |
|------|-----------------|
| CB13onTwitch | PG |
| JohhnyRed_ | SG |
| MamaImDatMan | SF |
| daws6x (also: dawb6x) | SF |
| SuperSeese (also: SuperSeenee) | SG |
| JOEMORNING (also: CEMORNING, JDEMONING) | PF |
| Nidal | SG/SF |

> Note: Gamertag spellings can vary slightly between screenshots due to font rendering. Use the closest match to the known roster list above.

---

## Opponent Name Normalization

When the same opponent appears across multiple games, use a consistent name:
- "20K unit" / "20k unit" / "Killa Bees" → use `"20K unit"`
- "SmokyGut47" / "Onsite" → use `"SmokyGut47"` (the team owner name shown)
- Always use the name shown in the **team header row** of the box score (not the logo/mascot)

---

## Verification Checklist

Before writing to pending, verify:
- [ ] USA team score matches `sum(quarters.us)` ≈ final score
- [ ] Opponent score matches `sum(quarters.them)` ≈ final score
- [ ] Each player's `pts` is consistent with `fgm*2 + tpm*1 + ftm` (3PM already included in FGM in 2K)
- [ ] `result` is `"W"` if `us > them`, `"L"` if `us < them`
- [ ] Date extracted from screenshot filename

---

## Notes

- **2K scoring rule**: In NBA 2K box scores, FGM includes 3PM (3-pointers count as field goals). So `pts = (fgm - tpm)*2 + tpm*3 + ftm`. Verify this adds up.
- **Confidence**: Target 99%+ confidence on all stat fields before writing to pending. Use the crop+upscale technique for small numbers.
- **Separate scouting**: Games scouted for **opponents** (e.g., Puerto Rico) go into `scouting.json` via `scout_data.py`, NOT into `games.json`. Only USA's own games go here.
