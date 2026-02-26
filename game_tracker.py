"""
USAB Esports - 2K Game Tracker
Extracts live game stats from NBA 2K Pro-Am video recordings.

Uses:
- EasyOCR for score reading (handles chunky game fonts)
- Tesseract for clock/quarter/shot clock (clean white text)
- OpenCV for frame extraction and preprocessing

Regions calibrated for 1080p (1920x1080) game capture.
"""

import cv2
import numpy as np
import json
import time
import sys
import os
from dataclasses import dataclass, field, asdict
from typing import Optional, List

import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

_easyocr_reader = None

def get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        _easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _easyocr_reader


# ── HUD Region Definitions (1080p) ──────────────────────────────────────────
REGION_BOTTOM_BAR   = (1005, 1065, 30, 800)   # Full bottom bar for EasyOCR scores
REGION_CLOCK        = (1005, 1060, 720, 820)  # Game clock (Tesseract)
REGION_SHOT_CLOCK   = (1005, 1060, 825, 875)  # Shot clock (Tesseract)
REGION_QUARTER      = (1005, 1060, 878, 950)  # Quarter indicator (Tesseract)
REGION_PLAYER_STATS = (40, 85, 1450, 1900)    # Full stats overlay (top-right)


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class FrameData:
    """Data extracted from a single frame."""
    timestamp_sec: float = 0.0
    left_score: Optional[int] = None
    right_score: Optional[int] = None
    clock: str = ""
    shot_clock: str = ""
    quarter: str = ""
    player_pts: Optional[int] = None
    player_reb: Optional[int] = None
    player_ast: Optional[int] = None
    player_fg: str = ""


@dataclass
class GameEvent:
    """A detected game event."""
    timestamp_sec: float
    video_time: str          # MM:SS format
    game_clock: str
    quarter: str
    event_type: str          # score_left, score_right, score_jump, quarter_change
    details: str
    left_score: int = 0
    right_score: int = 0


@dataclass
class QuarterScore:
    """Score tracking for a single quarter."""
    quarter: str
    start_score: List[int] = field(default_factory=lambda: [0, 0])
    end_score: Optional[List[int]] = None

    @property
    def left_pts(self):
        if self.end_score:
            return self.end_score[0] - self.start_score[0]
        return None

    @property
    def right_pts(self):
        if self.end_score:
            return self.end_score[1] - self.start_score[1]
        return None


@dataclass
class GameTracker:
    """Tracks game state across frames."""
    events: list = field(default_factory=list)
    last_left_score: int = 0
    last_right_score: int = 0
    last_quarter: str = "1st"   # Pre-seeded: no spurious event at game start
    frame_count: int = 0
    errors: int = 0
    quarter_scores: list = field(default_factory=list)
    player_stats_history: list = field(default_factory=list)


# ── OCR Functions ─────────────────────────────────────────────────────────────

def crop_region(frame, region):
    """Crop a region from frame. Region = (y1, y2, x1, x2)."""
    y1, y2, x1, x2 = region
    return frame[y1:y2, x1:x2]


def ocr_clock(frame):
    """Read game clock using Tesseract. Returns string like '4:52'."""
    crop = crop_region(frame, REGION_CLOCK)
    big = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    padded = cv2.copyMakeBorder(thresh, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=0)
    text = pytesseract.image_to_string(
        padded, config='--psm 7 -c tessedit_char_whitelist=0123456789:.'
    ).strip()
    return text


def ocr_quarter(frame):
    """Read quarter. Returns '1st'/'2nd'/'3rd'/'4th'/'OT' or empty string."""
    crop = crop_region(frame, REGION_QUARTER)
    big = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    # Yellow HSV isolation (quarter text is yellow in 2K HUD)
    hsv = cv2.cvtColor(big, cv2.COLOR_BGR2HSV)
    yellow_mask = cv2.inRange(hsv, np.array([15, 60, 150]), np.array([45, 255, 255]))
    yellow_mask = cv2.dilate(yellow_mask, np.ones((2, 2), np.uint8), iterations=1)
    padded = cv2.copyMakeBorder(yellow_mask, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=0)
    text = pytesseract.image_to_string(padded, config='--psm 7').strip()

    # Fallback: white threshold
    if not text or len(text) < 2:
        gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        padded2 = cv2.copyMakeBorder(thresh, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=0)
        text2 = pytesseract.image_to_string(padded2, config='--psm 7').strip()
        if len(text2) > len(text):
            text = text2

    text_clean = ''.join(c for c in text.lower() if c.isalnum())

    for q, variants in [
        ('1st', ['1st', '1s', 'ist', 'lst', '1t']),
        ('2nd', ['2nd', '2n', '2nc', 'and', 'znd']),
        ('3rd', ['3rd', '3r', '3re', '3ra']),
        ('4th', ['4th', '4t', '4tr', '4ti']),
        ('OT',  ['ot', 'oot']),
    ]:
        if text_clean in [v.lower() for v in variants]:
            return q

    if '1' in text_clean and ('s' in text_clean or 't' in text_clean):
        return '1st'
    if '2' in text_clean and 'n' in text_clean:
        return '2nd'
    if '3' in text_clean and 'r' in text_clean:
        return '3rd'
    if '4' in text_clean and 't' in text_clean:
        return '4th'

    return ""   # Unknown - do not fire spurious quarter change


def ocr_shot_clock(frame):
    """Read shot clock using Tesseract."""
    crop = crop_region(frame, REGION_SHOT_CLOCK)
    big = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    padded = cv2.copyMakeBorder(thresh, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=0)
    text = pytesseract.image_to_string(
        padded, config='--psm 8 -c tessedit_char_whitelist=0123456789'
    ).strip()
    return text


def is_gameplay_frame(frame):
    """Return True if the HUD bottom bar is visible (real gameplay frame)."""
    bar_region = frame[1005:1065, 700:820]
    mean_brightness = np.mean(cv2.cvtColor(bar_region, cv2.COLOR_BGR2GRAY))
    # During gameplay this area is dark (<120). Cutscenes/menus are brighter.
    return mean_brightness < 120


def ocr_scores(frame):
    """
    Read both scores using EasyOCR.

    Fixes applied vs original:
    - Filter len(text) <= 2  (scores are max 2 digits in a Pro-Am game)
    - Filter bounding box WIDTH <= 150px  (clock/concatenated digits are wider)
    - Discard values outside 0-99
    - Left score zone:  x 190-310 in the crop  (crop starts at x=30 in frame)
    - Right score zone: x 430-580 in the crop
    - Pick highest-confidence hit per zone

    Returns (left_score, right_score) as ints or None.
    """
    crop = crop_region(frame, REGION_BOTTOM_BAR)
    reader = get_easyocr_reader()
    results = reader.readtext(crop, allowlist='0123456789')

    left_score  = None
    right_score = None
    left_conf   = 0.0
    right_conf  = 0.0

    for (bbox, text, conf) in results:
        # Must be digit-only, 1-2 chars, minimum confidence
        if not (text.isdigit() and 1 <= len(text) <= 2 and conf > 0.25):
            continue

        val = int(text)
        if val < 0 or val > 99:          # Valid game score range
            continue

        x_center  = (bbox[0][0] + bbox[2][0]) / 2
        bbox_width = bbox[1][0] - bbox[0][0]

        # Reject wide bounding boxes (these are clock digits being concatenated)
        if bbox_width > 150:
            continue

        # Left score zone: x 190-310 in crop
        if 190 < x_center < 310 and conf > left_conf:
            left_score = val
            left_conf  = conf

        # Right score zone: x 430-580 in crop
        elif 430 < x_center < 580 and conf > right_conf:
            right_score = val
            right_conf  = conf

    return left_score, right_score


def ocr_player_stats(frame):
    """
    Read player stats from top-right overlay using EasyOCR (more reliable than Tesseract).
    Crops frame[50:80, 1570:1900] for just the numbers row.

    Expected x-offsets within the crop (crop starts at x=1570):
      PTS  ~  70px  (frame x 1640)
      REB  ~ 150px  (frame x 1720)
      AST  ~ 230px  (frame x 1800)
      FG%  ~ 300px  (frame x 1870)

    Returns (pts, reb, ast, fg_pct_str).
    """
    crop = frame[50:80, 1570:1900]
    reader = get_easyocr_reader()
    results = reader.readtext(crop, allowlist='0123456789%')

    pts = reb = ast = None
    fg  = ""
    pts_conf = reb_conf = ast_conf = fg_conf = 0.0

    for (bbox, text, conf) in results:
        if conf < 0.10:
            continue
        x_center = (bbox[0][0] + bbox[2][0]) / 2

        if '%' in text:
            if conf > fg_conf:
                fg = text
                fg_conf = conf
        elif text.isdigit():
            val = int(text)
            if val > 999:
                continue
            if  20 < x_center < 120 and conf > pts_conf:
                pts = val; pts_conf = conf
            elif 120 < x_center < 200 and conf > reb_conf:
                reb = val; reb_conf = conf
            elif 200 < x_center < 280 and conf > ast_conf:
                ast = val; ast_conf = conf

    # Tesseract fallback when EasyOCR gets nothing
    if pts is None and reb is None and ast is None:
        try:
            big = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
            padded = cv2.copyMakeBorder(thresh, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=0)
            raw = pytesseract.image_to_string(
                padded, config='--psm 7 -c tessedit_char_whitelist=0123456789%'
            ).strip()
            parts = raw.split()
            if len(parts) >= 3:
                pts = int(parts[0])
                reb = int(parts[1])
                ast = int(parts[2])
            if len(parts) >= 4:
                fg = parts[3]
        except Exception:
            pass

    return pts, reb, ast, fg


# ── Frame Processing ──────────────────────────────────────────────────────────

def process_frame(frame, tracker: GameTracker, timestamp_sec: float,
                  read_scores=True, read_stats=False) -> Optional[FrameData]:
    """Process a single frame and detect events."""

    # Normalize to 1920x1080 so all hardcoded region coords work at any input resolution
    if frame.shape[0] != 1080 or frame.shape[1] != 1920:
        frame = cv2.resize(frame, (1920, 1080), interpolation=cv2.INTER_LINEAR)

    data = FrameData(timestamp_sec=timestamp_sec)

    if not is_gameplay_frame(frame):
        tracker.frame_count += 1
        return data

    data.clock     = ocr_clock(frame)
    data.quarter   = ocr_quarter(frame)
    data.shot_clock = ocr_shot_clock(frame)

    if read_scores:
        left, right = ocr_scores(frame)
        data.left_score  = left
        data.right_score = right

    if read_stats:
        pts, reb, ast, fg = ocr_player_stats(frame)
        data.player_pts = pts
        data.player_reb = reb
        data.player_ast = ast
        data.player_fg  = fg
        if pts is not None:
            tracker.player_stats_history.append({
                "timestamp_sec": timestamp_sec,
                "pts": pts, "reb": reb, "ast": ast, "fg": fg,
            })

    video_time     = f"{int(timestamp_sec // 60)}:{int(timestamp_sec % 60):02d}"
    valid_quarters = {"1st", "2nd", "3rd", "4th", "OT"}

    # ── Quarter change detection ──────────────────────────────────────────────
    # tracker.last_quarter is pre-seeded to "1st" so the very first frame
    # that reads "1st" does NOT fire a spurious quarter_change event.
    # A real transition (e.g. 1st -> 2nd) WILL fire because it is a new value.
    if (data.quarter in valid_quarters
            and data.quarter != tracker.last_quarter
            and tracker.last_quarter in valid_quarters):

        # Close out the previous quarter's score record
        if tracker.quarter_scores:
            tracker.quarter_scores[-1].end_score = [
                tracker.last_left_score, tracker.last_right_score
            ]

        # Open a new quarter record
        tracker.quarter_scores.append(QuarterScore(
            quarter=data.quarter,
            start_score=[tracker.last_left_score, tracker.last_right_score],
        ))

        tracker.events.append(GameEvent(
            timestamp_sec=timestamp_sec,
            video_time=video_time,
            game_clock=data.clock,
            quarter=data.quarter,
            event_type="quarter_change",
            details=f"Quarter: {tracker.last_quarter} -> {data.quarter}",
            left_score=tracker.last_left_score,
            right_score=tracker.last_right_score,
        ))

    if data.quarter in valid_quarters:
        # On the very first valid reading, open the first quarter record
        if not tracker.quarter_scores:
            tracker.quarter_scores.append(QuarterScore(
                quarter=data.quarter,
                start_score=[tracker.last_left_score, tracker.last_right_score],
            ))
        tracker.last_quarter = data.quarter

    # ── Score change detection ────────────────────────────────────────────────
    current_left  = data.left_score  if data.left_score  is not None else tracker.last_left_score
    current_right = data.right_score if data.right_score is not None else tracker.last_right_score

    if current_left != tracker.last_left_score or current_right != tracker.last_right_score:
        left_diff  = current_left  - tracker.last_left_score
        right_diff = current_right - tracker.last_right_score

        # Hard sanity: discard impossible values
        if current_left < 0 or current_left > 99 or current_right < 0 or current_right > 99:
            tracker.errors += 1

        elif left_diff < 0 or right_diff < 0:
            # Scores never go down (bad OCR read) - discard
            tracker.errors += 1

        elif left_diff <= 4 and right_diff <= 4 and (left_diff > 0 or right_diff > 0):
            # Normal scoring event: 1-4 pts covers FT + 3PT combos
            if left_diff > 0:
                shot_type = {1: "FT", 2: "2PT", 3: "3PT", 4: "3PT+FT"}.get(left_diff, f"+{left_diff}")
                tracker.events.append(GameEvent(
                    timestamp_sec=timestamp_sec,
                    video_time=video_time,
                    game_clock=data.clock,
                    quarter=data.quarter or tracker.last_quarter,
                    event_type="score_left",
                    details=f"Left scored {shot_type} ({tracker.last_left_score}->{current_left})",
                    left_score=current_left,
                    right_score=current_right,
                ))
            if right_diff > 0:
                shot_type = {1: "FT", 2: "2PT", 3: "3PT", 4: "3PT+FT"}.get(right_diff, f"+{right_diff}")
                tracker.events.append(GameEvent(
                    timestamp_sec=timestamp_sec,
                    video_time=video_time,
                    game_clock=data.clock,
                    quarter=data.quarter or tracker.last_quarter,
                    event_type="score_right",
                    details=f"Right scored {shot_type} ({tracker.last_right_score}->{current_right})",
                    left_score=current_left,
                    right_score=current_right,
                ))
            tracker.last_left_score  = current_left
            tracker.last_right_score = current_right

        elif (left_diff == 0 or 0 < left_diff <= 15) and (right_diff == 0 or 0 < right_diff <= 15) and (left_diff > 0 or right_diff > 0):
            # Plausible gap from missed sampling window (> 4 pts but each team <= 15)
            tracker.events.append(GameEvent(
                timestamp_sec=timestamp_sec,
                video_time=video_time,
                game_clock=data.clock,
                quarter=data.quarter or tracker.last_quarter,
                event_type="score_jump",
                details=(f"Score jump (missed window): "
                         f"{tracker.last_left_score}-{tracker.last_right_score} "
                         f"-> {current_left}-{current_right}"),
                left_score=current_left,
                right_score=current_right,
            ))
            tracker.last_left_score  = current_left
            tracker.last_right_score = current_right

        else:
            # Jump > 15 pts on one team - almost certainly an OCR error
            tracker.errors += 1

    tracker.frame_count += 1
    return data


# ── Post-processing Summary ───────────────────────────────────────────────────

def process_video_to_summary(tracker: GameTracker) -> dict:
    """
    Compute high-level summary from collected tracker data.
    Called after all frames have been processed.
    """
    # Close out the last quarter
    if tracker.quarter_scores:
        last_qs = tracker.quarter_scores[-1]
        if last_qs.end_score is None:
            last_qs.end_score = [tracker.last_left_score, tracker.last_right_score]

    # Quarter-by-quarter breakdown
    quarter_scores_out = []
    for qs in tracker.quarter_scores:
        end = qs.end_score or [tracker.last_left_score, tracker.last_right_score]
        quarter_scores_out.append({
            "quarter":     qs.quarter,
            "start_score": qs.start_score,
            "end_score":   end,
            "left_pts":    (end[0] - qs.start_score[0]),
            "right_pts":   (end[1] - qs.start_score[1]),
        })

    # Shot type breakdown from scoring events
    shot_breakdown = {
        "left":  {"FT": 0, "2PT": 0, "3PT": 0, "3PT+FT": 0, "jump": 0},
        "right": {"FT": 0, "2PT": 0, "3PT": 0, "3PT+FT": 0, "jump": 0},
    }
    for ev in tracker.events:
        if ev.event_type == "score_left":
            for key in ("FT", "2PT", "3PT", "3PT+FT"):
                if key in ev.details:
                    shot_breakdown["left"][key] += 1
                    break
        elif ev.event_type == "score_right":
            for key in ("FT", "2PT", "3PT", "3PT+FT"):
                if key in ev.details:
                    shot_breakdown["right"][key] += 1
                    break
        elif ev.event_type == "score_jump":
            # Can't determine shot type from a gap event
            shot_breakdown["left"]["jump"] += 1
            shot_breakdown["right"]["jump"] += 1

    # Scoring runs: detect when one team scores 6+ unanswered points
    scoring_runs = []
    run_team       = None
    run_start_pts  = [0, 0]
    run_start_time = None
    run_opp_pts    = 0   # points opponent scored since this run started

    for ev in tracker.events:
        if ev.event_type not in ("score_left", "score_right", "score_jump"):
            continue

        if ev.event_type == "score_left":
            if run_team != "left":
                # Check if previous right run qualifies
                if run_team == "right" and run_opp_pts == 0:
                    run_pts = ev.right_score - run_start_pts[1]
                    if run_pts >= 6:
                        scoring_runs.append({
                            "team": "right", "points": run_pts,
                            "start_time": run_start_time, "end_time": ev.video_time,
                        })
                run_team       = "left"
                run_start_pts  = [ev.left_score, ev.right_score]
                run_start_time = ev.video_time
                run_opp_pts    = 0
            # right scored nothing this run
        elif ev.event_type == "score_right":
            if run_team != "right":
                if run_team == "left" and run_opp_pts == 0:
                    run_pts = ev.left_score - run_start_pts[0]
                    if run_pts >= 6:
                        scoring_runs.append({
                            "team": "left", "points": run_pts,
                            "start_time": run_start_time, "end_time": ev.video_time,
                        })
                run_team       = "right"
                run_start_pts  = [ev.left_score, ev.right_score]
                run_start_time = ev.video_time
                run_opp_pts    = 0
        else:
            # score_jump - reset run tracking
            run_team = None

    # Player final stats (last seen values)
    player_final = {"pts": None, "reb": None, "ast": None, "fg": ""}
    if tracker.player_stats_history:
        last = tracker.player_stats_history[-1]
        player_final = {
            "pts": last.get("pts"),
            "reb": last.get("reb"),
            "ast": last.get("ast"),
            "fg":  last.get("fg", ""),
        }

    return {
        "quarter_scores":    quarter_scores_out,
        "shot_type_breakdown": shot_breakdown,
        "scoring_runs":      scoring_runs,
        "player_final_stats": player_final,
    }


# ── Main Processing ───────────────────────────────────────────────────────────

def process_video(video_path: str, sample_interval: float = 2.0,
                  max_seconds: Optional[float] = None,
                  read_stats: bool = True,
                  progress_callback=None) -> dict:
    """
    Process a video file and extract game events.

    Args:
        video_path:        Path to the video file (MP4)
        sample_interval:   Seconds between frame samples (default 2.0)
        max_seconds:       Stop after this many seconds (None = full game)
        read_stats:        Also read player stats from top-right overlay
        progress_callback: Optional callable(pct: float, 0.0-1.0)

    Returns:
        Dictionary with game data, events, and summary stats.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    fps          = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration     = total_frames / fps
    width        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"Video: {width}x{height} @ {fps:.1f}fps, {duration/60:.1f} minutes")
    print(f"Sampling every {sample_interval}s ...")
    print("Loading EasyOCR model (first run may take a moment)...")
    get_easyocr_reader()
    print("EasyOCR ready!")

    tracker = GameTracker()
    current_sec = 0.0
    end_sec     = min(max_seconds, duration) if max_seconds else duration
    start_time  = time.time()

    while current_sec < end_sec:
        frame_num = int(current_sec * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        if not ret:
            break

        data = process_frame(frame, tracker, current_sec,
                             read_scores=True, read_stats=read_stats)

        elapsed = time.time() - start_time
        pct = (current_sec / end_sec) * 100
        msg = (f"  [{pct:5.1f}%] {current_sec:.0f}s/{end_sec:.0f}s | "
              f"Score: {tracker.last_left_score}-{tracker.last_right_score} | "
              f"Q: {tracker.last_quarter} | "
              f"Events: {len(tracker.events)} | "
              f"{elapsed:.0f}s elapsed")
        print(chr(13) + msg, end="", flush=True)


        if progress_callback:
            progress_callback(pct / 100.0)

        current_sec += sample_interval

    cap.release()
    elapsed_total = time.time() - start_time
    print(f"Done! {tracker.frame_count} frames in {elapsed_total:.1f}s")
    print(f"Events: {len(tracker.events)}, OCR errors discarded: {tracker.errors}")

    summary = process_video_to_summary(tracker)

    result = {
        "video_path":         video_path,
        "video_duration_sec": duration,
        "frames_processed":   tracker.frame_count,
        "sample_interval_sec": sample_interval,
        "ocr_errors":         tracker.errors,
        "final_score": {
            "left":  tracker.last_left_score,
            "right": tracker.last_right_score,
        },
        "events":  [asdict(e) for e in tracker.events],
        "summary": summary,
    }

    return result


# ── Clip Extraction ───────────────────────────────────────────────────────────

def check_ffmpeg() -> bool:
    """Return True if ffmpeg is available on PATH."""
    import subprocess
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def extract_clip(video_path: str, timestamp_sec: float, output_path: str,
                 before_sec: float = 30.0, after_sec: float = 2.0) -> None:
    """
    Cut a clip from video_path centred around timestamp_sec using ffmpeg stream copy.
    Stream copy = no re-encoding, typically <0.5s per clip.

    Args:
        video_path:    Source video file
        timestamp_sec: Score event timestamp (the moment the basket went in)
        output_path:   Destination .mp4 path
        before_sec:    Seconds before the event to include (default 30)
        after_sec:     Seconds after the event to include (default 2)
    """
    import subprocess, os
    start    = max(0.0, timestamp_sec - before_sec)
    duration = before_sec + after_sec
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y",
         "-ss", f"{start:.3f}",
         "-i",  video_path,
         "-t",  f"{duration:.3f}",
         "-c",  "copy",
         output_path],
        check=True,
        capture_output=True,
    )


def batch_extract_clips(
    video_path:  str,
    events:      list,
    team_side:   str,   # "left" → USA baskets, "right" → Opponent baskets, "both"
    output_dir:  str,
    before_sec:  float = 30.0,
    after_sec:   float = 2.0,
    progress_cb=None,
) -> list:
    """
    Extract one clip per scoring event for the requested team_side.

    Returns list of clip metadata dicts:
      { filename, path, timestamp, quarter, clock, shot_type, score_before, score_after }
    """
    import os, re

    def _safe(s: str) -> str:
        return re.sub(r'[^\w\-]', '_', s)

    # Filter events — include score_jump (missed sampling window) for both sides
    if team_side == "both":
        target_types = {"score_left", "score_right", "score_jump"}
    elif team_side == "left":
        target_types = {"score_left", "score_jump"}
    else:
        target_types = {"score_right", "score_jump"}

    scoring = [e for e in events if e.get("event_type") in target_types]
    clips   = []
    total   = len(scoring)

    for i, ev in enumerate(scoring):
        ts        = ev["timestamp_sec"]
        quarter   = ev.get("quarter", "Q?")
        clock     = ev.get("game_clock", "?")
        details   = ev.get("details", "")
        left_sc   = ev.get("left_score",  0)
        right_sc  = ev.get("right_score", 0)
        evt_type  = ev.get("event_type", "")

        # Parse shot type from details string e.g. "Left scored 2PT (0->2)"
        shot_type = "basket"
        for st in ("3PT+FT", "3PT", "2PT", "FT"):
            if st in details:
                shot_type = st
                break

        # Clean clock for filename (replace : with m)
        clock_fn  = clock.replace(":", "m").replace(".", "s") if clock else "???"
        team_tag  = "USA" if evt_type == "score_left" else "OPP"
        filename  = f"basket_{i+1:02d}_{_safe(quarter)}_{clock_fn}_{shot_type}_{team_tag}.mp4"
        out_path  = os.path.join(output_dir, filename)

        try:
            extract_clip(video_path, ts, out_path, before_sec, after_sec)
            clips.append({
                "filename":    filename,
                "path":        out_path,
                "timestamp":   ts,
                "quarter":     quarter,
                "clock":       clock,
                "shot_type":   shot_type,
                "score_before": f"{left_sc - (left_sc - ev.get('left_score', left_sc))}-{right_sc}",
                "score_after": f"{left_sc}-{right_sc}",
                "team":        team_tag,
            })
        except Exception as exc:
            clips.append({
                "filename":  filename,
                "path":      out_path,
                "error":     str(exc),
                "timestamp": ts,
                "quarter":   quarter,
                "clock":     clock,
                "shot_type": shot_type,
                "team":      team_tag,
            })

        if progress_cb:
            progress_cb((i + 1) / total)

    return clips


# ── CLI Entry Point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python game_tracker.py <video_path> [sample_interval] [max_seconds]")
        print("  video_path:      Path to the game recording (MP4)")
        print("  sample_interval: Seconds between samples (default 2.0)")
        print("  max_seconds:     Max video seconds to process (default: all)")
        sys.exit(1)

    video_path = sys.argv[1]
    interval   = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    max_sec    = float(sys.argv[3]) if len(sys.argv) > 3 else None

    result = process_video(video_path, sample_interval=interval,
                           max_seconds=max_sec, read_stats=True)

    output_path = os.path.splitext(video_path)[0] + "_tracked.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Results saved to: {output_path}")
    print(f"{'='*60}")
    print("GAME SUMMARY")
    print(f"{'='*60}")
    print(f"Final Score: {result['final_score']['left']} - {result['final_score']['right']}")

    summary = result.get("summary", {})
    qs_list = summary.get("quarter_scores", [])
    if qs_list:
        print("Quarter-by-Quarter:")
        for qs in qs_list:
            end = qs['end_score']
            print(f"  {qs['quarter']}: Left +{qs['left_pts']}  "
                  f"Right +{qs['right_pts']}  "
                  f"(Running: {end[0]}-{end[1]})")

    runs = summary.get("scoring_runs", [])
    if runs:
        print(f"Scoring Runs (6+ unanswered):")
        for r in runs:
            print(f"  {r['team']} team: {r['points']} unanswered "
                  f"({r['start_time']} - {r['end_time']})")

    print(f"Play-by-Play (first 40 events):")
    for ev in result["events"][:40]:
        print(f"  [{ev['video_time']}] Q{ev['quarter']} {ev['game_clock']} - {ev['details']}")
    if len(result["events"]) > 40:
        print(f"  ... and {len(result['events'])-40} more events")
