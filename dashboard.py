# dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
from data import load_games, save_games, get_player_totals, get_player_averages, get_derived_stats

st.set_page_config(
    page_title='USAB Esports Dashboard',
    page_icon='\U0001f3c0',
    layout='wide'
)

# Load data
data = load_games()
games = data['games']

st.title('\U0001f3c0 USAB Esports \u2014 2K Stats Dashboard')

if not games:
    st.warning('No games loaded yet. Share screenshots with Claude Code in the terminal to import games.')
    st.stop()

# Tabs
tab_games, tab_players, tab_compare, tab_lineup, tab_teams = st.tabs([
    '\U0001f4cb Games', '\U0001f464 Players', '\u2694\ufe0f Comparisons', '\U0001f527 Lineup Builder', '\U0001f19a Teams Faced'
])

# TAB 1: GAMES
with tab_games:
    st.subheader('Game Log')

    total_games = len(games)
    wins = sum(1 for g in games if g['score']['us'] > g['score']['them'])
    losses = total_games - wins
    col1, col2, col3, col4 = st.columns(4)
    col1.metric('Games Played', total_games)
    col2.metric('Wins', wins)
    col3.metric('Losses', losses)
    col4.metric('Win %', f'{wins/total_games*100:.0f}%' if total_games else '\u2014')

    st.divider()

    for game in reversed(games):
        score_us = game['score']['us']
        score_them = game['score']['them']
        result = '\u2705 W' if score_us > score_them else '\u274c L'
        label = f"{result}  |  USA {score_us} – {score_them} {game['opponent']}  |  {game['date']}"
        with st.expander(label):
            q_us = game['quarters']['us']
            q_them = game['quarters']['them']
            import pandas as pd
            qdf = pd.DataFrame({
                'Team': ['USA', game['opponent']],
                'Q1': [q_us[0], q_them[0]],
                'Q2': [q_us[1], q_them[1]],
                'Q3': [q_us[2], q_them[2]],
                'Q4': [q_us[3], q_them[3]],
                'Total': [score_us, score_them]
            })
            st.dataframe(qdf, hide_index=True, use_container_width=True)
            st.markdown('**Player Stats**')
            player_rows = []
            for p in game['players']:
                conf = p.get('confidence', {}).get('overall', 1.0)
                low_fields = p.get('confidence', {}).get('low_fields', [])
                fga = p.get('fga', 0)
                fgm = p.get('fgm', 0)
                tpa = p.get('tpa', 0)
                tpm = p.get('tpm', 0)
                fta = p.get('fta', 0)
                ftm = p.get('ftm', 0)
                player_rows.append({
                    'Name': p['name'],
                    'GRD': p.get('grade', '\u2014'),
                    'PTS': p.get('pts', 0),
                    'REB': p.get('reb', 0),
                    'AST': p.get('ast', 0),
                    'STL': p.get('stl', 0),
                    'BLK': p.get('blk', 0),
                    'FLS': p.get('fls', 0),
                    'TO': p.get('to', 0),
                    'FG': f'{fgm}/{fga}',
                    '3P': f'{tpm}/{tpa}',
                    'FT': f'{ftm}/{fta}',
                    'FG%': f'{fgm/fga*100:.0f}%' if fga > 0 else '\u2014',
                    'Confidence': f'{conf:.0%}',
                    '\u26a0\ufe0f Check': ', '.join(low_fields) if low_fields else ''
                })
            pdf = pd.DataFrame(player_rows)
            def highlight_confidence(row):
                try:
                    conf_val = float(row['Confidence'].replace('%', '')) / 100
                except (ValueError, AttributeError):
                    conf_val = 1.0
                if conf_val < 0.85:
                    return ['background-color: #fffacd'] * len(row)
                return [''] * len(row)
            styled = pdf.style.apply(highlight_confidence, axis=1)
            st.data_editor(styled, hide_index=True, use_container_width=True, key=f"game_{game['id']}")
            if st.button("💾 Save edits", key=f"save_{game['id']}"):
                st.success('Saved! (Reload dashboard to confirm)')

# TAB 2: PLAYERS
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

    pct_cols = ["fg_pct","tp_pct","ft_pct"]
    for col in pct_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "â")

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

    st.subheader("Stat Comparison Chart")
    stat_choice = st.selectbox("Compare players by:", ["pts","reb","ast","stl","blk","to"], key="players_stat")
    raw_df = get_player_averages(games) if view == "Per Game Averages" else get_player_totals(games)
    _chart_label = "Avg" if view == "Per Game Averages" else "Total"
    fig = px.bar(raw_df.sort_values(stat_choice, ascending=False),
                 x="name", y=stat_choice, color="name",
                 labels={"name":"Player", stat_choice: stat_choice.upper()},
                 title=f"{_chart_label} {stat_choice.upper()} by Player")
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# TAB 3: COMPARISONS
with tab_compare:
    st.subheader("Head-to-Head Player Comparison")

    all_players_compare = sorted(set(p["name"] for g in games for p in g["players"]))

    if len(all_players_compare) < 2:
        st.info("Need at least 2 players in the data to compare.")
    else:
        col_a, col_b = st.columns(2)
        player_a = col_a.selectbox("Player A", all_players_compare, index=0, key="compare_a")
        player_b = col_b.selectbox("Player B", all_players_compare, index=min(1, len(all_players_compare)-1), key="compare_b")

        avgs_compare = get_player_averages(games)
        avgs_compare = get_derived_stats(avgs_compare)

        a_row = avgs_compare[avgs_compare["name"] == player_a]
        b_row = avgs_compare[avgs_compare["name"] == player_b]

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

            fig_compare = px.bar(
                compare_df.melt(id_vars="Stat", var_name="Player", value_name="Value"),
                x="Stat", y="Value", color="Player", barmode="group",
                title=f"{player_a} vs {player_b} â Per Game Averages"
            )
            st.plotly_chart(fig_compare, use_container_width=True)

            st.subheader("Stat-by-Stat Breakdown")
            breakdown_rows = []
            for stat in compare_stats:
                va, vb = a[stat], b[stat]
                if stat == "to":
                    better = player_a if va < vb else (player_b if vb < va else "TIE")
                else:
                    better = player_a if va > vb else (player_b if vb > va else "TIE")
                breakdown_rows.append({"Stat": stat.upper(), player_a: va, player_b: vb, "Edge": better})
            st.dataframe(pd.DataFrame(breakdown_rows), hide_index=True, use_container_width=True)

            st.subheader("Win Rate When Playing")
            wr_cols = st.columns(2)
            for i, pname in enumerate([player_a, player_b]):
                pg = [g for g in games if any(p["name"] == pname for p in g["players"])]
                pw = sum(1 for g in pg if g["score"]["us"] > g["score"]["them"])
                wr_cols[i].metric(f"{pname}", f"{pw/len(pg)*100:.0f}% ({pw}W-{len(pg)-pw}L)" if pg else "â")

# TAB 4: LINEUP BUILDER
with tab_lineup:
    st.subheader("Lineup Builder")
    st.caption("Select up to 5 players to see projected combined stats based on per-game averages.")

    all_players_lineup = sorted(set(p["name"] for g in games for p in g["players"]))
    selected_lineup = st.multiselect("Choose players (max 5):", all_players_lineup, max_selections=5)

    if selected_lineup:
        avgs_lineup = get_player_averages(games)
        avgs_lineup = get_derived_stats(avgs_lineup)
        lineup_df = avgs_lineup[avgs_lineup["name"].isin(selected_lineup)].copy()

        stat_cols_lineup = ["pts","reb","ast","stl","blk","to"]
        projected = lineup_df[stat_cols_lineup].sum().round(1)

        st.subheader("Projected Combined Output (Per Game)")
        labels_map = {"pts":"PPG","reb":"RPG","ast":"APG","stl":"SPG","blk":"BPG","to":"TOPG"}
        m_cols = st.columns(len(stat_cols_lineup))
        for i, stat in enumerate(stat_cols_lineup):
            m_cols[i].metric(labels_map[stat], projected[stat])

        st.divider()
        st.subheader("Individual Contributions")

        display_lineup = lineup_df[["name","pts","reb","ast","stl","blk","to"]].rename(columns={
            "name":"Player","pts":"PTS","reb":"REB","ast":"AST",
            "stl":"STL","blk":"BLK","to":"TO"
        })
        st.dataframe(display_lineup, hide_index=True, use_container_width=True)

        radar_stats = ["pts","reb","ast","stl","blk"]
        radar_data = lineup_df[["name"] + radar_stats].melt(id_vars="name", var_name="Stat", value_name="Value")
        fig_radar = px.line_polar(
            radar_data, r="Value", theta="Stat", color="name",
            line_close=True,
            title="Player Radar â Per Game Averages"
        )
        fig_radar.update_traces(fill="toself")
        st.plotly_chart(fig_radar, use_container_width=True)
    else:
        st.info("Select players above to build a lineup and see projected stats.")

# TAB 5: TEAMS FACED
with tab_teams:
    st.subheader("Teams Faced")

    team_rows = {}
    for game in games:
        opp = game["opponent"]
        if opp not in team_rows:
            team_rows[opp] = {"Opponent": opp, "GP": 0, "W": 0, "L": 0,
                               "_pts_for": 0, "_pts_against": 0, "Scores": []}
        r = team_rows[opp]
        r["GP"] += 1
        us = game["score"]["us"]
        them = game["score"]["them"]
        r["_pts_for"] += us
        r["_pts_against"] += them
        r["Scores"].append(f"{us}-{them}")
        if us > them:
            r["W"] += 1
        else:
            r["L"] += 1

    team_display = []
    for opp, r in team_rows.items():
        gp = r["GP"]
        _win_pct = f"{r['W']/gp*100:.0f}%"
        team_display.append({
            "Opponent": opp,
            "GP": gp,
            "W": r["W"],
            "L": r["L"],
            "Win%": _win_pct,
            "Avg Pts For": round(r["_pts_for"]/gp, 1),
            "Avg Pts Against": round(r["_pts_against"]/gp, 1),
            "Scores": "  |  ".join(r["Scores"])
        })

    team_df = pd.DataFrame(team_display).sort_values("GP", ascending=False)
    st.dataframe(team_df, hide_index=True, use_container_width=True)

    fig_teams = px.bar(team_df, x="Opponent",
                       y=["Avg Pts For","Avg Pts Against"],
                       barmode="group",
                       title="Points For vs Against by Opponent",
                       color_discrete_map={"Avg Pts For": "#2196F3", "Avg Pts Against": "#F44336"})
    st.plotly_chart(fig_teams, use_container_width=True)
