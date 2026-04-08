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
.gitk-table th.sortable {{ cursor:pointer; }}
.gitk-table th.sortable:hover {{ color:#c9d1d9; }}
.gitk-table th.sort-asc::after  {{ content:" ▲"; color:#388bfd; }}
.gitk-table th.sort-desc::after {{ content:" ▼"; color:#388bfd; }}
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
    <th class="sortable" onclick="sortTable(0)">Week</th>
    <th class="sortable" onclick="sortTable(1)">Ticket</th>
    <th>Pri</th><th>Duration</th>
    <th>SLA Status</th><th>Drift</th><th>SMS</th><th>Report</th>
    <th>Result</th><th>Identified Deviations</th><th>Click to select → Ctrl+C</th>
  </tr></thead>
  <tbody>{table_rows_html}</tbody>
</table>
<script>
var _sortDir = {{}};
function sortTable(col) {{
    var tbl = document.getElementById("gitk-main-table");
    if (!tbl) return;
    var tbody = tbl.tBodies[0];
    var rows = Array.from(tbody.rows);
    var asc = !_sortDir[col];
    _sortDir = {{}};
    _sortDir[col] = asc;
    rows.sort(function(a, b) {{
        var ta = a.cells[col].innerText.trim();
        var tb = b.cells[col].innerText.trim();
        return asc ? ta.localeCompare(tb) : tb.localeCompare(ta);
    }});
    rows.forEach(function(r) {{ tbody.appendChild(r); }});
    var ths = tbl.tHead.rows[0].cells;
    for (var i = 0; i < ths.length; i++) {{
        ths[i].classList.remove("sort-asc", "sort-desc");
    }}
    ths[col].classList.add(asc ? "sort-asc" : "sort-desc");
}}
</script>
""", unsafe_allow_html=True)
    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)

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
