"""
DexcomG7 desktop tray app - Windows-first port of the DexcomG7 Omarchy
plugin (https://github.com/Boricuatec/DexcomG7). Same unofficial Dexcom
Share API logic (dexcom_client.py), reimplemented as a system tray icon
(pystray) + a tkinter popup instead of a Quickshell/QML bar widget.

Not a medical device - informational use only. See README.md.
"""
import os
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser

import pystray

import autostart
import dexcom_client
import icon_render
import settings_store
from popup import Popup
from settings_dialog import SettingsDialog

APP_NAME = "Dexcom G7"


class TrayApp:
    def __init__(self):
        self.settings = settings_store.load()
        self.result = {"ok": False, "tooltip": "Starting…"}
        self.lock = threading.Lock()
        self.wake_event = threading.Event()
        self.stop_event = threading.Event()

        self.root = tk.Tk()
        self.root.withdraw()

        self.popup = Popup(
            self.root,
            on_range_change=self.on_range_change,
            on_threshold_change=self.on_threshold_change,
        )
        self.settings_dialog = None

        initial_image = icon_render.make_icon_image("…", "unknown")
        self.icon = pystray.Icon(
            "dexcom-g7",
            icon=initial_image,
            title=f"{APP_NAME} - starting…",
            menu=pystray.Menu(
                pystray.MenuItem("Open", self.on_open, default=True),
                pystray.MenuItem("Refresh now", lambda icon, item: self.request_refresh()),
                pystray.MenuItem("Settings…", lambda icon, item: self.on_open_settings()),
                pystray.MenuItem("Edit credentials…", lambda icon, item: self.on_edit_credentials()),
                pystray.MenuItem("Open settings folder", lambda icon, item: self.on_open_settings_folder()),
                pystray.MenuItem(
                    "Start with Windows",
                    lambda icon, item: self.on_toggle_autostart(),
                    checked=lambda item: autostart.is_enabled(),
                    visible=autostart.is_supported(),
                ),
                pystray.MenuItem("Quit", lambda icon, item: self.on_quit()),
            ),
        )

        credentials_path = settings_store.ensure_credentials_template()
        creds = dexcom_client.load_credentials(credentials_path)
        if not creds or dexcom_client.credentials_look_unconfigured(creds):
            self._notify(
                "Edit credentials.env with your real Dexcom Share login, then Refresh now. "
                "The app won't attempt to log in until you do.",
                title=APP_NAME,
            )

    # --- lifecycle ---

    def run(self):
        icon_thread = threading.Thread(target=self.icon.run, daemon=True)
        icon_thread.start()
        poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        poll_thread.start()
        self.root.mainloop()

    def on_quit(self):
        self.stop_event.set()
        self.wake_event.set()
        try:
            self.icon.stop()
        except Exception:
            pass
        self.root.after(0, self.root.quit)

    def _notify(self, message, title=APP_NAME):
        try:
            self.icon.notify(message, title)
        except Exception:
            pass

    # --- polling ---

    def _poll_loop(self):
        while not self.stop_event.is_set():
            with self.lock:
                settings_snapshot = dict(self.settings)
            result = dexcom_client.poll(settings_snapshot)
            self.result = result
            self._update_icon(result)
            self.root.after(0, self._push_to_popup, result, settings_snapshot)

            delay = dexcom_client.next_poll_delay_seconds(result, settings_snapshot)
            self.wake_event.wait(timeout=delay)
            self.wake_event.clear()

    def _push_to_popup(self, result, settings_snapshot):
        self.popup.refresh(result, settings_snapshot)

    def _update_icon(self, result):
        if result.get("ok"):
            status = result.get("status", "unknown")
            text = result.get("mgdl", "--")
            tooltip = result.get("tooltip", "")
        else:
            status = "error"
            text = "?"
            tooltip = result.get("tooltip", result.get("error", "Error"))
        try:
            self.icon.icon = icon_render.make_icon_image(str(text), status)
            self.icon.title = f"{APP_NAME}\n{tooltip}"[:127]  # Shell_NotifyIcon tip length limit
        except Exception:
            pass

    def request_refresh(self):
        self.wake_event.set()

    # --- menu actions ---

    def on_open(self, icon, item):
        self.root.after(0, self._show_popup)

    def _show_popup(self):
        with self.lock:
            settings_snapshot = dict(self.settings)
        self.popup.refresh(self.result, settings_snapshot)
        self.popup.show()

    def on_edit_credentials(self):
        path = settings_store.ensure_credentials_template()
        try:
            if sys.platform == "win32":
                os.startfile(path)  # noqa: S606 - opening a local text file with its default app
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except OSError:
            webbrowser.open(f"file://{path}")

    def on_open_settings(self):
        self.root.after(0, self._show_settings_dialog)

    def _show_settings_dialog(self):
        if self.settings_dialog is not None and self.settings_dialog.winfo_exists():
            self.settings_dialog.lift()
            return
        with self.lock:
            settings_snapshot = dict(self.settings)
        self.settings_dialog = SettingsDialog(self.root, settings_snapshot, on_save=self._on_settings_saved)

    def _on_settings_saved(self, updated_settings):
        with self.lock:
            self.settings.update(updated_settings)
            settings_store.save(self.settings)
        self.request_refresh()

    def on_toggle_autostart(self):
        if autostart.is_enabled():
            autostart.disable()
        else:
            autostart.enable()
        try:
            self.icon.update_menu()
        except Exception:
            pass

    def on_open_settings_folder(self):
        path = dexcom_client.app_data_dir()
        try:
            if sys.platform == "win32":
                os.startfile(path)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except OSError:
            pass

    # --- popup callbacks (run on the Tk thread) ---

    def on_range_change(self, minutes):
        with self.lock:
            self.settings["graphWindowMinutes"] = minutes
            settings_store.save(self.settings)
        self.request_refresh()

    def on_threshold_change(self, key, value):
        with self.lock:
            self.settings[key] = value
            settings_store.save(self.settings)
        self.request_refresh()


def main():
    app = TrayApp()
    app.run()


if __name__ == "__main__":
    main()
