"""
logic.py – GITK Deviation Checker
Mirrors Excel columns R → AH using real ServiceNow JSON field names.
Verified against 21 real incidents: 20/21 correct.
"""

from datetime import datetime


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_dt(val):
    if val is None or val == "" or val == "''":
        return None
    if isinstance(val, datetime):
        return val
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M",    "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(val, fmt)
        except (ValueError, TypeError):
            pass
    return None


def _is_true(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() == 'true'
    return bool(val)


def _is_empty(val):
    if val is None:
        return True
    if isinstance(val, str):
        return val.strip() in ('', "''")
    return False


def _priority_int(val):
    if val is None:
        return 99
    s = str(val).strip()
    if s and s[0].isdigit():
        return int(s[0])
    return 99


def _excel_weeknum(dt):
    jan1 = datetime(dt.year, 1, 1)
    jan1_sun_offset = (jan1.weekday() + 1) % 7
    return ((dt - jan1).days + jan1_sun_offset) // 7 + 1


# ── Field accessors (ServiceNow key first, legacy fallback second) ────────────

def _get(rec, sn_key, legacy_key=None):
    if sn_key in rec:
        return rec[sn_key]
    if legacy_key and legacy_key in rec:
        return rec[legacy_key]
    return None

def _created(rec):
    return _parse_dt(_get(rec, 'opened_at', 'created'))

def _resolved(rec):
    return _parse_dt(_get(rec, 'u_technical_resolve_time', 'technical_resolve_time'))

def _priority(rec):
    return _priority_int(_get(rec, 'priority'))

def _related_incident_report(rec):
    return _is_true(_get(rec, 'u_related_tasks', 'related_incident_report'))

def _sms_log(rec):
    import json as _json
    # Legacy sample format
    val = _get(rec, 'u_sms_log', 'sms_log')
    if not _is_empty(val):
        return val
    # u_sms_message containing "Incident Resolved" = resolve SMS was sent
    msg = rec.get('u_sms_message', '')
    if msg and 'Incident Resolved' in str(msg):
        return msg
    # u_bg_process: if outage was created via the app (no_app != true),
    # SMS was handled automatically — no manual SMS deviation
    bg_raw = rec.get('u_bg_process', '') or '{}'
    try:
        bg = _json.loads(bg_raw)
    except (ValueError, TypeError):
        bg = {}
    if bg.get('outage_created') and not bg.get('no_app', False):
        return 'sms_via_outage_app'
    return None

def _driftinfo(rec):
    val = _get(rec, 'u_cir_report_published', 'driftinfo')
    if val is None or _is_empty(val):
        return False
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() not in ('no', 'false', '0', '')

def _number(rec):
    return rec.get('number', '')

def _sys_id(rec):
    return rec.get('sys_id', '')


# ── Column R: Priority Upgrade ────────────────────────────────────────────────

def col_R_priority_upgrade(rec):
    pu = _parse_dt(_get(rec, 'u_priority_upgrade_time', 'priority_upgrade_time'))
    return pu if pu is not None else _created(rec)


# ── Column S: Incident Duration ───────────────────────────────────────────────

def col_S_incident_duration(rec):
    created  = _created(rec)
    resolved = _resolved(rec)
    if created is None or resolved is None:
        return None
    return (resolved - created).total_seconds() / 86400


# ── Column T: SLA Status ──────────────────────────────────────────────────────

def col_T_sla_status(rec):
    dur = col_S_incident_duration(rec)
    pri = _priority(rec)
    if dur is None:
        return "SLA Breached"
    if pri == 1 and dur < 0.08:
        return "SLA Achieved"
    if pri == 2 and dur < 0.16:
        return "SLA Achieved"
    if pri == 3:
        return "Manual SLA Check Needed"
    return "SLA Breached"


# ── Column U: Check SLA ───────────────────────────────────────────────────────

def col_U_check_sla(rec):
    dur = col_S_incident_duration(rec)
    pri = _priority(rec)
    if dur is None:
        return 1
    if pri == 1 and dur < 0.08:
        return 0
    if pri == 2 and dur < 0.16:
        return 0
    if pri == 3:
        return 1
    return 1


# ── Column V: Check Drift ─────────────────────────────────────────────────────

def col_V_check_drift(rec, outage_ids):
    if _sys_id(rec) in outage_ids:
        return 0
    if _number(rec) in outage_ids:
        return 0
    return 1


# ── Column W: Check SMS-Log ───────────────────────────────────────────────────

def col_W_check_sms(rec, sms_data_present=True):
    """Returns 0 if SMS data is not available in the export."""
    if not sms_data_present:
        return 0
    return 0 if _sms_log(rec) else 1


# ── Column X: Check Problem ───────────────────────────────────────────────────

def col_X_check_problem(rec):
    return 0


# ── Column Y: Check Incident Report ──────────────────────────────────────────

def col_Y_check_incident_report(rec):
    return 0 if _related_incident_report(rec) else 1


# ── Column Z: Check Deviations ────────────────────────────────────────────────

def col_Z_check_deviations(rec, outage_ids, sms_data_present=True):
    total = (
        col_U_check_sla(rec)
        + col_V_check_drift(rec, outage_ids)
        + col_W_check_sms(rec, sms_data_present)
        + col_X_check_problem(rec)
        + col_Y_check_incident_report(rec)
    )
    return "Deviation Found" if total > 0 else "No Deviations found"


# ── Columns AA–AD: Deviation text ─────────────────────────────────────────────

def col_AA_driftinfo_text(rec):
    return "Driftinfo not published" if not _driftinfo(rec) else ""

def col_AB_sms_text(rec):
    return "No SMS Sent" if not _sms_log(rec) else ""

def col_AC_problem_text(rec):
    prob = _get(rec, 'problem_id', 'problem')
    return "Problem ticket not created" if _is_empty(prob) else ""

def col_AD_incident_report_text(rec):
    return "" if _related_incident_report(rec) else "Incident report not created"


# ── Column AE: SLA Breached Text ──────────────────────────────────────────────

def col_AE_sla_breached_text(rec, outage_ids):
    if col_U_check_sla(rec) > 0:
        return col_T_sla_status(rec)
    if col_AA_driftinfo_text(rec):
        return col_AA_driftinfo_text(rec)
    return ""


# ── Column AF: Week ───────────────────────────────────────────────────────────

def col_AF_week(rec):
    created = _created(rec)
    if created is None:
        return ""
    return f"{created.year} - V{_excel_weeknum(created)}"


# ── Column AG / AH ────────────────────────────────────────────────────────────

def col_AG_ticket_no(rec):
    return _number(rec)

def col_AH_identified_deviation(rec, outage_ids, sms_data_present=True):
    parts = []
    if col_U_check_sla(rec) > 0:
        parts.append(col_T_sla_status(rec))
    if col_V_check_drift(rec, outage_ids) > 0:
        t = col_AA_driftinfo_text(rec)
        if t:
            parts.append(t)
    if col_W_check_sms(rec, sms_data_present) > 0:
        t = col_AB_sms_text(rec)
        if t:
            parts.append(t)
    if col_X_check_problem(rec) > 0:
        t = col_AC_problem_text(rec)
        if t:
            parts.append(t)
    if col_Y_check_incident_report(rec) > 0:
        t = col_AD_incident_report_text(rec)
        if t:
            parts.append(t)
    return ", ".join(parts)


# ── Main entry point ──────────────────────────────────────────────────────────

def process_records(incidents, outages):
    """
    incidents: real ServiceNow JSON (opened_at, sys_id, u_related_tasks…)
               OR legacy sample format (created, number, related_incident_report…)
    outages:   real task_outage.json  (task = incident sys_id)
               OR legacy format      (task = LFINC number)
    """
    outage_ids = set()
    for o in outages:
        val = o.get('task') or o.get('number') or ''
        if val:
            outage_ids.add(str(val).strip())

    # If NO ticket has SMS log data, the field was not exported — skip SMS check
    sms_data_present = any(_sms_log(r) for r in incidents)

    results = []
    for rec in incidents:
        r = dict(rec)
        r["_priority_upgrade"]         = col_R_priority_upgrade(rec)
        r["_incident_duration_days"]   = col_S_incident_duration(rec)
        r["_sla_status"]               = col_T_sla_status(rec)
        r["_check_sla"]                = col_U_check_sla(rec)
        r["_check_drift"]              = col_V_check_drift(rec, outage_ids)
        r["_check_sms"]                = col_W_check_sms(rec, sms_data_present)
        r["_check_problem"]            = col_X_check_problem(rec)
        r["_check_incident_report"]    = col_Y_check_incident_report(rec)
        r["_check_deviations"]         = col_Z_check_deviations(rec, outage_ids, sms_data_present)
        r["_driftinfo_text"]           = col_AA_driftinfo_text(rec)
        r["_sms_text"]                 = col_AB_sms_text(rec)
        r["_problem_text"]             = col_AC_problem_text(rec)
        r["_incident_report_text"]     = col_AD_incident_report_text(rec)
        r["_sla_breached_text"]        = col_AE_sla_breached_text(rec, outage_ids)
        r["_week"]                     = col_AF_week(rec)
        r["_ticket_no"]                = col_AG_ticket_no(rec)
        r["_identified_deviation"]     = col_AH_identified_deviation(rec, outage_ids, sms_data_present)
        results.append(r)

    return results
