"""
USAB Esports — Film Breakdown Tab
Scan game recordings, auto-clip every basket for USA or Opponent,
and browse/download the persistent film library.
"""

import os
import io
import json
import zipfile
import importlib.util
import traceback
from datetime import date, datetime
from pathlib import Path

import streamlit as st

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE    = Path(__file__).parent
_LIB_DIR = _HERE / "film_library"
_LIB_JSON = _LIB_DIR / "film_library.json"


# ── Library helpers ────────────────────────────────────────────────────────────

def _load_library() -> dict:
    if _LIB_JSON.exists():
        with open(_LIB_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"sessions": []}


def _save_library(lib: dict) -> None:
    _LIB_DIR.mkdir(parents=True, exist_ok=True)
    with open(_LIB_JSON, "w", encoding="utf-8") as f:
        json.dump(lib, f, indent=2)


def _session_id(date_str: str, opponent: str) -> str:
    safe_opp = opponent.replace(" ", "-").replace("/", "-")
    return f"{date_str}_{safe_opp}"


# ── game_tracker loader (lazy, avoids top-level EasyOCR import) ───────────────

def _load_tracker_mod():
    spec = importlib.util.spec_from_file_location(
        "game_tracker", str(_HERE / "game_tracker.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── ffmpeg check banner ────────────────────────────────────────────────────────

def _ffmpeg_banner() -> bool:
    mod = _load_tracker_mod()
    ok  = mod.check_ffmpeg()
    if not ok:
        st.error(
            "**ffmpeg not found.** Clip generation requires ffmpeg.\n\n"
            "Install it with:\n"
            "```\nwinget install ffmpeg\n```\n"
            "Then restart your terminal and the dashboard.",
            icon="⚠️",
        )
    return ok


# ── Clip download helpers ──────────────────────────────────────────────────────

def _clip_bytes(path: str) -> bytes | None:
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return None


def _zip_clips(clips: list) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for c in clips:
            p = c.get("path", "")
            if p and os.path.exists(p) and not c.get("error"):
                zf.write(p, arcname=c["filename"])
    return buf.getvalue()


# ── Clip table renderer ────────────────────────────────────────────────────────

def _render_clip_table(clips: list, key_prefix: str) -> None:
    """Render a table of clips with individual download buttons."""
    if not clips:
        st.info("No clips in this session.")
        return

    ok_clips = [c for c in clips if not c.get("error") and os.path.exists(c.get("path", ""))]
    err_clips = [c for c in clips if c.get("error") or not os.path.exists(c.get("path", ""))]

    if err_clips:
        st.caption(f"⚠️ {len(err_clips)} clip(s) missing/failed — re-generate to fix.")

    # Header row
    hc = st.columns([1, 1.5, 1.2, 1.5, 2])
    hc[0].markdown("**#**")
    hc[1].markdown("**Quarter**")
    hc[2].markdown("**Clock**")
    hc[3].markdown("**Shot**")
    hc[4].markdown("**Download**")

    for i, clip in enumerate(ok_clips):
        row = st.columns([1, 1.5, 1.2, 1.5, 2])
        row[0].write(f"{i+1}")
        row[1].write(clip.get("quarter", "?"))
        row[2].write(clip.get("clock",   "?"))
        row[3].write(clip.get("shot_type", "?"))
        data = _clip_bytes(clip["path"])
        if data:
            row[4].download_button(
                label="⬇️ Download",
                data=data,
                file_name=clip["filename"],
                mime="video/mp4",
                key=f"{key_prefix}_{i}",
            )
        else:
            row[4].caption("—")

    st.divider()

    # Download All zip
    if ok_clips:
        zip_data = _zip_clips(ok_clips)
        st.download_button(
            label=f"📦 Download All {len(ok_clips)} clips (zip)",
            data=zip_data,
            file_name=f"{key_prefix}_all.zip",
            mime="application/zip",
            key=f"{key_prefix}_zip",
        )


# ── Library browser ────────────────────────────────────────────────────────────

def _render_library(sessions: list, team_key: str) -> None:
    """
    Browse sessions for one clip side.
    team_key = "left_clips" or "right_clips"
    Falls back to legacy "usa_clips"/"opp_clips" keys for old sessions.
    """
    legacy_map = {"left_clips": "usa_clips", "right_clips": "opp_clips"}
    relevant = [
        s for s in sessions
        if s.get(team_key) or s.get(legacy_map.get(team_key, ""))
    ]
    if not relevant:
        st.info("No clips here yet. Use the **📹 Add New Game** tab to generate clips.")
        return

    relevant = sorted(relevant, key=lambda s: s.get("date", ""), reverse=True)

    for s in relevant:
        # Support both new schema (left_team/right_team) and legacy (opponent)
        clips = s.get(team_key) or s.get(legacy_map.get(team_key, ""), [])

        left_t  = s.get("left_team")  or "Left"
        right_t = s.get("right_team") or s.get("opponent", "Right")
        team_label = left_t if team_key == "left_clips" else right_t

        n_ok    = sum(1 for c in clips if not c.get("error") and os.path.exists(c.get("path", "")))
        badge   = f"🏀 {n_ok} baskets" if n_ok > 0 else "⚠️ clips missing"
        header  = f"**{s['label']}**  ·  clipping **{team_label}**  ·  {badge}"
        sess_id = s["id"]

        with st.expander(header, expanded=False):
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.caption(f"📅 {s.get('date', '?')}")
            mc2.caption(f"⬅️ {left_t}")
            mc3.caption(f"➡️ {right_t}")
            mc4.caption(f"🎬 {s.get('processed_at', '?')[:10]}")

            _render_clip_table(clips, key_prefix=f"{sess_id}_{team_key}")

            with st.popover("🗑️ Delete session"):
                st.warning("Removes from library index — clip files on disk are NOT deleted.")
                if st.button("Confirm delete", key=f"del_{sess_id}_{team_key}"):
                    lib = _load_library()
                    lib["sessions"] = [x for x in lib["sessions"] if x["id"] != sess_id]
                    _save_library(lib)
                    st.success("Session removed from library.")
                    st.rerun()


# ── Add New Game tab ───────────────────────────────────────────────────────────

def _render_add_game(ffmpeg_ok: bool) -> None:
    st.markdown("### 📹 Scan Video & Generate Clips")
    st.caption(
        "Works for any game — USA vs opponent **or** a scouting video of two other teams. "
        "Just name both teams and pick which side to clip."
    )

    # ── Inputs ────────────────────────────────────────────────────────────────
    vid_path = st.text_input(
        "Video file path",
        placeholder="C:/Users/lance/Videos/game.mp4",
        key="film_vid_path",
    )
    # Strip surrounding quotes that Windows sometimes adds when copy-pasting paths
    vid_path = vid_path.strip().strip('"').strip("'")

    # Team names — left defaults to USA but can be anything
    tc1, tc2, tc3 = st.columns(3)
    left_team  = tc1.text_input("⬅️ Left team (scoreboard left)",  value="USA",   key="film_left_team")
    right_team = tc2.text_input("➡️ Right team (scoreboard right)", placeholder="Legendary Weapons", key="film_right_team")
    game_date  = tc3.date_input("📅 Game date", value=date.today(), key="film_date")

    # Dynamic radio options using the entered team names
    left_label  = left_team  or "Left team"
    right_label = right_team or "Right team"
    team_choice = st.radio(
        "Which team's baskets to clip?",
        options=[
            f"🏀 {left_label} baskets (left score)",
            f"🔴 {right_label} baskets (right score)",
            "⚡ Both teams",
        ],
        horizontal=True,
        key="film_team_choice",
    )
    if "Both" in team_choice:
        team_side = "both"
    elif left_label in team_choice:
        team_side = "left"
    else:
        team_side = "right"

    c3, c4 = st.columns(2)
    before_sec = c3.slider("Seconds BEFORE basket", 10, 45, 30, key="film_before")
    after_sec  = c4.slider("Seconds AFTER basket",   1, 10,  2, key="film_after")

    st.divider()

    # ── Scan + Clip button ────────────────────────────────────────────────────
    can_run = bool(vid_path and right_team and ffmpeg_ok)
    if not ffmpeg_ok:
        st.warning("Install ffmpeg first (see instructions above).", icon="⚠️")
    elif not right_team:
        st.info("Enter both team names above to enable scanning.", icon="ℹ️")

    scan_btn = st.button(
        "🎬 Scan & Clip",
        type="primary",
        disabled=not can_run,
        key="film_scan_btn",
    )

    if scan_btn:
        if not os.path.exists(vid_path):
            st.error(f"File not found: `{vid_path}`")
            return

        date_str   = game_date.strftime("%Y-%m-%d")
        sess_id    = _session_id(date_str, f"{left_team}-vs-{right_team}")
        sess_label = f"{game_date.strftime('%b %d')} · {left_team} vs {right_team}"

        # Output dirs named after actual teams
        left_safe  = left_team.replace(" ", "_")
        right_safe = right_team.replace(" ", "_")
        left_out  = _LIB_DIR / left_safe  / sess_id
        right_out = _LIB_DIR / right_safe / sess_id
        left_out.mkdir(parents=True, exist_ok=True)
        right_out.mkdir(parents=True, exist_ok=True)

        pb     = st.progress(0.0, text="Loading EasyOCR (first run ~30s)…")
        status = st.empty()

        try:
            mod = _load_tracker_mod()

            # ── Step 1: Scan video for score events ───────────────────────────
            status.info("Step 1/2 — Scanning video for scoring events…")

            def on_scan(p):
                pb.progress(p * 0.8, text=f"Scanning… {int(p*100)}%")

            game_data = mod.process_video(
                vid_path,
                sample_interval=2.0,
                read_stats=False,
                progress_callback=on_scan,
            )

            events = game_data.get("events", [])
            score_events = [e for e in events if e.get("event_type") in
                            ("score_left", "score_right")]
            status.info(f"Step 1 done — {len(score_events)} scoring events detected.")

            # ── Step 2: Extract clips ─────────────────────────────────────────
            status.info("Step 2/2 — Cutting clips with ffmpeg…")

            def on_clip(p):
                pb.progress(0.8 + p * 0.2, text=f"Clipping… {int(p*100)}%")

            left_clips  = []
            right_clips = []

            if team_side in ("left", "both"):
                left_clips = mod.batch_extract_clips(
                    vid_path, events, "left", str(left_out),
                    before_sec, after_sec,
                    progress_cb=on_clip if team_side == "left" else None,
                )
            if team_side in ("right", "both"):
                right_clips = mod.batch_extract_clips(
                    vid_path, events, "right", str(right_out),
                    before_sec, after_sec,
                    progress_cb=on_clip,
                )

            pb.progress(1.0, text="Done!")
            status.success(
                f"✅ **{left_team}**: {len(left_clips)} clip(s)  ·  "
                f"**{right_team}**: {len(right_clips)} clip(s)  —  {sess_label}"
            )

            # ── Save to library ───────────────────────────────────────────────
            lib = _load_library()
            lib["sessions"] = [s for s in lib["sessions"] if s["id"] != sess_id]
            lib["sessions"].append({
                "id":           sess_id,
                "label":        sess_label,
                "left_team":    left_team,
                "right_team":   right_team,
                "date":         date_str,
                "video_path":   vid_path,
                "left_clips":   left_clips,
                "right_clips":  right_clips,
                "processed_at": datetime.now().isoformat(timespec="seconds"),
            })
            _save_library(lib)

        except Exception as exc:
            pb.empty()
            status.error(f"Error: {exc}")
            st.code(traceback.format_exc())


# ── Main entry point ───────────────────────────────────────────────────────────

def render_film_tab() -> None:
    st.subheader("🎬 Film Breakdown")
    st.caption(
        "Auto-clip every basket from any game recording — USA games or pure scouting film. "
        "Name both teams, pick which side to clip, and download organised clips."
    )

    ffmpeg_ok = _ffmpeg_banner()

    lib      = _load_library()
    sessions = lib.get("sessions", [])

    # Count clips across both new schema and legacy keys
    def _count(key, legacy):
        return sum(len(s.get(key) or s.get(legacy, [])) for s in sessions)

    n_left  = _count("left_clips",  "usa_clips")
    n_right = _count("right_clips", "opp_clips")

    inner_add, inner_left, inner_right = st.tabs([
        "📹 Add New Game",
        f"🏀 Left Team Film ({n_left} clips)",
        f"🔴 Right Team Film ({n_right} clips)",
    ])

    with inner_add:
        _render_add_game(ffmpeg_ok)

    with inner_left:
        st.markdown("### 🏀 Left Team Film — All Sessions")
        st.caption("Clips of the **left scoreboard team** scoring (typically USA in your own games).")
        _render_library(sessions, "left_clips")

    with inner_right:
        st.markdown("### 🔴 Right Team Film — All Sessions")
        st.caption("Clips of the **right scoreboard team** scoring (opponent in your games, or scouted team).")
        _render_library(sessions, "right_clips")
