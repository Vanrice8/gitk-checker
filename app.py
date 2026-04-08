"""
app.py – GITK Deviation Checker
Run with:  streamlit run app.py
"""

import json
import math
from datetime import timedelta

import pandas as pd
import streamlit as st

from logic import process_records

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="GITK Deviation Checker",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Styling ──────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Base */
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #0f1117;
        border-right: 1px solid #1e2530;
    }
    section[data-testid="stSidebar"] * {
        color: #c9d1d9 !important;
    }

    /* Metric cards */
    [data-testid="metric-container"] {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
    }
    [data-testid="metric-container"] label {
        color: #8b949e !important;
        font-size: 0.75rem !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 2rem !important;
        font-weight: 600 !important;
    }

    /* Headers */
    h1 { font-weight: 600 !important; letter-spacing: -0.02em; }
    h2, h3 { font-weight: 400 !important; color: #8b949e !important; }

    /* Dataframe */
    .stDataFrame { border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }

    /* Badges */
    .badge-dev  { background:#3d1a1a; color:#f85149; padding:2px 8px; border-radius:4px;
                  font-family:'IBM Plex Mono',monospace; font-size:0.75rem; }
    .badge-ok   { background:#0d2818; color:#3fb950; padding:2px 8px; border-radius:4px;
                  font-family:'IBM Plex Mono',monospace; font-size:0.75rem; }

    /* Upload zones */
    [data-testid="stFileUploader"] {
        border: 1px dashed #30363d !important;
        border-radius: 8px;
        background: #0d1117 !important;
    }

    /* Expander */
    details { border: 1px solid #21262d !important; border-radius: 6px !important; }
</style>
""", unsafe_allow_html=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_json(uploaded_file):
    if uploaded_file is None:
        return None
    try:
        content = uploaded_file.read()
        data = json.loads(content)
        return data if isinstance(data, list) else data.get("records", data.get("data", [data]))
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        return None


# ─── Notes / Measures suggestions ────────────────────────────────────────────

NOTES_OPTIONS = [
    "After manual observation, no SLA breaches could be identified",
    "Complicated service restoration",
    "Incident caused and solved by external provider.",
    "Incident priority downgraded, after manual check of incident p2 duration, no deviation found.",
    "Incident resolved before MSI had the chance to put up driftinfo",
    "Incident was flagged as a security incident, sms distribution is at the discretion of Incident manager and MOD",
    "Incident was raised retrospectively for logging purpose due to it being resolved when it reached MSI",
    "No Driftinfo published due to P2 without immediate user impact",
    "No SMS was sent, in accordance with the agreement with Verksamhet Beredskap",
    "Application user pool had already been informed of the issue, after agreement with VB, it was decided to omit publishing of Driftinfo",
    "P2 without user impact, sms should have been sent to IT management",
]

MEASURES_OPTIONS = [
    "No measures taken",
    "Incident management team has been sensitized to the SLA lead time",
    "MSI has been sensitized to the established SMS distribution routines",
]


def suggest_notes(dev: str) -> str:
    d = dev or ""
    if "Manual SLA" in d:
        return "Incident priority downgraded, after manual check of incident p2 duration, no deviation found."
    if "SLA Breached" in d and "No SMS" in d:
        return "Incident was flagged as a security incident, sms distribution is at the discretion of Incident manager and MOD"
    if "SLA Breached" in d:
        return "After manual observation, no SLA breaches could be identified"
    if "Driftinfo" in d and "No SMS" in d:
        return "Incident was raised retrospectively for logging purpose due to it being resolved when it reached MSI"
    if "Driftinfo" in d:
        return "Incident was raised retrospectively for logging purpose due to it being resolved when it reached MSI"
    if "No SMS" in d:
        return "Incident was raised retrospectively for logging purpose due to it being resolved when it reached MSI"
    return ""


def suggest_measures(dev: str) -> str:
    d = dev or ""
    if "SLA Breached" in d:
        return "Incident management team has been sensitized to the SLA lead time"
    if "No SMS" in d and "SLA" not in d:
        return "No measures taken"
    return "No measures taken"


def fmt_duration(days: float | None) -> str:
    if days is None or (isinstance(days, float) and math.isnan(days)):
        return "—"
    td = timedelta(days=days)
    h, rem = divmod(int(td.total_seconds()), 3600)
    m = rem // 60
    return f"{h}h {m:02d}m"


def sla_color(status: str) -> str:
    colors = {
        "SLA Achieved": "🟢",
        "SLA Breached": "🔴",
        "Manual SLA Check Needed": "🟡",
    }
    return colors.get(status, "⚪")


def deviation_badge(val: str) -> str:
    if val == "Deviation Found":
        return "🔴 Deviation Found"
    return "🟢 No Deviations"


# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🔍 GITK Checker")
    st.markdown("---")

    st.markdown("### 1 · Incident Data")
    incidents_file = st.file_uploader(
        "incidents.json  *(columns A–Q)*",
        type=["json"],
        key="incidents",
    )

    st.markdown("### 2 · Outage Data")
    outages_file = st.file_uploader(
        "outages.json  *(task / begin / end)*",
        type=["json"],
        key="outages",
    )

    st.markdown("---")
    st.markdown("### Filters")
    filter_deviations_only = st.toggle("Show deviations only", value=False)
    filter_priority = []
    filter_week = st.text_input("Week (e.g. 2026 - V13)", "")



# ─── Main ─────────────────────────────────────────────────────────────────────

st.markdown("# GITK Deviation Checker")
st.markdown("Upload your incident and outage JSON files to calculate deviations.")

if incidents_file is None:
    st.info("👈  Upload **incidents.json** in the sidebar to get started.")

    # Show sample
    st.markdown("---")
    st.markdown("### Sample data preview")
    sample = [
        {
            "number": "LFINC0000001",
            "created": "2026-03-01T08:00:00",
            "priority_upgrade_time": "2026-03-01T08:10:00",
            "technical_resolve_time": "2026-03-01T11:30:00",
            "title": "Example: Login service unavailable",
            "priority": "2 - High",
            "assigned_to": "Demo User",
            "related_incident_report": False,
            "problem": None,
            "driftinfo": None,
            "sms_log": "2026-03-01 08:05 - Demo (SMS log)\nTo: Someone",
            "p2_without_immediate_user_impact": False,
        },
        {
            "number": "LFINC0000002",
            "created": "2026-03-03T09:00:00",
            "priority_upgrade_time": None,
            "technical_resolve_time": "2026-03-03T09:55:00",
            "title": "Example: Payment gateway timeout",
            "priority": "1 - Top",
            "assigned_to": "Demo User",
            "related_incident_report": True,
            "problem": "LFPRB999999",
            "driftinfo": True,
            "sms_log": "2026-03-03 09:02 - Demo (SMS log)\nTo: Team",
            "p2_without_immediate_user_impact": False,
        },
    ]
    results = process_records(sample, [])
    df_sample = pd.DataFrame([{
        "Ticket":         r["_ticket_no"],
        "Week":           r["_week"],
        "Priority":       r.get("priority", ""),
        "Duration":       fmt_duration(r["_incident_duration_days"]),
        "SLA":            sla_color(r["_sla_status"]) + " " + r["_sla_status"],
        "Deviations":     deviation_badge(r["_check_deviations"]),
        "Details":        r["_identified_deviation"] or "—",
    } for r in results])
    st.dataframe(df_sample, use_container_width=True, hide_index=True)
    st.stop()


# ─── Load data ────────────────────────────────────────────────────────────────

incidents_raw = load_json(incidents_file)
outages_raw   = load_json(outages_file) or []

if incidents_raw is None:
    st.stop()

results = process_records(incidents_raw, outages_raw)

# ─── Apply filters ────────────────────────────────────────────────────────────

filtered = list(results)  # copy so we don't mutate
if filter_deviations_only:
    filtered = [r for r in filtered if r["_check_deviations"] == "Deviation Found"]
if filter_priority:  # empty list = show all
    filtered = [r for r in filtered if str(r.get("priority", "")).strip() in filter_priority]
if filter_week.strip():
    filtered = [r for r in filtered if filter_week.strip().lower() in r["_week"].lower()]

# ─── Summary metrics ──────────────────────────────────────────────────────────

total       = len(results)
deviations  = sum(1 for r in results if r["_check_deviations"] == "Deviation Found")
sla_breach  = sum(1 for r in results if r["_check_sla"] > 0)
no_sms      = sum(1 for r in results if r["_check_sms"] > 0)
no_report   = sum(1 for r in results if r["_check_incident_report"] > 0)
no_drift    = sum(1 for r in results if r["_check_drift"] > 0)

st.markdown("---")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Tickets",    total)
c2.metric("⚠️ Deviations",   deviations,  delta=f"{round(deviations/total*100)}%" if total else None, delta_color="inverse")
c3.metric("🔴 SLA Issues",   sla_breach)
c4.metric("📵 No SMS",       no_sms)
c5.metric("📄 No Report",    no_report)

st.markdown("---")

# ─── Deviation breakdown chart ────────────────────────────────────────────────

if deviations > 0:
    with st.expander("📊 Deviation breakdown", expanded=True):
        breakdown = {
            "SLA Breach / Manual Check": sla_breach,
            "No Driftinfo":              no_drift,
            "No SMS":                    no_sms,
            "No Incident Report":        no_report,
        }
        df_bd = pd.DataFrame(list(breakdown.items()), columns=["Type", "Count"])
        df_bd = df_bd[df_bd["Count"] > 0]
        st.bar_chart(df_bd.set_index("Type"), color="#f85149")

# ─── Results table ────────────────────────────────────────────────────────────

st.markdown(f"### Results  `{len(filtered)} of {total} tickets`")

if not filtered:
    st.warning("No tickets match the current filters.")
else:
    # ─── Sort controls ────────────────────────────────────────────────────
    sort_col, sort_dir = st.columns([2, 1])
    with sort_col:
        sort_by = st.selectbox("Sort by", ["Week", "Ticket", "Duration", "SLA Status"], label_visibility="collapsed")
    with sort_dir:
        sort_asc = st.toggle("Ascending", value=True)

    sort_key = {"Week": "_week", "Ticket": "_ticket_no", "Duration": "_incident_duration_days", "SLA Status": "_sla_status"}[sort_by]
    filtered = sorted(filtered, key=lambda r: (r.get(sort_key) or ""), reverse=not sort_asc)

    # ─── Custom table with per-row copy buttons ───────────────────────────
    table_rows_html = ""
    for r in filtered:
        dur    = r["_incident_duration_days"]
        week   = r["_week"]
        ticket = r["_ticket_no"]
        pri    = str(r.get("priority", ""))
        dur_s  = fmt_duration(dur)
        sla    = r["_sla_status"]
        sla_dot = "🟢" if sla == "SLA Achieved" else ("🟡" if "Manual" in sla else "🔴")
        drift  = "🟢" if r["_check_drift"] == 0 else "🔴"
        sms    = "🟢" if r["_check_sms"]   == 0 else "🔴"
        rep    = "🟢" if r["_check_incident_report"] == 0 else "🔴"
        dev    = r["_check_deviations"]
        dev_dot   = "🔴" if dev == "Deviation Found" else "🟢"
        dev_label = "Deviation Found" if dev == "Deviation Found" else "No Deviations"
        deviation_text = r["_identified_deviation"] or "—"

        # Copy text: Excel column order Week | Ticket | Identified deviation (tab-separated)
        copy_text = f"{week}\t{ticket}\t{deviation_text}"
        copy_js   = copy_text.replace("'", "\'")

        table_rows_html += f"""
        <tr>
            <td>{week}</td>
            <td><code>{ticket}</code></td>
            <td>{pri}</td>
            <td>{dur_s}</td>
            <td>{sla_dot} {sla}</td>
            <td style="text-align:center">{drift}</td>
            <td style="text-align:center">{sms}</td>
            <td style="text-align:center">{rep}</td>
            <td>{dev_dot} {dev_label}</td>
            <td class="dev-text">{deviation_text}</td>
            <td>
                <input class="copy-input" type="text" value="{copy_js}" readonly
                    onclick="this.select()" title="Click then Ctrl+C to copy">
            </td>
        </tr>"""

    st.markdown(f"""
<style>
.gitk-table {{ width:100%; border-collapse:collapse; font-size:0.82rem; }}
.gitk-table th {{
    background:#161b22; color:#8b949e; text-transform:uppercase;
    font-size:0.7rem; letter-spacing:0.06em; padding:8px 10px;
    border-bottom:1px solid #30363d; text-align:left; white-space:nowrap;
    user-select:none;
}}
.gitk-table td {{ padding:7px 10px; border-bottom:1px solid #21262d; color:#c9d1d9; vertical-align:middle; }}
.gitk-table tr:hover td {{ background:#161b22; }}
.gitk-table code {{ font-family:monospace; font-size:0.8rem; color:#79c0ff; }}
.dev-text {{ color:#f85149; font-size:0.78rem; min-width:200px; }}
.copy-input {{
    background:#161b22; border:1px solid #30363d; border-radius:4px;
    color:#79c0ff; font-family:monospace; font-size:0.72rem;
    padding:3px 6px; width:260px; cursor:text;
}}
.copy-input:focus {{ outline:2px solid #388bfd; border-color:#388bfd; }}
</style>
<table class="gitk-table" id="gitk-main-table">
  <thead><tr>
    <th>Week</th><th>Ticket</th>
    <th>Pri</th><th>Duration</th>
    <th>SLA Status</th><th>Drift</th><th>SMS</th><th>Report</th>
    <th>Result</th><th>Identified Deviations</th><th>Click to select → Ctrl+C</th>
  </tr></thead>
  <tbody>{table_rows_html}</tbody>
</table>
""", unsafe_allow_html=True)
    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)

    # ─── Notes & Measures editor ──────────────────────────────────────────

    st.markdown("---")
    st.markdown("### 📋 Notes & Measures")
    st.caption("Notes and Measures are pre-filled with suggestions — edit any cell to customise. Select from the dropdown or type a custom value.")

    # Use session_state so edits survive reruns
    filter_key = tuple(r["_ticket_no"] for r in filtered)
    if st.session_state.get("nm_filter_key") != filter_key:
        nm_rows = []
        for r in filtered:
            dev = r["_identified_deviation"] or ""
            note = suggest_notes(dev)
            meas = suggest_measures(dev)
            nm_rows.append({
                "Week":                 r["_week"],
                "Ticket":               r["_ticket_no"],
                "Identified Deviation": dev,
                "Notes":                note if note in NOTES_OPTIONS else None,
                "Measures Taken":       meas if meas in MEASURES_OPTIONS else None,
            })
        st.session_state["nm_data"]       = pd.DataFrame(nm_rows)
        st.session_state["nm_filter_key"] = filter_key

    edited_df = st.data_editor(
        st.session_state["nm_data"],
        column_config={
            "Week":                 st.column_config.TextColumn(disabled=True, width="small"),
            "Ticket":               st.column_config.TextColumn(disabled=True, width="small"),
            "Identified Deviation": st.column_config.TextColumn(disabled=True, width="medium"),
            "Notes":          st.column_config.SelectboxColumn(
                                  options=NOTES_OPTIONS, width="large",
                              ),
            "Measures Taken": st.column_config.SelectboxColumn(
                                  options=MEASURES_OPTIONS, width="medium",
                              ),
        },
        hide_index=True,
        use_container_width=True,
        key="notes_editor",
    )

    # Copy all rows tab-separated, same sort order as the results table
    copy_df = edited_df.copy()
    copy_sort_col = {"Week": "Week", "Ticket": "Ticket"}.get(sort_by, "Week")
    copy_df = copy_df.sort_values(copy_sort_col, ascending=sort_asc)

    copy_all = "\n".join(
        f"{row['Week']}\t{row['Ticket']}\t{row['Identified Deviation']}\t{row['Notes']}\t{row['Measures Taken']}"
        for _, row in copy_df.iterrows()
    )
    st.text_area(
        "📋 Select all (Ctrl+A) → Copy (Ctrl+C) → Paste in Excel",
        value=copy_all,
        height=160,
    )

    # ─── Per-row detail drill-down ────────────────────────────────────────

    st.markdown("---")
    st.markdown("### 🔎 Ticket detail")

    ticket_ids = [r["_ticket_no"] for r in filtered]
    selected_id = st.selectbox("Select ticket", ticket_ids)

    selected = next((r for r in filtered if r["_ticket_no"] == selected_id), None)
    if selected:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Input fields")
            st.json({
                "number":                    selected.get("number"),
                "created":                   str(selected.get("created", "")),
                "priority_upgrade_time":     str(selected.get("priority_upgrade_time", "")) or None,
                "technical_resolve_time":    str(selected.get("technical_resolve_time", "")),
                "priority":                  selected.get("priority"),
                "assigned_to":               selected.get("assigned_to"),
                "related_incident_report":   selected.get("related_incident_report"),
                "problem":                   selected.get("problem"),
                "driftinfo":                 selected.get("driftinfo"),
                "sms_log":                   "✅ Present" if selected.get("sms_log") else "❌ Missing",
            }, expanded=True)

        with col2:
            st.markdown("#### Calculated results")
            st.json({
                "R – Priority Upgrade":        str(selected["_priority_upgrade"]),
                "S – Duration":                fmt_duration(selected["_incident_duration_days"]),
                "T – SLA Status":              selected["_sla_status"],
                "U – Check SLA":               selected["_check_sla"],
                "V – Check Drift":             selected["_check_drift"],
                "W – Check SMS":               selected["_check_sms"],
                "X – Check Problem":           selected["_check_problem"],
                "Y – Check Incident Report":   selected["_check_incident_report"],
                "Z – Check Deviations":        selected["_check_deviations"],
                "AF – Week":                   selected["_week"],
                "AH – Identified Deviation":   selected["_identified_deviation"] or "None",
            }, expanded=True)

    # ─── Export ───────────────────────────────────────────────────────────────

    st.markdown("---")
    export_rows = []
    for r in filtered:
        export_rows.append({
            "AF – Week":                r["_week"],
            "AG – Ticket No":           r["_ticket_no"],
            "R – Priority Upgrade":     str(r["_priority_upgrade"]),
            "S – Duration (days)":      round(r["_incident_duration_days"], 4) if r["_incident_duration_days"] is not None else "",
            "T – SLA Status":           r["_sla_status"],
            "U – Check SLA":            r["_check_sla"],
            "V – Check Drift":          r["_check_drift"],
            "W – Check SMS":            r["_check_sms"],
            "X – Check Problem":        r["_check_problem"],
            "Y – Check Incident Report":r["_check_incident_report"],
            "Z – Check Deviations":     r["_check_deviations"],
            "AH – Identified Deviation":r["_identified_deviation"],
        })

    csv = pd.DataFrame(export_rows).to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️  Export results as CSV",
        data=csv,
        file_name="gitk_results.csv",
        mime="text/csv",
    )
