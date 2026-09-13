"""
The detail popup window: current reading, a history graph, 3h/6h/12h/24h
range buttons, and a gear-icon threshold editor. Ported from the graph/slider
section of Dexcom.qml onto a tkinter Canvas + ttk widgets.
"""
import datetime
import tkinter as tk
from tkinter import ttk

BG = "#2a2a2a"
FG = "#cccccc"
FG_DIM = "#888888"
FG_BRIGHT = "#ffffff"
COLOR_HIGH = "#e0a030"
COLOR_URGENT = "#e05252"
GRAPH_LABEL_MARGIN = 34

RANGE_OPTIONS = [("3h", 180), ("6h", 360), ("12h", 720), ("24h", 1440)]

THRESHOLD_ROWS = [
    ("Urgent High", "urgentHigh", COLOR_URGENT, 200, 400),
    ("High", "highThreshold", COLOR_HIGH, 120, 300),
    ("Low", "lowThreshold", COLOR_HIGH, 40, 100),
    ("Urgent Low", "urgentLow", COLOR_URGENT, 30, 90),
]


def format_point_timestamp(seconds_ago):
    d = datetime.datetime.now() - datetime.timedelta(seconds=seconds_ago)
    now = datetime.datetime.now()
    yesterday = now - datetime.timedelta(days=1)
    time_str = d.strftime("%I:%M %p").lstrip("0")
    if d.date() == now.date():
        return time_str
    if d.date() == yesterday.date():
        return f"Yesterday, {time_str}"
    return f"{d.month}/{d.day}, {time_str}"


class Popup(tk.Toplevel):
    """A single persistent popup window; call refresh() whenever new data arrives."""

    def __init__(self, master, on_range_change, on_threshold_change):
        super().__init__(master)
        self.title("Dexcom G7")
        self.configure(bg=BG)
        self.geometry("360x360")
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        self.on_range_change = on_range_change
        self.on_threshold_change = on_threshold_change

        self.result = {"ok": False}
        self.settings = {}
        self.selected_point_index = None
        self.show_settings = False
        self.range_buttons = {}
        self.slider_vars = {}

        self._build_header()
        self._build_range_row()
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, height=140)
        self.canvas.pack(fill="x", padx=8, pady=(4, 0))
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self._build_settings_panel()

        self.withdraw()

    def _build_header(self):
        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", padx=8, pady=(8, 4))
        self.value_label = tk.Label(row, text="--", font=("Segoe UI", 22, "bold"), bg=BG, fg=FG_BRIGHT)
        self.value_label.pack(side="left")
        self.age_label = tk.Label(row, text="", font=("Segoe UI", 10), bg=BG, fg=FG_DIM)
        self.age_label.pack(side="left", padx=(10, 0), anchor="s", pady=(0, 4))
        self.gear_button = tk.Label(row, text="⚙", font=("Segoe UI", 14), bg=BG, fg=FG_DIM, cursor="hand2")
        self.gear_button.pack(side="right")
        self.gear_button.bind("<Button-1>", lambda e: self._toggle_settings())

    def _build_range_row(self):
        self.range_row = tk.Frame(self, bg=BG)
        self.range_row.pack(fill="x", padx=8, pady=(0, 4))
        for label, minutes in RANGE_OPTIONS:
            btn = tk.Label(
                self.range_row, text=label, font=("Segoe UI", 9), bg=BG, fg=FG_DIM,
                cursor="hand2", padx=8, pady=2,
            )
            btn.pack(side="left", padx=2)
            btn.bind("<Button-1>", lambda e, m=minutes: self.on_range_change(m))
            self.range_buttons[minutes] = btn

    def _build_settings_panel(self):
        self.settings_panel = tk.Frame(self, bg=BG)
        self.slider_vars = {}
        for label, key, color, lo, hi in THRESHOLD_ROWS:
            row = tk.Frame(self.settings_panel, bg=BG)
            row.pack(fill="x", padx=8, pady=4)
            name = tk.Label(row, text=label, font=("Segoe UI", 9), bg=BG, fg=color, width=11, anchor="w")
            name.pack(side="left")
            var = tk.DoubleVar(value=(lo + hi) / 2)
            value_lbl = tk.Label(row, text="", font=("Segoe UI", 9), bg=BG, fg=FG, width=4)
            value_lbl.pack(side="right")
            scale = ttk.Scale(row, from_=lo, to=hi, orient="horizontal", variable=var)
            scale.pack(side="left", fill="x", expand=True, padx=6)

            def make_on_move(v=var, lbl=value_lbl):
                def _(e=None):
                    lbl.config(text=str(round(v.get())))
                return _

            def make_on_release(k=key, v=var):
                def _(e=None):
                    self.on_threshold_change(k, round(v.get()))
                return _

            scale.bind("<B1-Motion>", make_on_move())
            scale.bind("<ButtonRelease-1>", make_on_release())
            self.slider_vars[key] = (var, value_lbl)

    def _toggle_settings(self):
        self.show_settings = not self.show_settings
        if self.show_settings:
            self.canvas.pack_forget()
            self.settings_panel.pack(fill="x", padx=0, pady=(4, 8))
        else:
            self.settings_panel.pack_forget()
            self.canvas.pack(fill="x", padx=8, pady=(4, 0))
        self._redraw()

    def set_selected_range(self, minutes):
        for m, btn in self.range_buttons.items():
            active = m == minutes
            btn.config(bg="#333333" if active else BG, fg=FG_BRIGHT if active else FG_DIM)

    def refresh(self, result, settings):
        self.result = result
        self.settings = settings
        self.selected_point_index = None

        for key, (var, lbl) in self.slider_vars.items():
            v = settings.get(key)
            if v is not None:
                var.set(v)
                lbl.config(text=str(round(v)))

        self.set_selected_range(settings.get("graphWindowMinutes", 180))

        if result.get("ok"):
            unit = result.get("unit", "mg/dL")
            arrow = result.get("trendArrow", "?")
            self.value_label.config(text=f"{result.get('mgdl', '--')} {unit} {arrow}")
            minutes_ago = result.get("minutesAgo")
            age = f"{minutes_ago} min ago" if minutes_ago is not None else "time unknown"
            self.age_label.config(text=age)
        else:
            self.value_label.config(text="--")
            self.age_label.config(text=result.get("tooltip", "Error"))

        self._redraw()

    def show(self):
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(50, lambda: self.attributes("-topmost", False))
        self._redraw()

    # --- graph drawing, ported from Dexcom.qml's Canvas.onPaint ---

    def _redraw(self):
        c = self.canvas
        c.delete("all")
        if self.show_settings:
            return
        w = max(c.winfo_width(), 300)
        h = int(c["height"])

        series = self.result.get("series") or []
        if len(series) < 2:
            c.create_text(10, h / 2, text="Not enough data yet", fill=FG_DIM, anchor="w", font=("Segoe UI", 9))
            return

        values = [p["value"] for p in series]
        th = self.result.get("thresholds") or {}
        lo, hi = min(values), max(values)
        if isinstance(th.get("urgentLow"), (int, float)):
            lo = min(lo, th["urgentLow"])
        if isinstance(th.get("urgentHigh"), (int, float)):
            hi = max(hi, th["urgentHigh"])
        pad = max((hi - lo) * 0.15, 1)
        y_min, y_max = lo - pad, hi + pad
        value_range = (y_max - y_min) or 1

        plot_width = w - GRAPH_LABEL_MARGIN

        def x_for(i):
            return (i / (len(series) - 1)) * plot_width

        def y_for(v):
            clamped = max(y_min, min(y_max, v))
            return h - ((clamped - y_min) / value_range) * h

        if isinstance(th.get("high"), (int, float)):
            hy = y_for(th["high"])
            c.create_line(0, hy, plot_width, hy, fill=COLOR_HIGH)
            c.create_text(plot_width + 5, hy, text=f"{th['high']:.0f}", fill=COLOR_HIGH, anchor="w", font=("Segoe UI", 8))
        if isinstance(th.get("low"), (int, float)):
            ly = y_for(th["low"])
            c.create_line(0, ly, plot_width, ly, fill=COLOR_URGENT)
            c.create_text(plot_width + 5, ly, text=f"{th['low']:.0f}", fill=COLOR_URGENT, anchor="w", font=("Segoe UI", 8))

        c.create_text(plot_width + 5, 9, text=f"{y_max:.0f}", fill="#555555", anchor="w", font=("Segoe UI", 7))
        c.create_text(plot_width + 5, h - 6, text=f"{y_min:.0f}", fill="#555555", anchor="w", font=("Segoe UI", 7))

        for i in range(len(series) - 1):
            x, y = x_for(i), y_for(series[i]["value"])
            c.create_oval(x - 1, y - 1, x + 1, y + 1, fill=FG_BRIGHT, outline="")

        last_x, last_y = x_for(len(series) - 1), y_for(series[-1]["value"])
        c.create_oval(last_x - 4, last_y - 4, last_x + 4, last_y + 4, outline=FG_BRIGHT, width=1.5)

        self._series_cache = series
        self._x_for = x_for
        self._y_for = y_for
        self._plot_width = plot_width
        self._graph_h = h

        if self.selected_point_index is not None and 0 <= self.selected_point_index < len(series):
            self._draw_callout(c, self.selected_point_index, series, x_for, y_for, h)

    def _draw_callout(self, c, idx, series, x_for, y_for, h):
        sx, sy = x_for(idx), y_for(series[idx]["value"])
        c.create_line(sx, sy, sx, h, fill=FG_DIM, dash=(3, 3))
        c.create_oval(sx - 3, sy - 3, sx + 3, sy + 3, outline=FG_BRIGHT, width=1.5)

        unit = self.result.get("unit", "mg/dL")
        label = f"{series[idx]['value']} {unit}"
        seconds_ago = series[idx].get("secondsAgo")
        when = format_point_timestamp(seconds_ago) if isinstance(seconds_ago, int) else ""
        full_label = f"{label}   {when}" if when else label

        bubble_w = 8 * len(full_label) + 16
        bubble_h = 20
        bubble_x = min(max(sx - bubble_w / 2, 0), self._plot_width + GRAPH_LABEL_MARGIN - bubble_w)
        bubble_y = max(sy - bubble_h - 8, 2)
        c.create_rectangle(bubble_x, bubble_y, bubble_x + bubble_w, bubble_y + bubble_h, fill=BG, outline="")
        c.create_text(bubble_x + 8, bubble_y + 10, text=full_label, fill=FG_BRIGHT, anchor="w", font=("Segoe UI", 8))

    def _on_canvas_click(self, event):
        series = self.result.get("series") or []
        if len(series) < 2 or not hasattr(self, "_x_for"):
            return
        nearest = min(range(len(series)), key=lambda i: abs(self._x_for(i) - event.x))
        self.selected_point_index = None if self.selected_point_index == nearest else nearest
        self._redraw()
