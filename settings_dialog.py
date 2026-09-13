"""
Settings dialog for the fields that used to live in Omarchy's bar
customization view (region, units, poll interval, stale timeout,
credentials path, tooltip toggles). Thresholds and graph range are edited
from the main popup instead (see popup.py) - not duplicated here.
"""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

BG = "#2a2a2a"
FG = "#cccccc"

SERVER_OPTIONS = [("United States", "share2"), ("Outside the US", "shareous1"), ("Japan", "share")]
UNITS_OPTIONS = [("mg/dL", "mgdl"), ("mmol/L", "mmol")]


class SettingsDialog(tk.Toplevel):
    def __init__(self, master, settings, on_save):
        super().__init__(master)
        self.title("Dexcom G7 Settings")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.on_save = on_save
        self.settings = settings

        pad = {"padx": 10, "pady": 6}

        row = 0
        tk.Label(self, text="Credentials file", bg=BG, fg=FG).grid(row=row, column=0, sticky="w", **pad)
        cred_frame = tk.Frame(self, bg=BG)
        cred_frame.grid(row=row, column=1, sticky="we", **pad)
        self.credentials_var = tk.StringVar(value=settings.get("credentialsPath", ""))
        tk.Entry(cred_frame, textvariable=self.credentials_var, width=28).pack(side="left")
        tk.Button(cred_frame, text="Browse…", command=self._browse_credentials).pack(side="left", padx=(6, 0))
        row += 1

        tk.Label(self, text="Dexcom region", bg=BG, fg=FG).grid(row=row, column=0, sticky="w", **pad)
        self.server_var = tk.StringVar()
        server_combo = ttk.Combobox(
            self, textvariable=self.server_var, state="readonly",
            values=[label for label, _ in SERVER_OPTIONS], width=26,
        )
        server_combo.grid(row=row, column=1, sticky="w", **pad)
        self._set_combo_by_value(server_combo, SERVER_OPTIONS, settings.get("server", "share2"))
        self.server_combo = server_combo
        row += 1

        tk.Label(self, text="Display units", bg=BG, fg=FG).grid(row=row, column=0, sticky="w", **pad)
        self.units_var = tk.StringVar()
        units_combo = ttk.Combobox(
            self, textvariable=self.units_var, state="readonly",
            values=[label for label, _ in UNITS_OPTIONS], width=26,
        )
        units_combo.grid(row=row, column=1, sticky="w", **pad)
        self._set_combo_by_value(units_combo, UNITS_OPTIONS, settings.get("units", "mgdl"))
        self.units_combo = units_combo
        row += 1

        self.poll_interval_var = self._add_spinbox(
            row, "Fallback poll interval (sec)", settings.get("pollIntervalSeconds", 60), 30, 600, 10, pad
        )
        row += 1

        self.stale_after_var = self._add_spinbox(
            row, "Stale after (minutes)", settings.get("staleAfterMinutes", 20), 10, 60, 5, pad
        )
        row += 1

        self.history_minutes_var = self._add_spinbox(
            row, "Tooltip history window (minutes)", settings.get("historyWindowMinutes", 60), 15, 180, 15, pad
        )
        row += 1

        self.show_history_var = tk.BooleanVar(value=bool(settings.get("showHistoryInTooltip", True)))
        tk.Checkbutton(
            self, text="Show recent-history line in tooltip", variable=self.show_history_var,
            bg=BG, fg=FG, selectcolor=BG, activebackground=BG, activeforeground=FG,
        ).grid(row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        self.show_trend_word_var = tk.BooleanVar(value=bool(settings.get("showTrendWord", False)))
        tk.Checkbutton(
            self, text='Spell out the trend (e.g. "rising") in the tooltip', variable=self.show_trend_word_var,
            bg=BG, fg=FG, selectcolor=BG, activebackground=BG, activeforeground=FG,
        ).grid(row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        button_row = tk.Frame(self, bg=BG)
        button_row.grid(row=row, column=0, columnspan=2, pady=(4, 10))
        tk.Button(button_row, text="Save", command=self._save, width=10).pack(side="left", padx=6)
        tk.Button(button_row, text="Cancel", command=self.destroy, width=10).pack(side="left", padx=6)

        self.transient(master)
        self.grab_set()

    def _add_spinbox(self, row, label, value, lo, hi, step, pad):
        tk.Label(self, text=label, bg=BG, fg=FG).grid(row=row, column=0, sticky="w", **pad)
        var = tk.IntVar(value=value)
        tk.Spinbox(self, from_=lo, to=hi, increment=step, textvariable=var, width=8).grid(
            row=row, column=1, sticky="w", **pad
        )
        return var

    @staticmethod
    def _set_combo_by_value(combo, options, value):
        for label, opt_value in options:
            if opt_value == value:
                combo.set(label)
                return
        combo.set(options[0][0])

    @staticmethod
    def _value_for_label(options, label):
        for opt_label, opt_value in options:
            if opt_label == label:
                return opt_value
        return options[0][1]

    def _browse_credentials(self):
        path = filedialog.askopenfilename(
            parent=self, title="Select credentials.env",
            filetypes=[("Env files", "*.env"), ("All files", "*.*")],
        )
        if path:
            self.credentials_var.set(path)

    def _save(self):
        try:
            poll_interval = max(30, min(600, int(self.poll_interval_var.get())))
            stale_after = max(10, min(60, int(self.stale_after_var.get())))
            history_minutes = max(15, min(180, int(self.history_minutes_var.get())))
        except (tk.TclError, ValueError):
            messagebox.showerror("Invalid value", "Poll interval, stale timeout, and history window must be numbers.", parent=self)
            return

        updated = dict(self.settings)
        updated["credentialsPath"] = self.credentials_var.get().strip()
        updated["server"] = self._value_for_label(SERVER_OPTIONS, self.server_var.get())
        updated["units"] = self._value_for_label(UNITS_OPTIONS, self.units_var.get())
        updated["pollIntervalSeconds"] = poll_interval
        updated["staleAfterMinutes"] = stale_after
        updated["historyWindowMinutes"] = history_minutes
        updated["showHistoryInTooltip"] = bool(self.show_history_var.get())
        updated["showTrendWord"] = bool(self.show_trend_word_var.get())

        self.on_save(updated)
        self.destroy()
