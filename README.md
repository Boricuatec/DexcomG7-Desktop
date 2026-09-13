# Dexcom G7 Desktop (Windows)

<p align="center">
  <a href="https://paypal.me/Boricuatec"><img alt="Donate via PayPal" src="https://img.shields.io/badge/donate-PayPal-00457C?logo=paypal&logoColor=white"></a>
  <img alt="Donate via Bitcoin" src="https://img.shields.io/badge/donate-Bitcoin-f7931a?logo=bitcoin&logoColor=white">
</p>

<p align="center">
  BTC: <code>38qF99r4PUsnh46KgLwpBcg7xvjBdgWotK</code>
</p>

A Windows system-tray port of the [DexcomG7 Omarchy plugin](https://github.com/Boricuatec/DexcomG7)
— live glucose value, trend arrow, and a click-to-open popup graph, pulled
straight from the Dexcom Share API. Same unofficial API logic, no Omarchy/
Hyprland/QML dependency.

Built for personal use, distributed like the original plugin (source you run
yourself) — not published to the Microsoft Store or Mac App Store. See the
notes at the bottom for why.

If this is useful to you and you'd like to contribute, every bit donated
through the PayPal link or Bitcoin address above goes straight into my son's
college fund — same as the original plugin. No pressure at all.

## Disclaimer

Independent, unofficial project. **Not affiliated with, endorsed by, or
supported by Dexcom.** It talks to a reverse-engineered API Dexcom has not
published and can change or break at any time without notice. Not a medical
device — informational use only. Always follow the official Dexcom app and
your care team's guidance.

## What it does

- Tray icon shows the current glucose value, colored by range (dark = normal,
  orange = low/high, red = urgent low/high, gray = stale/error). Hover for a
  tooltip with the trend, reading age, and a rolling history summary.
- Click the icon (or the "Open" menu item) for a popup with a graph of recent
  readings, shaded threshold lines, and 3h/6h/12h/24h range buttons. Click a
  point on the graph to see its exact value and time.
- Gear icon in the popup swaps the graph for four threshold sliders (Urgent
  High / High / Low / Urgent Low); releasing a slider saves it immediately.
- Adaptive polling around Dexcom's ~5 minute reporting cadence, same as the
  original plugin — not a fixed interval hammering the API.
- **Settings...** menu item for region, units, fallback poll interval, stale
  timeout, credentials path, and tooltip toggles.
- **Start with Windows** checkbox right in the tray menu — adds/removes a
  per-user registry Run entry, no installer needed.

## Setup

1. **Python 3.9+** (the [python.org](https://www.python.org/downloads/windows/)
   Windows installer bundles Tk, which this app needs — no extra install for
   that part).
2. Install the two dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run it:
   ```
   python tray_app.py
   ```
   On first run it creates `%APPDATA%\DexcomG7\credentials.env` and shows a
   tray notification. Use the tray icon's **Edit credentials...** menu item
   to open that file, fill in `DEXCOM_USERNAME`/`DEXCOM_PASSWORD`, save, then
   **Refresh now**.

   The Dexcom account **must be the sensor wearer's own account** (Share
   turned on in their own Dexcom G7 app) — a Follow/Caregiver account
   authenticates fine but returns no readings. See
   `credentials.env.example` for more gotchas ported from the original
   plugin's troubleshooting notes.

## Settings

- Thresholds and the graph range: edit from the popup (gear icon / range
  buttons).
- Region, units, fallback poll interval, stale timeout, credentials path,
  and tooltip toggles: tray menu → **Settings...**.
- Start with Windows: tray menu checkbox, no installer needed (writes a
  per-user `HKCU\...\Run` registry entry — see `autostart.py`).

All of it persists to `%APPDATA%\DexcomG7\settings.json` (same keys as the
original plugin's `manifest.json`), so you can also hand-edit that file if
you'd rather not use the dialog.

## Packaging as a standalone .exe (optional)

Not done yet, but straightforward when you want it:
```
pip install pyinstaller
pyinstaller --onefile --windowed --name "Dexcom G7" tray_app.py
```

## Testing status

Built and logic-tested on Linux (no Windows box available in this dev
environment): `dexcom_client.py`'s login/polling/classification logic is
pure stdlib and was verified here against mocked HTTP responses, and
`icon_render.py`'s icon generation was verified visually. **The tray icon +
popup window (pystray/tkinter) has not been run on real Windows yet** —
please smoke-test `python tray_app.py` on your PC before relying on it.
Likely rough edges: font fallback if neither Segoe UI nor Arial Bold is
found, and the exact tray icon size Windows prefers at your display scaling.
The settings dialog (`settings_dialog.py`) and "Start with Windows"
(`autostart.py`) are equally untested on real Windows — they compile and the
autostart module's non-Windows no-op path is verified, but the registry
write and the dialog's widgets themselves need a live smoke test.

## Relationship to the Omarchy plugin

`dexcom_client.py` is a straight refactor of the plugin's
`scripts/dexcom-status` (CLI script → importable module returning dicts
instead of printing JSON) — same login flow, application IDs, and trend/
classification logic. `popup.py`'s graph and threshold sliders are a
tkinter port of `Dexcom.qml`'s Canvas/Slider sections (same scaling math,
same colors). The Omarchy plugin's `qs.Ui` bar-widget APIs
(`WidgetButton`/`Panel`/`KeyboardPanel`/`omarchy bar set`) have no Windows
equivalent, so the whole UI shell (`tray_app.py`, `popup.py`,
`icon_render.py`, `settings_store.py`) is new code, not a port.

## Why this isn't on the Microsoft Store / Mac App Store

This was scoped down from an app-store-sellable product to a personal tool
you run yourself, on purpose:

- It depends on Dexcom's **unofficial** Share API (the same one the Follow
  app uses), not a published developer/partner API. Fine for a free tool
  you run yourself; commercializing it through store review raises Dexcom
  ToS and app-review risk that isn't worth it for a family tool.
- Store review for health-adjacent apps is stricter, and Dexcom could
  change or block this endpoint at any time with no recourse for someone
  who paid for the app.

If you ever do want real commercial distribution, the legitimate path is
Dexcom's official developer/partner API program, which is a different (and
slower) undertaking than this.

## License

MIT, matching the original plugin.
