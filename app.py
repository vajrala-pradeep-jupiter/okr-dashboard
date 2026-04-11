#!/usr/bin/env python3
"""OKR Tracking Dashboard — DSAT & FCR across Federal and CSB instances."""
from __future__ import annotations

import json
import os
import io
import base64
import calendar as cal
import urllib.request
import urllib.error
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta, date

# ════════════════════════════════════════════════════════════════════════
#  EDIT THESE — all hardcoded numbers live here
# ════════════════════════════════════════════════════════════════════════

import os as _os
try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except Exception:
    ADMIN_PASSWORD = _os.environ.get("ADMIN_PASSWORD", "okr2024")

BASELINES = {
    "DSAT": {"Federal": 18.05, "CSB": 11.07},
    "FCR":  {"Federal": 65.10, "CSB": 79.20},
}
LAST_QUARTER_PERF = {
    "DSAT": {"Federal": 22.42, "CSB": 9.88},
    "FCR":  {"Federal": 66.10, "CSB": 80.40},
}
DEFAULT_GOALS = {
    "DSAT": {"Federal": round(18.05 * 0.85, 2), "CSB": round(11.07 * 0.85, 2)},
    "FCR":  {"Federal": 80.00, "CSB": 80.00},
}

# GitHub repo used for persistent shared data storage
GITHUB_OWNER = "vajrala-pradeep-jupiter"
GITHUB_REPO  = "okr-dashboard"

# ════════════════════════════════════════════════════════════════════════

CURRENT_QUARTER = f"Q{((date.today().month - 1) // 3) + 1} {date.today().year}"
SETTINGS_FILE   = os.path.join(os.path.dirname(__file__), "settings.json")


def _load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "goals":     {m: dict(v) for m, v in DEFAULT_GOALS.items()},
        "baselines": {m: dict(v) for m, v in BASELINES.items()},
        "last_qtr":  {m: dict(v) for m, v in LAST_QUARTER_PERF.items()},
    }


def _save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump({
            "goals":     st.session_state.goals,
            "baselines": st.session_state.baselines,
            "last_qtr":  st.session_state.last_qtr,
        }, f, indent=2)


# ─────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="OKR Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
html, body, [class*="css"] { font-family: "Inter", "Segoe UI", sans-serif; }
[data-testid="stAppViewContainer"] { background: #f1f5f9; }

[data-testid="stSidebar"] > div:first-child {
    background: #1e293b; padding: 1.2rem 1rem;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span:not(.sb-badge-admin) { color: #cbd5e1 !important; }
[data-testid="stSidebar"] input  { color: #0f172a !important; background: #fff !important; }
[data-testid="stSidebar"] hr     { border-color: #334155 !important; }
[data-testid="stSidebar"] div[data-testid="stExpander"] {
    border: 1px solid #334155 !important; border-radius: 8px !important; background: #0f172a;
}
[data-testid="stSidebar"] div[data-testid="stExpander"] summary { background: #1e293b; }
[data-testid="stSidebar"] div[data-testid="stExpander"] summary p {
    color: #f1f5f9 !important; font-weight: 600 !important; font-size: 0.85rem !important;
}

.stTabs [data-baseweb="tab-list"] { gap:0; border-bottom:2px solid #cbd5e1; background:transparent; }
.stTabs [data-baseweb="tab"] {
    font-size:0.92rem !important; font-weight:600 !important;
    color:#475569 !important; padding:10px 24px !important;
    border-radius:8px 8px 0 0; background:transparent;
}
.stTabs [aria-selected="true"] {
    color:#1d4ed8 !important; border-bottom:3px solid #1d4ed8 !important; background:#eff6ff !important;
}

div[data-testid="stExpander"] { border:1px solid #e2e8f0 !important; border-radius:10px !important; background:#fff; }
div[data-testid="stExpander"] summary p { font-weight:600 !important; font-size:0.85rem !important; color:#1e293b !important; }

hr { border:none; border-top:1px solid #e2e8f0 !important; margin:4px 0 18px 0 !important; }

.sb-section-label {
    font-size:0.64rem; font-weight:800; text-transform:uppercase;
    letter-spacing:0.1em; color:#64748b; padding:10px 0 4px 0; display:block;
}
.sb-badge-admin {
    display:inline-block; background:#dcfce7; color:#14532d;
    font-size:0.72rem; font-weight:700; padding:2px 10px; border-radius:99px; margin-bottom:10px;
}
.section-header-wrap {
    display:flex; align-items:center; gap:12px;
    margin:4px 0 20px 0; padding-bottom:14px; border-bottom:1px solid #e2e8f0;
}
.section-color-bar { width:4px; height:30px; border-radius:3px; flex-shrink:0; }
.section-header-title { font-size:1.1rem; font-weight:800; color:#0f172a; }
.section-header-sub   { font-size:0.78rem; color:#475569; font-weight:500; margin-top:2px; }
.no-data-box {
    background:#f8fafc; border:1.5px dashed #cbd5e1; border-radius:10px;
    padding:32px 20px; text-align:center; color:#475569; font-size:0.85rem;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────
def _init_state():
    if "goals" not in st.session_state:
        saved = _load_settings()
        st.session_state.goals     = saved["goals"]
        st.session_state.baselines = saved["baselines"]
        st.session_state.last_qtr  = saved["last_qtr"]
    if "admin_unlocked" not in st.session_state:
        st.session_state.admin_unlocked = False


_init_state()


# ─────────────────────────────────────────────────────────────────────
# GITHUB PERSISTENT STORAGE
# Admin uploads a file → committed to GitHub repo → all users read it.
# ─────────────────────────────────────────────────────────────────────
def _gh_token() -> str:
    try:
        return st.secrets["GITHUB_TOKEN"]
    except Exception:
        return _os.environ.get("GITHUB_TOKEN", "")


def _gh_read(path: str) -> tuple[bytes | None, str | None]:
    """Fetch file from GitHub repo. Returns (content_bytes, sha) or (None, None)."""
    token = _gh_token()
    if not token:
        return None, None
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "okr-dashboard",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            return base64.b64decode(data["content"].replace("\n", "")), data["sha"]
    except Exception:
        return None, None


def _gh_write(path: str, content_bytes: bytes, sha: str | None = None) -> bool:
    """Commit file to GitHub repo. Returns True on success."""
    token = _gh_token()
    if not token:
        st.error("GITHUB_TOKEN not configured in Streamlit secrets.")
        return False
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
    body: dict = {
        "message": f"dashboard: update {path.split('/')[-1]}",
        "content": base64.b64encode(content_bytes).decode(),
    }
    if sha:
        body["sha"] = sha
    payload = json.dumps(body).encode()
    req = urllib.request.Request(url, data=payload, method="PUT", headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "okr-dashboard",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status in (200, 201)
    except urllib.error.HTTPError as e:
        st.error(f"GitHub write failed ({e.code}): {e.read().decode()}")
        return False
    except Exception as e:
        st.error(f"GitHub write failed: {e}")
        return False


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_gh_data(path: str) -> bytes | None:
    """Cached fetch of data file from GitHub. Refreshes every 5 minutes."""
    content, _ = _gh_read(path)
    return content


def _bytes_to_df(content: bytes, filename: str) -> pd.DataFrame | None:
    """Parse bytes into a DataFrame.
    Tries Excel first (handles xlsx/xls regardless of filename),
    then falls back to CSV with multiple encodings.
    """
    if not content or len(content) < 4:
        st.error(f"{filename} is empty.")
        return None

    attempts: list[str] = []

    # Always try Excel first — pd.read_excel raises if it's not Excel
    try:
        df = pd.read_excel(io.BytesIO(content))
        if len(df.columns) > 0:
            return df
    except Exception as e:
        attempts.append(f"Excel: {e}")

    # Try CSV with common encodings
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"):
        try:
            df = pd.read_csv(io.BytesIO(content), encoding=enc)
            if len(df.columns) > 0:
                return df
        except Exception as e:
            attempts.append(f"CSV({enc}): {e}")

    st.error(f"Could not parse **{filename}**. Is it a valid CSV or Excel file? "
             f"Details: {' | '.join(attempts)}")
    return None


# ─────────────────────────────────────────────────────────────────────
# INSTANCE FILTERS
# ─────────────────────────────────────────────────────────────────────
def _clean_str_col(series: pd.Series) -> pd.Series:
    return (series.astype(str)
            .str.replace(r'\s+', ' ', regex=True)
            .str.strip()
            .str.upper())


def _filter_dsat(df: pd.DataFrame, instance: str) -> pd.DataFrame:
    inst_up = instance.upper()
    if "combined_key" in df.columns:
        parsed = _clean_str_col(df["combined_key"]).str.rsplit(" - ", n=1).str[-1].str.strip()
        f = df[parsed == inst_up]
        if not f.empty:
            return f
    if "instance" in df.columns:
        f = df[_clean_str_col(df["instance"]) == inst_up]
        if not f.empty:
            return f
    _warn_no_instance(df, instance, "DSAT", ["combined_key", "instance"])
    return pd.DataFrame()


def _filter_fcr(df: pd.DataFrame, instance: str) -> pd.DataFrame:
    inst_up = instance.upper()
    if "fd_instance" in df.columns:
        f = df[_clean_str_col(df["fd_instance"]) == inst_up]
        if not f.empty:
            return f
    if "instance" in df.columns:
        f = df[_clean_str_col(df["instance"]) == inst_up]
        if not f.empty:
            return f
    _warn_no_instance(df, instance, "FCR", ["fd_instance", "instance"])
    return pd.DataFrame()


def _warn_no_instance(df, instance, label, tried_cols):
    hints = []
    for col in tried_cols:
        if col in df.columns:
            uniq = df[col].astype(str).str.strip().unique()[:8].tolist()
            hints.append(f"`{col}` unique values: **{uniq}**")
    hint_text = " · ".join(hints) if hints else "No relevant columns found."
    st.warning(
        f"⚠️ No **{instance}** rows in **{label}** dataset. "
        f"Tried: {', '.join(f'`{c}`' for c in tried_cols)}. {hint_text}"
    )


# ─────────────────────────────────────────────────────────────────────
# DATE HELPERS
# ─────────────────────────────────────────────────────────────────────
def _date_ranges():
    today      = date.today()
    yesterday  = today - timedelta(days=1)
    curr_start = today.replace(day=1)
    prev_end   = curr_start - timedelta(days=1)
    prev_start = prev_end.replace(day=1)

    curr_q = (today.month - 1) // 3
    pq_end_m = curr_q * 3
    if pq_end_m == 0:
        pq_end_m = 12; pq_year = today.year - 1
    else:
        pq_year = today.year
    pq_end   = date(pq_year, pq_end_m, cal.monthrange(pq_year, pq_end_m)[1])
    pq_start = date(pq_year, max(1, pq_end_m - 2), 1)

    return {
        "today":      today,
        "yesterday":  yesterday,
        "curr_start": curr_start,
        "prev_start": prev_start,
        "prev_end":   prev_end,
        "pq_start":   pq_start,
        "pq_end":     pq_end,
    }


# ─────────────────────────────────────────────────────────────────────
# CORE METRIC ENGINE
# ─────────────────────────────────────────────────────────────────────
def _compute(df_inst: pd.DataFrame, date_col: str, flag_col: str, flag_val: str) -> dict | None:
    if df_inst is None or df_inst.empty:
        return None

    dr = _date_ranges()
    df = df_inst.copy()

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    if df.empty:
        return None

    df["_date"] = df[date_col].dt.date
    df["_flag"] = df[flag_col].astype(str).str.strip().str.upper() == flag_val.upper()

    def _pct(mask):
        sub = df[mask]
        return (sub["_flag"].sum() / len(sub) * 100) if len(sub) > 0 else None

    def _daily(mask):
        sub = df[mask]
        if sub.empty:
            return None
        d = (sub.groupby("_date")
             .agg(total=("_flag", "count"), hits=("_flag", "sum"))
             .reset_index())
        d["pct"] = d["hits"] / d["total"] * 100
        d["day"] = d["_date"].apply(lambda x: x.day)
        return d.sort_values("day")

    curr_mask = df["_date"] >= dr["curr_start"]
    prev_mask = (df["_date"] >= dr["prev_start"]) & (df["_date"] <= dr["prev_end"])
    pq_mask   = (df["_date"] >= dr["pq_start"])   & (df["_date"] <= dr["pq_end"])
    yest_mask = df["_date"] == dr["yesterday"]

    yest_sub      = df[yest_mask]
    yesterday_val = (yest_sub["_flag"].sum() / len(yest_sub) * 100) if len(yest_sub) > 0 else None
    yesterday_vol = len(yest_sub) if len(yest_sub) > 0 else None

    return {
        "mtd_pct":       _pct(curr_mask),
        "yesterday_val": yesterday_val,
        "yesterday_vol": yesterday_vol,
        "daily_curr":    _daily(curr_mask),
        "daily_prev":    _daily(prev_mask),
        "prev_qtr_pct":  _pct(pq_mask),
    }


def calc_dsat(df: pd.DataFrame, instance: str) -> dict | None:
    if df is None or df.empty:
        return None
    inst_df = _filter_dsat(df, instance)
    if inst_df.empty:
        return None
    if "feedback_created_at" not in inst_df.columns or "feedback_rating" not in inst_df.columns:
        st.warning("DSAT dataset missing `feedback_created_at` or `feedback_rating`.")
        return None
    inst_df = inst_df.copy()
    inst_df["_dsat_flag"] = inst_df["feedback_rating"].astype(float).apply(
        lambda v: "DSAT" if v == 1 else "OK"
    )
    return _compute(inst_df, "feedback_created_at", "_dsat_flag", "DSAT")


def calc_fcr(df: pd.DataFrame, instance: str) -> dict | None:
    if df is None or df.empty:
        return None
    inst_df = _filter_fcr(df, instance)
    if inst_df.empty:
        return None
    date_col = next((c for c in ["ticket_created_at", "created_date"] if c in inst_df.columns), None)
    fcr_col  = next((c for c in ["fcr_flag", "FCR/Non-FCR"] if c in inst_df.columns), None)
    if not date_col:
        st.warning("FCR dataset missing date column (`ticket_created_at` or `created_date`).")
        return None
    if not fcr_col:
        st.warning("FCR dataset missing flag column (`fcr_flag` or `FCR/Non-FCR`).")
        return None
    return _compute(inst_df, date_col, fcr_col, "FCR")


def calc_dsat_all(df: pd.DataFrame) -> dict | None:
    if df is None or df.empty:
        return None
    if "feedback_created_at" not in df.columns or "feedback_rating" not in df.columns:
        return None
    tmp = df.copy()
    tmp["_dsat_flag"] = tmp["feedback_rating"].astype(float).apply(
        lambda v: "DSAT" if v == 1 else "OK"
    )
    return _compute(tmp, "feedback_created_at", "_dsat_flag", "DSAT")


def calc_fcr_all(df: pd.DataFrame) -> dict | None:
    if df is None or df.empty:
        return None
    date_col = next((c for c in ["ticket_created_at", "created_date"] if c in df.columns), None)
    fcr_col  = next((c for c in ["fcr_flag", "FCR/Non-FCR"] if c in df.columns), None)
    if not date_col or not fcr_col:
        return None
    return _compute(df, date_col, fcr_col, "FCR")


# ─────────────────────────────────────────────────────────────────────
# MOCK DATA
# ─────────────────────────────────────────────────────────────────────
def _mock_dsat(instance: str, seed: int) -> pd.DataFrame:
    rng   = np.random.default_rng(seed)
    today = date.today()
    start = (today.replace(day=1) - timedelta(days=92)).replace(day=1)
    base  = st.session_state.baselines["DSAT"][instance] / 100
    rows  = []
    d = start
    while d <= today:
        days_in = (d - start).days
        trend = max(0.0, base - days_in * 0.0003)
        for _ in range(int(rng.integers(60, 180))):
            is_dsat = rng.random() < max(0.0, trend + rng.normal(0, 0.012))
            tid = int(rng.integers(100_000, 999_999))
            rows.append({
                "feedback_created_at": pd.Timestamp(d),
                "fd_ticket_id":        tid,
                "feedback_rating":     int(1 if is_dsat else rng.choice([2, 3, 4, 5], p=[0.05, 0.15, 0.4, 0.4])),
                "combined_key":        f"{tid} - {instance.upper()}",
                "queue_name":          f"{instance} Support",
            })
        d += timedelta(days=1)
    return pd.DataFrame(rows)


def _mock_fcr(instance: str, seed: int) -> pd.DataFrame:
    rng   = np.random.default_rng(seed)
    today = date.today()
    start = (today.replace(day=1) - timedelta(days=92)).replace(day=1)
    base  = st.session_state.baselines["FCR"][instance] / 100
    rows  = []
    d = start
    while d <= today:
        days_in = (d - start).days
        trend = min(1.0, base + days_in * 0.0003)
        for _ in range(int(rng.integers(60, 180))):
            is_fcr = rng.random() < max(0.0, min(1.0, trend + rng.normal(0, 0.018)))
            tid = int(rng.integers(100_000, 999_999))
            rows.append({
                "ticket_created_at": pd.Timestamp(d),
                "fd_ticket_id":      tid,
                "fd_instance":       instance.upper(),
                "fcr_flag":          "FCR" if is_fcr else "Non FCR",
            })
        d += timedelta(days=1)
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────────────────
INSTANCE_COLORS = {"Federal": "#2563eb", "CSB": "#7c3aed"}


def _card(label: str, value: str, delta: str = "",
          delta_color: str = "#334155", top_color: str = "#cbd5e1") -> str:
    delta_html = (
        f'<div style="font-size:0.78rem;font-weight:700;color:{delta_color};margin-top:6px">{delta}</div>'
        if delta else ""
    )
    return (
        f'<div style="background:#ffffff;border:1px solid #e2e8f0;border-top:3px solid {top_color};'
        f'border-radius:12px;padding:16px 18px 14px;box-shadow:0 2px 8px rgba(0,0,0,0.06);min-height:102px">'
        f'<div style="font-size:0.67rem;font-weight:800;text-transform:uppercase;'
        f'letter-spacing:0.09em;color:#475569;margin-bottom:8px">{label}</div>'
        f'<div style="font-size:1.5rem;font-weight:800;color:#0f172a;line-height:1.1">{value}</div>'
        f'{delta_html}</div>'
    )


def _section_header(instance: str, metric: str):
    color = INSTANCE_COLORS.get(instance, "#2563eb")
    sub = ("Lower is better &nbsp;·&nbsp; feedback_rating = 1"
           if metric == "DSAT" else
           "Higher is better &nbsp;·&nbsp; fcr_flag = 'FCR'")
    st.markdown(
        f'<div class="section-header-wrap">'
        f'<div class="section-color-bar" style="background:{color}"></div>'
        f'<div><div class="section-header-title">{instance}</div>'
        f'<div class="section-header-sub">{sub}</div></div></div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────
# SHARED CHART LAYOUT BASE
# ─────────────────────────────────────────────────────────────────────
_BASE_LAYOUT = dict(
    hovermode="x unified",
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
    margin=dict(l=8, r=110, t=50, b=40),
    xaxis=dict(
        title="Day of month",
        range=[0.5, 31.5],
        dtick=5,
        tickfont=dict(size=10, color="#94a3b8"),
        gridcolor="#f3f4f6",
        showline=True, linecolor="#e5e7eb",
        zeroline=False,
    ),
    yaxis=dict(
        ticksuffix="%",
        gridcolor="#f3f4f6",
        tickfont=dict(size=10, color="#94a3b8"),
        zeroline=False,
        showline=False,
    ),
    legend=dict(
        orientation="h", x=0, y=1.16,
        font=dict(size=11, color="#374151"),
        bgcolor="rgba(0,0,0,0)",
        itemsizing="constant",
        traceorder="normal",
    ),
)


# ─────────────────────────────────────────────────────────────────────
# CHART A — Single metric, single instance (DSAT/FCR tabs)
# Two lines only: this month (bold) + last month (faint gray)
# Goal line clearly labeled. Green/red zone shading. Value annotation.
# ─────────────────────────────────────────────────────────────────────
def trajectory_chart(
    m: dict, goal: float,
    metric: str, instance: str, lower_is_better: bool,
) -> go.Figure:
    fig = go.Figure()
    today_day = date.today().day
    color = INSTANCE_COLORS.get(instance, "#2563eb")

    # Subtle shading for "target zone"
    if lower_is_better:
        fig.add_hrect(y0=0, y1=goal, fillcolor="rgba(22,163,74,0.05)", line_width=0)
    else:
        fig.add_hrect(y0=goal, y1=200, fillcolor="rgba(22,163,74,0.05)", line_width=0)

    # Last month — very faint, no markers, just context
    if m.get("daily_prev") is not None and not m["daily_prev"].empty:
        dp = m["daily_prev"]
        fig.add_trace(go.Scatter(
            x=dp["day"], y=dp["pct"],
            mode="lines",
            name="Last month",
            line=dict(color="#d1d5db", width=1.5),
            hovertemplate="Day %{x} (last month): %{y:.1f}%<extra></extra>",
        ))

    # This month — bold, colored markers (green = on track, red = off)
    if m.get("daily_curr") is not None and not m["daily_curr"].empty:
        dc = m["daily_curr"]
        mk_colors = [
            "#16a34a" if (v <= goal if lower_is_better else v >= goal) else "#ef4444"
            for v in dc["pct"]
        ]
        fig.add_trace(go.Scatter(
            x=dc["day"], y=dc["pct"],
            mode="lines+markers",
            name="This month",
            line=dict(color=color, width=2.5),
            marker=dict(size=7, color=mk_colors, line=dict(width=1.5, color="#fff")),
            hovertemplate="<b>Day %{x}</b>: %{y:.1f}%<extra></extra>",
        ))
        # Annotate the latest value directly on the chart — no need to hunt in legend
        last_day = int(dc["day"].iloc[-1])
        last_val = float(dc["pct"].iloc[-1])
        on_track = (last_val <= goal) if lower_is_better else (last_val >= goal)
        fig.add_annotation(
            x=last_day, y=last_val,
            text=f"<b>{last_val:.1f}%</b>",
            showarrow=False,
            xanchor="left", xshift=10,
            font=dict(size=13, color="#15803d" if on_track else "#dc2626"),
        )

    # Goal — single clean dashed line, labeled directly
    ann_pos = "top right" if lower_is_better else "bottom right"
    fig.add_hline(
        y=goal,
        line_dash="dash", line_color="#16a34a", line_width=1.5,
        annotation_text=f"Goal: {goal:.1f}%",
        annotation_position=ann_pos,
        annotation_font=dict(size=10, color="#15803d"),
        annotation_bgcolor="rgba(255,255,255,0.85)",
        annotation_borderpad=4,
    )

    # Today marker — subtle vertical line
    fig.add_vline(
        x=today_day, line_dash="solid", line_color="#e5e7eb", line_width=1,
        annotation_text="Today",
        annotation_position="top",
        annotation_font=dict(size=9, color="#9ca3af"),
    )

    direction = "↓ lower is better" if lower_is_better else "↑ higher is better"
    layout = dict(_BASE_LAYOUT)
    layout["height"] = 260
    layout["title"] = dict(
        text=(f"<b>{instance} — {metric}</b>"
              f"<span style='color:#9ca3af;font-size:11px'>  {direction}</span>"),
        font=dict(size=13, color="#111827"), x=0,
    )
    fig.update_layout(**layout)
    return fig


# ─────────────────────────────────────────────────────────────────────
# CHART B — Federal vs CSB for one metric (Overall tab)
# Clean side-by-side comparison. No dual axis. Each instance is a line.
# ─────────────────────────────────────────────────────────────────────
def comparison_chart(
    metric: str,
    fed_m: dict | None,
    csb_m: dict | None,
    fed_goal: float,
    csb_goal: float,
    lower_is_better: bool,
    title: str,
) -> go.Figure:
    fig = go.Figure()
    today_day = date.today().day

    FED_COLOR = "#2563eb"   # blue   — Federal
    CSB_COLOR = "#9333ea"   # purple — CSB

    # Federal line
    if fed_m and fed_m.get("daily_curr") is not None:
        dc = fed_m["daily_curr"]
        fig.add_trace(go.Scatter(
            x=dc["day"], y=dc["pct"],
            mode="lines+markers",
            name="Federal",
            line=dict(color=FED_COLOR, width=2.5),
            marker=dict(size=5, color=FED_COLOR, line=dict(width=1, color="#fff")),
            hovertemplate="<b>Federal · Day %{x}</b>: %{y:.1f}%<extra></extra>",
        ))
        last_day = int(dc["day"].iloc[-1])
        last_val = float(dc["pct"].iloc[-1])
        fig.add_annotation(
            x=last_day, y=last_val,
            text=f"<b>{last_val:.1f}%</b>",
            showarrow=False, xanchor="left", xshift=10,
            font=dict(size=11, color=FED_COLOR),
        )

    # CSB line
    if csb_m and csb_m.get("daily_curr") is not None:
        dc = csb_m["daily_curr"]
        fig.add_trace(go.Scatter(
            x=dc["day"], y=dc["pct"],
            mode="lines+markers",
            name="CSB",
            line=dict(color=CSB_COLOR, width=2.5),
            marker=dict(size=5, color=CSB_COLOR, line=dict(width=1, color="#fff")),
            hovertemplate="<b>CSB · Day %{x}</b>: %{y:.1f}%<extra></extra>",
        ))
        last_day = int(dc["day"].iloc[-1])
        last_val = float(dc["pct"].iloc[-1])
        # Offset CSB label slightly to avoid overlapping Federal label
        fig.add_annotation(
            x=last_day, y=last_val,
            text=f"<b>{last_val:.1f}%</b>",
            showarrow=False, xanchor="left", xshift=10, yshift=-14,
            font=dict(size=11, color=CSB_COLOR),
        )

    # Federal goal line
    fig.add_hline(
        y=fed_goal,
        line_dash="dash", line_color=FED_COLOR, line_width=1.2, opacity=0.45,
        annotation_text=f"Fed goal {fed_goal:.1f}%",
        annotation_position="top right",
        annotation_font=dict(size=9, color=FED_COLOR),
        annotation_bgcolor="rgba(255,255,255,0.85)",
    )

    # CSB goal line (only draw if meaningfully different)
    if abs(csb_goal - fed_goal) > 0.2:
        fig.add_hline(
            y=csb_goal,
            line_dash="dash", line_color=CSB_COLOR, line_width=1.2, opacity=0.45,
            annotation_text=f"CSB goal {csb_goal:.1f}%",
            annotation_position="bottom right",
            annotation_font=dict(size=9, color=CSB_COLOR),
            annotation_bgcolor="rgba(255,255,255,0.85)",
        )

    # Today marker
    fig.add_vline(
        x=today_day, line_dash="solid", line_color="#e5e7eb", line_width=1,
        annotation_text="Today",
        annotation_position="top",
        annotation_font=dict(size=9, color="#9ca3af"),
    )

    direction = "↓ lower is better" if lower_is_better else "↑ higher is better"
    layout = dict(_BASE_LAYOUT)
    layout["height"] = 280
    layout["title"] = dict(
        text=(f"<b>{title}</b>"
              f"<span style='color:#9ca3af;font-size:11px'>  {direction}</span>"),
        font=dict(size=13, color="#111827"), x=0,
    )
    fig.update_layout(**layout)
    return fig


# ─────────────────────────────────────────────────────────────────────
# METRIC SECTION RENDERER
# ─────────────────────────────────────────────────────────────────────
def render_section(
    instance: str, metric: str,
    baseline: float, last_qtr: float, goal: float,
    m: dict | None,
    lower_is_better: bool,
):
    color = INSTANCE_COLORS.get(instance, "#2563eb")
    _section_header(instance, metric)

    mtd_val       = m["mtd_pct"]       if m else None
    yesterday_val = m["yesterday_val"] if m else None
    yesterday_vol = m["yesterday_vol"] if m else None

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    with c1:
        st.markdown(_card("Historical Baseline", f"{baseline:.2f}%"), unsafe_allow_html=True)
    with c2:
        st.markdown(_card("Last Quarter", f"{last_qtr:.2f}%"), unsafe_allow_html=True)
    with c3:
        st.markdown(_card(f"{CURRENT_QUARTER} Goal", f"{goal:.2f}%", top_color=color),
                    unsafe_allow_html=True)
    with c4:
        if yesterday_val is not None and yesterday_vol:
            st.markdown(_card(
                "Yesterday", f"{yesterday_val:.2f}%",
                delta=f"n = {yesterday_vol:,}", delta_color="#334155",
            ), unsafe_allow_html=True)
        else:
            st.markdown(_card("Yesterday", "—"), unsafe_allow_html=True)
    with c5:
        if mtd_val is not None:
            ok = (mtd_val <= goal) if lower_is_better else (mtd_val >= goal)
            st.markdown(_card("MTD", f"{mtd_val:.2f}%",
                               top_color="#16a34a" if ok else "#dc2626"),
                        unsafe_allow_html=True)
        else:
            st.markdown(_card("MTD", "—"), unsafe_allow_html=True)
    with c6:
        if mtd_val is not None:
            gap = mtd_val - goal
            on_track = (mtd_val <= goal) if lower_is_better else (mtd_val >= goal)
            st.markdown(_card(
                "Gap to Goal", f"{gap:+.2f}pp",
                delta="On Track ✓" if on_track else "Off Track ✗",
                delta_color="#15803d" if on_track else "#dc2626",
                top_color="#16a34a" if on_track else "#ef4444",
            ), unsafe_allow_html=True)
        else:
            st.markdown(_card("Gap to Goal", "—"), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)

    if m is not None and (m.get("daily_curr") is not None or m.get("daily_prev") is not None):
        st.plotly_chart(
            trajectory_chart(m, goal, metric, instance, lower_is_better),
            use_container_width=True,
            config={"displayModeBar": False},
        )
    else:
        st.markdown(
            '<div class="no-data-box">Upload a dataset to see the chart.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin:10px 0 26px 0;border-bottom:1px solid #e2e8f0'></div>",
                unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# OVERALL TAB
# ─────────────────────────────────────────────────────────────────────
def _summary_card(label, value, sub="", top_color="#cbd5e1", sub_color="#475569"):
    sub_html = (f'<div style="font-size:0.76rem;font-weight:600;color:{sub_color};margin-top:5px">{sub}</div>'
                if sub else "")
    return (
        f'<div style="background:#fff;border:1px solid #e2e8f0;border-top:3px solid {top_color};'
        f'border-radius:12px;padding:14px 16px 12px;box-shadow:0 2px 8px rgba(0,0,0,0.06);min-height:90px">'
        f'<div style="font-size:0.64rem;font-weight:800;text-transform:uppercase;'
        f'letter-spacing:0.09em;color:#475569;margin-bottom:7px">{label}</div>'
        f'<div style="font-size:1.4rem;font-weight:800;color:#0f172a;line-height:1.1">{value}</div>'
        f'{sub_html}</div>'
    )


def render_overall_tab(dsat_all, fcr_all, dsat_fed, fcr_fed, dsat_csb, fcr_csb, goals):
    st.markdown("<div style='margin-top:14px'></div>", unsafe_allow_html=True)

    def _gap_info(mtd, goal, lib):
        if mtd is None:
            return "—", "#cbd5e1", "#334155"
        ok = (mtd <= goal) if lib else (mtd >= goal)
        gap = mtd - goal
        return (
            f"{gap:+.2f}pp  {'✓' if ok else '✗'}",
            "#16a34a" if ok else "#ef4444",
            "#15803d" if ok else "#dc2626",
        )

    # DSAT summary row
    st.markdown(
        "<div style='font-size:0.72rem;color:#94a3b8;margin-bottom:6px;font-weight:600'>"
        "DSAT &nbsp;(lower is better)</div>",
        unsafe_allow_html=True,
    )
    for col, (lbl, val, goal, lib) in zip(st.columns(6), [
        ("Combined MTD", dsat_all["mtd_pct"] if dsat_all else None, None, True),
        ("Federal MTD",  dsat_fed["mtd_pct"] if dsat_fed else None, goals["DSAT"]["Federal"], True),
        ("CSB MTD",      dsat_csb["mtd_pct"] if dsat_csb else None, goals["DSAT"]["CSB"], True),
        ("Federal Goal", goals["DSAT"]["Federal"], None, None),
        ("CSB Goal",     goals["DSAT"]["CSB"], None, None),
        ("Yesterday",    dsat_all["yesterday_val"] if dsat_all else None, None, None),
    ]):
        with col:
            if val is None:
                st.markdown(_summary_card(lbl, "—"), unsafe_allow_html=True)
            elif goal is not None and lib is not None:
                sub, top, fg = _gap_info(val, goal, lib)
                st.markdown(_summary_card(lbl, f"{val:.2f}%", sub, top, fg), unsafe_allow_html=True)
            else:
                st.markdown(_summary_card(lbl, f"{val:.2f}%"), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)

    # FCR summary row
    st.markdown(
        "<div style='font-size:0.72rem;color:#94a3b8;margin-bottom:6px;font-weight:600'>"
        "FCR &nbsp;(higher is better)</div>",
        unsafe_allow_html=True,
    )
    for col, (lbl, val, goal, lib) in zip(st.columns(6), [
        ("Combined MTD", fcr_all["mtd_pct"] if fcr_all else None, None, False),
        ("Federal MTD",  fcr_fed["mtd_pct"] if fcr_fed else None, goals["FCR"]["Federal"], False),
        ("CSB MTD",      fcr_csb["mtd_pct"] if fcr_csb else None, goals["FCR"]["CSB"], False),
        ("Federal Goal", goals["FCR"]["Federal"], None, None),
        ("CSB Goal",     goals["FCR"]["CSB"], None, None),
        ("Yesterday",    fcr_all["yesterday_val"] if fcr_all else None, None, None),
    ]):
        with col:
            if val is None:
                st.markdown(_summary_card(lbl, "—"), unsafe_allow_html=True)
            elif goal is not None and lib is not None:
                sub, top, fg = _gap_info(val, goal, lib)
                st.markdown(_summary_card(lbl, f"{val:.2f}%", sub, top, fg), unsafe_allow_html=True)
            else:
                st.markdown(_summary_card(lbl, f"{val:.2f}%"), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)

    # Charts — two clear separate charts (no dual axis)
    has_any = any(m is not None for m in [dsat_fed, dsat_csb, fcr_fed, fcr_csb])
    if not has_any:
        st.markdown('<div class="no-data-box">Upload datasets to see charts.</div>',
                    unsafe_allow_html=True)
        return

    col_d, col_f = st.columns(2)
    with col_d:
        st.plotly_chart(
            comparison_chart(
                "DSAT", dsat_fed, dsat_csb,
                goals["DSAT"]["Federal"], goals["DSAT"]["CSB"],
                lower_is_better=True,
                title="DSAT — Federal vs CSB",
            ),
            use_container_width=True,
            config={"displayModeBar": False},
            key="ov_dsat",
        )
    with col_f:
        st.plotly_chart(
            comparison_chart(
                "FCR", fcr_fed, fcr_csb,
                goals["FCR"]["Federal"], goals["FCR"]["CSB"],
                lower_is_better=False,
                title="FCR — Federal vs CSB",
            ),
            use_container_width=True,
            config={"displayModeBar": False},
            key="ov_fcr",
        )


# ─────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────
def _sb_label(text: str):
    st.sidebar.markdown(f'<span class="sb-section-label">{text}</span>', unsafe_allow_html=True)


def _publish_widget(upload_key: str, gh_path: str, label: str) -> bool:
    """File uploader + Publish button (call from inside admin expander context)."""
    f = st.file_uploader(
        f"{label} · .csv / .xlsx", type=["csv", "xlsx", "xls"], key=upload_key,
    )
    if f is not None:
        content = f.getvalue()
        if not content:
            st.error(f"Uploaded file is empty — please re-select the file and try again.")
            return False
        st.caption(f"Ready to publish: **{f.name}** ({len(content):,} bytes)")
        if st.button(f"☁️ Publish {label} to dashboard",
                     key=f"pub_{upload_key}", use_container_width=True, type="primary"):
            _, sha = _gh_read(gh_path)
            with st.spinner(f"Publishing {label}…"):
                ok = _gh_write(gh_path, content, sha)
            if ok:
                st.success(f"✓ {label} published — all viewers will see updated data.")
                _fetch_gh_data.clear()
                return True
    return False


def render_sidebar() -> dict:
    st.sidebar.markdown(
        f"<div style='padding:4px 0 16px'>"
        f"<div style='font-size:1.1rem;font-weight:800;color:#f8fafc'>📊 OKR Dashboard</div>"
        f"<div style='font-size:0.74rem;color:#64748b;margin-top:2px'>"
        f"{CURRENT_QUARTER} &nbsp;·&nbsp; {datetime.now().strftime('%b %d, %H:%M')}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    _sb_label("Admin")
    unlocked   = st.session_state.admin_unlocked
    pushed_new = False

    with st.sidebar.expander(
        "🔓 Admin Mode Active" if unlocked else "🔐 Admin — Locked",
        expanded=unlocked,
    ):
        if not unlocked:
            pwd = st.text_input("Password", type="password", key="_pwd", placeholder="Enter password")
            if st.button("Unlock", use_container_width=True, type="primary"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state.admin_unlocked = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        else:
            st.markdown('<span class="sb-badge-admin">● Admin mode active</span>', unsafe_allow_html=True)
            if st.button("🔒 Lock", use_container_width=True):
                st.session_state.admin_unlocked = False
                st.rerun()

            # ── Settings ─────────────────────────────────────────────
            with st.form("admin_form", border=False):
                st.markdown("**Quarter Goals**")
                ca, cb = st.columns(2)
                g_dsat_fed = ca.number_input("DSAT Federal", 0.0, 100.0,
                    st.session_state.goals["DSAT"]["Federal"], 0.1, "%.2f")
                g_dsat_csb = cb.number_input("DSAT CSB", 0.0, 100.0,
                    st.session_state.goals["DSAT"]["CSB"], 0.1, "%.2f")
                g_fcr_fed  = ca.number_input("FCR Federal", 0.0, 100.0,
                    st.session_state.goals["FCR"]["Federal"], 0.1, "%.2f")
                g_fcr_csb  = cb.number_input("FCR CSB", 0.0, 100.0,
                    st.session_state.goals["FCR"]["CSB"], 0.1, "%.2f")

                st.markdown("**Baselines**")
                cc, cd = st.columns(2)
                b_dsat_fed = cc.number_input("DSAT Fed ", 0.0, 100.0,
                    st.session_state.baselines["DSAT"]["Federal"], 0.01, "%.2f")
                b_dsat_csb = cd.number_input("DSAT CSB ", 0.0, 100.0,
                    st.session_state.baselines["DSAT"]["CSB"], 0.01, "%.2f")
                b_fcr_fed  = cc.number_input("FCR Fed ", 0.0, 100.0,
                    st.session_state.baselines["FCR"]["Federal"], 0.01, "%.2f")
                b_fcr_csb  = cd.number_input("FCR CSB ", 0.0, 100.0,
                    st.session_state.baselines["FCR"]["CSB"], 0.01, "%.2f")

                st.markdown("**Last Quarter**")
                ce, cf = st.columns(2)
                lq_dsat_fed = ce.number_input("DSAT Fed  ", 0.0, 100.0,
                    st.session_state.last_qtr["DSAT"]["Federal"], 0.01, "%.2f")
                lq_dsat_csb = cf.number_input("DSAT CSB  ", 0.0, 100.0,
                    st.session_state.last_qtr["DSAT"]["CSB"], 0.01, "%.2f")
                lq_fcr_fed  = ce.number_input("FCR Fed  ", 0.0, 100.0,
                    st.session_state.last_qtr["FCR"]["Federal"], 0.01, "%.2f")
                lq_fcr_csb  = cf.number_input("FCR CSB  ", 0.0, 100.0,
                    st.session_state.last_qtr["FCR"]["CSB"], 0.01, "%.2f")

                if st.form_submit_button("✅ Apply & Save", use_container_width=True, type="primary"):
                    st.session_state.goals = {
                        "DSAT": {"Federal": g_dsat_fed, "CSB": g_dsat_csb},
                        "FCR":  {"Federal": g_fcr_fed,  "CSB": g_fcr_csb},
                    }
                    st.session_state.baselines = {
                        "DSAT": {"Federal": b_dsat_fed, "CSB": b_dsat_csb},
                        "FCR":  {"Federal": b_fcr_fed,  "CSB": b_fcr_csb},
                    }
                    st.session_state.last_qtr = {
                        "DSAT": {"Federal": lq_dsat_fed, "CSB": lq_dsat_csb},
                        "FCR":  {"Federal": lq_fcr_fed,  "CSB": lq_fcr_csb},
                    }
                    _save_settings()
                    st.success("✓ Saved.")

            st.markdown("---")
            st.markdown("**📂 Publish Datasets**")
            st.caption("Upload a file and click Publish — all viewers see the new data instantly.")

            if not _gh_token():
                st.warning(
                    "Add `GITHUB_TOKEN` (with `repo` scope) to Streamlit secrets to enable publishing.",
                    icon="⚠️",
                )

            p1 = _publish_widget("up_dsat", "data/dsat_data.csv", "DSAT")
            p2 = _publish_widget("up_fcr",  "data/fcr_data.csv",  "FCR")
            pushed_new = p1 or p2

    st.sidebar.markdown("---")
    demo_mode = st.sidebar.checkbox(
        "🧪 Demo mode", value=True,
        help="Shows mock data when no published dataset exists in GitHub.",
    )

    return {"demo_mode": demo_mode, "pushed_new": pushed_new}


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────
def main():
    inputs    = render_sidebar()
    goals     = st.session_state.goals
    baselines = st.session_state.baselines
    last_qtr  = st.session_state.last_qtr

    # Force rerun immediately after a publish so fresh data is shown
    if inputs["pushed_new"]:
        st.rerun()

    # Load data: GitHub (shared, persistent) → demo fallback
    gh_dsat = _fetch_gh_data("data/dsat_data.csv")
    gh_fcr  = _fetch_gh_data("data/fcr_data.csv")

    if gh_dsat is not None:
        dsat_df = _bytes_to_df(gh_dsat, "dsat_data.csv")
        st.sidebar.success("DSAT: live data ✓")
    elif inputs["demo_mode"]:
        dsat_df = pd.concat([_mock_dsat("Federal", 42), _mock_dsat("CSB", 43)], ignore_index=True)
    else:
        dsat_df = None

    if gh_fcr is not None:
        fcr_df = _bytes_to_df(gh_fcr, "fcr_data.csv")
        st.sidebar.success("FCR: live data ✓")
    elif inputs["demo_mode"]:
        fcr_df = pd.concat([_mock_fcr("Federal", 99), _mock_fcr("CSB", 100)], ignore_index=True)
    else:
        fcr_df = None

    # Compute all metrics
    dsat_fed = calc_dsat(dsat_df, "Federal")
    dsat_csb = calc_dsat(dsat_df, "CSB")
    fcr_fed  = calc_fcr(fcr_df,  "Federal")
    fcr_csb  = calc_fcr(fcr_df,  "CSB")
    dsat_all = calc_dsat_all(dsat_df)
    fcr_all  = calc_fcr_all(fcr_df)

    # Page header
    h1, h2 = st.columns([4, 1])
    with h1:
        st.markdown(
            "<h1 style='font-size:1.7rem;font-weight:800;color:#0f172a;margin-bottom:2px'>"
            "📊 OKR Tracking Dashboard</h1>",
            unsafe_allow_html=True,
        )
    with h2:
        is_live    = gh_dsat is not None or gh_fcr is not None
        badge_text = "📁 Live Data" if is_live else "🧪 Demo Mode"
        badge_bg   = "#dcfce7" if is_live else "#fef9c3"
        badge_fg   = "#14532d" if is_live else "#713f12"
        st.markdown(
            f"<div style='padding-top:14px;text-align:right'>"
            f"<span style='background:{badge_bg};color:{badge_fg};font-size:0.75rem;"
            f"font-weight:700;padding:4px 12px;border-radius:99px'>{badge_text}</span>"
            f"<div style='font-size:0.72rem;color:#64748b;margin-top:4px'>{CURRENT_QUARTER}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-bottom:6px'></div>", unsafe_allow_html=True)

    tab_overall, tab_dsat, tab_fcr, tab_data = st.tabs(
        ["📊  Overall", "📉  DSAT", "📈  FCR", "🗂️  Raw Data"]
    )

    with tab_overall:
        render_overall_tab(dsat_all, fcr_all, dsat_fed, fcr_fed, dsat_csb, fcr_csb, goals)

    with tab_dsat:
        st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
        render_section("Federal", "DSAT",
            baselines["DSAT"]["Federal"], last_qtr["DSAT"]["Federal"], goals["DSAT"]["Federal"],
            dsat_fed, lower_is_better=True)
        render_section("CSB", "DSAT",
            baselines["DSAT"]["CSB"], last_qtr["DSAT"]["CSB"], goals["DSAT"]["CSB"],
            dsat_csb, lower_is_better=True)

    with tab_fcr:
        st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
        render_section("Federal", "FCR",
            baselines["FCR"]["Federal"], last_qtr["FCR"]["Federal"], goals["FCR"]["Federal"],
            fcr_fed, lower_is_better=False)
        render_section("CSB", "FCR",
            baselines["FCR"]["CSB"], last_qtr["FCR"]["CSB"], goals["FCR"]["CSB"],
            fcr_csb, lower_is_better=False)

    with tab_data:
        st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
        dc1, dc2 = st.columns(2)
        with dc1:
            st.markdown("**DSAT Dataset**")
            if dsat_df is not None:
                st.dataframe(dsat_df.head(200), use_container_width=True, height=400)
                st.caption(f"{len(dsat_df):,} total rows")
            else:
                st.markdown('<div class="no-data-box">No DSAT data loaded.</div>', unsafe_allow_html=True)
        with dc2:
            st.markdown("**FCR Dataset**")
            if fcr_df is not None:
                st.dataframe(fcr_df.head(200), use_container_width=True, height=400)
                st.caption(f"{len(fcr_df):,} total rows")
            else:
                st.markdown('<div class="no-data-box">No FCR data loaded.</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
