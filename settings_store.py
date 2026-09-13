"""
Settings persistence: a JSON file in the app data dir, replacing Omarchy's
`omarchy bar set` mechanism. Same keys/defaults as the plugin's manifest.json
so the two stay easy to compare.
"""
import json
import os

import dexcom_client

DEFAULTS = {
    "credentialsPath": "",
    "server": "share2",
    "pollIntervalSeconds": 60,
    "lowThreshold": 70,
    "highThreshold": 180,
    "urgentLow": 55,
    "urgentHigh": 250,
    "staleAfterMinutes": 20,
    "units": "mgdl",
    "showHistoryInTooltip": True,
    "historyWindowMinutes": 60,
    "showTrendWord": False,
    "graphWindowMinutes": 180,
}


def settings_path():
    return os.path.join(dexcom_client.app_data_dir(), "settings.json")


def load():
    path = settings_path()
    values = dict(DEFAULTS)
    try:
        with open(path, "r") as f:
            stored = json.load(f)
        if isinstance(stored, dict):
            values.update({k: v for k, v in stored.items() if k in DEFAULTS})
    except (FileNotFoundError, ValueError):
        pass
    return values


def save(values):
    path = settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    to_write = {k: values.get(k, DEFAULTS[k]) for k in DEFAULTS}
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(to_write, f, indent=2)
    os.replace(tmp_path, path)


def ensure_credentials_template():
    """Writes a starter credentials.env next to settings.json if none exists yet."""
    path = dexcom_client.default_credentials_path()
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(
            "# Dexcom Share credentials for the DexcomG7 desktop tray app.\n"
            "#\n"
            "# This MUST be the sensor wearer's own Dexcom G7 app login (Share\n"
            "# turned on in that app's own Settings) - not a Follow-app account\n"
            "# and not a Caregiver account watching a Dependent. Both of those\n"
            "# authenticate fine but return an empty reading list.\n"
            "#\n"
            "# Fill in real values below and keep this file private.\n"
            "\n"
            "DEXCOM_USERNAME=you@example.com\n"
            "DEXCOM_PASSWORD=your-dexcom-password\n"
        )
    return path
