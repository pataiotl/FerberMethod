import streamlit as st
import json
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd

st.set_page_config(
    page_title="Ferber Sleep Trainer",
    page_icon="🌙",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ── Ferber chart data from spreadsheet ─────────────────────────────────────
FERBER_CHART = {
    1: [3, 5, 10, 10],
    2: [5, 10, 12, 12],
    3: [10, 12, 15, 15],
    4: [12, 15, 20, 20],
    5: [15, 20, 25, 25],
    6: [17, 25, 30, 30],
    7: [20, 30, 35, 35],
}

CHECK_DURATION_SECONDS = 2 * 60
FIRST_FEED_WAIT_SECONDS = 5 * 60 * 60
NEXT_FEED_WAIT_SECONDS = 3 * 60 * 60
LOG_FILE = Path(__file__).with_name("sleep_log.json")
BANGKOK_TZ = ZoneInfo("Asia/Bangkok")


def now_bangkok():
    return datetime.now(BANGKOK_TZ)


def today_bangkok():
    return now_bangkok().date()


def load_logs():
    if not LOG_FILE.exists():
        return []
    try:
        data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def save_logs():
    LOG_FILE.write_text(
        json.dumps(st.session_state.logs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

# ── Custom CSS (iPhone-friendly) ────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .main { background: #0d0d1a; }
  .stApp { background: linear-gradient(135deg, #0d0d1a 0%, #1a1a2e 100%); color: #e8e8f0; }

  h1 { font-size: 1.7rem !important; text-align: center; }
  h2 { font-size: 1.2rem !important; }
  h3 { font-size: 1rem !important; }

  .card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 18px;
    margin: 10px 0;
  }
  .timer-display {
    font-size: 3.5rem;
    font-weight: 700;
    text-align: center;
    color: #a78bfa;
    letter-spacing: 2px;
    padding: 10px 0;
  }
  .interval-label {
    text-align: center;
    font-size: 0.85rem;
    color: #94a3b8;
    margin-bottom: 4px;
  }
  .next-interval {
    text-align: center;
    font-size: 0.9rem;
    color: #f0abfc;
    font-weight: 600;
  }
  .step-pill {
    display: inline-block;
    background: #7c3aed;
    color: white;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.8rem;
    font-weight: 600;
    margin: 2px 0;
  }
  .warn-box {
    background: rgba(251,191,36,0.15);
    border-left: 4px solid #fbbf24;
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
    font-size: 0.9rem;
  }
  .success-box {
    background: rgba(52,211,153,0.15);
    border-left: 4px solid #34d399;
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
    font-size: 0.9rem;
  }
  .stButton > button {
    width: 100%;
    border-radius: 12px;
    font-weight: 600;
    padding: 12px;
    font-size: 1rem;
    border: none;
  }
  div[data-testid="column"] .stButton > button {
    font-size: 0.9rem;
    padding: 10px 6px;
  }
  .stTabs [data-baseweb="tab"] {
    font-size: 0.85rem;
    padding: 8px 12px;
  }
  .stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.05);
    border-radius: 12px;
    padding: 4px;
  }
  .stDataFrame { border-radius: 12px; overflow: hidden; }
  [data-testid="stMetricValue"] { color: #a78bfa !important; font-size: 1.8rem !important; }
  [data-testid="stMetricLabel"] { color: #94a3b8 !important; }

  @media (max-width: 640px) {
    .block-container {
      padding-top: 1rem;
      padding-left: 0.8rem;
      padding-right: 0.8rem;
    }
    h1 { font-size: 1.45rem !important; }
    .card { padding: 14px; border-radius: 12px; }
    .timer-display {
      font-size: 3.2rem;
      letter-spacing: 1px;
    }
    .stButton > button {
      min-height: 48px;
      font-size: 1rem;
      margin-bottom: 4px;
    }
    .stTabs [data-baseweb="tab"] {
      font-size: 0.8rem;
      padding: 8px 8px;
    }
    [data-testid="stMetricValue"] { font-size: 1.45rem !important; }
  }
</style>
""", unsafe_allow_html=True)

# ── Session state initialisation ────────────────────────────────────────────
defaults = {
    "timer_running": False,
    "timer_start": None,
    "timer_mode": "wait",
    "elapsed_seconds": 0,
    "current_day": 1,
    "check_count": 0,          # how many checks done in this sleep session
    "bedtime_start": None,
    "crying_started_at": None,
    "session_start": None,     # legacy name, migrated to crying_started_at below
    "feeding_method_start": None,
    "feeding_records": [],
    "wake_count": 0,
    "logs": load_logs(),       # list of dicts {date, bedtime, sleep_min, wakeups, crying_min, notes}
    "session_crying_seconds": 0,
    "status_message": None,
    "confirm_delete_last": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state.session_start and not st.session_state.crying_started_at:
    st.session_state.crying_started_at = st.session_state.session_start

# ── Helper functions ─────────────────────────────────────────────────────────
def get_interval(day, check_index):
    day = min(max(day, 1), 7)
    intervals = FERBER_CHART[day]
    idx = min(check_index, 3)   # index 3 = 'subsequent'
    return intervals[idx]

def format_time(seconds):
    seconds = int(seconds)
    m, s = divmod(abs(seconds), 60)
    sign = "-" if seconds < 0 else ""
    return f"{sign}{m:02d}:{s:02d}"

def elapsed_now():
    if st.session_state.timer_running and st.session_state.timer_start:
        return st.session_state.elapsed_seconds + (time.time() - st.session_state.timer_start)
    return st.session_state.elapsed_seconds

def reset_sleep_session(reset_bedtime=False, reset_feeding=False):
    st.session_state.timer_running = False
    st.session_state.timer_start = None
    st.session_state.timer_mode = "wait"
    st.session_state.elapsed_seconds = 0
    st.session_state.check_count = 0
    st.session_state.crying_started_at = None
    st.session_state.session_start = None
    st.session_state.session_crying_seconds = 0
    st.session_state.wake_count = 0
    if reset_bedtime:
        st.session_state.bedtime_start = None
    if reset_feeding:
        st.session_state.feeding_method_start = None
        st.session_state.feeding_records = []

def add_log_entry(entry):
    st.session_state.logs.append(entry)
    save_logs()

def set_status(message):
    st.session_state.status_message = message

def start_method_clock(now):
    if st.session_state.bedtime_start is None:
        st.session_state.bedtime_start = now
    if st.session_state.crying_started_at is None:
        st.session_state.crying_started_at = now
        st.session_state.session_start = now
    if st.session_state.feeding_method_start is None:
        st.session_state.feeding_method_start = now

def begin_check_in():
    now = now_bangkok()
    start_method_clock(now)
    st.session_state.session_crying_seconds += elapsed_now()
    st.session_state.timer_mode = "check"
    st.session_state.elapsed_seconds = 0
    st.session_state.timer_running = True
    st.session_state.timer_start = time.time()

def finish_check_in():
    st.session_state.session_crying_seconds += min(elapsed_now(), CHECK_DURATION_SECONDS)
    st.session_state.check_count += 1
    st.session_state.timer_mode = "wait"
    st.session_state.elapsed_seconds = 0
    st.session_state.timer_running = True
    st.session_state.timer_start = time.time()

def format_duration(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def next_feed_due():
    method_start = st.session_state.feeding_method_start
    if method_start is None:
        return None, "1st feed"

    feed_count = len(st.session_state.feeding_records)
    if feed_count == 0:
        return method_start + timedelta(seconds=FIRST_FEED_WAIT_SECONDS), "1st feed"

    last_feed_iso = st.session_state.feeding_records[-1].get("iso_time")
    try:
        last_feed_time = datetime.fromisoformat(last_feed_iso)
    except (TypeError, ValueError):
        last_feed_time = now_bangkok()
    if last_feed_time.tzinfo is None:
        last_feed_time = last_feed_time.replace(tzinfo=BANGKOK_TZ)
    return last_feed_time + timedelta(seconds=NEXT_FEED_WAIT_SECONDS), f"Feed #{feed_count + 1}"

def feeding_summary():
    records = st.session_state.feeding_records
    total_oz = sum(float(feed.get("oz", 0) or 0) for feed in records)
    summary = ", ".join(f"{feed.get('time', '—')} ({float(feed.get('oz', 0) or 0):g} oz)" for feed in records)
    return len(records), total_oz, summary

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
st.markdown("# 🌙 Ferber Sleep Trainer")
st.markdown("<p style='text-align:center;color:#94a3b8;font-size:0.9rem;'>Gentle sleep training made simple</p>", unsafe_allow_html=True)

if st.session_state.status_message:
    st.success(st.session_state.status_message)
    st.session_state.status_message = None

tabs = st.tabs(["⏱ Timer", "📊 Schedule", "📓 Log", "💡 Guide"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 – TIMER
# ══════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    # Bedtime / night-start tracking
    st.markdown("### Bedtime")
    if st.session_state.bedtime_start:
        st.markdown(
            f"<div class='success-box'>🌙 Night started at <strong>{st.session_state.bedtime_start.strftime('%H:%M')}</strong> Bangkok time</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='card' style='color:#94a3b8;'>Set bedtime when baby goes into the crib. Start the timer when crying begins.</div>",
            unsafe_allow_html=True,
        )
    if st.button("Set Bedtime", type="secondary"):
        st.session_state.bedtime_start = now_bangkok()
        st.rerun()
    with st.expander("Reset night", expanded=False):
        st.warning("This clears the active timer, wake-ups, and feeding records for tonight.")
        if st.button("Reset Tonight", type="secondary"):
            reset_sleep_session(reset_bedtime=True, reset_feeding=True)
            st.rerun()

    # Day selector
    st.markdown("### Training Day")
    selected_day = st.selectbox(
        "Training day",
        options=list(range(1, 8)),
        index=st.session_state.current_day - 1,
        format_func=lambda day_num: f"Day {day_num}",
        label_visibility="collapsed",
    )
    if selected_day != st.session_state.current_day:
        st.session_state.current_day = selected_day
        reset_sleep_session(reset_bedtime=False)
        st.rerun()

    day = st.session_state.current_day
    check_idx = st.session_state.check_count
    timer_mode = st.session_state.timer_mode
    target_interval = get_interval(day, check_idx)
    target_seconds = CHECK_DURATION_SECONDS if timer_mode == "check" else target_interval * 60
    elapsed = elapsed_now()
    remaining = target_seconds - elapsed
    progress_pct = min(elapsed / target_seconds, 1.0) if target_seconds > 0 else 0

    if timer_mode == "check" and st.session_state.timer_running and remaining <= 0:
        finish_check_in()
        st.rerun()

    # Interval info
    interval_label = f"Check-in #{check_idx + 1}" if timer_mode == "check" else f"Day {day} — Check #{check_idx + 1}"
    interval_hint = "2 min max. Keep it brief, calm, and boring." if timer_mode == "check" else f"Wait {target_interval} min before checking"
    st.markdown(f"""
    <div class='card'>
      <div class='interval-label'>{interval_label}</div>
      <div class='timer-display'>{format_time(remaining)}</div>
      <div class='next-interval'>{interval_hint}</div>
    </div>
    """, unsafe_allow_html=True)

    # Progress bar
    st.progress(progress_pct)

    if timer_mode == "wait" and remaining <= 0 and elapsed > 0:
        st.markdown("<div class='warn-box'>🔔 <strong>Time to do a check!</strong> Enter briefly, speak softly, pat/shush. Do NOT pick up. Keep lights low. Leave within 1–2 minutes.</div>", unsafe_allow_html=True)

    # Control buttons
    if not st.session_state.timer_running:
        if st.button("▶ Start", type="primary"):
            st.session_state.timer_running = True
            st.session_state.timer_start = time.time()
            now = now_bangkok()
            start_method_clock(now)
            st.rerun()
    else:
        if st.button("⏸ Pause", type="primary"):
            st.session_state.elapsed_seconds = elapsed_now()
            st.session_state.timer_running = False
            st.session_state.timer_start = None
            st.rerun()

    check_button_label = "✅ Done with Check" if st.session_state.timer_mode == "check" else "✅ Start 2-Min Check"
    if st.button(check_button_label, type="secondary"):
        if st.session_state.timer_mode == "check":
            finish_check_in()
        else:
            begin_check_in()
        st.rerun()

    if st.button("🌙 Baby Asleep - Log Session", type="secondary"):
        now = now_bangkok()
        session_start = st.session_state.bedtime_start or st.session_state.crying_started_at
        sleep_min = 0
        if session_start:
            delta = now - session_start
            sleep_min = int(delta.total_seconds() / 60)
        st.session_state.session_crying_seconds += elapsed_now()
        crying_min = int(st.session_state.session_crying_seconds / 60)
        feed_count, total_feed_oz, feed_summary = feeding_summary()
        # Auto-log entry
        entry = {
            "date": today_bangkok().isoformat(),
            "bedtime": st.session_state.bedtime_start.strftime("%H:%M") if st.session_state.bedtime_start else "—",
            "crying_started": st.session_state.crying_started_at.strftime("%H:%M") if st.session_state.crying_started_at else "—",
            "asleep_time": now.strftime("%H:%M"),
            "sleep_min": sleep_min,
            "wakeups": st.session_state.wake_count,
            "crying_min": crying_min,
            "feeds": feed_count,
            "feed_oz_total": round(total_feed_oz, 2),
            "feed_details": feed_summary,
            "day": day,
            "notes": "",
        }
        add_log_entry(entry)
        reset_sleep_session(reset_bedtime=False)
        set_status(f"🎉 Baby asleep! Took {sleep_min} min. Logged automatically.")
        st.rerun()

    # Wake-up counter (night waking)
    st.markdown("---")
    st.markdown("### 🌜 Night Wake-ups")
    st.markdown("<p style='color:#94a3b8;font-size:0.85rem;'>For night wakings, log the wake-up, then use today's intervals.</p>", unsafe_allow_html=True)
    st.markdown(f"<div style='text-align:center;font-size:2rem;font-weight:700;color:#f0abfc;'>{st.session_state.wake_count}</div>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center;color:#94a3b8;font-size:0.8rem;'>wake-ups tonight</div>", unsafe_allow_html=True)
    if st.button("➕ Add Wake-up", key="wake_up"):
        st.session_state.wake_count += 1
        st.rerun()
    if st.session_state.wake_count > 0:
        if st.button("Undo Last Wake-up", key="wake_down"):
            st.session_state.wake_count = max(0, st.session_state.wake_count - 1)
            st.rerun()

    # 5-3-3 Night Feeding Guide
    st.markdown("---")
    feeding_countdown_active = False
    st.markdown("### 🍼 Night Feeding Timer (5-3-3 Rule)")
    if st.session_state.feeding_method_start:
        now = now_bangkok()
        due_time, feed_label = next_feed_due()
        remaining_feed_seconds = (due_time - now).total_seconds()
        feeding_countdown_active = remaining_feed_seconds > 0
        feed_count, total_feed_oz, feed_summary = feeding_summary()
        window_seconds = FIRST_FEED_WAIT_SECONDS if feed_count == 0 else NEXT_FEED_WAIT_SECONDS
        feed_progress = min(max(1 - (remaining_feed_seconds / window_seconds), 0), 1)

        st.markdown(
            f"<p style='color:#94a3b8;font-size:0.85rem;'>First feed timer started at <strong>{st.session_state.feeding_method_start.strftime('%H:%M')}</strong> Bangkok time when the method started.</p>",
            unsafe_allow_html=True,
        )

        if remaining_feed_seconds > 0:
            st.markdown(
                f"<div class='warn-box'>⛔ <strong>{feed_label} not yet.</strong> Opens in {format_duration(remaining_feed_seconds)}.</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div class='success-box'>✅ <strong>{feed_label} window open.</strong> Offer milk if baby woke up.</div>",
                unsafe_allow_html=True,
            )
        st.progress(feed_progress)

        feed_oz = st.number_input(
            "Volume this feed (oz)",
            min_value=0.0,
            max_value=16.0,
            value=4.0,
            step=0.25,
            format="%.2f",
            key="feed_oz",
        )
        if st.button("Log Feed", type="primary"):
            if feed_oz <= 0:
                st.error("Enter the amount in oz before logging.")
            else:
                feed_time = now_bangkok()
                st.session_state.feeding_records.append({
                    "iso_time": feed_time.isoformat(),
                    "time": feed_time.strftime("%H:%M"),
                    "oz": round(float(feed_oz), 2),
                })
                set_status(f"Logged {feed_oz:g} oz feed.")
                st.rerun()

        st.metric("Total Tonight", f"{total_feed_oz:g} oz", f"{feed_count} feed(s)")
        if feed_summary:
            st.markdown(f"<p style='color:#94a3b8;font-size:0.85rem;'>Feeds: {feed_summary}</p>", unsafe_allow_html=True)
        if st.session_state.feeding_records and st.button("Undo Last Feed"):
            st.session_state.feeding_records.pop()
            set_status("Last feed removed.")
            st.rerun()
    else:
        st.markdown("<p style='color:#94a3b8;font-size:0.85rem;'>Press ▶ Start when you begin the method. The first feeding timer will count 5 hours from that moment.</p>", unsafe_allow_html=True)

    # Auto-refresh while timer is running
    if st.session_state.timer_running or feeding_countdown_active:
        refresh_delay = 1 if st.session_state.timer_running or (feeding_countdown_active and remaining_feed_seconds <= 600) else 30
        time.sleep(refresh_delay)
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 – SCHEDULE
# ══════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.markdown("### 📊 Ferber Waiting Intervals (minutes)")
    chart_data = []
    for d, intervals in FERBER_CHART.items():
        chart_data.append({
            "Day": f"Day {d}",
            "1st Check": intervals[0],
            "2nd Check": intervals[1],
            "3rd Check": intervals[2],
            "Subsequent": intervals[3],
        })
    df = pd.DataFrame(chart_data).set_index("Day")
    st.dataframe(df, use_container_width=True)

    st.markdown("---")
    st.markdown("### 📅 Today's Intervals")
    day = st.session_state.current_day
    intervals = FERBER_CHART[min(max(day, 1), 7)]
    labels = ["1st Check", "2nd Check", "3rd Check", "Subsequent"]
    cols = st.columns(4)
    for i, (col, label, val) in enumerate(zip(cols, labels, intervals)):
        col.metric(label, f"{val} min")

    # Visual bar chart using st.bar_chart
    st.markdown("---")
    st.markdown("### Interval Progression Across Days")
    bar_df = pd.DataFrame({
        "Day": [f"D{d}" for d in range(1, 8)],
        "1st Check": [FERBER_CHART[d][0] for d in range(1, 8)],
        "2nd Check": [FERBER_CHART[d][1] for d in range(1, 8)],
        "3rd Check": [FERBER_CHART[d][2] for d in range(1, 8)],
    }).set_index("Day")
    st.bar_chart(bar_df)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 – LOG
# ══════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.markdown("### 📓 Sleep Log")

    # Manual entry form
    with st.expander("➕ Add Manual Entry", expanded=False):
        log_date = st.date_input("Date", value=today_bangkok(), key="log_date")
        log_bedtime = st.text_input("Bedtime (HH:MM)", value="20:00", key="log_bedtime")
        log_crying_started = st.text_input("Crying started (HH:MM)", value="", key="log_crying_started")
        log_asleep_time = st.text_input("Asleep time (HH:MM)", value="", key="log_asleep_time")
        log_sleep = st.number_input("Minutes to fall asleep", min_value=0, max_value=180, value=20, key="log_sleep")
        log_wakeups = st.number_input("Night wake-ups", min_value=0, max_value=20, value=0, key="log_wakeups")
        log_crying = st.number_input("Total crying (min)", min_value=0, max_value=300, value=0, key="log_crying")
        log_feeds = st.number_input("Feeds", min_value=0, max_value=10, value=0, key="log_feeds")
        log_feed_oz_total = st.number_input("Total feeding volume (oz)", min_value=0.0, max_value=80.0, value=0.0, step=0.25, format="%.2f", key="log_feed_oz_total")
        log_feed_details = st.text_input("Feed details", placeholder="01:10 (4 oz), 04:30 (3 oz)", key="log_feed_details")
        log_day = st.slider("Training day", 1, 7, st.session_state.current_day, key="log_day_slider")
        log_flags = st.multiselect(
            "Context",
            ["Illness", "Teething", "Travel", "Nap disruption", "Schedule change", "Growth spurt"],
            key="log_flags",
        )
        log_notes = st.text_area("Notes", placeholder="Teething, illness, travel…", key="log_notes")

        if st.button("Save Entry", type="primary"):
            entry = {
                "date": log_date.isoformat(),
                "bedtime": log_bedtime,
                "crying_started": log_crying_started or "—",
                "asleep_time": log_asleep_time or "—",
                "sleep_min": log_sleep,
                "wakeups": log_wakeups,
                "crying_min": log_crying,
                "feeds": log_feeds,
                "feed_oz_total": round(float(log_feed_oz_total), 2),
                "feed_details": log_feed_details,
                "day": log_day,
                "flags": ", ".join(log_flags),
                "notes": log_notes,
            }
            add_log_entry(entry)
            st.session_state.confirm_delete_last = False
            set_status("Entry saved.")
            st.rerun()

    with st.expander("↕ Backup / Restore", expanded=False):
        backup_file = st.file_uploader("Restore from JSON backup", type=["json"])
        if backup_file is not None:
            if st.button("Replace Log with Backup", type="primary"):
                try:
                    restored_logs = json.loads(backup_file.getvalue().decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    st.error("That backup file could not be read.")
                else:
                    if isinstance(restored_logs, list) and all(isinstance(item, dict) for item in restored_logs):
                        st.session_state.logs = restored_logs
                        save_logs()
                        st.session_state.confirm_delete_last = False
                        set_status("Backup restored.")
                        st.rerun()
                    else:
                        st.error("That backup file does not look like a Ferber sleep log.")

    if not st.session_state.logs:
        st.markdown("<div class='card' style='text-align:center;color:#94a3b8;'>No entries yet. Complete a session or add a manual entry.</div>", unsafe_allow_html=True)
    else:
        logs = st.session_state.logs
        df_log = pd.DataFrame(logs)
        for numeric_col in ["sleep_min", "wakeups", "crying_min", "feeds", "feed_oz_total"]:
            if numeric_col not in df_log:
                df_log[numeric_col] = 0
            df_log[numeric_col] = pd.to_numeric(df_log[numeric_col], errors="coerce").fillna(0)
        if "date" not in df_log:
            df_log["date"] = ""

        # Summary metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Avg. Sleep Time", f"{df_log['sleep_min'].mean():.0f} min")
        m2.metric("Avg. Wake-ups", f"{df_log['wakeups'].mean():.1f}")
        m3.metric("Avg. Crying", f"{df_log['crying_min'].mean():.0f} min")
        m4.metric("Avg. Feeding", f"{df_log['feed_oz_total'].mean():.1f} oz")

        export_cols = st.columns(2)
        with export_cols[0]:
            st.download_button(
                "⬇ Export CSV",
                data=df_log.to_csv(index=False).encode("utf-8"),
                file_name="ferber_sleep_log.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with export_cols[1]:
            st.download_button(
                "⬇ Backup JSON",
                data=json.dumps(st.session_state.logs, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name="ferber_sleep_log.json",
                mime="application/json",
                use_container_width=True,
            )

        # Trend chart
        if len(df_log) > 1:
            st.markdown("#### Sleep Time Trend")
            trend = df_log[["date", "sleep_min", "crying_min"]].set_index("date")
            st.line_chart(trend)

        display_columns = ["date", "bedtime", "crying_started", "asleep_time", "sleep_min", "wakeups", "crying_min", "feeds", "feed_oz_total", "feed_details", "day", "flags", "notes"]
        display_df = df_log.reindex(columns=display_columns).fillna("").copy()

        st.markdown("#### Recent Nights")
        recent_entries = display_df.tail(5).iloc[::-1]
        for _, row in recent_entries.iterrows():
            feed_text = f"{row['feed_oz_total']:g} oz" if row["feed_oz_total"] else "No feeds"
            context_text = f"<br><span style='color:#94a3b8;'>Context: {row['flags']}</span>" if row["flags"] else ""
            notes_text = f"<br><span style='color:#94a3b8;'>Notes: {row['notes']}</span>" if row["notes"] else ""
            st.markdown(
                f"""
                <div class='card'>
                  <strong>{row['date']} · Day {int(row['day']) if row['day'] else '—'}</strong><br>
                  Sleep: <strong>{row['sleep_min']:.0f} min</strong> · Crying: <strong>{row['crying_min']:.0f} min</strong><br>
                  Wake-ups: <strong>{row['wakeups']:.0f}</strong> · Feeding: <strong>{feed_text}</strong><br>
                  Bedtime {row['bedtime']} · Asleep {row['asleep_time']}
                  {context_text}{notes_text}
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Table
        with st.expander("Detailed table", expanded=False):
            st.markdown("#### All Entries")
            table_df = display_df.copy()
            table_df.columns = ["Date", "Bedtime", "Crying Started", "Asleep", "Sleep (min)", "Wake-ups", "Crying (min)", "Feeds", "Oz Total", "Feed Details", "Day", "Context", "Notes"]
            st.dataframe(table_df, use_container_width=True)

        # Delete last entry
        if not st.session_state.confirm_delete_last:
            if st.button("🗑 Delete Last Entry"):
                st.session_state.confirm_delete_last = True
                st.rerun()
        else:
            st.warning("Delete the most recent log entry?")
            del_cols = st.columns(2)
            with del_cols[0]:
                if st.button("Yes, delete", type="primary"):
                    st.session_state.logs.pop()
                    save_logs()
                    st.session_state.confirm_delete_last = False
                    set_status("Last entry deleted.")
                    st.rerun()
            with del_cols[1]:
                if st.button("Cancel"):
                    st.session_state.confirm_delete_last = False
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 – GUIDE
# ══════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.markdown("### 💡 How to Use This App")
    st.markdown("""
    <div class='card'>
    <span class='step-pill'>Step 1</span><br>
    <strong>Put Down Drowsy but Awake</strong><br>
    Place baby in crib while still awake, tap Set Bedtime, say goodnight, and leave immediately. Times are saved in Bangkok time.
    </div>

    <div class='card'>
    <span class='step-pill'>Step 2</span><br>
    <strong>Start the Timer</strong><br>
    Tap ▶ Start when protest crying begins. The app keeps bedtime separate from crying time so the log and feeding window stay accurate.
    </div>

    <div class='card'>
    <span class='step-pill'>Step 3</span><br>
    <strong>The Check</strong><br>
    When the timer hits 00:00, tap ✅ Checked as you enter. The app starts a 2-minute check timer. Speak softly, pat or shush. Do NOT pick up. Keep lights low. Leave when it ends, or tap ✅ Done if you leave early.
    </div>

    <div class='card'>
    <span class='step-pill'>Step 4</span><br>
    <strong>Repeat</strong><br>
    The timer resets to the next interval. Continue until baby falls asleep. Tap 🌙 Asleep! to log the session.
    </div>

    <div class='card'>
    <span class='step-pill'>Night Wakings</span><br>
    For night wakings, tap ➕ to count them and restart the timer using the same day's intervals.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🍼 The 5-3-3 Night Feeding Rule")
    st.markdown("""
    <div class='card'>
    <b>First 5 hours after starting the method</b> → No feeding. Focus on self-soothing.<br><br>
    <b>After a feed</b> → The next feeding timer counts 3 hours from that feed.<br><br>
    <b>Volume</b> → Log each feed in ounces so the night total is saved with the sleep log.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### ⚠️ Important Reminders")
    st.markdown("""
    <div class='warn-box'>
    • Ferber method is generally recommended for babies <strong>5–6 months+</strong>.<br>
    • Always consult your paediatrician before starting sleep training.<br>
    • If your baby is unwell, skip training that night.<br>
    • Be consistent — avoid skipping nights during the 7-day period.<br>
    • This app is a helper only and is not medical advice.
    </div>
    """, unsafe_allow_html=True)
