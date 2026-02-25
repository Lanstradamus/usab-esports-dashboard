# dashboard.py
import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from data import (load_games, save_games, get_player_totals, get_player_averages,
                  get_derived_stats, get_advanced_stats, normalize_name,
                  get_win_loss_splits, get_scoring_profile, get_scoring_shares,
                  get_positional_matchups, get_close_game_stats,
                  # New analytics engine
                  get_quarter_stats, get_momentum_analysis, get_team_stats_by_game,
                  get_opponent_player_intel, get_player_impact_index,
                  get_clutch_stats, get_hot_cold_streaks, get_per_game_player_stats,
                  get_best_lineup_combos, get_ai_coach_insights,
                  get_usage_and_pie, get_defensive_impact)
from pending import load_pending, approve_game, reject_game
from scout_data import (load_scouting, save_scouting,
                        approve_scout_game, reject_scout_game,
                        get_scout_player_profiles, get_scout_team_tendencies)

st.set_page_config(
    page_title="USAB Esports Dashboard",
    page_icon="🏀",
    layout="wide"
)

# ── Mobile-responsive CSS ────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Tab bar: horizontally scrollable on mobile ── */
.stTabs [data-baseweb="tab-list"] {
    overflow-x: auto !important;
    flex-wrap: nowrap !important;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    gap: 2px !important;
}
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { display: none; }
.stTabs [data-baseweb="tab"] {
    flex-shrink: 0 !important;
    white-space: nowrap !important;
}

/* ── Reduce main block padding on mobile ── */
@media (max-width: 768px) {
    .block-container {
        padding: 0.75rem 0.5rem 2rem 0.5rem !important;
    }
    h1 { font-size: 1.25rem !important; }
    h2 { font-size: 1.05rem !important; }
    h3 { font-size: 0.95rem !important; }

    /* Stack ALL columns vertically on small screens */
    [data-testid="column"] {
        width: 100% !important;
        min-width: 100% !important;
        flex: none !important;
    }

    /* Full-width metrics on mobile */
    [data-testid="metric-container"] {
        width: 100% !important;
        padding: 8px !important;
    }

    /* Prevent overflow on wide HTML card content */
    .stMarkdown { overflow-x: hidden !important; }

    /* Tighten the sidebar toggle area */
    [data-testid="stSidebarNav"] { display: none; }

    /* Charts: enforce min height so they don't collapse */
    .js-plotly-plot .plotly { min-height: 280px !important; }

    /* Make dataframes scroll horizontally instead of overflowing */
    [data-testid="stDataFrame"] {
        overflow-x: auto !important;
        max-width: 100vw !important;
    }

    /* Tab text slightly smaller so more tabs fit before scrolling */
    .stTabs [data-baseweb="tab"] p {
        font-size: 12px !important;
    }
}

/* ── Slightly tighter tab text on ALL screen sizes ── */
.stTabs [data-baseweb="tab"] p {
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)

# ── Authentication ──────────────────────────────────────────
def _to_dict(obj):
    """Recursively convert AttrDict/Secrets objects to plain dicts."""
    if hasattr(obj, "to_dict"):
        return _to_dict(obj.to_dict())
    if hasattr(obj, "items"):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj

_creds = _to_dict(st.secrets.get("credentials", {}))
authenticator = stauth.Authenticate(
    credentials=_creds,
    cookie_name="usab_esports",
    cookie_key=str(st.secrets.get("cookie_key", "changeme")),
    cookie_expiry_days=7,
)
authenticator.login()
if not st.session_state.get("authentication_status"):
    if st.session_state.get("authentication_status") is False:
        st.error("Incorrect username or password.")
    st.stop()

# ── Load data ──────────────────────────────────────────────
approved_data = load_games()
_all_games = approved_data["games"]
pending_data = load_pending()
pending_games = pending_data.get("pending", [])

st.title("🏀 USAB Esports — 2K Stats Dashboard")

with st.sidebar:
    st.markdown("### 🔍 Filter by Opponent")
    _all_opponents = sorted(set(g.get("opponent", "?") for g in _all_games))
    _opp_filter = st.multiselect(
        "Show only games vs:",
        options=_all_opponents,
        default=[],
        placeholder="All opponents (no filter)",
        key="global_opp_filter",
    )
    # Apply filter — if nothing selected, use all games
    games = [g for g in _all_games if g.get("opponent") in _opp_filter] if _opp_filter else _all_games

    if _opp_filter:
        _f_wins   = sum(1 for g in games if g["score"]["us"] > g["score"]["them"])
        _f_losses = len(games) - _f_wins
        st.caption(f"Showing **{len(games)} game{'s' if len(games) != 1 else ''}** vs {', '.join(_opp_filter)}  —  {_f_wins}W {_f_losses}L")
    else:
        st.caption(f"Showing all **{len(_all_games)} games**")

    st.divider()
    st.markdown("### 🎮 Game Window")
    _gw_total = len(games)
    _gw_opts  = sorted(set(list(range(3, _gw_total, 2)) + [_gw_total])) if _gw_total >= 3 else [_gw_total]
    _gw_n     = st.select_slider(
        "Last N games (all stats):",
        options=_gw_opts,
        value=_gw_total,
        key="global_game_window",
        help="Filters every single tab — players, trends, AI insights, clutch, analytics, everything",
    )
    # Redefine `games` to the selected window — all tabs inherit this automatically
    _gw_sorted = sorted(games, key=lambda g: g["date"])
    games      = _gw_sorted[-_gw_n:]
    _gw_range  = (f"{games[0]['date']} → {games[-1]['date']}"
                  if len(games) > 1 else games[0]["date"] if games else "—")
    st.caption(f"📅 **{_gw_n} of {_gw_total}** games  ·  {_gw_range}")

    st.divider()
    st.markdown("### 📌 Data Notes")
    st.caption(
        "Stats are OCR-extracted from box score screenshots. "
        "Numbers may be slightly off due to **quit-outs** (incomplete games), "
        "**mid-season roster changes**, and occasional OCR read errors. "
        "Use as a directional snapshot — not a perfect record."
    )
    st.divider()


def build_stat_rows(players, grade_key="grade"):
    rows = []
    for p in players:
        fgm = p.get("fgm", 0)
        fga = p.get("fga", 0)
        conf = p.get("confidence", {}).get("overall", 1.0)
        rows.append({
            "Name": p.get("name", ""),
            "Pos":  p.get("pos", ""),
            "GRD":  p.get(grade_key, "") or p.get("grd", "") or p.get("grade", ""),
            "PTS":  int(p.get("pts", 0)),
            "REB":  int(p.get("reb", 0)),
            "AST":  int(p.get("ast", 0)),
            "STL":  int(p.get("stl", 0)),
            "BLK":  int(p.get("blk", 0)),
            "FLS":  int(p.get("fls", 0)),
            "TO":   int(p.get("to",  0)),
            "FGM":  int(fgm),
            "FGA":  int(fga),
            "3PM":  int(p.get("tpm", 0)),
            "3PA":  int(p.get("tpa", 0)),
            "FTM":  int(p.get("ftm", 0)),
            "FTA":  int(p.get("fta", 0)),
            "FG%":  f"{fgm/fga*100:.0f}%" if fga > 0 else "N/A",
            "Conf%": f"{conf:.0%}",
        })
    return rows

# ── Tabs (Review Queue is always first) ───────────────────
# Load scouting data for tab badge
_scout_data    = load_scouting()
_scout_pending = _scout_data.get("pending", [])
_scout_games   = _scout_data.get("games", [])
_scout_team    = _scout_data.get("scout_team", "Opponent")

tab_review, tab_ai, tab_games, tab_players, tab_compare, tab_advanced, tab_scouting, \
tab_lineup, tab_teams, tab_analytics, tab_opp_intel, tab_clutch, \
tab_trends, tab_pix, tab_scout = st.tabs([
    f"📥 Review Queue ({len(pending_games)})",
    "🧠 AI Insights",
    "📋 Games",
    "👤 Players",
    "⚔️ Comparisons",
    "📊 Advanced Stats",
    "🎯 Scouting",
    "🔧 Lineup Builder",
    "🆚 Teams Faced",
    "🔥 Team Analytics",
    "🕵️ Opp Intel",
    "⚡ Clutch",
    "📈 Trends",
    "🏆 Perf Index",
    f"🔬 Scout ({_scout_team})",
])

# ══════════════════════════════════════════════════════════
# TAB 0: REVIEW QUEUE
# ══════════════════════════════════════════════════════════
with tab_review:
    if not pending_games:
        st.success("✅ No games pending review — all caught up!")
        st.info("When Claude Code extracts screenshots, they will appear here for your approval before going into analytics.")
    else:
        st.subheader(f"📥 {len(pending_games)} Game(s) Awaiting Your Approval")
        st.caption("Review each game. Edit any stats that look wrong. Click **Approve** to add to analytics, or **Discard** to remove.")

        for game in pending_games:
            players = game.get("players", [])
            opp_players_conf = game.get("opponent_players", [])
            all_players_conf = players + opp_players_conf
            avg_conf = sum(p.get("confidence", {}).get("overall", 1.0) for p in all_players_conf) / max(len(all_players_conf), 1)
            conf_emoji = "🟢" if avg_conf >= 0.90 else ("🟡" if avg_conf >= 0.75 else "🔴")
            needs_review = avg_conf < 0.85
            flag = " ⚠️ LOW CONFIDENCE — REVIEW CAREFULLY" if needs_review else ""
            header = f"{conf_emoji} vs {game['opponent']}  |  USA {game['score']['us']} – {game['score']['them']}  |  {game['date']}  |  {avg_conf:.0%} confident{flag}"

            with st.expander(header, expanded=needs_review):
                img_col, stats_col = st.columns([1, 2])

                # ── Left: screenshot + quarter scores ──
                with img_col:
                    screenshot_name = game["screenshot"]
                    possible_paths = [
                        Path("C:/Users/lance/Desktop/USAB Esports/2026/Screenshots/analyzed") / screenshot_name,
                        Path("C:/Users/lance/Desktop/USAB Esports/2026/Screenshots") / screenshot_name,
                        Path("C:/Users/lance/Desktop/USAB Esports/2026/analyzed") / screenshot_name,
                    ]
                    found_path = next((p for p in possible_paths if p.exists()), None)
                    if found_path:
                        st.image(found_path.read_bytes(), caption=screenshot_name, use_column_width=True)
                    else:
                        st.warning(f"Screenshot not found:\n`{screenshot_name}`")

                    st.divider()
                    st.markdown("**Quarter Scores**")
                    q_us = game["quarters"]["us"]
                    q_them = game["quarters"]["them"]
                    qdf = pd.DataFrame({
                        "Team": ["USA", game["opponent"]],
                        "Q1": [q_us[0], q_them[0]],
                        "Q2": [q_us[1], q_them[1]],
                        "Q3": [q_us[2], q_them[2]],
                        "Q4": [q_us[3], q_them[3]],
                        "Total": [game["score"]["us"], game["score"]["them"]]
                    })
                    st.dataframe(qdf, hide_index=True, use_container_width=True)

                    st.metric("Avg Confidence", f"{avg_conf:.0%}")

                # ── Right: editable stats ──
                with stats_col:
                    st.markdown("**All cells are editable — fix anything that looks wrong, then Approve:**")

                    player_rows = []
                    for p in players:
                        conf = p.get("confidence", {}).get("overall", 1.0)
                        low_fields = p.get("confidence", {}).get("low_fields", [])
                        player_rows.append({
                            "Name": p.get("name", ""),
                            "GRD": p.get("grade", ""),
                            "PTS": int(p.get("pts", 0)),
                            "REB": int(p.get("reb", 0)),
                            "AST": int(p.get("ast", 0)),
                            "STL": int(p.get("stl", 0)),
                            "BLK": int(p.get("blk", 0)),
                            "FLS": int(p.get("fls", 0)),
                            "TO":  int(p.get("to", 0)),
                            "FGM": int(p.get("fgm", 0)),
                            "FGA": int(p.get("fga", 0)),
                            "3PM": int(p.get("tpm", 0)),
                            "3PA": int(p.get("tpa", 0)),
                            "FTM": int(p.get("ftm", 0)),
                            "FTA": int(p.get("fta", 0)),
                            "Conf%": f"{conf:.0%}",
                            "Fix These": ", ".join(low_fields) if low_fields else "OK"
                        })

                    pdf = pd.DataFrame(player_rows)

                    def highlight_low_conf_review(row):
                        try:
                            val = float(str(row["Conf%"]).replace("%", "")) / 100
                        except Exception:
                            val = 1.0
                        if val < 0.85:
                            return ["background-color: #fff3cd; color: #856404"] * len(row)
                        return [""] * len(row)

                    styled_pending = pdf.style.apply(highlight_low_conf_review, axis=1)
                    edited = st.data_editor(
                        styled_pending,
                        hide_index=True,
                        use_container_width=True,
                        key=f"pending_editor_{game['id']}"
                    )

                    # Opponent editor (above buttons so Approve can read edits)
                    opp_players = game.get("opponent_players", [])
                    opp_edited = None
                    if opp_players:
                        st.divider()
                        st.markdown(f"**{game['opponent']} Player Stats** *(editable)*")
                        opp_edited = st.data_editor(
                            pd.DataFrame(build_stat_rows(opp_players, grade_key="grd")),
                            hide_index=True,
                            use_container_width=True,
                            key=f"opp_editor_{game['id']}"
                        )

                    btn_col1, btn_col2 = st.columns([3, 1])
                    with btn_col1:
                        if st.button(
                            f"✅ Approve & Add to Analytics",
                            key=f"approve_{game['id']}",
                            type="primary",
                            use_container_width=True
                        ):
                            approved_players = []
                            for _, row in edited.iterrows():
                                try:
                                    conf_val = float(str(row["Conf%"]).replace("%", "")) / 100
                                except Exception:
                                    conf_val = 1.0
                                approved_players.append({
                                    "name": str(row["Name"]),
                                    "grade": str(row["GRD"]),
                                    "pts": int(row["PTS"]),
                                    "reb": int(row["REB"]),
                                    "ast": int(row["AST"]),
                                    "stl": int(row["STL"]),
                                    "blk": int(row["BLK"]),
                                    "fls": int(row["FLS"]),
                                    "to":  int(row["TO"]),
                                    "fgm": int(row["FGM"]),
                                    "fga": int(row["FGA"]),
                                    "tpm": int(row["3PM"]),
                                    "tpa": int(row["3PA"]),
                                    "ftm": int(row["FTM"]),
                                    "fta": int(row["FTA"]),
                                    "confidence": {"overall": conf_val, "low_fields": []}
                                })
                            approved_opp_players = None
                            if opp_edited is not None:
                                approved_opp_players = []
                                for i, (_, row) in enumerate(opp_edited.iterrows()):
                                    try:
                                        conf_val = float(str(row["Conf%"]).replace("%", "")) / 100
                                    except Exception:
                                        conf_val = 1.0
                                    orig_low = opp_players[i].get("confidence", {}).get("low_fields", []) if i < len(opp_players) else []
                                    approved_opp_players.append({
                                        "name": str(row["Name"]),
                                        "pos":  str(row["Pos"]),
                                        "grd":  str(row["GRD"]),
                                        "pts":  int(row["PTS"]),
                                        "reb":  int(row["REB"]),
                                        "ast":  int(row["AST"]),
                                        "stl":  int(row["STL"]),
                                        "blk":  int(row["BLK"]),
                                        "fls":  int(row["FLS"]),
                                        "to":   int(row["TO"]),
                                        "fgm":  int(row["FGM"]),
                                        "fga":  int(row["FGA"]),
                                        "tpm":  int(row["3PM"]),
                                        "tpa":  int(row["3PA"]),
                                        "ftm":  int(row["FTM"]),
                                        "fta":  int(row["FTA"]),
                                        "confidence": {"overall": conf_val, "low_fields": orig_low}
                                    })
                            if approve_game(game["id"], approved_players, approved_opp_players):
                                st.success(f"✅ Game vs {game['opponent']} approved and added to analytics!")
                                st.rerun()
                            else:
                                st.error("Approval failed.")
                    with btn_col2:
                        if st.button(
                            "🗑️ Discard",
                            key=f"reject_{game['id']}",
                            use_container_width=True
                        ):
                            if reject_game(game["id"]):
                                st.warning("Game discarded.")
                                st.rerun()

# ══════════════════════════════════════════════════════════
# TAB 1: GAMES
# ══════════════════════════════════════════════════════════
with tab_games:
    if not games:
        st.info("No approved games yet. Go to the Review Queue tab to approve extracted games.")
    else:
        st.subheader("Game Log")
        total_games = len(games)
        wins = sum(1 for g in games if g["score"]["us"] > g["score"]["them"])
        losses = total_games - wins
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Games Played", total_games)
        col2.metric("Wins", wins)
        col3.metric("Losses", losses)
        col4.metric("Win %", f"{wins/total_games*100:.0f}%" if total_games else "N/A")

        st.divider()

        for game in reversed(games):
            score_us = game["score"]["us"]
            score_them = game["score"]["them"]
            result = "✅ W" if score_us > score_them else "❌ L"
            label = f"{result}  |  USA {score_us} – {score_them} {game['opponent']}  |  {game['date']}"

            with st.expander(label):
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

                st.markdown("**🇺🇸 USA Player Stats**")
                st.dataframe(
                    pd.DataFrame(build_stat_rows(game["players"], grade_key="grade")),
                    hide_index=True, use_container_width=True
                )

                opp_players = game.get("opponent_players", [])
                if opp_players:
                    st.markdown(f"**{game['opponent']} Player Stats**")
                    st.dataframe(
                        pd.DataFrame(build_stat_rows(opp_players, grade_key="grd")),
                        hide_index=True, use_container_width=True
                    )

# ══════════════════════════════════════════════════════════
# TAB 2: PLAYERS
# ══════════════════════════════════════════════════════════
with tab_players:
    if not games:
        st.info("No approved games yet. Approve games in the Review Queue tab first.")
    else:
        st.subheader("Player Stats")
        view = st.radio("View", ["Per Game Averages", "Season Totals"], horizontal=True)

        df = get_player_totals(games) if view == "Season Totals" else get_player_averages(games)
        df = get_derived_stats(df)

        display_cols = ["name","pos","games","pts","reb","ast","stl","blk","to","fls",
                        "fg_pct","tp_pct","ft_pct","fgm","fga","tpm","tpa","ftm","fta"]
        display_cols = [c for c in display_cols if c in df.columns]

        for col in ["fg_pct","tp_pct","ft_pct"]:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A")

        st.dataframe(
            df[display_cols].rename(columns={
                "name":"Player","pos":"Pos","games":"GP","pts":"PTS","reb":"REB",
                "ast":"AST","stl":"STL","blk":"BLK","to":"TO","fls":"FLS",
                "fg_pct":"FG%","tp_pct":"3P%","ft_pct":"FT%",
                "fgm":"FGM","fga":"FGA","tpm":"3PM","tpa":"3PA","ftm":"FTM","fta":"FTA"
            }),
            hide_index=True,
            use_container_width=True
        )

        st.divider()
        st.subheader("Stat Comparison Chart")
        stat_choice = st.selectbox("Compare players by:", ["pts","reb","ast","stl","blk","to","fgm","fga","tpm","tpa"], key="players_stat")
        raw_df = get_player_averages(games) if view == "Per Game Averages" else get_player_totals(games)
        chart_label = "Avg" if view == "Per Game Averages" else "Total"
        fig = px.bar(
            raw_df.sort_values(stat_choice, ascending=False),
            x="name", y=stat_choice, color="name",
            labels={"name": "Player", stat_choice: stat_choice.upper()},
            title=f"{chart_label} {stat_choice.upper()} by Player",
            text=stat_choice
        )
        fig.update_layout(showlegend=False, plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white")
        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("🕸️ Player Radar — Multi-Stat Profile")
        st.caption("Normalized across your roster. Bigger polygon = more dominant player.")
        radar_avgs = get_player_averages(games)
        radar_players_sel = st.multiselect("Players to include in radar:",
                                           sorted(radar_avgs["name"].unique()),
                                           default=sorted(radar_avgs["name"].unique())[:5],
                                           key="radar_players_sel")
        if radar_players_sel:
            r_df = radar_avgs[radar_avgs["name"].isin(radar_players_sel)].copy()
            r_stats = ["pts","reb","ast","stl","blk"]
            # Normalize each stat to 0-10 within the selected group
            r_norm = r_df[r_stats].copy()
            for col in r_stats:
                mn, mx = r_norm[col].min(), r_norm[col].max()
                r_norm[col] = (r_norm[col] - mn) / (mx - mn) * 10 if mx != mn else 5
            fig_pr = go.Figure()
            pr_colors = ["#FFD700","#1E88E5","#E53935","#43A047","#FB8C00","#8E24AA","#00BCD4"]
            for ci, (_, row) in enumerate(r_df.iterrows()):
                vals = [float(r_norm.loc[row.name, s]) for s in r_stats]
                vals += [vals[0]]
                fig_pr.add_trace(go.Scatterpolar(
                    r=vals, theta=[s.upper() for s in r_stats] + [r_stats[0].upper()],
                    fill="toself", name=row["name"],
                    line_color=pr_colors[ci % len(pr_colors)], opacity=0.7
                ))
            fig_pr.update_layout(
                polar=dict(bgcolor="#0e1117", radialaxis=dict(visible=True, range=[0,10])),
                paper_bgcolor="#0e1117", font_color="white",
                title="Player Radar (Normalized 0-10 within roster)"
            )
            st.plotly_chart(fig_pr, use_container_width=True)

        st.divider()
        st.subheader("📈 Player Shooting Efficiency")
        adv_p = get_advanced_stats(games)
        if not adv_p.empty:
            # Scatter: scoring load vs TS%
            adv_p_dedup = adv_p.sort_values("games", ascending=False).drop_duplicates("name")
            fig_eff = px.scatter(
                adv_p_dedup.dropna(subset=["ts_pct","scoring_load"]),
                x="scoring_load", y="ts_pct",
                color="name", size="games",
                text="name",
                title="Scoring Load vs True Shooting% (bubble = games played)",
                labels={"scoring_load":"Shot Attempts/Game","ts_pct":"True Shooting%"}
            )
            fig_eff.update_traces(textposition="top center")
            fig_eff.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                                   font_color="white", showlegend=False)
            st.plotly_chart(fig_eff, use_container_width=True)
            st.caption("Top-right = high volume AND efficient. That's your go-to scorer. Top-left = efficient but light usage (good role player). Bottom-right = volume scorer with poor efficiency (ball-dominant, consider role adjustment).")

        st.divider()
        st.subheader("📊 Per-Game Timeline (select player)")
        game_log_p = get_per_game_player_stats(games)
        if not game_log_p.empty:
            player_drill = st.selectbox("Select player for game-by-game breakdown:",
                                        sorted(game_log_p["name"].unique()), key="player_drill")
            player_log   = game_log_p[game_log_p["name"] == player_drill].copy()
            if not player_log.empty:
                # Build readable game labels (G1 vs Opp, G2 vs Opp, …)
                player_log = player_log.reset_index(drop=True)
                player_log["game_label"] = [f"G{i+1} vs {row['opponent'][:8]}" for i, row in player_log.iterrows()]
                drill_stat = st.radio("Stat to view:", ["pts","reb","ast","game_score","ts_pct"], horizontal=True, key="drill_stat")
                stat_label = {"pts":"PTS","reb":"REB","ast":"AST","game_score":"Game Score","ts_pct":"TS%"}[drill_stat]
                fig_drill = px.bar(
                    player_log, x="game_label", y=drill_stat,
                    color="result",
                    color_discrete_map={"W":"#4CAF50","L":"#F44336"},
                    title=f"{player_drill} — {stat_label} by Game",
                    text=drill_stat,
                    hover_data=["opponent","pts","reb","ast","game_score","ts_pct"]
                )
                fig_drill.update_layout(
                    plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white",
                    xaxis_tickangle=-45, xaxis_title="Game"
                )
                st.plotly_chart(fig_drill, use_container_width=True)

                # Mini stat table
                drill_display = player_log[["date","opponent","result","pts","reb","ast",
                                             "stl","blk","to","fg_pct","three_pct","ts_pct","game_score"]].copy()
                drill_display.columns = ["Date","Opp","W/L","PTS","REB","AST","STL","BLK","TO","FG%","3P%","TS%","GS"]
                st.dataframe(drill_display, hide_index=True, use_container_width=True)

# ══════════════════════════════════════════════════════════
# TAB 3: COMPARISONS
# ══════════════════════════════════════════════════════════
with tab_compare:
    if not games:
        st.info("No approved games yet. Approve games in the Review Queue tab first.")
    else:
        st.subheader("Head-to-Head Player Comparison")

        # Build position-aware player list: if a player played multiple positions,
        # offer them as separate entries (e.g. "Nidal (SG)" and "Nidal (SF)")
        _cmp_pos_counts: dict = {}
        for g in games:
            for p in g["players"]:
                nm = normalize_name(p["name"])
                pos = p.get("pos", "").strip()
                if not pos:          # skip blank/missing positions — don't create empty () bucket
                    continue
                if nm not in _cmp_pos_counts:
                    _cmp_pos_counts[nm] = {}
                _cmp_pos_counts[nm][pos] = _cmp_pos_counts[nm].get(pos, 0) + 1

        # Build selectable labels: "Name" if one pos, "Name (POS)" per pos if 2+ distinct named positions
        _cmp_options = []
        for nm in sorted(_cmp_pos_counts.keys()):
            positions = {p: c for p, c in _cmp_pos_counts[nm].items() if p}  # only named positions
            if len(positions) > 1:
                for pos in sorted(positions.keys()):
                    _cmp_options.append(f"{nm} ({pos})")
            else:
                _cmp_options.append(nm)

        if len(_cmp_options) < 2:
            st.info("Need at least 2 players in the data to compare.")
        else:
            col_a, col_b = st.columns(2)
            sel_a = col_a.selectbox("Player A", _cmp_options, index=0, key="compare_a")
            sel_b = col_b.selectbox("Player B", _cmp_options, index=min(1, len(_cmp_options)-1), key="compare_b")

            # Parse name and optional position filter from selection label
            def _parse_cmp_sel(sel):
                if sel.endswith(")") and " (" in sel:
                    nm, pos = sel.rsplit(" (", 1)
                    return nm, pos.rstrip(")")
                return sel, None

            cmp_name_a, cmp_pos_a = _parse_cmp_sel(sel_a)
            cmp_name_b, cmp_pos_b = _parse_cmp_sel(sel_b)

            # Show multi-position alert if stats are combined
            for _sel_nm, _sel_pos, _sel_label in [(cmp_name_a, cmp_pos_a, "Player A"), (cmp_name_b, cmp_pos_b, "Player B")]:
                _nm_positions = _cmp_pos_counts.get(_sel_nm, {})
                if len(_nm_positions) > 1 and _sel_pos is None:
                    _pos_summary = ", ".join(f"{pos} ({cnt}G)" for pos, cnt in sorted(_nm_positions.items()))
                    st.info(f"ℹ️ **{_sel_nm}** ({_sel_label}) played multiple positions: {_pos_summary}. Stats are combined — select a specific position role above to isolate.")

            # Build per-game averages filtered by position if needed
            def _build_cmp_avgs(name, pos_filter):
                """Compute per-game avgs for a player, optionally filtered by position."""
                stat_keys = ["pts","reb","ast","stl","blk","fls","to","fgm","fga","tpm","tpa","ftm","fta"]
                totals = {s: 0 for s in stat_keys}
                gp = 0
                for g in games:
                    for p in g["players"]:
                        if normalize_name(p["name"]) == name:
                            if pos_filter is None or p.get("pos","") == pos_filter:
                                gp += 1
                                for s in stat_keys:
                                    totals[s] += p.get(s, 0)
                if gp == 0:
                    return None, 0
                avgs = {s: round(totals[s] / gp, 1) for s in stat_keys}
                avgs["fg_pct"]  = round(totals["fgm"] / totals["fga"] * 100, 1) if totals["fga"] > 0 else None
                avgs["tp_pct"]  = round(totals["tpm"] / totals["tpa"] * 100, 1) if totals["tpa"] > 0 else None
                avgs["name"]    = name
                avgs["pos"]     = pos_filter or max(_cmp_pos_counts[name], key=_cmp_pos_counts[name].get)
                avgs["games"]   = gp
                return avgs, gp

            a_avgs, a_gp = _build_cmp_avgs(cmp_name_a, cmp_pos_a)
            b_avgs, b_gp = _build_cmp_avgs(cmp_name_b, cmp_pos_b)

            if a_avgs is None or b_avgs is None:
                st.warning("One or both players not found.")
            else:
                compare_stats = ["pts","reb","ast","stl","blk","to","fgm","fga","tpm","tpa"]
                stat_labels   = ["PTS","REB","AST","STL","BLK","TO","FGM","FGA","3PM","3PA"]

                # Label for chart titles includes position if filtered
                label_a = sel_a
                label_b = sel_b

                fig_compare = px.bar(
                    pd.DataFrame({
                        "Stat": stat_labels,
                        label_a: [a_avgs[s] for s in compare_stats],
                        label_b: [b_avgs[s] for s in compare_stats],
                    }).melt(id_vars="Stat", var_name="Player", value_name="Value"),
                    x="Stat", y="Value", color="Player", barmode="group",
                    title=f"{label_a} vs {label_b} — Per Game Averages"
                )
                fig_compare.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white")
                st.plotly_chart(fig_compare, use_container_width=True)

                st.subheader("Stat-by-Stat Breakdown")
                breakdown_rows = []
                for stat, slbl in zip(compare_stats, stat_labels):
                    va, vb = a_avgs[stat], b_avgs[stat]
                    better = (label_a if va < vb else label_b if vb < va else "TIE") if stat == "to" else (label_a if va > vb else label_b if vb > va else "TIE")
                    breakdown_rows.append({"Stat": slbl, label_a: va, label_b: vb, "Edge": better})
                # Also add shooting %
                for pct_key, pct_lbl in [("fg_pct","FG%"), ("tp_pct","3P%")]:
                    va2 = a_avgs.get(pct_key)
                    vb2 = b_avgs.get(pct_key)
                    if va2 is not None and vb2 is not None:
                        better2 = label_a if va2 > vb2 else label_b if vb2 > va2 else "TIE"
                        breakdown_rows.append({"Stat": pct_lbl, label_a: f"{va2:.1f}%", label_b: f"{vb2:.1f}%", "Edge": better2})
                st.dataframe(pd.DataFrame(breakdown_rows), hide_index=True, use_container_width=True)

                st.subheader("Win Rate When Playing")
                wr_cols = st.columns(2)
                for i, (pname, pos_filt, lbl) in enumerate([(cmp_name_a, cmp_pos_a, label_a), (cmp_name_b, cmp_pos_b, label_b)]):
                    pg = [g for g in games if any(
                        normalize_name(p["name"]) == pname and (pos_filt is None or p.get("pos","") == pos_filt)
                        for p in g["players"]
                    )]
                    pw = sum(1 for g in pg if g["score"]["us"] > g["score"]["them"])
                    wr_cols[i].metric(lbl, f"{pw/len(pg)*100:.0f}% ({pw}W-{len(pg)-pw}L)" if pg else "N/A")

# ══════════════════════════════════════════════════════════
# TAB 4: ADVANCED STATS
# ══════════════════════════════════════════════════════════
POS_ORDER = ["PG", "SG", "SF", "PF", "C"]
_POS_RANK = {p: i for i, p in enumerate(POS_ORDER)}


def _add_label(df: pd.DataFrame) -> pd.DataFrame:
    """Add a 'label' column that appends (POS) for players with multiple position rows."""
    counts = df["name"].value_counts()
    df = df.copy()
    df["label"] = df.apply(
        lambda r: f"{r['name']} ({r['pos']})" if counts[r["name"]] > 1 else r["name"],
        axis=1,
    )
    return df


def _sort_by_pos(df: pd.DataFrame) -> pd.DataFrame:
    """Sort a DataFrame by PG → SG → SF → PF → C order."""
    return df.assign(_r=df["pos"].map(_POS_RANK)).sort_values("_r").drop(columns="_r")


with tab_advanced:
    if not games:
        st.info("No approved games yet. Approve games in the Review Queue tab first.")
    else:
        adv_df = get_advanced_stats(games)

        # ── Section A: Advanced Stats Leaderboard ──────────────
        st.subheader("Advanced Stats Leaderboard")

        leaderboard = adv_df.sort_values("avg_game_score", ascending=False).copy()

        def fmt_pct(v):
            return f"{v:.1f}%" if v is not None and pd.notna(v) else "N/A"

        def fmt_asto(v):
            return f"{v:.2f}" if v is not None and pd.notna(v) else "N/A"

        leaderboard_display = pd.DataFrame({
            "Player":      leaderboard["name"].values,
            "Pos":         leaderboard["pos"].values,
            "GP":          leaderboard["games"].values,
            "Game Score":  leaderboard["avg_game_score"].values,
            "GS σ":        leaderboard["gs_std"].values,
            "TS%":         [fmt_pct(v) for v in leaderboard["ts_pct"]],
            "eFG%":        [fmt_pct(v) for v in leaderboard["efg_pct"]],
            "3PM/G":       leaderboard["three_pm_pg"].values,
            "3PA/G":       leaderboard["three_pa_pg"].values,
            "3P%":         [fmt_pct(v) for v in leaderboard["three_pct"]],
            "3PT Rate":    [fmt_pct(v) for v in leaderboard["three_rate"]],
            "Poss/G":      leaderboard["poss_used_pg"].values,
            "Off Rtg":     [fmt_pct(v).replace("%","") if v is not None and pd.notna(v) else "N/A" for v in leaderboard["off_rtg"]],
            "USG%":        [fmt_pct(v) for v in leaderboard["usg_pct"]],
            "AST/TO":      [fmt_asto(v) for v in leaderboard["ast_to"]],
            "Shot Load":   leaderboard["scoring_load"].values,
            "Win%":        [fmt_pct(v) for v in leaderboard["win_pct"]],
        })

        st.dataframe(
            leaderboard_display,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Game Score": st.column_config.NumberColumn("Game Score", format="%.1f"),
                "GS σ":       st.column_config.NumberColumn("GS σ (lower=better)"),
                "3PM/G":      st.column_config.NumberColumn("3PM/G",  format="%.1f"),
                "3PA/G":      st.column_config.NumberColumn("3PA/G",  format="%.1f"),
                "Poss/G":     st.column_config.NumberColumn("Poss/G", format="%.1f"),
                "Shot Load":  st.column_config.NumberColumn("Shot Load", format="%.1f"),
            }
        )

        st.caption("**Game Score**: Hollinger composite   |   **TS%/eFG%**: shooting efficiency   |   **3PT Rate**: % of shots that are 3s   |   **Poss/G**: possessions used per game (FGA+0.44×FTA+TO)   |   **Off Rtg**: pts scored per 100 possessions   |   **USG%**: % of team possessions used")

        st.divider()

        # ── Section B: Head-to-Head Advanced Comparison ────────
        st.subheader("Head-to-Head Advanced Comparison")

        all_players_adv = sorted(set(normalize_name(p["name"]) for g in games for p in g["players"]))

        if len(all_players_adv) < 2:
            st.info("Need at least 2 players in the data to compare.")
        else:
            adv_col_a, adv_col_b = st.columns(2)
            adv_player_a = adv_col_a.selectbox("Player A", all_players_adv, index=0, key="adv_compare_a")
            adv_player_b = adv_col_b.selectbox("Player B", all_players_adv, index=min(1, len(all_players_adv) - 1), key="adv_compare_b")

            adv_a_rows = adv_df[adv_df["name"] == adv_player_a]
            adv_b_rows = adv_df[adv_df["name"] == adv_player_b]

            if adv_a_rows.empty or adv_b_rows.empty:
                st.warning("One or both players not found in advanced stats.")
            else:
                adv_a = adv_a_rows.iloc[0]
                adv_b = adv_b_rows.iloc[0]

                # Big 6 metrics side by side
                m_col1, m_col2, m_col3, m_col4, m_col5, m_col6 = st.columns(6)

                def _fmt_metric(val, fmt="pct"):
                    if val is None or (isinstance(val, float) and pd.isna(val)):
                        return "N/A"
                    if fmt == "pct":
                        return f"{val:.1f}%"
                    if fmt == "ratio":
                        return f"{val:.2f}"
                    return f"{val:.1f}"

                m_col1.metric(f"{adv_player_a} — Game Score", _fmt_metric(adv_a["avg_game_score"], "plain"))
                m_col1.metric(f"{adv_player_b} — Game Score", _fmt_metric(adv_b["avg_game_score"], "plain"))

                m_col2.metric(f"{adv_player_a} — TS%", _fmt_metric(adv_a["ts_pct"], "pct"))
                m_col2.metric(f"{adv_player_b} — TS%", _fmt_metric(adv_b["ts_pct"], "pct"))

                m_col3.metric(f"{adv_player_a} — 3P%", _fmt_metric(adv_a["three_pct"], "pct"))
                m_col3.metric(f"{adv_player_b} — 3P%", _fmt_metric(adv_b["three_pct"], "pct"))

                m_col4.metric(f"{adv_player_a} — 3PM/G", _fmt_metric(adv_a["three_pm_pg"], "plain"))
                m_col4.metric(f"{adv_player_b} — 3PM/G", _fmt_metric(adv_b["three_pm_pg"], "plain"))

                m_col5.metric(f"{adv_player_a} — Win%", _fmt_metric(adv_a["win_pct"], "pct"))
                m_col5.metric(f"{adv_player_b} — Win%", _fmt_metric(adv_b["win_pct"], "pct"))

                m_col6.metric(f"{adv_player_a} — AST/TO", _fmt_metric(adv_a["ast_to"], "ratio"))
                m_col6.metric(f"{adv_player_b} — AST/TO", _fmt_metric(adv_b["ast_to"], "ratio"))

                st.divider()

                # Grouped bar chart: Game Score, TS%, eFG%, 3P%, AST/TO, Shot Load
                def _safe(v):
                    return float(v) if v is not None and pd.notna(v) else 0.0

                chart_stats = ["Game Score", "TS%", "eFG%", "3P%", "AST/TO", "Shot Load"]
                a_vals = [
                    _safe(adv_a["avg_game_score"]),
                    _safe(adv_a["ts_pct"]),
                    _safe(adv_a["efg_pct"]),
                    _safe(adv_a["three_pct"]),
                    _safe(adv_a["ast_to"]),
                    _safe(adv_a["scoring_load"]),
                ]
                b_vals = [
                    _safe(adv_b["avg_game_score"]),
                    _safe(adv_b["ts_pct"]),
                    _safe(adv_b["efg_pct"]),
                    _safe(adv_b["three_pct"]),
                    _safe(adv_b["ast_to"]),
                    _safe(adv_b["scoring_load"]),
                ]

                chart_df = pd.DataFrame({
                    "Stat":   chart_stats * 2,
                    "Player": [adv_player_a] * len(chart_stats) + [adv_player_b] * len(chart_stats),
                    "Value":  a_vals + b_vals,
                })

                fig_adv = px.bar(
                    chart_df,
                    x="Stat", y="Value", color="Player", barmode="group",
                    title=f"{adv_player_a} vs {adv_player_b} — Advanced Stats"
                )
                st.plotly_chart(fig_adv, use_container_width=True)

                st.divider()

                # Verdict block
                st.subheader("Verdict")
                verdict_lines = []

                def _edge(label, va, vb, higher_better=True, context_only=False):
                    if va is None or vb is None or (isinstance(va, float) and pd.isna(va)) or (isinstance(vb, float) and pd.isna(vb)):
                        return f"- **{label}**: Not enough data to compare."
                    diff = abs(va - vb)
                    if context_only:
                        return f"- **{label}**: {adv_player_a} = {va:.1f}, {adv_player_b} = {vb:.1f} (context only)"
                    if diff == 0:
                        return f"- **{label}**: Even — both at {va:.1f}"
                    winner = adv_player_a if (va > vb) == higher_better else adv_player_b
                    loser  = adv_player_b if winner == adv_player_a else adv_player_a
                    return f"- **{label}**: **{winner}** has the edge (+{diff:.1f} over {loser})"

                def _edge_ratio(label, va, vb):
                    if va is None or vb is None or (isinstance(va, float) and pd.isna(va)) or (isinstance(vb, float) and pd.isna(vb)):
                        return f"- **{label}**: Not enough data (division by zero or missing TO)."
                    diff = abs(va - vb)
                    if diff < 0.01:
                        return f"- **{label}**: Even — both at {va:.2f}"
                    winner = adv_player_a if va > vb else adv_player_b
                    loser  = adv_player_b if winner == adv_player_a else adv_player_a
                    return f"- **{label}**: **{winner}** has the edge (+{diff:.2f} over {loser})"

                verdict_lines.append(_edge("Game Score",       adv_a["avg_game_score"], adv_b["avg_game_score"]))
                verdict_lines.append(_edge("True Shooting %",  adv_a["ts_pct"],         adv_b["ts_pct"]))
                verdict_lines.append(_edge("Effective FG %",   adv_a["efg_pct"],        adv_b["efg_pct"]))
                verdict_lines.append(_edge("3PT %",            adv_a["three_pct"],      adv_b["three_pct"]))
                verdict_lines.append(_edge("3PT Rate (% of FGA that are 3s)", adv_a["three_rate"], adv_b["three_rate"], context_only=True))
                verdict_lines.append(_edge("Win %",            adv_a["win_pct"],        adv_b["win_pct"]))
                verdict_lines.append(_edge_ratio("AST/TO",     adv_a["ast_to"],         adv_b["ast_to"]))
                verdict_lines.append(_edge("Shot Load",        adv_a["scoring_load"],   adv_b["scoring_load"], context_only=True))

                st.markdown("\n".join(verdict_lines))

        # ── Section C: Win/Loss Performance Splits ──────────────
        st.divider()
        st.subheader("Win / Loss Performance Splits")

        wl_data = get_win_loss_splits(games)
        if not wl_data.empty:
            wl_df = _add_label(wl_data)
            # Only players with both wins and losses for the chart
            wl_both = wl_df[(wl_df["w_games"] > 0) & (wl_df["l_games"] > 0)].copy()

            def _raw_wl(v):
                return float(v) if pd.notna(v) else None

            wl_display_rows = []
            for _, row in wl_df.iterrows():
                wl_display_rows.append({
                    "Player":    row["label"],
                    "Pos":       row["pos"],
                    "W Games":   int(row["w_games"]) if pd.notna(row["w_games"]) else None,
                    "L Games":   int(row["l_games"]) if pd.notna(row["l_games"]) else None,
                    "W PTS":     _raw_wl(row["w_pts"]),
                    "L PTS":     _raw_wl(row["l_pts"]),
                    "W REB":     _raw_wl(row["w_reb"]),
                    "L REB":     _raw_wl(row["l_reb"]),
                    "W AST":     _raw_wl(row["w_ast"]),
                    "L AST":     _raw_wl(row["l_ast"]),
                    "W GS":      _raw_wl(row["w_gs"]),
                    "L GS":      _raw_wl(row["l_gs"]),
                })
            st.dataframe(
                pd.DataFrame(wl_display_rows),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "W Games":  st.column_config.NumberColumn("W Games",  format="%d"),
                    "L Games":  st.column_config.NumberColumn("L Games",  format="%d"),
                    "W PTS":    st.column_config.NumberColumn("W PTS",    format="%.1f"),
                    "L PTS":    st.column_config.NumberColumn("L PTS",    format="%.1f"),
                    "W REB":    st.column_config.NumberColumn("W REB",    format="%.1f"),
                    "L REB":    st.column_config.NumberColumn("L REB",    format="%.1f"),
                    "W AST":    st.column_config.NumberColumn("W AST",    format="%.1f"),
                    "L AST":    st.column_config.NumberColumn("L AST",    format="%.1f"),
                    "W GS":     st.column_config.NumberColumn("W GS",     format="%.1f"),
                    "L GS":     st.column_config.NumberColumn("L GS",     format="%.1f"),
                }
            )

            if not wl_both.empty:
                wl_chart_src = _sort_by_pos(wl_both)
                wl_ordered = wl_chart_src["label"].tolist()
                wl_chart_rows = []
                for _, row in wl_chart_src.iterrows():
                    wl_chart_rows.append({"Player": row["label"], "Game Score": row["w_gs"] if pd.notna(row["w_gs"]) else 0.0, "Result": "Win"})
                    wl_chart_rows.append({"Player": row["label"], "Game Score": row["l_gs"] if pd.notna(row["l_gs"]) else 0.0, "Result": "Loss"})
                fig_wl = px.bar(
                    pd.DataFrame(wl_chart_rows),
                    x="Player", y="Game Score", color="Result", barmode="group",
                    color_discrete_map={"Win": "#4CAF50", "Loss": "#F44336"},
                    title="Avg Game Score: Wins vs Losses",
                    category_orders={"Player": wl_ordered},
                )
                st.plotly_chart(fig_wl, use_container_width=True)
        else:
            st.info("Not enough game data for win/loss splits.")

        # ── Section D: Scoring Profile ──────────────────────────
        st.divider()
        st.subheader("Scoring Profile")

        sp_data = get_scoring_profile(games)
        if not sp_data.empty:
            sp_df = _add_label(sp_data)

            def _raw_sp(v):
                return float(v) if pd.notna(v) else None

            sp_sorted = sp_df.sort_values("stocks_per_game", ascending=False)
            sp_display_rows = []
            for _, row in sp_sorted.iterrows():
                sp_display_rows.append({
                    "Player":         row["label"],
                    "Pos":            row["pos"],
                    "GP":             int(row["games"]) if pd.notna(row["games"]) else None,
                    "2PT%":           _raw_sp(row["two_pct"]),
                    "3PT Rate":       _raw_sp(row["three_rate"]),
                    "FT Rate":        _raw_sp(row["ft_rate"]),
                    "% Pts from 2":   _raw_sp(row["pct_pts_from_2"]),
                    "% Pts from 3":   _raw_sp(row["pct_pts_from_3"]),
                    "% Pts from FT":  _raw_sp(row["pct_pts_from_ft"]),
                    "Stocks/G":       _raw_sp(row["stocks_per_game"]),
                    "TO Rate":        _raw_sp(row["to_rate"]),
                })
            st.dataframe(
                pd.DataFrame(sp_display_rows),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "GP":           st.column_config.NumberColumn("GP",           format="%d"),
                    "2PT%":         st.column_config.NumberColumn("2PT%",         format="%.1f%%"),
                    "3PT Rate":     st.column_config.NumberColumn("3PT Rate",     format="%.1f%%"),
                    "FT Rate":      st.column_config.NumberColumn("FT Rate",      format="%.1f%%"),
                    "% Pts from 2": st.column_config.NumberColumn("% Pts from 2", format="%.1f%%"),
                    "% Pts from 3": st.column_config.NumberColumn("% Pts from 3", format="%.1f%%"),
                    "% Pts from FT":st.column_config.NumberColumn("% Pts from FT",format="%.1f%%"),
                    "Stocks/G":     st.column_config.NumberColumn("Stocks/G",     format="%.2f"),
                    "TO Rate":      st.column_config.NumberColumn("TO Rate",      format="%.1f%%"),
                }
            )

            # Stacked bar: scoring source breakdown
            sp_chart_src = _sort_by_pos(sp_df)
            sp_ordered = sp_chart_src["label"].tolist()
            sp_stack_rows = []
            for _, row in sp_chart_src.iterrows():
                sp_stack_rows.append({
                    "Player": row["label"],
                    "% from 2PT": row["pct_pts_from_2"] if pd.notna(row["pct_pts_from_2"]) else 0.0,
                    "% from 3PT": row["pct_pts_from_3"] if pd.notna(row["pct_pts_from_3"]) else 0.0,
                    "% from FT":  row["pct_pts_from_ft"] if pd.notna(row["pct_pts_from_ft"]) else 0.0,
                })
            sp_stack_df = pd.DataFrame(sp_stack_rows).melt(
                id_vars="Player", var_name="Source", value_name="Pct"
            )
            fig_sp = px.bar(
                sp_stack_df, x="Player", y="Pct", color="Source", barmode="stack",
                title="Scoring Source Breakdown",
                color_discrete_map={
                    "% from 2PT": "#2196F3",
                    "% from 3PT": "#FF9800",
                    "% from FT":  "#9C27B0",
                },
                category_orders={"Player": sp_ordered},
            )
            fig_sp.update_layout(yaxis_title="% of Points")
            st.plotly_chart(fig_sp, use_container_width=True)
        else:
            st.info("Not enough game data for scoring profiles.")

        # ── Section E: Scoring Share & Load ─────────────────────
        st.divider()
        st.subheader("Scoring Share & Lead Scorer")

        ss_data = get_scoring_shares(games)
        if not ss_data.empty:
            ss_df = _add_label(ss_data.sort_values("avg_scoring_share", ascending=False))

            ss_chart_src = _sort_by_pos(ss_df)
            ss_ordered = ss_chart_src["label"].tolist()
            fig_ss = px.bar(
                ss_chart_src,
                x="label", y="avg_scoring_share",
                color="label",
                labels={"label": "Player", "avg_scoring_share": "Avg Scoring Share (%)"},
                title="Average Scoring Share by Player",
                category_orders={"label": ss_ordered},
            )
            fig_ss.update_layout(showlegend=False, yaxis_title="Avg Scoring Share (%)")
            st.plotly_chart(fig_ss, use_container_width=True)

            st.markdown("**Lead Scorer Frequency**")
            lead_cols = st.columns(min(len(ss_df), 4))
            for i, (_, row) in enumerate(ss_df.iterrows()):
                col_idx = i % len(lead_cols)
                total_games = int(row["games"]) if pd.notna(row["games"]) else 0
                lead_games = int(row["lead_scorer_games"]) if pd.notna(row["lead_scorer_games"]) else 0
                lead_cols[col_idx].metric(
                    row["label"],
                    f"Led scoring in {lead_games} / {total_games} games"
                )
        else:
            st.info("Not enough game data for scoring shares.")

        # ── Section F: Usage Rate & PIE ─────────────────────────
        st.divider()
        st.subheader("📐 Usage Rate & Player Impact Estimate (PIE)")
        st.caption("USG% = share of team possessions used. PIE = positive contributions / total team+player stats.")

        usg_pie = get_usage_and_pie(games)
        if not usg_pie.empty:
            # Deduplicate by name
            usg_pie_d = (usg_pie.sort_values("games", ascending=False)
                                .drop_duplicates("name").reset_index(drop=True))
            fig_pie = px.scatter(
                usg_pie_d.dropna(subset=["usg_pct","pie"]),
                x="usg_pct", y="pie",
                color="name", size="games",
                text="name",
                title="Usage Rate vs PIE (bubble = games played)",
                labels={"usg_pct":"Usage Rate %","pie":"Player Impact Estimate %"}
            )
            fig_pie.update_traces(textposition="top center")
            fig_pie.add_hline(y=usg_pie_d["pie"].mean(), line_dash="dash",
                              line_color="gray", annotation_text="Avg PIE")
            fig_pie.add_vline(x=usg_pie_d["usg_pct"].mean(), line_dash="dash",
                              line_color="gray", annotation_text="Avg USG%")
            fig_pie.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                                   font_color="white", showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)
            st.caption("Top-right quadrant = high usage AND high impact. That's your franchise player.")

            usg_disp = usg_pie_d[["name","pos","games","usg_pct","pie"]].copy()
            usg_disp.columns = ["Player","Pos","GP","USG%","PIE%"]
            st.dataframe(usg_disp, hide_index=True, use_container_width=True)

        # ── Section G: Defensive Impact ──────────────────────────
        st.divider()
        st.subheader("🛡️ Defensive Impact")
        def_data = get_defensive_impact(games)
        if not def_data.empty:
            def_d = (def_data.sort_values("games", ascending=False)
                             .drop_duplicates("name").reset_index(drop=True))
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                fig_stocks = px.bar(
                    def_d.sort_values("stocks_pg", ascending=False),
                    x="name", y="stocks_pg",
                    color="name", text="stocks_pg",
                    title="Stocks (STL+BLK) Per Game",
                    labels={"name":"Player","stocks_pg":"Stocks/G"}
                )
                fig_stocks.update_layout(showlegend=False, plot_bgcolor="#0e1117",
                                          paper_bgcolor="#0e1117", font_color="white")
                st.plotly_chart(fig_stocks, use_container_width=True)
            with d_col2:
                fig_fouls = px.bar(
                    def_d.sort_values("fls_pg", ascending=False),
                    x="name", y="fls_pg",
                    color="fls_pg", color_continuous_scale="RdYlGn_r",
                    text="fls_pg",
                    title="Fouls Per Game (lower = better)",
                    labels={"name":"Player","fls_pg":"Fouls/G"}
                )
                fig_fouls.update_layout(showlegend=False, plot_bgcolor="#0e1117",
                                         paper_bgcolor="#0e1117", font_color="white")
                st.plotly_chart(fig_fouls, use_container_width=True)

            def_disp = def_d[["name","pos","games","stl_pg","blk_pg","stocks_pg","fls_pg","foul_rate","avg_opp_pts"]].copy()
            def_disp.columns = ["Player","Pos","GP","STL/G","BLK/G","Stocks/G","FLS/G","Foul Rate%","Avg Opp Pts When Playing"]
            st.dataframe(def_disp, hide_index=True, use_container_width=True)
            st.caption("Foul Rate% = avg fouls / 4 (max fouls before foul-out). Avg Opp Pts = team defensive proxy when this player is in the lineup.")

# ══════════════════════════════════════════════════════════
# TAB 5: SCOUTING
# ══════════════════════════════════════════════════════════
with tab_scouting:
    if not games:
        st.info("No approved games yet.")
    else:
        # ── Section A: Positional Matchup Battle ────────────────
        st.subheader("Positional Matchup Battle")

        pm_data = get_positional_matchups(games)
        if not pm_data.empty:
            pm_df = pm_data

            def _fmt_pm(v, decimals=1):
                return f"{v:.{decimals}f}" if pd.notna(v) else "N/A"

            def _raw_pm(v):
                return float(v) if pd.notna(v) else None

            def _edge(a, b):
                return round(float(a) - float(b), 1) if (pd.notna(a) and pd.notna(b)) else None

            pm_display_rows = []
            weak_positions = set()
            for _, row in pm_df.iterrows():
                if pd.notna(row["opp_avg_pts"]) and pd.notna(row["our_avg_pts"]) and row["opp_avg_pts"] > row["our_avg_pts"]:
                    weak_positions.add(row["pos"])
                pm_display_rows.append({
                    "Pos":            row["pos"],
                    "Games":          int(row["games"]) if pd.notna(row["games"]) else None,
                    "Our Avg PTS":    _raw_pm(row["our_avg_pts"]),
                    "Opp Avg PTS":    _raw_pm(row["opp_avg_pts"]),
                    "Pts Edge":       _edge(row["our_avg_pts"], row["opp_avg_pts"]),
                    "Our GS":         _raw_pm(row["our_avg_gs"]),
                    "Opp GS":         _raw_pm(row["opp_avg_gs"]),
                    "GS Edge":        _edge(row["our_avg_gs"], row["opp_avg_gs"]),
                    "USA Win% at Pos": _raw_pm(row["usa_wins_matchup"]),
                })
            pm_display_df = pd.DataFrame(pm_display_rows)

            def _highlight_weak(row):
                if row["Pos"] in weak_positions:
                    return ["background-color: #fff3cd; color: #856404"] * len(row)
                return [""] * len(row)

            st.dataframe(
                pm_display_df.style.apply(_highlight_weak, axis=1),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Games":          st.column_config.NumberColumn("Games",          format="%d"),
                    "Our Avg PTS":    st.column_config.NumberColumn("Our Avg PTS",    format="%.1f",  help="Our team's average points scored at this position per game. Higher is better."),
                    "Opp Avg PTS":    st.column_config.NumberColumn("Opp Avg PTS",    format="%.1f",  help="Opponent's average points scored at this position per game. Lower is better for us."),
                    "Pts Edge":       st.column_config.NumberColumn("Pts Edge",       format="%.1f",  help="Our avg PTS minus opponent avg PTS. Positive = we win the scoring battle. Higher is better."),
                    "Our GS":         st.column_config.NumberColumn("Our GS",         format="%.1f",  help="Our team's avg Hollinger Game Score at this position. Higher is better."),
                    "Opp GS":         st.column_config.NumberColumn("Opp GS",         format="%.1f",  help="Opponent's avg Hollinger Game Score at this position. Lower = easier matchup for us."),
                    "GS Edge":        st.column_config.NumberColumn("GS Edge",        format="%.1f",  help="Our avg GS minus opponent avg GS. Positive = we dominate this slot. Higher is better."),
                    "USA Win% at Pos":st.column_config.NumberColumn("USA Win% at Pos",format="%.1f%%",help="% of games where our player's GS exceeded the opponent's. 50%+ = we win this matchup more often than not."),
                }
            )
            st.caption("Highlighted rows: opponent outscores us at that position.")

            # Grouped bar chart: our_avg_pts vs opp_avg_pts by position
            pm_chart_rows = []
            for _, row in pm_df.iterrows():
                pm_chart_rows.append({"Position": row["pos"], "Avg PTS": row["our_avg_pts"] if pd.notna(row["our_avg_pts"]) else 0.0, "Team": "USA"})
                pm_chart_rows.append({"Position": row["pos"], "Avg PTS": row["opp_avg_pts"] if pd.notna(row["opp_avg_pts"]) else 0.0, "Team": "Opponent"})
            fig_pm = px.bar(
                pd.DataFrame(pm_chart_rows),
                x="Position", y="Avg PTS", color="Team", barmode="group",
                color_discrete_map={"USA": "#2196F3", "Opponent": "#F44336"},
                title="Points Scored by Position: USA vs Opponent",
                category_orders={"Position": POS_ORDER},
            )
            st.plotly_chart(fig_pm, use_container_width=True)

            # ── Section B: Opponent Threat by Position ──────────
            st.divider()
            st.subheader("Opponent Threat by Position")

            pm_threat = pm_df.sort_values("opp_avg_pts", ascending=False)
            for rank, (_, row) in enumerate(pm_threat.iterrows()):
                opp_pts = _fmt_pm(row["opp_avg_pts"])
                our_pts = _fmt_pm(row["our_avg_pts"])
                icon = "⚠️" if row["pos"] in weak_positions else "✅"
                st.markdown(
                    f"{icon} **#{rank+1} — {row['pos']}**: Opponents avg **{opp_pts} pts** vs our **{our_pts} pts** "
                    f"({int(row['games']) if pd.notna(row['games']) else 'N/A'} games)"
                )
        else:
            st.info("Not enough opponent data for positional matchups.")

        # ── Section C: Close Game Performance ──────────────────
        st.divider()
        st.subheader("Close Game Performance")
        st.caption("Close games = margin <= 10 pts")

        cg_data = get_close_game_stats(games)
        if not cg_data.empty:
            cg_df = _add_label(cg_data)
            cg_with_close = cg_df[cg_df["close_games"] >= 1].copy()

            def _raw_float(v):
                return float(v) if pd.notna(v) else None

            if cg_with_close.empty:
                st.info("No close games in the dataset yet.")
            else:
                cg_display_rows = []
                for _, row in cg_with_close.iterrows():
                    close_gs = _raw_float(row["close_gs"])
                    other_gs = _raw_float(row["other_gs"])
                    cg_display_rows.append({
                        "Player":      row["label"],
                        "Pos":         row["pos"],
                        "Close Games": int(row["close_games"]) if pd.notna(row["close_games"]) else None,
                        "Close GS":    close_gs,
                        "Other GS":    other_gs,
                        "GS Diff":     round(close_gs - other_gs, 1) if (close_gs is not None and other_gs is not None) else None,
                        "Close PTS":   _raw_float(row["close_pts"]),
                        "Other PTS":   _raw_float(row["other_pts"]),
                    })
                st.dataframe(
                    pd.DataFrame(cg_display_rows),
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Close Games": st.column_config.NumberColumn(
                            "Close Games",
                            format="%d",
                            help="Number of games this player appeared in where the final margin was ≤10 pts."
                        ),
                        "Close GS": st.column_config.NumberColumn(
                            "Close GS",
                            format="%.1f",
                            help="Avg Hollinger Game Score in close games (margin ≤10 pts). Higher is better."
                        ),
                        "Other GS": st.column_config.NumberColumn(
                            "Other GS",
                            format="%.1f",
                            help="Avg Hollinger Game Score in non-close games (margin >10 pts). Higher is better."
                        ),
                        "GS Diff": st.column_config.NumberColumn(
                            "GS Diff",
                            format="%.1f",
                            help="Close game GS minus other game GS. Positive = player performs BETTER under pressure. Negative = drops off in tight games. Higher is better."
                        ),
                        "Close PTS": st.column_config.NumberColumn(
                            "Close PTS",
                            format="%.1f",
                            help="Avg points per game in close games (margin ≤10 pts)."
                        ),
                        "Other PTS": st.column_config.NumberColumn(
                            "Other PTS",
                            format="%.1f",
                            help="Avg points per game in non-close games (margin >10 pts)."
                        ),
                    }
                )

                cg_chart_src = _sort_by_pos(cg_with_close)
                cg_ordered = cg_chart_src["label"].tolist()
                cg_chart_rows = []
                for _, row in cg_chart_src.iterrows():
                    cg_chart_rows.append({"Player": row["label"], "Avg Game Score": row["close_gs"] if pd.notna(row["close_gs"]) else 0.0, "Context": "Close Games"})
                    cg_chart_rows.append({"Player": row["label"], "Avg Game Score": row["other_gs"] if pd.notna(row["other_gs"]) else 0.0, "Context": "Other Games"})
                fig_cg = px.bar(
                    pd.DataFrame(cg_chart_rows),
                    x="Player", y="Avg Game Score", color="Context", barmode="group",
                    color_discrete_map={"Close Games": "#FF9800", "Other Games": "#607D8B"},
                    title="Game Score: Close Games vs Other Games",
                    category_orders={"Player": cg_ordered},
                )
                st.plotly_chart(fig_cg, use_container_width=True)
        else:
            st.info("Not enough game data for close game analysis.")

# ══════════════════════════════════════════════════════════
# TAB 6: LINEUP BUILDER
# ══════════════════════════════════════════════════════════
with tab_lineup:
    if not games:
        st.info("No approved games yet. Approve games in the Review Queue tab first.")
    else:
        st.subheader("🔧 Lineup Builder & Optimizer")
        st.caption("Build custom 5-man lineups, project output, and see historical lineup performance.")

        # ── Historical Best Lineups ───────────────────────────
        st.markdown("### 📊 Historical Lineup Performance")
        hist_combos = get_best_lineup_combos(games)
        if not hist_combos.empty:
            for i, (_, row) in enumerate(hist_combos.head(5).iterrows()):
                medal = "🥇" if i==0 else "🥈" if i==1 else "🥉" if i==2 else f"#{i+1}"
                win_color = "#4CAF50" if row["win_pct"] >= 50 else "#F44336"
                st.markdown(f"""
<div style="background:#111827;border:1px solid #2d3748;border-radius:8px;padding:12px;margin:6px 0;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div><span style="font-size:16px">{medal}</span>
    <span style="font-weight:bold;margin-left:8px;font-size:14px">{row['lineup']}</span></div>
    <div style="display:flex;gap:20px;font-size:13px;">
      <span style="color:{win_color};font-weight:bold">{row['win_pct']}% W</span>
      <span>{row['games']}G played</span>
      <span>Avg GS: <b>{row['avg_team_gs']}</b></span>
      <span>Avg Pts: <b>{row['avg_team_pts']}</b></span>
    </div>
  </div>
</div>""", unsafe_allow_html=True)
        else:
            st.info("Need multiple games to rank lineup combinations.")

        st.divider()

        # ── Custom Lineup Builder ─────────────────────────────
        st.markdown("### 🛠️ Build a Custom Lineup")
        all_players_lineup = sorted(set(normalize_name(p["name"]) for g in games for p in g["players"]))
        selected_lineup = st.multiselect("Choose players (max 5):", all_players_lineup, max_selections=5)

        if selected_lineup:
            avgs_l   = get_derived_stats(get_player_averages(games))
            adv_l    = get_advanced_stats(games)
            pix_l    = get_player_impact_index(games)
            # Deduplicate by name, keep row with most games
            lineup_df = (avgs_l[avgs_l["name"].isin(selected_lineup)]
                         .sort_values("games", ascending=False)
                         .drop_duplicates(subset=["name"], keep="first")
                         .copy())
            adv_sel   = (adv_l[adv_l["name"].isin(selected_lineup)]
                         .sort_values("games", ascending=False)
                         .drop_duplicates(subset=["name"], keep="first"))
            pix_sel   = pix_l[pix_l["name"].isin(selected_lineup)]

            stat_cols_l = ["pts","reb","ast","stl","blk","to"]
            projected   = lineup_df[stat_cols_l].sum().round(1)

            # Synergy score: avg impact score of selected players
            synergy = round(pix_sel["impact_score"].mean(), 1) if not pix_sel.empty else None
            avg_ts  = round(adv_sel["ts_pct"].mean(), 1) if not adv_sel.empty else None
            avg_asto = round(adv_sel["ast_to"].mean(), 2) if not adv_sel.empty else None

            # Estimated win% from historical data: look up if this exact combo played
            lineup_key = tuple(sorted(selected_lineup))
            _hist_match = None
            for _, _row in hist_combos.iterrows():
                _players_in_row = set(_row["lineup"].split(" | "))
                if _players_in_row == set(selected_lineup):
                    _hist_match = _row
                    break

            st.markdown("### 📈 Projected Output (Per Game)")
            _lc1,_lc2,_lc3,_lc4,_lc5,_lc6,_lc7,_lc8 = st.columns(8)
            _lc1.metric("PPG",     projected["pts"])
            _lc2.metric("RPG",     projected["reb"])
            _lc3.metric("APG",     projected["ast"])
            _lc4.metric("SPG",     projected["stl"])
            _lc5.metric("BPG",     projected["blk"])
            _lc6.metric("TOPG",    projected["to"])
            _lc7.metric("Synergy", f"{synergy}/100" if synergy else "N/A")
            _lc8.metric("Lineup TS%", f"{avg_ts}%" if avg_ts else "N/A")

            if _hist_match is not None:
                st.success(f"✅ This exact lineup has **{_hist_match['games']} game(s)** of history: "
                           f"**{_hist_match['win_pct']}% win rate**, avg **{_hist_match['avg_team_pts']} pts**.")
            else:
                st.info("No historical data for this exact lineup. Projections based on individual averages.")

            st.divider()

            # Individual contributions table
            st.markdown("### 👥 Individual Contributions")
            # Ensure adv_sel has exactly one row per name before merge
            adv_sel_deduped = (adv_sel
                               .drop_duplicates(subset=["name"], keep="first")
                               [["name","avg_game_score","ts_pct","ast_to","scoring_load"]])
            _adv_merged = (lineup_df
                           .drop_duplicates(subset=["name"], keep="first")
                           .merge(adv_sel_deduped, on="name", how="left")
                           .drop_duplicates(subset=["name"], keep="first")
                           .reset_index(drop=True))
            contrib_disp = _adv_merged[["name","pts","reb","ast","stl","blk","to",
                                        "avg_game_score","ts_pct","ast_to"]].copy()
            contrib_disp.columns = ["Player","PTS","REB","AST","STL","BLK","TO","GS","TS%","AST/TO"]
            st.dataframe(contrib_disp, hide_index=True, use_container_width=True)

            # Radar chart — normalized so all stats are on same 0-10 scale
            st.markdown("### 🕸️ Player Radar Comparison")
            st.caption("Each stat normalized 0–10 within this lineup. Bigger = better relative to teammates.")
            radar_stats  = ["pts","reb","ast","stl","blk"]
            radar_labels = ["Scoring","Rebounding","Playmaking","Steals","Blocks"]
            radar_data   = lineup_df[["name"] + radar_stats].copy()
            if not radar_data.empty:
                # Normalize each stat to 0-10 within the selected lineup
                radar_norm = radar_data[radar_stats].copy()
                for col in radar_stats:
                    mn, mx = radar_norm[col].min(), radar_norm[col].max()
                    radar_norm[col] = (radar_norm[col] - mn) / (mx - mn) * 10 if mx != mn else 5.0
                fig_radar = go.Figure()
                radar_colors = ["#FFD700","#1E88E5","#E53935","#43A047","#FB8C00","#AB47BC","#26C6DA"]
                for ci, (_, row) in enumerate(radar_data.iterrows()):
                    vals = [float(radar_norm.loc[row.name, s]) if pd.notna(radar_norm.loc[row.name, s]) else 0
                            for s in radar_stats]
                    raw_vals = [float(row[s]) if pd.notna(row[s]) else 0 for s in radar_stats]
                    hover = [f"{radar_labels[i]}: {raw_vals[i]:.1f}" for i in range(len(radar_stats))]
                    vals_closed = vals + [vals[0]]
                    fig_radar.add_trace(go.Scatterpolar(
                        r=vals_closed,
                        theta=radar_labels + [radar_labels[0]],
                        fill="toself", name=row["name"],
                        line_color=radar_colors[ci % len(radar_colors)], opacity=0.75,
                        hovertext=hover + [hover[0]], hoverinfo="text+name"
                    ))
                fig_radar.update_layout(
                    polar=dict(bgcolor="#0e1117", radialaxis=dict(visible=True, range=[0,10],
                               tickfont=dict(color="#888"), gridcolor="#333")),
                    paper_bgcolor="#0e1117", font_color="white",
                    title="Lineup Player Radar (Normalized — hover for real values)",
                    legend=dict(bgcolor="#0e1117")
                )
                st.plotly_chart(fig_radar, use_container_width=True)

            # Stacked bar: one trace per player, sorted per-stat so biggest is always on bottom
            st.markdown("### 🏗️ Lineup Contribution Breakdown")
            stat_cols   = ["pts","reb","ast","stl","blk"]
            stat_labels = ["PTS","REB","AST","STL","BLK"]
            bar_colors  = ["#1E88E5","#FB8C00","#E53935","#43A047","#FFD700","#AB47BC","#26C6DA"]
            fig_contr   = go.Figure()
            # For each stat, sort players by that stat descending so the biggest chunk is at the bottom
            # We do this by adding one go.Bar trace per player, but ordering the x-categories per stat
            # Simpler: build one horizontal grouped set per stat sorted independently
            # Best approach: one trace per player sorted by PTS (primary stat)
            pts_order = lineup_df.sort_values("pts", ascending=True)["name"].tolist()
            for ci, name in enumerate(pts_order):
                row = lineup_df[lineup_df["name"] == name].iloc[0]
                vals = [float(row[s]) if pd.notna(row[s]) else 0 for s in stat_cols]
                fig_contr.add_trace(go.Bar(
                    name=name, x=stat_labels, y=vals,
                    marker_color=bar_colors[ci % len(bar_colors)],
                    hovertemplate="%{x}: %{y:.1f}<extra>" + name + "</extra>"
                ))
            fig_contr.update_layout(
                barmode="stack",
                title="Who Contributes What in This Lineup",
                plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white",
                legend=dict(traceorder="reversed")  # highest scorer shows on top of legend
            )
            st.plotly_chart(fig_contr, use_container_width=True)

            # Synergy rating breakdown
            st.markdown("### 🧬 Synergy Analysis")
            _sa1, _sa2, _sa3 = st.columns(3)
            _sa1.metric("Lineup Synergy Score", f"{synergy}/100" if synergy else "N/A",
                        help="Average Impact Index across selected players. Higher = stronger lineup.")
            _sa2.metric("Combined AST/TO", f"{avg_asto}" if avg_asto else "N/A",
                        help="Average assist-to-turnover ratio. Higher = cleaner ball movement.")
            # Scoring balance: lower std dev of pts = more balanced
            pts_vals = lineup_df["pts"].dropna().tolist()
            pts_std  = round(pd.Series(pts_vals).std(), 1) if len(pts_vals) > 1 else None
            _sa3.metric("Scoring Balance σ", f"{pts_std}" if pts_std else "N/A",
                        help="Std dev of avg pts across players. Lower = more balanced scoring load.")

            if synergy:
                grade = ("S" if synergy >= 70 else "A" if synergy >= 55 else
                         "B" if synergy >= 40 else "C" if synergy >= 25 else "D")
                grade_color = {"S":"#FFD700","A":"#4CAF50","B":"#1E88E5","C":"#FF9800","D":"#F44336"}[grade]
                st.markdown(f"""
<div style="text-align:center;padding:20px;background:#111827;border-radius:12px;margin:12px 0;">
  <div style="font-size:60px;font-weight:bold;color:{grade_color}">{grade}</div>
  <div style="font-size:18px;color:#ccc">Lineup Grade</div>
  <div style="font-size:13px;color:#888;margin-top:8px">Based on composite Impact Index of selected players</div>
</div>""", unsafe_allow_html=True)

        else:
            st.info("Select players above to build a lineup and see projections.")

# ══════════════════════════════════════════════════════════
# TAB 7: TEAMS FACED
# ══════════════════════════════════════════════════════════
with tab_teams:
    if not games:
        st.info("No approved games yet. Approve games in the Review Queue tab first.")
    else:
        st.subheader("Teams Faced")
        team_rows = {}
        for game in games:
            opp = game["opponent"]
            if opp not in team_rows:
                team_rows[opp] = {"Opponent": opp, "GP": 0, "W": 0, "L": 0,
                                   "_pts_for": 0, "_pts_against": 0, "Scores": []}
            r = team_rows[opp]
            r["GP"] += 1
            us, them = game["score"]["us"], game["score"]["them"]
            r["_pts_for"] += us
            r["_pts_against"] += them
            r["Scores"].append(f"{us}-{them}")
            if us > them: r["W"] += 1
            else: r["L"] += 1

        team_display = []
        for opp, r in team_rows.items():
            gp = r["GP"]
            team_display.append({
                "Opponent": opp, "GP": gp, "W": r["W"], "L": r["L"],
                "Win%": f"{r['W']/gp*100:.0f}%",
                "Avg Pts For": round(r["_pts_for"]/gp, 1),
                "Avg Pts Against": round(r["_pts_against"]/gp, 1),
                "Scores": "  |  ".join(r["Scores"])
            })

        team_df = pd.DataFrame(team_display).sort_values(["W","GP"], ascending=False)
        st.dataframe(team_df.drop(columns=["Scores"]), hide_index=True, use_container_width=True)

        # Scores detail
        with st.expander("📋 All Scores vs Each Opponent"):
            for _, r in team_df.iterrows():
                st.markdown(f"**{r['Opponent']}**: {r['Scores']}")

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            fig_teams = px.bar(
                team_df, x="Opponent", y=["Avg Pts For","Avg Pts Against"],
                barmode="group", title="Points For vs Against by Opponent",
                color_discrete_map={"Avg Pts For": "#2196F3", "Avg Pts Against": "#F44336"}
            )
            fig_teams.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white")
            st.plotly_chart(fig_teams, use_container_width=True)

        with col_t2:
            # Win% per opponent
            team_df["Win% Num"] = team_df["W"] / team_df["GP"] * 100
            fig_winpct = px.bar(
                team_df.sort_values("Win% Num", ascending=False),
                x="Opponent", y="Win% Num",
                color="Win% Num",
                color_continuous_scale="RdYlGn",
                title="Win% vs Each Opponent",
                labels={"Win% Num":"Win%"},
                text=team_df.sort_values("Win% Num", ascending=False)["Win%"]
            )
            fig_winpct.add_hline(y=50, line_dash="dash", line_color="white", annotation_text="50%")
            fig_winpct.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                                      font_color="white", showlegend=False)
            st.plotly_chart(fig_winpct, use_container_width=True)

        # Net rating per opponent
        team_df["Net Rtg"] = team_df["Avg Pts For"] - team_df["Avg Pts Against"]
        fig_net = px.bar(
            team_df.sort_values("Net Rtg", ascending=False),
            x="Opponent", y="Net Rtg",
            color="Net Rtg",
            color_continuous_scale="RdYlGn",
            title="Net Rating (Avg Margin) vs Each Opponent",
            text=team_df.sort_values("Net Rtg", ascending=False)["Net Rtg"].round(1)
        )
        fig_net.add_hline(y=0, line_dash="dash", line_color="white")
        fig_net.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                               font_color="white", showlegend=False)
        st.plotly_chart(fig_net, use_container_width=True)


# ══════════════════════════════════════════════════════════
# TAB 8: TEAM ANALYTICS
# ══════════════════════════════════════════════════════════
with tab_analytics:
    if not games:
        st.info("No approved games yet.")
    else:
        st.subheader("🔥 Team Analytics — Command Center")

        team_ts = get_team_stats_by_game(games)
        momentum = get_momentum_analysis(games)
        q_stats  = get_quarter_stats(games)

        # ── Section A: Season Summary Metrics ─────────────────
        st.markdown("### Season Summary")
        _ca1, _ca2, _ca3, _ca4, _ca5, _ca6, _ca7, _ca8 = st.columns(8)
        if not team_ts.empty:
            _ca1.metric("Avg Pts Scored",   round(team_ts["us_pts"].mean(), 1))
            _ca2.metric("Avg Pts Allowed",  round(team_ts["them_pts"].mean(), 1))
            _ca3.metric("Avg Rebounds",     round(team_ts["us_reb"].mean(), 1),
                        delta=f"{round(team_ts['reb_margin'].mean(), 1):+.1f} margin")
            _ca4.metric("Avg Assists",      round(team_ts["us_ast"].mean(), 1))
            _ca5.metric("Avg Turnovers",    round(team_ts["us_to"].mean(), 1))
            _ca6.metric("Avg Team TS%",
                        f"{round(team_ts['us_ts_pct'].mean(), 1)}%" if team_ts["us_ts_pct"].notna().any() else "N/A")
            _ca7.metric("Off Rtg",
                        f"{round(team_ts['off_rtg'].mean(), 1)}" if "off_rtg" in team_ts and team_ts["off_rtg"].notna().any() else "N/A",
                        help="Points scored per 100 possessions")
            _ca8.metric("Net Rtg",
                        f"{round(team_ts['net_rtg'].mean(), 1):+.1f}" if "net_rtg" in team_ts and team_ts["net_rtg"].notna().any() else "N/A",
                        delta=None,
                        help="Offensive Rating minus Defensive Rating")

        st.divider()

        # ── Section B: Quarter Momentum Heatmap ───────────────
        st.markdown("### Quarter-by-Quarter Scoring")
        q_labels = ["Q1", "Q2", "Q3", "Q4"]
        us_avgs  = momentum["us_avg"]
        them_avgs = momentum["them_avg"]
        q_diffs  = momentum["q_diff"]

        col_q = st.columns(4)
        for i, (ql, ua, ta, qd) in enumerate(zip(q_labels, us_avgs, them_avgs, q_diffs)):
            col_q[i].metric(f"{ql} Avg", f"USA {ua} | Opp {ta}", delta=f"{qd:+.1f}")

        # Bar chart: quarter scoring
        q_chart_data = []
        for i, ql in enumerate(q_labels):
            q_chart_data.append({"Quarter": ql, "Points": us_avgs[i], "Team": "USA"})
            q_chart_data.append({"Quarter": ql, "Points": them_avgs[i], "Team": "Opponent"})
        fig_q = px.bar(
            pd.DataFrame(q_chart_data),
            x="Quarter", y="Points", color="Team", barmode="group",
            color_discrete_map={"USA": "#1565C0", "Opponent": "#C62828"},
            title="Average Points Per Quarter: USA vs Opponents"
        )
        fig_q.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white")
        st.plotly_chart(fig_q, use_container_width=True)

        best_q  = momentum["us_best_quarter"]
        worst_q = momentum["us_worst_quarter"]
        st.info(f"🏆 **Best quarter:** {best_q} (avg {us_avgs[q_labels.index(best_q)]} pts)  |  "
                f"⚠️ **Weakest quarter:** {worst_q} (avg {us_avgs[q_labels.index(worst_q)]} pts)  |  "
                f"💪 **Comeback wins (down after Q3):** {momentum['comeback_wins']}")

        st.divider()

        # ── Section C: Scoring Timeline ────────────────────────
        st.markdown("### Game-by-Game Scoring Timeline")
        if not team_ts.empty and len(team_ts) > 0:
            fig_timeline = go.Figure()
            fig_timeline.add_trace(go.Scatter(
                x=team_ts["game_label"], y=team_ts["us_pts"],
                mode="lines+markers+text", name="USA",
                text=team_ts["us_pts"], textposition="top center",
                line=dict(color="#1E88E5", width=3),
                marker=dict(size=10, color=["#4CAF50" if r=="W" else "#F44336" for r in team_ts["result"]])
            ))
            fig_timeline.add_trace(go.Scatter(
                x=team_ts["game_label"], y=team_ts["them_pts"],
                mode="lines+markers+text", name="Opponent",
                text=team_ts["them_pts"], textposition="bottom center",
                line=dict(color="#E53935", width=2, dash="dash"),
                marker=dict(size=8)
            ))
            fig_timeline.update_layout(
                title="Scoring Timeline by Game",
                xaxis_title="Game",
                yaxis_title="Points",
                xaxis_tickangle=-45,
                plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white"
            )
            st.plotly_chart(fig_timeline, use_container_width=True)

        st.divider()

        # ── Section D: Team Efficiency Metrics ─────────────────
        st.markdown("### Efficiency Metrics by Game")
        if not team_ts.empty:
            eff_cols_to_show = ["opponent","result","margin","us_fg_pct","us_three_pct",
                                "us_ts_pct","ast_to_ratio","pace_est","reb_margin","to_margin","team_gs"]
            eff_display = team_ts[[c for c in eff_cols_to_show if c in team_ts.columns]].copy()
            eff_display.columns = [c.replace("_"," ").title() for c in eff_display.columns]
            st.dataframe(eff_display, hide_index=True, use_container_width=True)

        st.divider()

        # ── Section E: Possession & Pace ──────────────────────
        st.markdown("### Possessions, Pace & Ratings")
        st.caption("Possessions = FGA + 0.44×FTA + TO (NBA standard estimate).  Off/Def Rtg = pts per 100 possessions.")
        if not team_ts.empty and "us_poss" in team_ts.columns:

            # Season avg KPIs
            _pe1, _pe2, _pe3, _pe4, _pe5 = st.columns(5)
            _avg_us_poss  = round(team_ts["us_poss"].mean(), 1)
            _avg_opp_poss = round(team_ts["opp_poss"].mean(), 1)
            _avg_pace     = round(team_ts["pace"].mean(), 1)
            _avg_off      = round(team_ts["off_rtg"].dropna().mean(), 1) if team_ts["off_rtg"].notna().any() else None
            _avg_def      = round(team_ts["def_rtg"].dropna().mean(), 1) if team_ts["def_rtg"].notna().any() else None
            _avg_net      = round(team_ts["net_rtg"].dropna().mean(), 1) if team_ts["net_rtg"].notna().any() else None

            _pe1.metric("Avg USA Poss/G",  _avg_us_poss,  help="Estimated possessions USA uses per game")
            _pe2.metric("Avg Opp Poss/G",  _avg_opp_poss, help="Estimated possessions opponents use per game")
            _pe3.metric("Avg Pace",        _avg_pace,     help="Avg possessions both teams combined ÷ 2")
            _pe4.metric("Off Rtg",         f"{_avg_off}" if _avg_off else "N/A",
                        delta=f"{round(_avg_off - _avg_def, 1):+.1f} net" if _avg_off and _avg_def else None,
                        help="Points scored per 100 possessions")
            _pe5.metric("Def Rtg",         f"{_avg_def}" if _avg_def else "N/A",
                        help="Points allowed per 100 possessions (lower = better)")

            st.divider()

            # USA poss vs Opp poss per game — dual bar
            _poss_rows = []
            for _, row in team_ts.iterrows():
                _poss_rows.append({"Game": row["game_label"], "Possessions": row["us_poss"],  "Team": "USA"})
                _poss_rows.append({"Game": row["game_label"], "Possessions": row["opp_poss"], "Team": "Opponent"})
            fig_poss = px.bar(
                pd.DataFrame(_poss_rows),
                x="Game", y="Possessions", color="Team", barmode="group",
                color_discrete_map={"USA": "#1565C0", "Opponent": "#C62828"},
                title="Estimated Possessions Per Game — USA vs Opponent",
                text="Possessions"
            )
            fig_poss.update_traces(texttemplate="%{text:.0f}", textposition="outside")
            fig_poss.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                                   font_color="white", xaxis_tickangle=-45)
            st.plotly_chart(fig_poss, use_container_width=True)

            # Off Rtg / Def Rtg / Net Rtg per game
            _rtg_df = team_ts[team_ts["off_rtg"].notna() & team_ts["def_rtg"].notna()].copy()
            if not _rtg_df.empty:
                fig_rtg = go.Figure()
                fig_rtg.add_trace(go.Scatter(
                    x=_rtg_df["game_label"], y=_rtg_df["off_rtg"],
                    mode="lines+markers", name="Off Rtg",
                    line=dict(color="#1E88E5", width=2),
                    marker=dict(size=8)
                ))
                fig_rtg.add_trace(go.Scatter(
                    x=_rtg_df["game_label"], y=_rtg_df["def_rtg"],
                    mode="lines+markers", name="Def Rtg",
                    line=dict(color="#E53935", width=2, dash="dash"),
                    marker=dict(size=8)
                ))
                fig_rtg.add_trace(go.Bar(
                    x=_rtg_df["game_label"], y=_rtg_df["net_rtg"],
                    name="Net Rtg",
                    marker_color=[("#4CAF50" if v >= 0 else "#F44336") for v in _rtg_df["net_rtg"]],
                    opacity=0.5, yaxis="y2"
                ))
                fig_rtg.update_layout(
                    title="Offensive / Defensive / Net Rating by Game",
                    xaxis_tickangle=-45,
                    plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white",
                    yaxis=dict(title="Rating (pts/100 poss)"),
                    yaxis2=dict(title="Net Rtg", overlaying="y", side="right", showgrid=False),
                    legend=dict(bgcolor="#0e1117"),
                    hovermode="x unified"
                )
                fig_rtg.add_hline(y=100, line_dash="dot", line_color="#555",
                                  annotation_text="100 baseline")
                st.plotly_chart(fig_rtg, use_container_width=True)
                st.caption("**Off Rtg** = pts scored per 100 poss (higher = better)  |  **Def Rtg** = pts allowed per 100 poss (lower = better)  |  **Net Rtg** = Off − Def (green = won the possession battle)")

        # ── Section F: Quarter Box Score Grid ─────────────────
        if not q_stats.empty:
            st.divider()
            st.markdown("### Quarter Score Grid")
            q_grid = q_stats[["date","opponent","result",
                               "q1_us","q1_them","q2_us","q2_them",
                               "q3_us","q3_them","q4_us","q4_them",
                               "final_margin","best_quarter","worst_quarter"]].copy()
            q_grid.columns = ["Date","Opponent","Result",
                               "Q1 US","Q1 OPP","Q2 US","Q2 OPP",
                               "Q3 US","Q3 OPP","Q4 US","Q4 OPP",
                               "Final Margin","Best Q","Worst Q"]
            st.dataframe(q_grid, hide_index=True, use_container_width=True)


# ══════════════════════════════════════════════════════════
# TAB 9: AI INSIGHTS
# ══════════════════════════════════════════════════════════
with tab_ai:
    if not games:
        st.info("No approved games yet.")
    else:
        st.subheader("🧠 AI Insights — Team Quick Look")
        st.caption("Comprehensive team snapshot. Use the **Game Window** slider in the sidebar to filter all stats.")

        # ── fetch all data up front (scoped to global game window) ─────────────
        _ins      = get_ai_coach_insights(games)
        _streaks  = get_hot_cold_streaks(games)
        _impact   = get_player_impact_index(games)
        _adv      = get_advanced_stats(games)
        _wl       = get_win_loss_splits(games)
        _ts_data  = get_team_stats_by_game(games)
        _momentum = get_momentum_analysis(games)

        total_g    = len(games)
        _wins      = sum(1 for g in games if g["score"]["us"] > g["score"]["them"])
        _losses    = total_g - _wins
        _win_pct   = round(_wins / total_g * 100) if total_g else 0
        _avg_us    = round(sum(g["score"]["us"]   for g in games) / total_g, 1)
        _avg_them  = round(sum(g["score"]["them"] for g in games) / total_g, 1)
        _avg_marg  = round(_avg_us - _avg_them, 1)
        _hot_list  = [n for n, d in _streaks.items() if "HOT"  in d["status"]]
        _cold_list = [n for n, d in _streaks.items() if "COLD" in d["status"]]

        # ══ SECTION 1 — TEAM COMMAND CENTER ══════════════════════════════════
        st.markdown("### 📊 Team Command Center")
        cc1, cc2, cc3, cc4, cc5, cc6 = st.columns(6)
        cc1.metric("Record",        f"{_wins}W – {_losses}L",   f"{_win_pct}% Win Rate")
        cc2.metric("Avg PTS Scored", _avg_us,  f"{_avg_marg:+.1f} margin")
        cc3.metric("Avg PTS Allowed", _avg_them)
        if not _ts_data.empty and len(_ts_data) > 1:
            _fm  = int(_ts_data["margin"].iloc[0])
            _lm  = int(_ts_data["margin"].iloc[-1])
            _trj = "📈 Improving" if _lm > _fm else "📉 Declining"
            cc4.metric("Trajectory", _trj, f"{_fm:+d} → {_lm:+d} pts")
        else:
            cc4.metric("Trajectory", "—")
        _avg_reb = round(_ts_data["reb_margin"].mean(), 1) if not _ts_data.empty else 0
        cc5.metric("Reb Margin", f"{_avg_reb:+.1f}", "per game")
        cc6.metric("Comeback Wins", _momentum.get("comeback_wins", 0), "trailed after Q3")

        st.divider()

        # ══ SECTION 2 — PLAYER FORM BADGES ═══════════════════════════════════
        st.markdown("### 🌡️ Player Form Right Now (Last 3 vs Season Avg)")
        if _streaks:
            _n = len(_streaks)
            _fc = st.columns(_n)
            for _i, (_nm, _d) in enumerate(_streaks.items()):
                _dv  = _d["delta"]
                _st  = _d["status"]
                _clr = "#FF5722" if "HOT" in _st else ("#607D8B" if "COLD" in _st else "#1E88E5")
                _arr = "▲" if _dv > 0 else ("▼" if _dv < 0 else "●")
                _fc[_i].markdown(f"""
<div style="background:{_clr}22;border:1px solid {_clr};border-radius:10px;padding:14px 10px;margin:4px;text-align:center;">
<div style="color:{_clr};font-weight:700;font-size:13px;margin-bottom:4px">{_nm}</div>
<div style="font-size:22px;line-height:1.2">{_st}</div>
<div style="font-size:22px;color:{_clr};font-weight:800;margin:2px 0">{_arr} {_dv:+.1f}</div>
<hr style="border-color:{_clr}44;margin:6px 0">
<div style="font-size:11px;color:#ccc">Season <b>{_d['season_avg_pts']}</b> PPG</div>
<div style="font-size:11px;color:#ccc">Recent <b>{_d['recent_avg_pts']}</b> PPG</div>
<div style="font-size:10px;color:#777;margin-top:4px">GS avg: {_d['season_avg_gs']}</div>
</div>""", unsafe_allow_html=True)

        st.divider()

        # ══ SECTION 3 — IMPACT RANKINGS ══════════════════════════════════════
        st.markdown("### 🏆 Player Impact Rankings")
        if not _impact.empty:
            _rank_colors  = ["#FFD700", "#C0C0C0", "#CD7F32", "#607D8B", "#455A64"]
            _rank_labels  = ["#1", "#2", "#3", "#4", "#5"]
            _imp_cols     = st.columns(len(_impact))
            for _ri, (_idx, _row) in enumerate(_impact.iterrows()):
                if _ri >= len(_imp_cols):
                    break
                _sc   = _row["impact_score"]
                _rc   = _rank_colors[_ri] if _ri < len(_rank_colors) else "#607D8B"
                _rl   = _rank_labels[_ri] if _ri < len(_rank_labels) else f"#{_ri+1}"
                _ts_v = "—"
                if not _adv.empty and "ts_pct" in _adv.columns:
                    _ar = _adv[_adv["name"] == _row["name"]]
                    if not _ar.empty and _ar.iloc[0]["ts_pct"] is not None:
                        _ts_v = f"{_ar.iloc[0]['ts_pct']}%"
                _imp_cols[_ri].markdown(f"""
<div style="background:#1a1a2e;border:2px solid {_rc};border-radius:10px;padding:14px 10px;margin:4px;text-align:center;">
<div style="color:{_rc};font-size:22px;font-weight:900">{_rl}</div>
<div style="color:white;font-weight:700;font-size:13px;margin:4px 0">{_row['name']}</div>
<div style="color:{_rc};font-size:30px;font-weight:900;line-height:1">{_sc}</div>
<div style="font-size:10px;color:#777;margin-bottom:6px">Impact Score / 100</div>
<div style="background:#333;border-radius:4px;height:6px;margin:6px 2px">
  <div style="background:{_rc};height:6px;border-radius:4px;width:{int(_sc)}%"></div>
</div>
<div style="font-size:11px;color:#aaa;margin-top:6px">TS% {_ts_v}</div>
</div>""", unsafe_allow_html=True)

        st.divider()

        # ══ SECTION 4 — WIN / LOSS SPLITS ════════════════════════════════════
        st.markdown("### ⚖️ Win / Loss Performance Splits")
        if not _wl.empty:
            _wl_cols = st.columns(min(len(_wl), 5))
            for _wi, (_, _wr) in enumerate(_wl.iterrows()):
                _col_i = _wi % len(_wl_cols)
                _wp  = _wr.get("w_pts") or 0
                _lp  = _wr.get("l_pts") or 0
                _wg  = _wr.get("w_gs")  or 0
                _lg  = _wr.get("l_gs")  or 0
                _dif = round(float(_wp) - float(_lp), 1)
                _tc  = "#4CAF50" if _dif >= 0 else "#F44336"
                _tl  = "▲ Elevates in Wins" if _dif >= 0 else "▼ Higher vol. in Losses"
                _wl_cols[_col_i].markdown(f"""
<div style="background:#1a1a2e;border:1px solid #2a2a3e;border-radius:10px;padding:12px 10px;margin:4px;text-align:center;">
<div style="color:white;font-weight:700;font-size:13px">{_wr['name']}</div>
<div style="color:{_tc};font-size:11px;margin:3px 0">{_tl}</div>
<div style="display:flex;gap:6px;margin:8px 0;justify-content:center;">
  <div style="background:#4CAF5033;border:1px solid #4CAF50;border-radius:6px;padding:6px 12px">
    <div style="color:#4CAF50;font-size:10px;font-weight:700">WINS</div>
    <div style="color:white;font-size:20px;font-weight:900">{_wp}</div>
    <div style="color:#888;font-size:10px">GS {_wg}</div>
  </div>
  <div style="background:#F4433633;border:1px solid #F44336;border-radius:6px;padding:6px 12px">
    <div style="color:#F44336;font-size:10px;font-weight:700">LOSS</div>
    <div style="color:white;font-size:20px;font-weight:900">{_lp}</div>
    <div style="color:#888;font-size:10px">GS {_lg}</div>
  </div>
</div>
<div style="font-size:11px;color:#888">Δ pts: <span style="color:{_tc};font-weight:700">{_dif:+.1f}</span></div>
</div>""", unsafe_allow_html=True)

        st.divider()

        # ══ SECTION 5 — QUARTER BREAKDOWN ════════════════════════════════════
        st.markdown("### 🕐 Quarter-by-Quarter Breakdown")
        if _momentum:
            _us_avg   = _momentum.get("us_avg",   [0,0,0,0])
            _opp_avg  = _momentum.get("them_avg", [0,0,0,0])
            _best_q   = _momentum.get("us_best_quarter",  "Q1")
            _worst_q  = _momentum.get("us_worst_quarter", "Q4")
            _q_labels = ["Q1", "Q2", "Q3", "Q4"]
            _q_cols   = st.columns(4)
            for _qi, _ql in enumerate(_q_labels):
                _uv = _us_avg[_qi]  if _qi < len(_us_avg)  else 0
                _ov = _opp_avg[_qi] if _qi < len(_opp_avg) else 0
                _dv = round(_uv - _ov, 1)
                _is_best  = (_ql == _best_q)
                _is_worst = (_ql == _worst_q)
                _qc = "#4CAF50" if _is_best else ("#F44336" if _is_worst else ("#2196F3" if _dv >= 0 else "#FF9800"))
                _badge = "🏆 BEST" if _is_best else ("⚠️ WORST" if _is_worst else ("✅ WIN" if _dv >= 0 else "📉 LOSE"))
                _q_cols[_qi].markdown(f"""
<div style="background:{_qc}22;border:2px solid {_qc};border-radius:10px;padding:16px 10px;margin:4px;text-align:center;">
<div style="color:{_qc};font-size:24px;font-weight:900">{_ql}</div>
<div style="color:white;font-size:30px;font-weight:900;line-height:1.1">{_uv:.1f}</div>
<div style="font-size:11px;color:#aaa;margin:2px 0">avg pts scored</div>
<div style="font-size:12px;color:#888">Opp: {_ov:.1f}</div>
<div style="color:{_qc};font-size:16px;font-weight:700;margin:4px 0">{_dv:+.1f} margin</div>
<div style="background:{_qc}33;color:{_qc};font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;display:inline-block;margin-top:4px">{_badge}</div>
</div>""", unsafe_allow_html=True)

        st.divider()

        # ══ SECTION 6 — SHOOTING EFFICIENCY SNAPSHOT ═════════════════════════
        st.markdown("### 🎯 Shooting Efficiency Snapshot")
        if not _adv.empty and "ts_pct" in _adv.columns:
            _adv_s   = _adv.dropna(subset=["ts_pct"]).sort_values("ts_pct", ascending=False).reset_index(drop=True)
            _eff_c   = st.columns(min(len(_adv_s), 5))
            for _ei, (_, _er) in enumerate(_adv_s.iterrows()):
                if _ei >= len(_eff_c):
                    break
                _tv = _er.get("ts_pct")  or 0
                _fv = _er.get("fg_pct")  or 0
                _pv = _er.get("three_pct") or 0
                _ftv= _er.get("ft_pct")  or 0
                _ec = "#4CAF50" if _tv >= 55 else ("#FFC107" if _tv >= 45 else "#F44336")
                _eff_c[_ei].markdown(f"""
<div style="background:#1a1a2e;border:1px solid {_ec};border-radius:10px;padding:14px 10px;margin:4px;text-align:center;">
<div style="color:white;font-weight:700;font-size:13px">{_er['name']}</div>
<div style="color:{_ec};font-size:28px;font-weight:900;line-height:1.1">{_tv}%</div>
<div style="font-size:10px;color:#777;margin-bottom:8px">True Shooting %</div>
<div style="display:flex;gap:4px;justify-content:center;flex-wrap:wrap;font-size:11px">
  <div style="background:#222;border-radius:4px;padding:3px 7px"><span style="color:#aaa">FG</span> <b style="color:white">{_fv}%</b></div>
  <div style="background:#222;border-radius:4px;padding:3px 7px"><span style="color:#aaa">3P</span> <b style="color:white">{_pv}%</b></div>
  <div style="background:#222;border-radius:4px;padding:3px 7px"><span style="color:#aaa">FT</span> <b style="color:white">{_ftv}%</b></div>
</div>
</div>""", unsafe_allow_html=True)

        st.divider()

        # ══ SECTION 7 — FULL INSIGHTS BOARD (2-col cards) ════════════════════
        st.markdown("### 💡 Full Insights Board")
        _CAT_CLR = {
            "Team Momentum":       "#1E88E5",
            "Ball Security":       "#F44336",
            "Shooting Efficiency": "#4CAF50",
            "Form — Hot":          "#FF5722",
            "Form — Cold":         "#78909C",
            "Win Correlation":     "#9C27B0",
            "Playmaking":          "#00BCD4",
            "Resilience":          "#8BC34A",
            "Performance Index":   "#FFC107",
            "Net Rating Trend":    "#3F51B5",
            "Rebounding":          "#795548",
        }
        if not _ins:
            st.info("Not enough data for insights yet. Add more games.")
        else:
            def _ins_card(col, ins):
                _cc = _CAT_CLR.get(ins["category"], "#607D8B")
                col.markdown(f"""
<div style="background:{_cc}11;border:1px solid {_cc}55;border-radius:10px;padding:14px 16px;margin:6px 0;">
<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
  <span style="font-size:22px">{ins['icon']}</span>
  <span style="background:{_cc}33;color:{_cc};font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;padding:2px 8px;border-radius:20px">{ins['category']}</span>
</div>
<div style="color:white;font-weight:600;font-size:13px;margin-bottom:4px">{ins['title']}</div>
<div style="color:#aaa;font-size:11px;line-height:1.5">{ins['detail']}</div>
</div>""", unsafe_allow_html=True)

            _gc1, _gc2 = st.columns(2)
            for _ii, _ins_item in enumerate(_ins):
                _ins_card(_gc1 if _ii % 2 == 0 else _gc2, _ins_item)


# ══════════════════════════════════════════════════════════
# TAB 10: OPPONENT INTEL
# ══════════════════════════════════════════════════════════
with tab_opp_intel:
    if not games:
        st.info("No approved games yet.")
    else:
        st.subheader("🕵️ Opponent Intelligence")
        st.caption("Full breakdown of how opponents attack us, where we're vulnerable, and who we can't stop.")

        opp_intel = get_opponent_player_intel(games)

        if opp_intel.empty:
            st.info("No opponent player data yet.")
        else:
            _THREAT_COLORS = {
                "🔴 Elite": "#C62828", "🟠 High": "#EF6C00",
                "🟡 Moderate": "#F9A825", "🟢 Low": "#2E7D32"
            }

            # ── SECTION 1: Season Overview KPIs ──────────────────────────
            st.markdown("### 📊 Season Overview")
            _oi_games_total = len(games)
            _oi_wins  = sum(1 for g in games if g["score"]["us"] > g["score"]["them"])
            _oi_losses = _oi_games_total - _oi_wins
            _oi_opp_avg_pts = round(sum(g["score"]["them"] for g in games) / _oi_games_total, 1)
            _oi_our_avg_pts = round(sum(g["score"]["us"]   for g in games) / _oi_games_total, 1)

            # Opponent team stats
            _team_rows = {}
            for g in games:
                opp = g.get("opponent", "?")
                won = g["score"]["us"] > g["score"]["them"]
                if opp not in _team_rows:
                    _team_rows[opp] = {"gp": 0, "wins": 0, "pts_for": 0, "pts_against": 0}
                _team_rows[opp]["gp"] += 1
                _team_rows[opp]["wins"] += int(won)
                _team_rows[opp]["pts_for"]     += g["score"]["us"]
                _team_rows[opp]["pts_against"] += g["score"]["them"]

            # Hardest opponent = lowest win%
            _hardest = min(_team_rows.items(), key=lambda x: x[1]["wins"]/x[1]["gp"])
            _easiest = max(_team_rows.items(), key=lambda x: x[1]["wins"]/x[1]["gp"])

            # Kryptonite player = elite threat, 0% win rate when they're in lineup
            _krypto = opp_intel[(opp_intel["usa_win_pct"] == 0) & (opp_intel["games"] >= 2)].sort_values("threat_score", ascending=False)
            _krypto_name = _krypto.iloc[0]["name"] if not _krypto.empty else "None"

            _ov1, _ov2, _ov3, _ov4, _ov5 = st.columns(5)
            _ov1.metric("Record", f"{_oi_wins}W – {_oi_losses}L")
            _ov2.metric("Avg Pts Allowed", _oi_opp_avg_pts, delta=f"{round(_oi_our_avg_pts - _oi_opp_avg_pts, 1):+.1f} margin")
            _ov3.metric("Hardest Opponent", _hardest[0], delta=f"{round(_hardest[1]['wins']/_hardest[1]['gp']*100)}% W")
            _ov4.metric("Best Matchup", _easiest[0], delta=f"{round(_easiest[1]['wins']/_easiest[1]['gp']*100)}% W")
            _ov5.metric("🚨 Kryptonite Player", _krypto_name)

            st.divider()

            # ── SECTION 2: Team-by-Team Breakdown ────────────────────────
            st.markdown("### 🆚 Team-by-Team Breakdown")
            st.caption("How you perform against each opponent — click to expand scouting notes.")

            _team_df_rows = []
            for opp, td in _team_rows.items():
                gp = td["gp"]
                win_pct = round(td["wins"] / gp * 100, 1)
                avg_for     = round(td["pts_for"] / gp, 1)
                avg_against = round(td["pts_against"] / gp, 1)
                margin      = round(avg_for - avg_against, 1)
                # Find their top scorer
                opp_players = opp_intel[opp_intel["teams"].str.contains(opp, na=False)]
                top_scorer  = opp_players.sort_values("avg_pts", ascending=False).iloc[0]["name"] if not opp_players.empty else "?"
                top_pts     = opp_players.sort_values("avg_pts", ascending=False).iloc[0]["avg_pts"] if not opp_players.empty else 0
                _team_df_rows.append({
                    "Opponent": opp, "GP": gp, "W": td["wins"], "L": gp - td["wins"],
                    "Win%": win_pct, "Avg Pts For": avg_for, "Avg Pts Against": avg_against,
                    "Margin": margin, "Top Scorer": f"{top_scorer} ({top_pts})"
                })

            _team_df = pd.DataFrame(_team_df_rows).sort_values("Win%", ascending=False)

            def _team_win_style(row):
                wp = row.get("Win%", 50)
                if wp >= 60:  return ["background-color: #0d2b0d"] * len(row)
                if wp <= 30:  return ["background-color: #2b0d0d"] * len(row)
                return [""] * len(row)

            st.dataframe(
                _team_df.style.apply(_team_win_style, axis=1),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "GP":              st.column_config.NumberColumn("GP",              format="%d"),
                    "W":               st.column_config.NumberColumn("W",               format="%d"),
                    "L":               st.column_config.NumberColumn("L",               format="%d"),
                    "Win%":            st.column_config.NumberColumn("Win%",            format="%.1f%%"),
                    "Avg Pts For":     st.column_config.NumberColumn("Avg Pts For",     format="%.1f"),
                    "Avg Pts Against": st.column_config.NumberColumn("Avg Pts Against", format="%.1f"),
                    "Margin":          st.column_config.NumberColumn("Margin",          format="%.1f"),
                }
            )

            # Win% bar per team
            fig_team_win = px.bar(
                _team_df.sort_values("Win%"),
                x="Win%", y="Opponent", orientation="h",
                color="Win%", color_continuous_scale="RdYlGn",
                range_color=[0, 100],
                title="Win% by Opponent",
                text="Win%"
            )
            fig_team_win.add_vline(x=50, line_dash="dash", line_color="white")
            fig_team_win.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                                       font_color="white", showlegend=False,
                                       coloraxis_showscale=False)
            st.plotly_chart(fig_team_win, use_container_width=True)

            st.divider()

            # ── SECTION 3: Where They Hurt Us — Position Damage Map ──────
            st.markdown("### 🎯 Where Opponents Hurt Us Most")
            st.caption("Average stats scored against us by opponent position. Red = major damage.")

            _pos_order = ["PG", "SG", "SF", "PF", "C"]
            _pos_stats = ["avg_pts", "avg_ast", "avg_reb", "avg_stl", "avg_blk"]
            _pos_labels = ["Avg PTS", "Avg AST", "Avg REB", "Avg STL", "Avg BLK"]

            _pos_df = opp_intel[opp_intel["pos"].isin(_pos_order)].groupby("pos")[_pos_stats].mean().round(1).reindex(_pos_order).dropna()

            if not _pos_df.empty:
                _pc1, _pc2 = st.columns(2)
                with _pc1:
                    # Heatmap
                    fig_heat = go.Figure(go.Heatmap(
                        z=_pos_df.values,
                        x=_pos_labels,
                        y=_pos_df.index.tolist(),
                        colorscale="Reds",
                        text=_pos_df.values,
                        texttemplate="%{text:.1f}",
                        showscale=False,
                        hovertemplate="Position: %{y}<br>%{x}: %{z:.1f}<extra></extra>"
                    ))
                    fig_heat.update_layout(
                        title="Opponent Damage by Position",
                        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white",
                        height=300
                    )
                    st.plotly_chart(fig_heat, use_container_width=True)

                with _pc2:
                    # Which position scores most on us
                    _pos_pts = _pos_df["avg_pts"].sort_values(ascending=False)
                    fig_pos_pts = px.bar(
                        x=_pos_pts.index, y=_pos_pts.values,
                        color=_pos_pts.values, color_continuous_scale="Reds",
                        labels={"x": "Position", "y": "Avg PTS Against Us"},
                        title="Avg Points Scored Against Us by Position",
                        text=[f"{v:.1f}" for v in _pos_pts.values]
                    )
                    fig_pos_pts.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                                              font_color="white", showlegend=False,
                                              coloraxis_showscale=False)
                    st.plotly_chart(fig_pos_pts, use_container_width=True)

            st.divider()

            # ── SECTION 4: Win vs Loss — How Opponents Differ ────────────
            st.markdown("### 📉 How Opponents Play Different in Our Wins vs Losses")
            st.caption("When we lose, what are opponents doing more of?")

            _wl_opp_rows = []
            for g in games:
                won = g["score"]["us"] > g["score"]["them"]
                for p in g.get("opponent_players", []):
                    _wl_opp_rows.append({
                        "result": "Win" if won else "Loss",
                        "pts": p.get("pts", 0), "ast": p.get("ast", 0),
                        "reb": p.get("reb", 0), "to":  p.get("to",  0),
                        "fgm": p.get("fgm", 0), "fga": p.get("fga", 0),
                        "tpm": p.get("tpm", 0), "tpa": p.get("tpa", 0),
                    })

            if _wl_opp_rows:
                _wl_df = pd.DataFrame(_wl_opp_rows)
                _wl_avg = _wl_df.groupby("result")[["pts","ast","reb","to"]].mean().round(1).reset_index()
                _wl_melt = _wl_avg.melt(id_vars="result", var_name="Stat", value_name="Avg")

                fig_wl = px.bar(
                    _wl_melt, x="Stat", y="Avg", color="result", barmode="group",
                    color_discrete_map={"Win": "#43A047", "Loss": "#E53935"},
                    title="Opponent Avg Stats: Our Wins vs Our Losses",
                    text_auto=".1f"
                )
                fig_wl.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white")
                st.plotly_chart(fig_wl, use_container_width=True)

                # 3PT attempts in wins vs losses
                _tpa_win  = round(_wl_df[_wl_df["result"]=="Win"]["tpa"].mean(), 1)
                _tpa_loss = round(_wl_df[_wl_df["result"]=="Loss"]["tpa"].mean(), 1)
                _fg_win   = round((_wl_df[_wl_df["result"]=="Win"]["fgm"].sum() /
                                   _wl_df[_wl_df["result"]=="Win"]["fga"].sum() * 100) if
                                   _wl_df[_wl_df["result"]=="Win"]["fga"].sum() > 0 else 0, 1)
                _fg_loss  = round((_wl_df[_wl_df["result"]=="Loss"]["fgm"].sum() /
                                   _wl_df[_wl_df["result"]=="Loss"]["fga"].sum() * 100) if
                                   _wl_df[_wl_df["result"]=="Loss"]["fga"].sum() > 0 else 0, 1)

                _wi1, _wi2, _wi3, _wi4 = st.columns(4)
                _wi1.metric("Opp 3PA in Our Wins",   f"{_tpa_win}")
                _wi2.metric("Opp 3PA in Our Losses", f"{_tpa_loss}", delta=f"{round(_tpa_loss-_tpa_win,1):+.1f}", delta_color="inverse")
                _wi3.metric("Opp FG% in Our Wins",   f"{_fg_win}%")
                _wi4.metric("Opp FG% in Our Losses", f"{_fg_loss}%", delta=f"{round(_fg_loss-_fg_win,1):+.1f}%", delta_color="inverse")

            st.divider()

            # ── SECTION 5: Kryptonite Players — Can't Stop Them ──────────
            st.markdown("### 🚨 Kryptonite Players")
            st.caption("Players you've faced 2+ times with 0% or very low win rate — these are your problem matchups.")

            _krypto_all = opp_intel[opp_intel["games"] >= 2].sort_values(["usa_win_pct","threat_score"], ascending=[True, False]).head(10)
            if not _krypto_all.empty:
                _kr_disp = _krypto_all[["name","pos","teams","games","avg_pts","avg_ast","avg_reb","ts_pct","usa_win_pct","threat_level"]].copy()
                _kr_disp.columns = ["Player","Pos","Team","GP","PPG","APG","RPG","TS%","USA Win%","Threat"]

                def _kr_style(row):
                    wp = row.get("USA Win%", 50)
                    if wp == 0:    return ["background-color: #3b0000"] * len(row)
                    if wp <= 25:   return ["background-color: #2b1000"] * len(row)
                    return [""] * len(row)

                st.dataframe(
                    _kr_disp.style.apply(_kr_style, axis=1),
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "GP":       st.column_config.NumberColumn("GP",       format="%d"),
                        "PPG":      st.column_config.NumberColumn("PPG",      format="%.1f"),
                        "APG":      st.column_config.NumberColumn("APG",      format="%.1f"),
                        "RPG":      st.column_config.NumberColumn("RPG",      format="%.1f"),
                        "TS%":      st.column_config.NumberColumn("TS%",      format="%.1f%%"),
                        "USA Win%": st.column_config.NumberColumn("USA Win%", format="%.1f%%"),
                    }
                )

                fig_kr = px.scatter(
                    _krypto_all, x="avg_pts", y="usa_win_pct",
                    size="games", color="threat_level",
                    color_discrete_map=_THREAT_COLORS,
                    text="name",
                    labels={"avg_pts": "Avg PPG Against Us", "usa_win_pct": "USA Win% When Facing"},
                    title="Kryptonite Map — High PPG + Low Win% = Problem",
                    size_max=30
                )
                fig_kr.add_hline(y=50, line_dash="dash", line_color="white", annotation_text="50% win")
                fig_kr.update_traces(textposition="top center")
                fig_kr.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white")
                st.plotly_chart(fig_kr, use_container_width=True)

            st.divider()

            # ── SECTION 6: Full Player Database (collapsible) ────────────
            with st.expander("📋 Full Opponent Player Database", expanded=False):
                all_opp_teams = sorted(set(opp_intel["teams"].str.split(", ").explode()))
                filter_team = st.selectbox("Filter by team:", ["All"] + all_opp_teams, key="opp_intel_team_filter")
                filter_pos  = st.selectbox("Filter by position:", ["All","PG","SG","SF","PF","C"], key="opp_intel_pos_filter")
                filtered = opp_intel.copy()
                if filter_team != "All":
                    filtered = filtered[filtered["teams"].str.contains(filter_team, na=False)]
                if filter_pos != "All":
                    filtered = filtered[filtered["pos"] == filter_pos]

                display_cols = ["name","pos","teams","games","avg_pts","avg_reb","avg_ast",
                                "avg_stl","avg_blk","avg_to","fg_pct","three_pct",
                                "ts_pct","efg_pct","usa_win_pct","threat_score","threat_level"]
                disp = filtered[[c for c in display_cols if c in filtered.columns]].copy()
                disp.columns = [c.replace("_"," ").title() for c in disp.columns]

                def _threat_row_style(row):
                    lv = row.get("Threat Level", "")
                    if "Elite"    in str(lv): return ["background-color: #3b0000"] * len(row)
                    if "High"     in str(lv): return ["background-color: #3b1a00"] * len(row)
                    if "Moderate" in str(lv): return ["background-color: #2a2a00"] * len(row)
                    return [""] * len(row)

                st.dataframe(
                    disp.style.apply(_threat_row_style, axis=1),
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Games":        st.column_config.NumberColumn("GP",       format="%d"),
                        "Avg Pts":      st.column_config.NumberColumn("PPG",      format="%.1f"),
                        "Avg Reb":      st.column_config.NumberColumn("RPG",      format="%.1f"),
                        "Avg Ast":      st.column_config.NumberColumn("APG",      format="%.1f"),
                        "Avg Stl":      st.column_config.NumberColumn("SPG",      format="%.1f"),
                        "Avg Blk":      st.column_config.NumberColumn("BPG",      format="%.1f"),
                        "Avg To":       st.column_config.NumberColumn("TO/G",     format="%.1f"),
                        "Fg Pct":       st.column_config.NumberColumn("FG%",      format="%.1f%%"),
                        "Three Pct":    st.column_config.NumberColumn("3P%",      format="%.1f%%"),
                        "Ts Pct":       st.column_config.NumberColumn("TS%",      format="%.1f%%"),
                        "Efg Pct":      st.column_config.NumberColumn("eFG%",     format="%.1f%%"),
                        "Usa Win Pct":  st.column_config.NumberColumn("USA Win%", format="%.1f%%"),
                        "Threat Score": st.column_config.NumberColumn("Threat Score", format="%.1f"),
                    }
                )


# ══════════════════════════════════════════════════════════
# TAB 11: CLUTCH STATS
# ══════════════════════════════════════════════════════════
with tab_clutch:
    if not games:
        st.info("No approved games yet.")
    else:
        st.subheader("⚡ Clutch Performance Analysis")
        st.caption("Close games = final margin ≤ 10 pts. Who shows up when it matters most?")

        clutch = get_clutch_stats(games)

        if clutch.empty:
            st.info("No data available.")
        else:
            # Clutch leaderboard
            st.markdown("### Clutch Leaderboard (sorted by Clutch Game Score)")
            clutch_display = clutch.copy()
            clutch_display["clutch_boost_disp"] = clutch_display["clutch_boost"].apply(
                lambda v: f"{v:+.1f}" if v is not None and pd.notna(v) else "N/A"
            )

            _cld_cols = ["name","pos","clutch_games","clutch_pts","reg_pts",
                         "clutch_boost","clutch_gs","reg_gs","clutch_wins","clutch_win_pct"]
            _cld = clutch[[c for c in _cld_cols if c in clutch.columns]].copy()
            _cld.columns = [c.replace("_"," ").title() for c in _cld.columns]
            st.dataframe(_cld, hide_index=True, use_container_width=True)

            st.divider()

            # Clutch boost chart
            clutch_boost_data = clutch.dropna(subset=["clutch_boost"]).copy()
            if not clutch_boost_data.empty:
                clutch_boost_data["color"] = clutch_boost_data["clutch_boost"].apply(
                    lambda v: "Clutch+" if v >= 0 else "Drops Off"
                )
                fig_boost = px.bar(
                    clutch_boost_data.sort_values("clutch_boost", ascending=False),
                    x="name", y="clutch_boost",
                    color="color",
                    color_discrete_map={"Clutch+": "#4CAF50", "Drops Off": "#F44336"},
                    title="Clutch Boost: Pts Above/Below Normal in Close Games",
                    labels={"name": "Player", "clutch_boost": "Pts vs Season Avg"},
                    text="clutch_boost"
                )
                fig_boost.add_hline(y=0, line_dash="dash", line_color="white")
                fig_boost.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white")
                st.plotly_chart(fig_boost, use_container_width=True)

            # Clutch vs Regular GS comparison
            clutch_reg_data = clutch.dropna(subset=["clutch_gs","reg_gs"]).copy()
            if not clutch_reg_data.empty:
                rows_cr = []
                for _, row in clutch_reg_data.iterrows():
                    rows_cr.append({"Player": row["name"], "GS": row["clutch_gs"], "Context": "Clutch"})
                    rows_cr.append({"Player": row["name"], "GS": row["reg_gs"],    "Context": "Regular"})
                fig_cr = px.bar(
                    pd.DataFrame(rows_cr),
                    x="Player", y="GS", color="Context", barmode="group",
                    color_discrete_map={"Clutch": "#FF5722", "Regular": "#607D8B"},
                    title="Game Score: Clutch vs Regular Games"
                )
                fig_cr.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white")
                st.plotly_chart(fig_cr, use_container_width=True)

            # Win % in clutch games per player
            clutch_wins_data = clutch[clutch["clutch_games"] > 0].dropna(subset=["clutch_win_pct"]).copy()
            if not clutch_wins_data.empty:
                fig_cwp = px.bar(
                    clutch_wins_data.sort_values("clutch_win_pct", ascending=False),
                    x="name", y="clutch_win_pct",
                    color="clutch_win_pct",
                    color_continuous_scale="RdYlGn",
                    title="Win% in Close Games by Player",
                    labels={"name": "Player", "clutch_win_pct": "Win%"}
                )
                fig_cwp.add_hline(y=50, line_dash="dash", line_color="white", annotation_text="50%")
                fig_cwp.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white")
                st.plotly_chart(fig_cwp, use_container_width=True)


# ══════════════════════════════════════════════════════════
# TAB 12: TRENDS
# ══════════════════════════════════════════════════════════
with tab_trends:
    if not games:
        st.info("No approved games yet.")
    else:
        st.subheader("📈 Trend Tracker")

        streaks = get_hot_cold_streaks(games)
        game_log = get_per_game_player_stats(games)

        # ── Hot/Cold Status Cards ─────────────────────────────
        st.markdown("### 🌡️ Current Form (Last 3 Games vs Season Avg)")
        if streaks:
            streak_cols = st.columns(min(len(streaks), 5))
            for i, (name, d) in enumerate(streaks.items()):
                col_i = i % len(streak_cols)
                delta_val = d["delta"]
                status = d["status"]
                color = "#FF5722" if "HOT" in status else ("#607D8B" if "COLD" in status else "#1E88E5")
                streak_cols[col_i].markdown(f"""
<div style="background:{color}22; border: 1px solid {color}; border-radius: 8px; padding: 10px; margin: 4px;">
<div style="color:{color}; font-weight:bold">{name}</div>
<div style="font-size:22px">{status}</div>
<div>Season: <b>{d['season_avg_pts']}</b> PPG</div>
<div>Recent: <b>{d['recent_avg_pts']}</b> PPG ({delta_val:+.1f})</div>
<div style="font-size:11px;color:#888">GS avg: {d['season_avg_gs']}</div>
</div>""", unsafe_allow_html=True)

        st.divider()

        # ── Per-Game Points Timeline ──────────────────────────
        st.markdown("### Points Per Game Timeline")
        if not game_log.empty:
            all_players_trend = sorted(game_log["name"].unique())
            selected_trend = st.multiselect(
                "Select players to track:", all_players_trend,
                default=all_players_trend, key="trend_players"
            )
            if selected_trend:
                trend_filtered = game_log[game_log["name"].isin(selected_trend)].sort_values("game_num")
                fig_trend = px.line(
                    trend_filtered,
                    x="game_label", y="pts", color="name",
                    markers=True,
                    title="Points Per Game Over Time",
                    labels={"game_label": "Game", "pts": "Points", "name": "Player"}
                )
                fig_trend.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white",
                                        xaxis_tickangle=-45)
                st.plotly_chart(fig_trend, use_container_width=True)

                # Game Score trend
                fig_gs_trend = px.line(
                    trend_filtered,
                    x="game_label", y="game_score", color="name",
                    markers=True,
                    title="Game Score (Hollinger) Over Time",
                    labels={"game_label": "Game", "game_score": "Game Score", "name": "Player"}
                )
                fig_gs_trend.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white",
                                           xaxis_tickangle=-45)
                st.plotly_chart(fig_gs_trend, use_container_width=True)

        st.divider()

        # ── TS% Trend ──────────────────────────────────────────
        st.markdown("### True Shooting % Trend")
        if not game_log.empty and "ts_pct" in game_log.columns:
            ts_trend = game_log[game_log["ts_pct"].notna() & game_log["name"].isin(selected_trend if 'selected_trend' in dir() else [])].sort_values("game_num")
            if not ts_trend.empty:
                fig_ts = px.line(
                    ts_trend, x="game_label", y="ts_pct", color="name",
                    markers=True,
                    title="True Shooting % Per Game",
                    labels={"game_label": "Game", "ts_pct": "TS%", "name": "Player"}
                )
                fig_ts.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="League avg proxy")
                fig_ts.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white",
                                     xaxis_tickangle=-45)
                st.plotly_chart(fig_ts, use_container_width=True)

        st.divider()

        # ── Per-Game Full Log ──────────────────────────────────
        st.markdown("### Full Game Log (All Players)")
        if not game_log.empty:
            log_disp = game_log[["date","opponent","result","name","pos","pts","reb","ast",
                                  "stl","blk","to","fg_pct","three_pct","ts_pct","game_score"]].copy()
            log_disp.columns = ["Date","Opponent","Result","Player","Pos","PTS","REB","AST",
                                  "STL","BLK","TO","FG%","3P%","TS%","GS"]
            st.dataframe(log_disp, hide_index=True, use_container_width=True)


# ══════════════════════════════════════════════════════════
# TAB 13: PERFORMANCE INDEX
# ══════════════════════════════════════════════════════════
with tab_pix:
    if not games:
        st.info("No approved games yet.")
    else:
        st.subheader("🏆 Composite Performance Index")
        st.caption("Impact Score (0–100) weights: Game Score 30% | True Shooting% 20% | AST/TO 15% | Stocks 15% | Scoring Share 10% | TO Control 10%")

        pix = get_player_impact_index(games)

        if pix.empty:
            st.info("Need more game data to compute Performance Index.")
        else:
            # Ranked list with progress bars
            st.markdown("### Player Rankings")
            for rank, (_, row) in enumerate(pix.iterrows()):
                score    = row["impact_score"]
                score_f  = float(score) if pd.notna(score) else 0
                bar_pct  = score_f / 100
                color    = ("#FFD700" if rank == 0 else
                            "#C0C0C0" if rank == 1 else
                            "#CD7F32" if rank == 2 else "#1E88E5")
                medal    = ("🥇" if rank == 0 else "🥈" if rank == 1 else "🥉" if rank == 2 else f"#{rank+1}")
                ts_str   = f"{row['ts_pct']:.1f}%" if pd.notna(row.get("ts_pct")) else "N/A"
                asto_str = f"{row['ast_to']:.2f}"  if pd.notna(row.get("ast_to"))  else "N/A"
                stk_str  = f"{row['stocks_per_game']:.1f}" if pd.notna(row.get("stocks_per_game")) else "N/A"
                sh_str   = f"{row['avg_scoring_share']:.1f}%" if pd.notna(row.get("avg_scoring_share")) else "N/A"

                st.markdown(f"""
<div style="background:#111827; border:1px solid #2d3748; border-radius:10px; padding:16px; margin:8px 0;">
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <div>
      <span style="font-size:20px">{medal}</span>
      <span style="font-size:18px; font-weight:bold; margin-left:8px">{row['name']}</span>
      <span style="color:#888; margin-left:8px">{row['pos']} · {int(row['games'])}G</span>
    </div>
    <div style="font-size:28px; font-weight:bold; color:{color}">{score_f:.1f}</div>
  </div>
  <div style="background:#1a2035; border-radius:6px; height:12px; margin:10px 0;">
    <div style="background:{color}; height:12px; border-radius:6px; width:{bar_pct*100:.1f}%"></div>
  </div>
  <div style="display:flex; gap:24px; font-size:13px; color:#ccc;">
    <span>GS: <b>{row['avg_game_score']:.1f}</b></span>
    <span>TS%: <b>{ts_str}</b></span>
    <span>AST/TO: <b>{asto_str}</b></span>
    <span>Stocks: <b>{stk_str}</b></span>
    <span>Score Share: <b>{sh_str}</b></span>
  </div>
</div>""", unsafe_allow_html=True)

            st.divider()

            # Radar chart for all players
            st.markdown("### Radar Comparison (Normalized Stats)")
            radar_cats = ["avg_game_score", "ts_pct", "ast_to", "stocks_per_game", "avg_scoring_share"]
            radar_labels = ["Game Score", "TS%", "AST/TO", "Stocks/G", "Score Share%"]

            # Normalize for radar
            radar_norm = pix[radar_cats].copy()
            for col in radar_cats:
                mn = radar_norm[col].min(); mx = radar_norm[col].max()
                radar_norm[col] = (radar_norm[col] - mn) / (mx - mn) * 10 if mx != mn else 5

            fig_radar = go.Figure()
            colors_radar = ["#FFD700","#1E88E5","#E53935","#43A047","#FB8C00","#8E24AA"]
            for i, (_, row) in enumerate(pix.iterrows()):
                vals = [float(radar_norm.iloc[i][c]) if pd.notna(radar_norm.iloc[i][c]) else 0
                        for c in radar_cats]
                vals += [vals[0]]  # close polygon
                fig_radar.add_trace(go.Scatterpolar(
                    r=vals,
                    theta=radar_labels + [radar_labels[0]],
                    fill="toself",
                    name=row["name"],
                    line_color=colors_radar[i % len(colors_radar)],
                    opacity=0.7
                ))
            fig_radar.update_layout(
                polar=dict(bgcolor="#0e1117", radialaxis=dict(visible=True, range=[0,10])),
                paper_bgcolor="#0e1117", font_color="white",
                title="Player Performance Radar (Normalized 0–10)"
            )
            st.plotly_chart(fig_radar, use_container_width=True)

            st.divider()

            # Table version
            st.markdown("### Full Impact Score Table")
            pix_display = pix.copy()
            for col in ["ts_pct","avg_scoring_share","to_rate"]:
                if col in pix_display.columns:
                    pix_display[col] = pix_display[col].apply(
                        lambda v: f"{v:.1f}%" if pd.notna(v) else "N/A"
                    )
            for col in ["ast_to"]:
                if col in pix_display.columns:
                    pix_display[col] = pix_display[col].apply(
                        lambda v: f"{v:.2f}" if pd.notna(v) else "N/A"
                    )
            pix_display.columns = [c.replace("_"," ").title() for c in pix_display.columns]
            st.dataframe(pix_display, hide_index=True, use_container_width=True)

            st.divider()

            # Best lineup suggestion
            st.markdown("### Best Lineup Combos (Historical)")
            lineup_combos = get_best_lineup_combos(games)
            if not lineup_combos.empty:
                st.dataframe(lineup_combos, hide_index=True, use_container_width=True)
            else:
                st.info("Need multiple games to evaluate lineup combinations.")


# ══════════════════════════════════════════════════════════
# TAB 15: SCOUT — Opponent Scouting Dossier
# ══════════════════════════════════════════════════════════
with tab_scout:
    # Reload fresh on each render
    _sd        = load_scouting()
    _sc_team   = _sd.get("scout_team", "Opponent")
    _sc_games  = _sd.get("games", [])
    _sc_pend   = _sd.get("pending", [])

    st.subheader(f"🔬 Scouting Dossier — {_sc_team}")
    st.caption("Separate from your team data. Upload their games vs other teams to build a full picture.")

    # ── Change scout team name ──────────────────────────────
    with st.expander("⚙️ Settings — Change Scout Team", expanded=False):
        new_team_name = st.text_input("Team being scouted:", value=_sc_team, key="scout_team_name_input")
        if st.button("Update Team Name", key="scout_update_team"):
            _sd["scout_team"] = new_team_name
            save_scouting(_sd)
            st.success(f"Now scouting: {new_team_name}")
            st.rerun()

    st.divider()

    # ══════════════════════════════════════════════════════
    # SECTION 1: OUR GAMES vs THEM (from existing data)
    # ══════════════════════════════════════════════════════
    st.markdown(f"### 📊 Our Games vs {_sc_team}")
    st.caption("Pulled directly from your approved games — no extra work needed.")

    # Find games vs the scout team in our data
    _our_vs_them = [g for g in _all_games if g.get("opponent","").lower() == _sc_team.lower()]

    if not _our_vs_them:
        st.info(f"No approved games vs {_sc_team} found. Check the team name matches exactly.")
    else:
        _ov_wins   = sum(1 for g in _our_vs_them if g["score"]["us"] > g["score"]["them"])
        _ov_losses = len(_our_vs_them) - _ov_wins
        _ov_avg_us   = round(sum(g["score"]["us"]   for g in _our_vs_them) / len(_our_vs_them), 1)
        _ov_avg_them = round(sum(g["score"]["them"] for g in _our_vs_them) / len(_our_vs_them), 1)

        _ov1, _ov2, _ov3, _ov4 = st.columns(4)
        _ov1.metric("Our Record vs Them",  f"{_ov_wins}W – {_ov_losses}L")
        _ov2.metric("Our Avg Score",        _ov_avg_us,
                    delta=f"{round(_ov_avg_us - _ov_avg_them, 1):+.1f} margin")
        _ov3.metric("Their Avg Score",      _ov_avg_them)
        _ov4.metric("Games Played",         len(_our_vs_them))

        # Our player stats in those games
        st.markdown("#### Our Players in These Games")
        _our_p_rows = []
        _our_p_acc: dict = {}
        for g in _our_vs_them:
            for p in g["players"]:
                nm = normalize_name(p["name"])
                if nm not in _our_p_acc:
                    _our_p_acc[nm] = {"pos": p.get("pos",""), "gp": 0,
                                       "pts":0,"reb":0,"ast":0,"stl":0,"blk":0,
                                       "to":0,"fgm":0,"fga":0,"tpm":0,"tpa":0,"ftm":0,"fta":0}
                d = _our_p_acc[nm]
                d["gp"] += 1
                for s in ["pts","reb","ast","stl","blk","to","fgm","fga","tpm","tpa","ftm","fta"]:
                    d[s] += p.get(s, 0)
        for nm, d in _our_p_acc.items():
            n = d["gp"]
            fga = d["fga"]; fgm = d["fgm"]; tpa = d["tpa"]; tpm = d["tpm"]
            fta = d["fta"]; pts = d["pts"]
            ts_d = 2 * (fga + 0.44 * fta)
            _our_p_rows.append({
                "Player": nm, "Pos": d["pos"], "GP": n,
                "PPG": round(pts/n,1), "RPG": round(d["reb"]/n,1), "APG": round(d["ast"]/n,1),
                "SPG": round(d["stl"]/n,1), "BPG": round(d["blk"]/n,1), "TO/G": round(d["to"]/n,1),
                "FG%": f"{fgm/fga*100:.1f}%" if fga>0 else "N/A",
                "3P%": f"{tpm/tpa*100:.1f}%" if tpa>0 else "N/A",
                "TS%": f"{pts/ts_d*100:.1f}%" if ts_d>0 else "N/A",
            })
        _our_p_df = pd.DataFrame(_our_p_rows).sort_values("PPG", ascending=False)
        st.dataframe(_our_p_df, hide_index=True, use_container_width=True)

        # Their players in our games
        st.markdown(f"#### Their Players in Our Games (from your box scores)")
        _their_p_acc: dict = {}
        for g in _our_vs_them:
            for p in g.get("opponent_players", []):
                nm = p.get("name", "Unknown")
                if nm not in _their_p_acc:
                    _their_p_acc[nm] = {"pos": p.get("pos",""), "gp": 0,
                                         "pts":0,"reb":0,"ast":0,"stl":0,"blk":0,
                                         "to":0,"fgm":0,"fga":0,"tpm":0,"tpa":0,"ftm":0,"fta":0}
                d = _their_p_acc[nm]
                d["gp"] += 1
                for s in ["pts","reb","ast","stl","blk","to","fgm","fga","tpm","tpa","ftm","fta"]:
                    d[s] += p.get(s, 0)
        _their_p_rows = []
        for nm, d in _their_p_acc.items():
            n = d["gp"]
            fga = d["fga"]; fgm = d["fgm"]; tpa = d["tpa"]; tpm = d["tpm"]
            fta = d["fta"]; pts = d["pts"]
            ts_d = 2 * (fga + 0.44 * fta)
            _their_p_rows.append({
                "Player": nm, "Pos": d["pos"], "GP": n,
                "PPG": round(pts/n,1), "RPG": round(d["reb"]/n,1), "APG": round(d["ast"]/n,1),
                "SPG": round(d["stl"]/n,1), "BPG": round(d["blk"]/n,1), "TO/G": round(d["to"]/n,1),
                "FG%": f"{fgm/fga*100:.1f}%" if fga>0 else "N/A",
                "3P%": f"{tpm/tpa*100:.1f}%" if tpa>0 else "N/A",
                "TS%": f"{pts/ts_d*100:.1f}%" if ts_d>0 else "N/A",
            })

        _THREAT_C = {"🔴 Elite":"#3b0000","🟠 High":"#3b1a00","🟡 Moderate":"#2a2a00","🟢 Low":""}
        if _their_p_rows:
            _their_p_df = pd.DataFrame(_their_p_rows).sort_values("PPG", ascending=False)
            st.dataframe(_their_p_df, hide_index=True, use_container_width=True)

        # Game-by-game log
        st.markdown("#### Game Log vs Them")
        _glog_rows = []
        for g in sorted(_our_vs_them, key=lambda x: x["date"]):
            won = g["score"]["us"] > g["score"]["them"]
            _glog_rows.append({
                "Date": g["date"], "Result": "W" if won else "L",
                "Our Score": g["score"]["us"], "Their Score": g["score"]["them"],
                "Margin": g["score"]["us"] - g["score"]["them"],
            })
        st.dataframe(pd.DataFrame(_glog_rows), hide_index=True, use_container_width=True)

    st.divider()

    # ══════════════════════════════════════════════════════
    # SECTION 2: SCOUT GAME PENDING QUEUE
    # ══════════════════════════════════════════════════════
    st.markdown("### 📥 Scout Game Queue")
    st.caption("Games I've extracted from screenshots you've shared. Approve to add to the scouting dossier.")

    if not _sc_pend:
        st.info("No pending scouting games. Share a screenshot of their game vs another team and I'll extract the stats.")
    else:
        for sg in _sc_pend:
            with st.expander(f"🔍 {sg.get('scout_team','?')} vs {sg.get('opponent','?')}  —  {sg.get('date','?')}  |  Score: {sg.get('scout_score','?')} – {sg.get('opp_score','?')}", expanded=True):
                st.markdown(f"**Scout Team:** {sg.get('scout_team','?')}  |  **vs:** {sg.get('opponent','?')}  |  **Result:** {'W' if sg.get('scout_team_won') else 'L'}")
                _sp_disp = pd.DataFrame(sg.get("players", []))
                if not _sp_disp.empty:
                    disp_cols = [c for c in ["name","pos","pts","reb","ast","stl","blk","to","fgm","fga","tpm","tpa"] if c in _sp_disp.columns]
                    st.dataframe(_sp_disp[disp_cols], hide_index=True, use_container_width=True)
                _sc1, _sc2 = st.columns(2)
                if _sc1.button(f"✅ Approve", key=f"sc_approve_{sg['id']}"):
                    approve_scout_game(sg["id"])
                    st.success("Approved!")
                    st.rerun()
                if _sc2.button(f"❌ Reject", key=f"sc_reject_{sg['id']}"):
                    reject_scout_game(sg["id"])
                    st.warning("Rejected.")
                    st.rerun()

    st.divider()

    # ══════════════════════════════════════════════════════
    # SECTION 3: FULL SCOUTING DOSSIER (approved games)
    # ══════════════════════════════════════════════════════
    st.markdown(f"### 🗂️ {_sc_team} — Full Scouting Dossier")
    st.caption("Built from all approved scouting games. The more games you add, the more accurate this gets.")

    if not _sc_games:
        st.info(f"No approved scouting games yet for {_sc_team}. Share screenshots of their games vs other teams and I'll extract the stats.")
    else:
        _tend = get_scout_team_tendencies(_sc_games)
        _prof = get_scout_player_profiles(_sc_games)

        # Team tendency KPIs
        st.markdown("#### Team Tendencies")
        _t1, _t2, _t3, _t4, _t5, _t6, _t7 = st.columns(7)
        _t1.metric("Scouted Games",   _tend.get("games","?"))
        _t2.metric("Their Record",    _tend.get("record","?"))
        _t3.metric("Avg Pts For",     _tend.get("avg_pts_for","?"))
        _t4.metric("Avg Poss/G",      _tend.get("avg_poss","?"), help="FGA + 0.44×FTA + TO")
        _t5.metric("Off Rtg",         _tend.get("off_rtg","?"),  help="Pts per 100 possessions")
        _t6.metric("3PT Rate",        f"{_tend.get('three_rate','?')}%" if _tend.get('three_rate') else "N/A",
                   help="% of shots that are 3s")
        _t7.metric("AST/TO",          _tend.get("ast_to","?"))

        # Tendencies bar
        _tb1, _tb2, _tb3 = st.columns(3)
        _tb1.metric("FG%",     f"{_tend.get('fg_pct','?')}%"    if _tend.get('fg_pct')    else "N/A")
        _tb2.metric("3P%",     f"{_tend.get('three_pct','?')}%" if _tend.get('three_pct') else "N/A")
        _tb3.metric("TS%",     f"{_tend.get('ts_pct','?')}%"    if _tend.get('ts_pct')    else "N/A")

        st.divider()

        # Player profiles
        if not _prof.empty:
            st.markdown("#### Player Profiles — Threat Map")

            _THREAT_COLORS_SCOUT = {
                "🔴 Elite": "#C62828", "🟠 High": "#EF6C00",
                "🟡 Moderate": "#F9A825", "🟢 Low": "#2E7D32"
            }

            # Scatter: PPG vs TS%
            fig_scout_scatter = px.scatter(
                _prof.dropna(subset=["ppg","ts_pct"]),
                x="ppg", y="ts_pct",
                color="threat", size="games",
                color_discrete_map=_THREAT_COLORS_SCOUT,
                text="name",
                labels={"ppg":"PPG","ts_pct":"TS%"},
                title=f"{_sc_team} — Player Threat Map (PPG vs TS%)",
                size_max=25
            )
            fig_scout_scatter.update_traces(textposition="top center")
            fig_scout_scatter.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                                             font_color="white")
            st.plotly_chart(fig_scout_scatter, use_container_width=True)

            # Full player table
            st.markdown("#### Full Player Stats Table")
            _prof_disp = _prof[["name","pos","games","ppg","rpg","apg","spg","bpg","topg",
                                  "fg_pct","three_pct","three_rate","ts_pct","ast_to","off_rtg","avg_gs","threat"]].copy()
            _prof_disp.columns = ["Player","Pos","GP","PPG","RPG","APG","SPG","BPG","TO/G",
                                   "FG%","3P%","3PT Rate","TS%","AST/TO","Off Rtg","Game Score","Threat"]

            def _scout_threat_style(row):
                t = str(row.get("Threat",""))
                if "Elite"    in t: return ["background-color: #3b0000"] * len(row)
                if "High"     in t: return ["background-color: #3b1a00"] * len(row)
                if "Moderate" in t: return ["background-color: #2a2a00"] * len(row)
                return [""] * len(row)

            st.dataframe(
                _prof_disp.style.apply(_scout_threat_style, axis=1),
                hide_index=True, use_container_width=True,
                column_config={
                    "GP":       st.column_config.NumberColumn("GP",       format="%d"),
                    "PPG":      st.column_config.NumberColumn("PPG",      format="%.1f"),
                    "RPG":      st.column_config.NumberColumn("RPG",      format="%.1f"),
                    "APG":      st.column_config.NumberColumn("APG",      format="%.1f"),
                    "SPG":      st.column_config.NumberColumn("SPG",      format="%.1f"),
                    "BPG":      st.column_config.NumberColumn("BPG",      format="%.1f"),
                    "TO/G":     st.column_config.NumberColumn("TO/G",     format="%.1f"),
                    "FG%":      st.column_config.NumberColumn("FG%",      format="%.1f%%"),
                    "3P%":      st.column_config.NumberColumn("3P%",      format="%.1f%%"),
                    "3PT Rate": st.column_config.NumberColumn("3PT Rate", format="%.1f%%"),
                    "TS%":      st.column_config.NumberColumn("TS%",      format="%.1f%%"),
                    "AST/TO":   st.column_config.NumberColumn("AST/TO",   format="%.2f"),
                    "Off Rtg":  st.column_config.NumberColumn("Off Rtg",  format="%.1f"),
                    "Game Score":st.column_config.NumberColumn("Game Score",format="%.1f"),
                }
            )

            # Strengths & Weaknesses callout
            st.divider()
            st.markdown("#### Strengths & Weaknesses")
            _sw1, _sw2 = st.columns(2)
            with _sw1:
                st.markdown("**🔴 Threats / Strengths**")
                _top3 = _prof.head(3)
                for _, pr in _top3.iterrows():
                    st.markdown(f"- **{pr['name']}** ({pr['pos']}) — {pr['ppg']} PPG | {pr['ts_pct'] or 'N/A'}% TS | {pr['threat']}")
                _best_3pt = _prof.dropna(subset=["three_pct"]).sort_values("three_pct", ascending=False).head(1)
                if not _best_3pt.empty:
                    r = _best_3pt.iloc[0]
                    st.markdown(f"- **Best 3PT shooter:** {r['name']} — {r['three_pct']}% on {r['three_rate']}% rate")
            with _sw2:
                st.markdown("**🟢 Weaknesses / Exploits**")
                _worst_to = _prof.sort_values("topg", ascending=False).head(1)
                if not _worst_to.empty:
                    r = _worst_to.iloc[0]
                    st.markdown(f"- **Ball handler:** {r['name']} — {r['topg']} TO/G (force them off ball)")
                _worst_ts = _prof.dropna(subset=["ts_pct"]).sort_values("ts_pct").head(1)
                if not _worst_ts.empty:
                    r = _worst_ts.iloc[0]
                    st.markdown(f"- **Least efficient:** {r['name']} — {r['ts_pct']}% TS (make them shoot)")
                _lowest_ast = _prof.sort_values("apg").head(1)
                if not _lowest_ast.empty:
                    r = _lowest_ast.iloc[0]
                    st.markdown(f"- **Low playmaker:** {r['name']} — {r['apg']} APG (isolate them)")

            # Scouted game log
            st.divider()
            st.markdown("#### Scouted Game Log")
            _sg_log = []
            for sg in _sc_games:
                _sg_log.append({
                    "Date":       sg.get("date","?"),
                    "vs":         sg.get("opponent","?"),
                    "Result":     "W" if sg.get("scout_team_won") else "L",
                    "Their Score": sg.get("scout_score","?"),
                    "Opp Score":   sg.get("opp_score","?"),
                })
            st.dataframe(pd.DataFrame(_sg_log), hide_index=True, use_container_width=True)

    st.divider()

    # ══════════════════════════════════════════════════════
    # SECTION 4: MATCHUP PREVIEW
    # ══════════════════════════════════════════════════════
    st.markdown(f"### ⚔️ Matchup Preview — Us vs {_sc_team}")
    st.caption(f"Your stats IN games vs {_sc_team} vs their combined stats from all scouted sources.")

    _has_our_games  = len(_our_vs_them) > 0 if '_our_vs_them' in dir() else False
    _has_scout_data = len(_sc_games) > 0

    if not _has_our_games and not _has_scout_data:
        st.info("No data available yet for matchup preview.")
    else:
        # Build our avg stats from vs-them games
        _mv_rows = []
        if _has_our_games:
            _us_g = _our_vs_them
            _us_n = len(_us_g)
            _us_stats = {s: round(sum(p.get(s,0) for g in _us_g for p in g["players"]) / _us_n, 1)
                         for s in ["pts","reb","ast","stl","blk","to","fgm","fga","tpm","tpa"]}
            _us_fga = sum(p.get("fga",0) for g in _us_g for p in g["players"])
            _us_fta = sum(p.get("fta",0) for g in _us_g for p in g["players"])
            _us_pts = sum(p.get("pts",0) for g in _us_g for p in g["players"])
            _us_ts = round(_us_pts / (2*(_us_fga + 0.44*_us_fta)) * 100, 1) if _us_fga > 0 else None

        if _has_scout_data:
            _tend2 = get_scout_team_tendencies(_sc_games)

        # Side-by-side KPI comparison
        _mp_cols = st.columns(2)
        with _mp_cols[0]:
            st.markdown(f"#### 🔵 USA (in {_sc_team} games)")
            if _has_our_games:
                st.metric("Avg Team PTS",    round(sum(g["score"]["us"]   for g in _us_g)/_us_n, 1))
                st.metric("Avg Team REB",    _us_stats["reb"])
                st.metric("Avg Team AST",    _us_stats["ast"])
                st.metric("Avg Team TO",     _us_stats["to"])
                st.metric("Team TS%",        f"{_us_ts}%" if _us_ts else "N/A")
                st.metric("3PA/G",           _us_stats["tpa"])
            else:
                st.info("No games vs this team yet.")

        with _mp_cols[1]:
            st.markdown(f"#### 🔴 {_sc_team} (scouted games)")
            if _has_scout_data:
                st.metric("Avg Team PTS",    _tend2.get("avg_pts_for","N/A"))
                st.metric("Avg Team REB",    _tend2.get("avg_reb","N/A"))
                st.metric("Avg Team AST",    _tend2.get("avg_ast","N/A"))
                st.metric("Avg Team TO",     _tend2.get("avg_to","N/A"))
                st.metric("Team TS%",        f"{_tend2.get('ts_pct','?')}%" if _tend2.get('ts_pct') else "N/A")
                st.metric("Off Rtg",         _tend2.get("off_rtg","N/A"))
            else:
                st.info("Add scouting games to see their side of the matchup preview.")

