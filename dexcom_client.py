"""
Dexcom Share API client - ported from the DexcomG7 Omarchy plugin's
scripts/dexcom-status (https://github.com/Boricuatec/DexcomG7).

Same reverse-engineered two-step login flow (AuthenticatePublisherAccount ->
LoginPublisherAccountById) and the same application IDs, trend tables, and
mg/dL<->mmol/L conversion as that script and pydexcom. Refactored from a
CLI/subprocess script into an importable module returning plain dicts, since
this app polls in a background thread instead of shelling out per poll.

Unofficial API: not affiliated with or supported by Dexcom. It can change or
break without notice. Not a medical device - informational use only.
"""
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request

APPLICATION_ID_US = "d89443d2-327c-4a6f-89e5-496bbb0317db"
APPLICATION_IDS = {
    "share2": APPLICATION_ID_US,      # US
    "shareous1": APPLICATION_ID_US,   # outside US
    "share": "d8665ade-9673-4e27-9ff6-92db4ce13d13",  # Japan
}

TREND_ARROWS = {
    "DoubleUp": "⇈",
    "SingleUp": "↑",
    "FortyFiveUp": "↗",
    "Flat": "→",
    "FortyFiveDown": "↘",
    "SingleDown": "↓",
    "DoubleDown": "⇊",
    "NotComputable": "?",
    "RateOutOfRange": "?",
    "None": "?",
}

TREND_WORDS = {
    "DoubleUp": "rising quickly",
    "SingleUp": "rising",
    "FortyFiveUp": "rising slightly",
    "Flat": "steady",
    "FortyFiveDown": "falling slightly",
    "SingleDown": "falling",
    "DoubleDown": "falling quickly",
    "NotComputable": "unable to determine trend",
    "RateOutOfRange": "trend unavailable",
    "None": "unknown",
}

MMOL_L_PER_MGDL = 0.0555

# The exact placeholder values written into a freshly-created credentials
# file (see settings_store.ensure_credentials_template, which imports these
# same constants so the two can never drift apart). Attempting a real login
# with these - or with only one of them replaced, e.g. a real username paired
# with the still-placeholder password - would send a failed-login request to
# Dexcom for whatever real account name is present, risking the account
# lockout the original plugin's troubleshooting notes warn about. poll()
# refuses to even attempt login while either field still matches.
PLACEHOLDER_USERNAME = "you@example.com"
PLACEHOLDER_PASSWORD = "your-dexcom-password"

READING_INTERVAL_SECONDS = 300
PUBLISH_BUFFER_SECONDS = 20
MIN_POLL_SECONDS = 15


class DexcomError(Exception):
    def __init__(self, code, tooltip=None):
        super().__init__(tooltip or code)
        self.code = code
        self.tooltip = tooltip or code


def app_data_dir():
    """Roaming per-user config dir: credentials.env and settings.json live here."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "DexcomG7")
    return os.path.expanduser("~/.config/dexcom-g7-desktop")


def cache_dir():
    """Local (non-roaming) per-user cache dir: the Share session token lives here."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "DexcomG7")
    return os.path.expanduser("~/.cache/dexcom-g7-desktop")


def default_credentials_path():
    return os.path.join(app_data_dir(), "credentials.env")


def session_cache_path():
    return os.path.join(cache_dir(), "session.json")


def format_value(mgdl, units):
    if units == "mmol":
        return f"{round(mgdl * MMOL_L_PER_MGDL, 1):.1f}"
    return str(int(round(mgdl)))


def unit_label(units):
    return "mmol/L" if units == "mmol" else "mg/dL"


def load_credentials(path):
    values = {}
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return values


def credentials_look_unconfigured(creds):
    """True if either field is still the unedited template placeholder."""
    return (
        creds.get("DEXCOM_USERNAME") == PLACEHOLDER_USERNAME
        or creds.get("DEXCOM_PASSWORD") == PLACEHOLDER_PASSWORD
    )


def server_base(server):
    return f"https://{server}.dexcom.com/ShareWebServices/Services"


def _api_post(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "application/json",
            "User-Agent": "Dexcom Share/3.0.2.11",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8")


def _api_post_checked(url, payload, step):
    try:
        body = _api_post(url, payload)
    except urllib.error.HTTPError as e:
        detail = e.code
        try:
            err = json.loads(e.read().decode("utf-8"))
            detail = err.get("Code") or detail
        except Exception:
            pass
        raise DexcomError(f"{step}_http_error", f"Dexcom {step} failed: {detail}")
    except urllib.error.URLError as e:
        raise DexcomError(f"{step}_network_error", f"Dexcom {step} failed: {e.reason}")
    return body.strip().strip('"')


def login(creds, server):
    username = creds.get("DEXCOM_USERNAME")
    password = creds.get("DEXCOM_PASSWORD")
    if not username or not password:
        raise DexcomError(
            "no_credentials",
            "Set DEXCOM_USERNAME/DEXCOM_PASSWORD in the credentials file (see README)",
        )

    app_id = APPLICATION_IDS[server]
    base = server_base(server)

    account_id = _api_post_checked(
        base + "/General/AuthenticatePublisherAccount",
        {"accountName": username, "password": password, "applicationId": app_id},
        "authenticate",
    )
    if not account_id or account_id == "00000000-0000-0000-0000-000000000000":
        raise DexcomError("login_rejected", "Dexcom authentication rejected (bad username/password?)")

    session_id = _api_post_checked(
        base + "/General/LoginPublisherAccountById",
        {"accountId": account_id, "password": password, "applicationId": app_id},
        "login",
    )
    if not session_id or session_id == "00000000-0000-0000-0000-000000000000":
        raise DexcomError("login_rejected", "Dexcom login rejected (bad username/password?)")

    try:
        path = session_cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({"sessionId": session_id, "server": server, "ts": time.time()}, f)
        if sys.platform != "win32":
            os.chmod(path, 0o600)
    except OSError:
        pass

    return session_id


def cached_session(server):
    try:
        with open(session_cache_path(), "r") as f:
            data = json.load(f)
        if data.get("server") == server and time.time() - data.get("ts", 0) < 12 * 3600:
            return data.get("sessionId")
    except (FileNotFoundError, ValueError, KeyError):
        pass
    return None


def fetch_readings(server, session_id, minutes=60, max_count=12):
    url = (
        server_base(server)
        + f"/Publisher/ReadPublisherLatestGlucoseValues?sessionId={session_id}&minutes={minutes}&maxCount={max_count}"
    )
    req = urllib.request.Request(
        url,
        data=b"",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "application/json",
            "User-Agent": "Dexcom Share/3.0.2.11",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_dotnet_date(value):
    match = re.search(r"Date\((\d+)", value or "")
    if not match:
        return None
    return int(match.group(1)) / 1000.0


def classify(mgdl, minutes_ago, thresholds, stale_after):
    if minutes_ago is not None and minutes_ago > stale_after:
        return "stale"
    if mgdl <= thresholds["urgentLow"]:
        return "urgent_low"
    if mgdl <= thresholds["low"]:
        return "low"
    if mgdl >= thresholds["urgentHigh"]:
        return "urgent_high"
    if mgdl >= thresholds["high"]:
        return "high"
    return "normal"


def summarize_history(readings, units):
    values = [r.get("Value") for r in readings if isinstance(r.get("Value"), (int, float))]
    if len(values) < 2:
        return None

    lo, hi = min(values), max(values)
    newest, oldest = values[0], values[-1]  # API returns newest-first
    delta = newest - oldest

    if delta >= 15:
        direction = f"rising (+{format_value(abs(delta), units)} {unit_label(units)})"
    elif delta <= -15:
        direction = f"falling (-{format_value(abs(delta), units)} {unit_label(units)})"
    else:
        direction = "steady overall"

    span_minutes = 5 * (len(values) - 1)
    lo_s, hi_s = format_value(lo, units), format_value(hi, units)
    return f"Last {span_minutes} min: {lo_s}-{hi_s} {unit_label(units)} ({direction})"


def poll(settings):
    """
    settings: dict with keys credentialsPath, server, lowThreshold,
    highThreshold, urgentLow, urgentHigh, staleAfterMinutes, units,
    showHistoryInTooltip, historyWindowMinutes, showTrendWord, graphWindowMinutes.

    Returns the same shape dexcom-status printed as JSON: either
    {"ok": True, "mgdl": ..., "series": [...], "thresholds": {...}, ...}
    or {"ok": False, "error": ..., "tooltip": ...}.
    """
    creds_path = settings.get("credentialsPath") or default_credentials_path()
    server = settings.get("server", "share2")
    thresholds_mgdl = {
        "low": settings.get("lowThreshold", 70),
        "high": settings.get("highThreshold", 180),
        "urgentLow": settings.get("urgentLow", 55),
        "urgentHigh": settings.get("urgentHigh", 250),
    }
    stale_after = settings.get("staleAfterMinutes", 20)
    units = settings.get("units", "mgdl")
    show_history = settings.get("showHistoryInTooltip", True)
    history_minutes = settings.get("historyWindowMinutes", 60)
    show_trend_word = settings.get("showTrendWord", False)
    graph_minutes = settings.get("graphWindowMinutes", 180)

    creds = load_credentials(creds_path)
    if not creds:
        return {
            "ok": False,
            "error": "no_credentials",
            "tooltip": f"Create {creds_path} - see README",
        }
    if credentials_look_unconfigured(creds):
        return {
            "ok": False,
            "error": "placeholder_credentials",
            "tooltip": (
                f"{creds_path} still has the example username/password - "
                "edit it with your real Dexcom Share login, then Refresh now."
            ),
        }

    window = max(15, graph_minutes, history_minutes if show_history else 0)
    max_count = min(288, max(2, math.ceil(window / 5) + 1))

    session_id = cached_session(server)
    readings = None
    try:
        for attempt in range(2):
            if not session_id:
                session_id = login(creds, server)
            try:
                readings = fetch_readings(server, session_id, minutes=window, max_count=max_count)
                break
            except urllib.error.HTTPError as e:
                if e.code in (500, 401) and attempt == 0:
                    session_id = None
                    continue
                raise DexcomError("fetch_http_error", f"Dexcom read failed: HTTP {e.code}")
            except urllib.error.URLError as e:
                raise DexcomError("fetch_network_error", f"Dexcom read failed: {e.reason}")
    except DexcomError as e:
        return {"ok": False, "error": e.code, "tooltip": e.tooltip}

    if not readings:
        return {"ok": False, "error": "no_data", "tooltip": "No recent Dexcom readings"}

    latest = readings[0]
    mgdl = latest.get("Value")
    trend = str(latest.get("Trend", "None"))
    wt = latest.get("WT") or latest.get("ST") or latest.get("DT") or ""
    reading_ts = parse_dotnet_date(wt)

    seconds_ago = None
    minutes_ago = None
    if reading_ts is not None:
        seconds_ago = max(0, int(time.time() - reading_ts))
        minutes_ago = seconds_ago // 60

    status = classify(mgdl, minutes_ago, thresholds_mgdl, stale_after)
    arrow = TREND_ARROWS.get(trend, "?")
    display_value = format_value(mgdl, units)
    unit = unit_label(units)
    trend_text = TREND_WORDS.get(trend, trend) if show_trend_word else trend

    age_text = f"{minutes_ago} min ago" if minutes_ago is not None else "time unknown"
    tooltip = f"{display_value} {unit}, {trend_text} - {age_text}"
    if status == "stale":
        tooltip = f"Last reading {age_text}: {display_value} {unit} (sensor may be disconnected)"
    elif show_history:
        history_line = summarize_history(readings, units)
        if history_line:
            tooltip += "\n" + history_line

    series = []
    now = time.time()
    for r in readings:
        v = r.get("Value")
        if not isinstance(v, (int, float)):
            continue
        ts = parse_dotnet_date(r.get("WT") or r.get("ST") or r.get("DT") or "")
        series.append(
            {
                "secondsAgo": max(0, int(now - ts)) if ts is not None else None,
                "raw": v,
                "value": float(format_value(v, units)),
            }
        )
    series.reverse()  # oldest first, natural left-to-right plotting

    return {
        "ok": True,
        "mgdl": display_value,
        "rawMgdl": mgdl,
        "unit": unit,
        "trendArrow": arrow,
        "trendLabel": trend,
        "minutesAgo": minutes_ago,
        "secondsAgo": seconds_ago,
        "status": status,
        "tooltip": tooltip,
        "series": series,
        "thresholds": {
            "low": float(format_value(thresholds_mgdl["low"], units)),
            "high": float(format_value(thresholds_mgdl["high"], units)),
            "urgentLow": float(format_value(thresholds_mgdl["urgentLow"], units)),
            "urgentHigh": float(format_value(thresholds_mgdl["urgentHigh"], units)),
        },
    }


def next_poll_delay_seconds(result, settings):
    """Adaptive poll scheduling, ported from Dexcom.qml's scheduleNextPoll()."""
    fallback = max(30, settings.get("pollIntervalSeconds", 60))
    if result.get("ok") and result.get("status") != "stale" and isinstance(result.get("secondsAgo"), int):
        wait = (READING_INTERVAL_SECONDS + PUBLISH_BUFFER_SECONDS) - result["secondsAgo"]
        delay = max(MIN_POLL_SECONDS, wait)
        return min(delay, fallback)
    return fallback
