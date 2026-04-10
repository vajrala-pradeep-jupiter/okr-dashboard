#!/usr/bin/env python3
"""OKR Tracking Dashboard — DSAT & FCR across Federal and CSB instances."""
from __future__ import annotations

import json
import os
import calendar as cal
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta, date

# ════════════════════════════════════════════════════════════════════════
#  EDIT THESE — all hardcoded numbers live here
# ════════════════════════════════════════════════════════════════════════

# Read password from Streamlit secrets (cloud) or fall back to default (local)
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
# DSAT goal = 15 % reduction from baseline; FCR goal = 80 % for both
DEFAULT_GOALS = {
    "DSAT": {"Federal": round(18.05 * 0.85, 2), "CSB": round(11.07 * 0.85, 2)},
    "FCR":  {"Federal": 80.00, "CSB": 80.00},
}

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

/* ── Dark sidebar ── */
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

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] { gap:0; border-bottom:2px solid #cbd5e1; background:transparent; }
.stTabs [data-baseweb="tab"] {
    font-size:0.92rem !important; font-weight:600 !important;
    color:#475569 !important; padding:10px 24px !important;
    border-radius:8px 8px 0 0; background:transparent;
}
.stTabs [aria-selected="true"] {
    color:#1d4ed8 !important; border-bottom:3px solid #1d4ed8 !important; background:#eff6ff !important;
}

/* ── Expanders (main area) ── */
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
# INSTANCE FILTERS
# ─────────────────────────────────────────────────────────────────────
def _clean_str_col(series: pd.Series) -> pd.Series:
    """Strip all whitespace variants and uppercase for reliable matching."""
    return (series.astype(str)
            .str.replace(r'\s+', ' ', regex=True)
            .str.strip()
            .str.upper())


def _filter_dsat(df: pd.DataFrame, instance: str) -> pd.DataFrame:
    """DSAT: instance encoded as suffix in combined_key  e.g. '123456 - FEDERAL'."""
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
    """FCR: instance in fd_instance column directly  e.g. 'FEDERAL' or 'CSB'."""
    inst_up = instance.upper()
    if "fd_instance" in df.columns:
        cleaned = _clean_str_col(df["fd_instance"])
        f = df[cleaned == inst_up]
        if not f.empty:
            return f
    if "instance" in df.columns:
        f = df[_clean_str_col(df["instance"]) == inst_up]
        if not f.empty:
            return f
    _warn_no_instance(df, instance, "FCR", ["fd_instance", "instance"])
    return pd.DataFrame()


def _warn_no_instance(df, instance, label, tried_cols):
    # Show unique values of any relevant column to help diagnose
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
    """Return key date boundaries relative to today."""
    today      = date.today()
    yesterday  = today - timedelta(days=1)
    curr_start = today.replace(day=1)
    prev_end   = curr_start - timedelta(days=1)
    prev_start = prev_end.replace(day=1)

    # Previous quarter bounds
    curr_q = (today.month - 1) // 3          # 0-indexed: 0=Q1..3=Q4
    pq_end_m = curr_q * 3                    # last month of prev quarter
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
# Computes everything from the raw filtered DataFrame
# ─────────────────────────────────────────────────────────────────────
def _compute(df_inst: pd.DataFrame, date_col: str, flag_col: str, flag_val: str) -> dict | None:
    """
    Returns a dict with:
      mtd_pct        – current-month overall %
      yesterday_val  – yesterday %  (None if no data)
      yesterday_vol  – yesterday ticket count
      daily_curr     – DataFrame[day(1-31), pct, total] current month
      daily_prev     – DataFrame[day(1-31), pct, total] previous month
      prev_qtr_pct   – previous quarter overall %
    All calculated directly from raw data — no manual entry needed.
    """
    if df_inst is None or df_inst.empty:
        return None

    dr = _date_ranges()
    df = df_inst.copy()

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    if df.empty:
        return None

    df["_date"] = df[date_col].dt.date
    df["_day"]  = df[date_col].dt.day
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
        "mtd_pct":      _pct(curr_mask),
        "yesterday_val": yesterday_val,
        "yesterday_vol": yesterday_vol,
        "daily_curr":   _daily(curr_mask),
        "daily_prev":   _daily(prev_mask),
        "prev_qtr_pct": _pct(pq_mask),
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
    # Temporarily map feedback_rating==1 into a string flag column for _compute
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
    """DSAT across all instances combined — no instance filter."""
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
    """FCR across all instances combined — no instance filter."""
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
    # Generate 4 months of data (enough for prev quarter + current month)
    start = (today.replace(day=1) - timedelta(days=92)).replace(day=1)
    base  = st.session_state.baselines["DSAT"][instance] / 100
    rows  = []
    d = start
    while d <= today:
        # Slight downward trend over time (improvement)
        days_in = (d - start).days
        trend = max(0.0, base - days_in * 0.0003)
        for _ in range(int(rng.integers(60, 180))):
            is_dsat = rng.random() < max(0.0, trend + rng.normal(0, 0.012))
            tid = int(rng.integers(100_000, 999_999))
            rows.append({
                "feedback_created_at": pd.Timestamp(d),
                "fd_ticket_id":        tid,
                "channel":             rng.choice(["EMAIL", "PHONE", "CHAT"], p=[0.5, 0.3, 0.2]),
                "user_id":             f"user_{rng.integers(1000, 9999)}",
                "fd_product_category": rng.choice(["Billing", "Technical", "Account", "General"]),
                "fd_issue":            rng.choice(["Login Issue", "Payment Failed", "Feature Request", "Bug"]),
                "fd_resolution":       rng.choice(["Resolved", "Workaround", "Escalated"]),
                "fd_product_category_issue_resolution": "mock",
                "agent_email":         f"agent{rng.integers(1, 20)}@company.com",
                "queue_name":          f"{instance} Support",
                "feedback_rating":     int(1 if is_dsat else rng.choice([2, 3, 4, 5], p=[0.05, 0.15, 0.4, 0.4])),
                "combined_key":        f"{tid} - {instance.upper()}",
                "custom_feedback":     "",
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
                "ticket_id":               f"mock_{tid}",
                "fd_ticket_id":            tid,
                "ticket_created_at":       pd.Timestamp(d),
                "ticket_resolved_at":      pd.Timestamp(d + timedelta(hours=int(rng.integers(1, 72)))),
                "user_id":                 f"user_{rng.integers(1000, 9999)}",
                "user_affluent_class":     rng.choice(["None", "e. Affluent Band 5"]),
                "channel":                 rng.choice(["EMAIL", "PHONE", "CHAT"], p=[0.5, 0.3, 0.2]),
                "fd_instance":             instance.upper(),
                "fd_product_category":     rng.choice(["Billing", "Technical", "Onboarding", "General"]),
                "fd_issue":                rng.choice(["Login Issue", "Payment Failed", "Card Application"]),
                "fd_resolution":           rng.choice(["Resolved", "Workaround", "Escalated"]),
                "fd_product_category_subcategory": "mock_sub",
                "status":                  rng.choice(["CLOSED", "WAIT_ON_CUSTOMER", "OPEN"]),
                "agent_email":             f"agent{rng.integers(1, 20)}@company.com",
                "fd_group_name":           "Unassigned",
                "queue_name":              f"{instance} Support",
                "ticket_association_type": "PARENT",
                "parent_ticket_type":      "L1",
                "fcr_flag":                "FCR" if is_fcr else "Non FCR",
                "amb_flag":                rng.choice(["AMB", "Non AMB"], p=[0.1, 0.9]),
            })
        d += timedelta(days=1)
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────
# FILE READER
# ─────────────────────────────────────────────────────────────────────
def read_file(uploaded) -> pd.DataFrame | None:
    if uploaded is None:
        return None
    try:
        name = uploaded.name.lower()
        if name.endswith(".csv"):
            return pd.read_csv(uploaded)
        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(uploaded)
        st.sidebar.error(f"Unsupported format: {uploaded.name}")
        return None
    except Exception as exc:
        st.sidebar.error(f"Could not read file: {exc}")
        return None


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


# ─────────────────────────────────────────────────────────────────────
# DUAL-AXIS CHART  — DSAT (left/orange) + FCR (right/blue) on one graph
# ─────────────────────────────────────────────────────────────────────
def dual_chart(
    dsat_m: dict | None,
    fcr_m:  dict | None,
    dsat_goal: float,
    fcr_goal:  float,
    title: str,
    dsat_goal2: float | None = None,   # second goal line (for combined view)
    fcr_goal2:  float | None = None,
) -> go.Figure:
    from plotly.subplots import make_subplots as _msp
    fig = _msp(specs=[[{"secondary_y": True}]])

    today_day = date.today().day

    # ── DSAT prev month (faint orange dotted) ────────────────────
    if dsat_m and dsat_m.get("daily_prev") is not None:
        dp = dsat_m["daily_prev"]
        fig.add_trace(go.Scatter(
            x=dp["day"], y=dp["pct"], mode="lines",
            name="DSAT — Prev Month",
            line=dict(color="#fdba74", width=1.6, dash="dot"),
            hovertemplate="Day %{x} (DSAT prev month)<br>%{y:.2f}%<extra></extra>",
        ), secondary_y=False)

    # ── DSAT this month (solid orange, coloured markers) ─────────
    if dsat_m and dsat_m.get("daily_curr") is not None:
        dc = dsat_m["daily_curr"]
        mk = ["#16a34a" if v <= dsat_goal else "#dc2626" for v in dc["pct"]]
        fig.add_trace(go.Scatter(
            x=dc["day"], y=dc["pct"], mode="lines+markers",
            name="DSAT — This Month",
            line=dict(color="#f97316", width=2.6),
            marker=dict(size=7, color=mk, line=dict(width=1.8, color="#fff")),
            hovertemplate="Day %{x}<br>DSAT: <b>%{y:.2f}%</b><extra></extra>",
        ), secondary_y=False)

    # ── DSAT goal(s) (orange dashed horizontal via Scatter) ───────
    fig.add_trace(go.Scatter(
        x=[1, 31], y=[dsat_goal, dsat_goal], mode="lines",
        name=f"DSAT Goal — {dsat_goal:.1f}%",
        line=dict(color="#c2410c", width=1.8, dash="dash"),
    ), secondary_y=False)
    if dsat_goal2 is not None:
        fig.add_trace(go.Scatter(
            x=[1, 31], y=[dsat_goal2, dsat_goal2], mode="lines",
            name=f"DSAT Goal 2 — {dsat_goal2:.1f}%",
            line=dict(color="#c2410c", width=1.4, dash="longdash"),
        ), secondary_y=False)

    # ── FCR prev month (faint blue dotted) ───────────────────────
    if fcr_m and fcr_m.get("daily_prev") is not None:
        fp = fcr_m["daily_prev"]
        fig.add_trace(go.Scatter(
            x=fp["day"], y=fp["pct"], mode="lines",
            name="FCR — Prev Month",
            line=dict(color="#93c5fd", width=1.6, dash="dot"),
            hovertemplate="Day %{x} (FCR prev month)<br>%{y:.2f}%<extra></extra>",
        ), secondary_y=True)

    # ── FCR this month (solid blue, coloured markers) ─────────────
    if fcr_m and fcr_m.get("daily_curr") is not None:
        fc = fcr_m["daily_curr"]
        mk = ["#16a34a" if v >= fcr_goal else "#dc2626" for v in fc["pct"]]
        fig.add_trace(go.Scatter(
            x=fc["day"], y=fc["pct"], mode="lines+markers",
            name="FCR — This Month",
            line=dict(color="#2563eb", width=2.6),
            marker=dict(size=7, color=mk, line=dict(width=1.8, color="#fff")),
            hovertemplate="Day %{x}<br>FCR: <b>%{y:.2f}%</b><extra></extra>",
        ), secondary_y=True)

    # ── FCR goal(s) (blue dashed horizontal via Scatter) ─────────
    fig.add_trace(go.Scatter(
        x=[1, 31], y=[fcr_goal, fcr_goal], mode="lines",
        name=f"FCR Goal — {fcr_goal:.1f}%",
        line=dict(color="#1d4ed8", width=1.8, dash="dash"),
    ), secondary_y=True)
    if fcr_goal2 is not None:
        fig.add_trace(go.Scatter(
            x=[1, 31], y=[fcr_goal2, fcr_goal2], mode="lines",
            name=f"FCR Goal 2 — {fcr_goal2:.1f}%",
            line=dict(color="#1d4ed8", width=1.4, dash="longdash"),
        ), secondary_y=True)

    # ── Today marker ─────────────────────────────────────────────
    fig.add_vline(
        x=today_day, line_dash="solid", line_color="#e2e8f0", line_width=1.5,
        annotation_text=f"Today ({today_day})",
        annotation_position="top",
        annotation_font=dict(size=9, color="#94a3b8"),
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color="#0f172a"), x=0, xanchor="left"),
        hovermode="x unified",
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        height=340,
        margin=dict(l=8, r=12, t=52, b=36),
        legend=dict(
            orientation="h", x=0, y=1.17, font=dict(size=10, color="#334155"),
            bgcolor="rgba(0,0,0,0)", traceorder="normal",
        ),
        xaxis=dict(
            title="Day of Month", range=[0.5, 31.5], dtick=5,
            tickfont=dict(size=11, color="#475569"),
            gridcolor="#f1f5f9", showline=True, linecolor="#e2e8f0",
        ),
    )
    fig.update_yaxes(
        title_text="DSAT %  ↓ lower is better",
        ticksuffix="%", gridcolor="#f1f5f9", zeroline=False,
        tickfont=dict(size=11, color="#ea580c"),
        title_font=dict(color="#ea580c", size=11),
        secondary_y=False,
    )
    fig.update_yaxes(
        title_text="FCR %  ↑ higher is better",
        ticksuffix="%", showgrid=False, zeroline=False,
        tickfont=dict(size=11, color="#1d4ed8"),
        title_font=dict(color="#1d4ed8", size=11),
        secondary_y=True,
    )
    return fig


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
# CHART  — 4 lines: prev quarter avg · prev month · current month · goal
# X-axis = day of month so current and previous month align directly
# ─────────────────────────────────────────────────────────────────────
def trajectory_chart(
    m: dict, goal: float, baseline: float,
    metric: str, instance: str, lower_is_better: bool,
) -> go.Figure:
    fig = go.Figure()
    color = INSTANCE_COLORS.get(instance, "#2563eb")

    # ── Previous month (gray dotted) ─────────────────────────────
    if m["daily_prev"] is not None and not m["daily_prev"].empty:
        dp = m["daily_prev"]
        fig.add_trace(go.Scatter(
            x=dp["day"], y=dp["pct"],
            mode="lines",
            name="Prev Month",
            line=dict(color="#94a3b8", width=1.8, dash="dot"),
            hovertemplate="<b>Day %{x}</b> (Prev Month)<br>%{y:.2f}%<extra></extra>",
        ))

    # ── Previous quarter avg (purple dashed horizontal) ───────────
    pq = m["prev_qtr_pct"]
    if pq is not None:
        dr = _date_ranges()
        pq_label = (f"Prev Qtr avg  {pq:.1f}%  "
                    f"({dr['pq_start'].strftime('%b')}–{dr['pq_end'].strftime('%b %Y')})")
        fig.add_hline(
            y=pq, line_dash="dashdot", line_color="#8b5cf6", line_width=1.6,
            annotation_text=f"  {pq_label}",
            annotation_position="top right",
            annotation_font=dict(size=10, color="#7c3aed"),
        )

    # ── Current month (main line, colored markers) ────────────────
    if m["daily_curr"] is not None and not m["daily_curr"].empty:
        dc = m["daily_curr"]
        mk_colors = [
            "#16a34a" if (v <= goal if lower_is_better else v >= goal) else "#dc2626"
            for v in dc["pct"]
        ]
        fig.add_trace(go.Scatter(
            x=dc["day"], y=dc["pct"],
            mode="lines+markers",
            name="This Month",
            line=dict(color=color, width=2.8),
            marker=dict(size=8, color=mk_colors, line=dict(width=2, color="#fff")),
            hovertemplate=(
                "<b>Day %{x}</b> (This Month)<br>"
                + metric + ": <b>%{y:.2f}%</b><extra></extra>"
            ),
        ))

    # ── Goal line (green dashed) ──────────────────────────────────
    fig.add_hline(
        y=goal, line_dash="dash", line_color="#16a34a", line_width=2,
        annotation_text=f"  Goal  {goal:.1f}%",
        annotation_position="bottom right",
        annotation_font=dict(size=11, color="#15803d"),
    )

    # ── Layout ────────────────────────────────────────────────────
    direction = "↓ lower is better" if lower_is_better else "↑ higher is better"
    today_day = date.today().day

    fig.update_layout(
        title=dict(
            text=(f"<b>{instance} — {metric}</b>"
                  f"<span style='color:#94a3b8;font-size:11px'>  {direction}</span>"),
            font=dict(size=14, color="#0f172a"), x=0, xanchor="left",
        ),
        hovermode="x unified",
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        height=320,
        margin=dict(l=8, r=20, t=52, b=36),
        legend=dict(
            orientation="h", x=0, y=1.13,
            font=dict(size=11, color="#334155"),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            title="Day of Month",
            range=[0.5, 31.5],
            dtick=5,
            tickfont=dict(size=11, color="#475569"),
            gridcolor="#f1f5f9", gridwidth=1,
            showline=True, linecolor="#e2e8f0",
        ),
        yaxis=dict(
            ticksuffix="%",
            gridcolor="#f1f5f9", gridwidth=1,
            tickfont=dict(size=11, color="#475569"),
            title=dict(text=f"{metric} (%)", font=dict(size=11, color="#475569")),
            zeroline=False,
            showline=True, linecolor="#e2e8f0",
        ),
    )

    # Vertical line for today
    fig.add_vline(
        x=today_day, line_dash="solid", line_color="#e2e8f0", line_width=1.5,
        annotation_text=f"Today ({today_day})",
        annotation_position="top",
        annotation_font=dict(size=10, color="#94a3b8"),
    )

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

    # Pull computed values (or None if no data)
    mtd_val      = m["mtd_pct"]       if m else None
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
            g_fg = "#15803d" if on_track else "#dc2626"
            g_top = "#16a34a" if on_track else "#ef4444"
            st.markdown(_card(
                "Gap to Goal", f"{gap:+.2f}pp",
                delta="On Track ✓" if on_track else "Off Track ✗",
                delta_color=g_fg, top_color=g_top,
            ), unsafe_allow_html=True)
        else:
            st.markdown(_card("Gap to Goal", "—"), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)

    if m is not None and (m["daily_curr"] is not None or m["daily_prev"] is not None):
        st.plotly_chart(
            trajectory_chart(m, goal, baseline, metric, instance, lower_is_better),
            use_container_width=True,
            config={"displayModeBar": False},
        )
    else:
        st.markdown(
            '<div class="no-data-box">Upload a dataset or enable Demo Mode to see the chart.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin:10px 0 26px 0;border-bottom:1px solid #e2e8f0'></div>",
                unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# OVERALL TAB RENDERER
# ─────────────────────────────────────────────────────────────────────
def _summary_card(label: str, value: str, sub: str = "",
                  top_color: str = "#cbd5e1", sub_color: str = "#475569") -> str:
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


def render_overall_tab(
    dsat_all: dict | None, fcr_all: dict | None,
    dsat_fed: dict | None, fcr_fed: dict | None,
    dsat_csb: dict | None, fcr_csb: dict | None,
    goals: dict,
):
    st.markdown("<div style='margin-top:14px'></div>", unsafe_allow_html=True)

    # ── KPI summary grid ─────────────────────────────────────────
    st.markdown(
        "<div style='font-size:0.78rem;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.08em;color:#475569;margin-bottom:12px'>Current Month Snapshot</div>",
        unsafe_allow_html=True,
    )

    def _gap_info(mtd, goal, lower_is_better):
        if mtd is None:
            return "—", "#cbd5e1", "#334155"
        ok = (mtd <= goal) if lower_is_better else (mtd >= goal)
        gap = mtd - goal
        return (
            f"{gap:+.2f}pp  {'✓' if ok else '✗'}",
            "#16a34a" if ok else "#ef4444",
            "#15803d" if ok else "#dc2626",
        )

    # Row 1 — DSAT
    st.markdown("<div style='font-size:0.72rem;color:#94a3b8;margin-bottom:6px;font-weight:600'>DSAT &nbsp;(lower is better)</div>", unsafe_allow_html=True)
    r1 = st.columns(6)
    metrics_row = [
        ("Combined MTD",  dsat_all["mtd_pct"] if dsat_all else None, None, True),
        ("Federal MTD",   dsat_fed["mtd_pct"] if dsat_fed else None,
         goals["DSAT"]["Federal"], True),
        ("CSB MTD",       dsat_csb["mtd_pct"] if dsat_csb else None,
         goals["DSAT"]["CSB"], True),
        ("Federal Goal",  goals["DSAT"]["Federal"], None, None),
        ("CSB Goal",      goals["DSAT"]["CSB"], None, None),
        ("Yesterday",
         dsat_all["yesterday_val"] if dsat_all else None, None, None),
    ]
    for col, (lbl, val, goal, lib) in zip(r1, metrics_row):
        with col:
            if val is None:
                st.markdown(_summary_card(lbl, "—"), unsafe_allow_html=True)
            elif goal is not None and lib is not None:
                sub, top, fg = _gap_info(val, goal, lib)
                st.markdown(_summary_card(lbl, f"{val:.2f}%", sub=sub,
                                          top_color=top, sub_color=fg), unsafe_allow_html=True)
            else:
                st.markdown(_summary_card(lbl, f"{val:.2f}%"), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)

    # Row 2 — FCR
    st.markdown("<div style='font-size:0.72rem;color:#94a3b8;margin-bottom:6px;font-weight:600'>FCR &nbsp;(higher is better)</div>", unsafe_allow_html=True)
    r2 = st.columns(6)
    metrics_row2 = [
        ("Combined MTD",  fcr_all["mtd_pct"] if fcr_all else None, None, False),
        ("Federal MTD",   fcr_fed["mtd_pct"] if fcr_fed else None,
         goals["FCR"]["Federal"], False),
        ("CSB MTD",       fcr_csb["mtd_pct"] if fcr_csb else None,
         goals["FCR"]["CSB"], False),
        ("Federal Goal",  goals["FCR"]["Federal"], None, None),
        ("CSB Goal",      goals["FCR"]["CSB"], None, None),
        ("Yesterday",
         fcr_all["yesterday_val"] if fcr_all else None, None, None),
    ]
    for col, (lbl, val, goal, lib) in zip(r2, metrics_row2):
        with col:
            if val is None:
                st.markdown(_summary_card(lbl, "—"), unsafe_allow_html=True)
            elif goal is not None and lib is not None:
                sub, top, fg = _gap_info(val, goal, lib)
                st.markdown(_summary_card(lbl, f"{val:.2f}%", sub=sub,
                                          top_color=top, sub_color=fg), unsafe_allow_html=True)
            else:
                st.markdown(_summary_card(lbl, f"{val:.2f}%"), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)

    # ── Charts ───────────────────────────────────────────────────
    # Shared legend guide
    st.markdown("""
    <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;
                padding:10px 16px;margin-bottom:20px;font-size:0.78rem;color:#334155;
                display:flex;gap:24px;flex-wrap:wrap">
        <span><b style="color:#f97316">━━</b> DSAT this month (dots = on/off track)</span>
        <span><b style="color:#fdba74">┄┄</b> DSAT prev month</span>
        <span><b style="color:#c2410c">- -</b> DSAT goal</span>
        &nbsp;&nbsp;
        <span><b style="color:#2563eb">━━</b> FCR this month (dots = on/off track)</span>
        <span><b style="color:#93c5fd">┄┄</b> FCR prev month</span>
        <span><b style="color:#1d4ed8">- -</b> FCR goal</span>
        &nbsp;&nbsp;
        <span><b style="color:#16a34a">●</b> On track</span>
        <span><b style="color:#dc2626">●</b> Off track</span>
    </div>""", unsafe_allow_html=True)

    # Chart 1 — Overall combined
    has_any = any(m is not None for m in [dsat_all, fcr_all])
    if has_any:
        # For combined, show both Fed and CSB goals as two reference lines
        st.plotly_chart(
            dual_chart(
                dsat_all, fcr_all,
                dsat_goal=goals["DSAT"]["Federal"],
                fcr_goal=goals["FCR"]["Federal"],
                title="<b>Overall (Federal + CSB combined)</b>  ·  DSAT vs FCR",
                dsat_goal2=goals["DSAT"]["CSB"],
                fcr_goal2=goals["FCR"]["CSB"],
            ),
            use_container_width=True,
            config={"displayModeBar": False},
            key="chart_overall",
        )
    else:
        st.markdown('<div class="no-data-box">Upload datasets or enable Demo Mode to see charts.</div>',
                    unsafe_allow_html=True)

    st.markdown("<div style='margin:6px 0 20px;border-bottom:1px solid #e2e8f0'></div>",
                unsafe_allow_html=True)

    # Charts 2 & 3 — Federal and CSB side by side
    col_f, col_c = st.columns(2)

    with col_f:
        if dsat_fed is not None or fcr_fed is not None:
            st.plotly_chart(
                dual_chart(
                    dsat_fed, fcr_fed,
                    dsat_goal=goals["DSAT"]["Federal"],
                    fcr_goal=goals["FCR"]["Federal"],
                    title="<b>Federal</b>  ·  DSAT vs FCR",
                ),
                use_container_width=True,
                config={"displayModeBar": False},
                key="chart_federal",
            )
        else:
            st.markdown('<div class="no-data-box">No Federal data.</div>', unsafe_allow_html=True)

    with col_c:
        if dsat_csb is not None or fcr_csb is not None:
            st.plotly_chart(
                dual_chart(
                    dsat_csb, fcr_csb,
                    dsat_goal=goals["DSAT"]["CSB"],
                    fcr_goal=goals["FCR"]["CSB"],
                    title="<b>CSB</b>  ·  DSAT vs FCR",
                ),
                use_container_width=True,
                config={"displayModeBar": False},
                key="chart_csb",
            )
        else:
            st.markdown('<div class="no-data-box">No CSB data.</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────
def _sb_label(text: str):
    st.sidebar.markdown(f'<span class="sb-section-label">{text}</span>', unsafe_allow_html=True)


def render_sidebar():
    st.sidebar.markdown(
        f"<div style='padding:4px 0 16px'>"
        f"<div style='font-size:1.1rem;font-weight:800;color:#f8fafc'>📊 OKR Dashboard</div>"
        f"<div style='font-size:0.74rem;color:#64748b;margin-top:2px'>"
        f"{CURRENT_QUARTER} &nbsp;·&nbsp; {datetime.now().strftime('%b %d, %H:%M')}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Admin ─────────────────────────────────────────────────────
    _sb_label("Admin")
    unlocked = st.session_state.admin_unlocked
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
                    st.success("✓ Saved — persists across restarts.")

    st.sidebar.markdown("---")

    # ── Uploads ───────────────────────────────────────────────────
    _sb_label("📂 Upload MTD Datasets")
    dsat_file = st.sidebar.file_uploader(
        "DSAT · .csv / .xlsx", type=["csv", "xlsx", "xls"], key="up_dsat")
    st.sidebar.markdown("<div style='margin-bottom:6px'></div>", unsafe_allow_html=True)
    fcr_file = st.sidebar.file_uploader(
        "FCR · .csv / .xlsx", type=["csv", "xlsx", "xls"], key="up_fcr")

    st.sidebar.markdown("---")
    demo_mode = st.sidebar.checkbox(
        "🧪 Demo mode", value=True,
        help="Generates realistic mock data when no file is uploaded.",
    )

    return {"demo_mode": demo_mode, "dsat_file": dsat_file, "fcr_file": fcr_file}


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────
def main():
    inputs    = render_sidebar()
    goals     = st.session_state.goals
    baselines = st.session_state.baselines
    last_qtr  = st.session_state.last_qtr

    # Load data
    dsat_df = read_file(inputs["dsat_file"])
    if dsat_df is not None:
        st.sidebar.success(f"DSAT: {len(dsat_df):,} rows ✓")
    elif inputs["demo_mode"]:
        dsat_df = pd.concat([_mock_dsat("Federal", 42), _mock_dsat("CSB", 43)], ignore_index=True)

    fcr_df = read_file(inputs["fcr_file"])
    if fcr_df is not None:
        st.sidebar.success(f"FCR: {len(fcr_df):,} rows ✓")
    elif inputs["demo_mode"]:
        fcr_df = pd.concat([_mock_fcr("Federal", 99), _mock_fcr("CSB", 100)], ignore_index=True)

    # Compute all metrics from raw data
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
        is_live    = inputs["dsat_file"] is not None or inputs["fcr_file"] is not None
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
        render_overall_tab(
            dsat_all, fcr_all,
            dsat_fed, fcr_fed,
            dsat_csb, fcr_csb,
            goals,
        )

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
