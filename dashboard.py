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

# TAB 2: PLAYERS (placeholder)
with tab_players:
    st.info('Players tab coming soon.')

# TAB 3: COMPARISONS (placeholder)
with tab_compare:
    st.info('Comparisons tab coming soon.')

# TAB 4: LINEUP BUILDER (placeholder)
with tab_lineup:
    st.info('Lineup Builder coming soon.')

# TAB 5: TEAMS FACED (placeholder)
with tab_teams:
    st.info('Teams Faced coming soon.')
