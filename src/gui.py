"""Tkinter desktop interface for the Dhaka weather project.

The screens call the same validated model, manager and loop-based analysis used by
the console application. Charts are drawn with Tkinter Canvas, not a new library.
"""

import calendar
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta
import os
from pathlib import Path
import subprocess
import sys
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .analytics import screen_extremes, trend_summaries
from .config import BOUNDS, LABELS, PARAMETERS
from .forecaster import RollingForecaster
from .gui_helpers import (
    daily_temperatures,
    filter_observations,
    record_from_form,
    selected_summary,
    snapshot_manager,
)
from .gui_widgets import (
    COLORS,
    FONTS,
    Card,
    MetricCard,
    PagedTable,
    PlotCanvas,
    label,
    setup_styles,
)
from .reporting import export_analysis
from .file_helpers import write_csv_file
from .weather_manager import WeatherManager
from .weather_record import parse_timestamp

MONTH_OPTIONS = ("All months",) + tuple(
    f"{month:02d}  {calendar.month_name[month]}" for month in range(1, 13)
)
NAVIGATION = (
    ("overview", "Overview", "01"),
    ("records", "Weather records", "02"),
    ("analysis", "Climate analysis", "03"),
    ("forecast", "Forecast lab", "04"),
    ("events", "Event screening", "05"),
    ("exports", "Export center", "06"),
)
RECORD_COLUMNS = (
    ("timestamp", "TIMESTAMP  LST", 168),
    ("temperature", "TEMP  C", 102),
    ("humidity", "RH  %", 95),
    ("pressure", "PS  kPa", 105),
    ("wind", "WIND  m/s", 107),
    ("rain", "RAIN  mm/h", 112),
)
EXPECTED_ERRORS = (ValueError, OSError, UnicodeError, csv.Error)


class RecordDialog(tk.Toplevel):
    """A modal input form; the WeatherRecord model enforces the final rules."""

    def __init__(self, app, original=None):
        super().__init__(app.root)
        self.app, self.original = app, original
        self.title("Edit observation" if original else "Add observation")
        self.configure(background=COLORS["background"])
        self.geometry("510x650")
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()
        self.fields = {}
        body = tk.Frame(self, background=COLORS["background"])
        body.pack(fill="both", expand=True, padx=28, pady=24)
        label(
            body, "Edit observation" if original else "Add observation", 21, bold=True
        ).pack(anchor="w")
        label(
            body,
            "Hourly measurements for the editable weather dataset.",
            10,
            COLORS["muted"],
        ).pack(anchor="w", pady=(6, 18))
        label(body, "TIMESTAMP IN SOURCE LST", 9, COLORS["muted"], True).pack(
            anchor="w"
        )
        stamp = (
            original.record_id
            if original
            else (app.manager.records[-1].timestamp + timedelta(hours=1)).strftime(
                "%Y-%m-%d %H:%M"
            )
        )
        self.timestamp_var = tk.StringVar(self, value=stamp)
        entry = ttk.Entry(
            body,
            textvariable=self.timestamp_var,
            state="readonly" if original else "normal",
        )
        entry.pack(fill="x", pady=(5, 3))
        label(body, "Format: YYYY-MM-DD HH:00", 9, COLORS["muted"]).pack(
            anchor="w", pady=(0, 12)
        )
        previous = original.values() if original else ("",) * 5
        for parameter, value in zip(PARAMETERS, previous):
            title, unit = LABELS[parameter]
            low, high = BOUNDS[parameter]
            row = tk.Frame(body, background=COLORS["background"])
            row.pack(fill="x", pady=5)
            left = tk.Frame(row, background=COLORS["background"])
            left.pack(side="left", fill="x", expand=True)
            label(left, f"{title} ({unit})", 10, bold=True).pack(anchor="w")
            label(left, f"Accepted range {low:g} to {high:g}", 9, COLORS["muted"]).pack(
                anchor="w"
            )
            variable = tk.StringVar(self, value=str(value))
            self.fields[parameter] = variable
            ttk.Entry(row, textvariable=variable, width=15).pack(side="right")
        self.error_var = tk.StringVar(self)
        tk.Label(
            body,
            textvariable=self.error_var,
            background=COLORS["background"],
            foreground=COLORS["red"],
            wraplength=450,
            justify="left",
            anchor="w",
            font=(FONTS["family"], 10),
        ).pack(fill="x", pady=(12, 8))
        footer = tk.Frame(body, background=COLORS["background"])
        footer.pack(side="bottom", fill="x")
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side="left")
        ttk.Button(
            footer, text="Save observation", style="Accent.TButton", command=self.submit
        ).pack(side="right")
        self.bind("<Escape>", lambda event: self.destroy())
        self.bind("<Return>", lambda event: self.submit())
        self.update_idletasks()
        x = app.root.winfo_rootx() + (app.root.winfo_width() - self.winfo_width()) // 2
        y = app.root.winfo_rooty() + max(
            12, (app.root.winfo_height() - self.winfo_height()) // 2
        )
        self.geometry(f"+{max(0,x)}+{max(0,y)}")
        entry.focus_set()

    def submit(self):
        """Read the form, save through the manager, then refresh the records screen."""
        try:
            record = record_from_form(
                self.timestamp_var.get(),
                {name: var.get() for name, var in self.fields.items()},
            )
            if self.original is None:
                self.app.manager.add(record)
            else:
                self.app.manager.update(record)
        except EXPECTED_ERRORS as exc:
            self.error_var.set(str(exc))
            return False
        self.app.invalidate_data()
        self.app.record_query.set(record.record_id)
        self.app.record_year.set("All years")
        self.app.record_month.set("All months")
        self.destroy()
        self.app.navigate("records")
        self.app.set_status(f"Saved {record.record_id}. The working CSV is up to date.")
        return True


class WeatherGUI:
    """Build the desktop screens and connect buttons to the project functions.

    build_* methods draw screens. Other callbacks validate input, call a manager
    or analysis function, and display the result. Data rules stay in the model.
    """

    # Window setup and controls shared by all six screens.
    def __init__(self, root, manager, output_path, source_path):
        self.root, self.manager = root, manager
        self.output_path, self.source_path = Path(output_path), Path(source_path)
        self.root.title("Dhaka Weather | Forecast and Trend Analysis")
        screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
        width, height = min(1320, max(1080, screen_w - 80)), min(
            900, max(680, screen_h - 90)
        )
        self.root.geometry(
            f"{width}x{height}+{max(0,(screen_w-width)//2)}+{max(0,(screen_h-height)//2)}"
        )
        self.root.minsize(1080, 680)
        self.root.configure(background=COLORS["background"])
        self.style = setup_styles(root)
        # One worker runs slow calculations while the Tkinter window stays responsive.
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.pending_jobs = 0
        self.closed = False
        self.callback_errors = []
        self.cached_summary = None
        self.cached_monthly = None
        self.nav_buttons = {}
        self.page = ""
        self.dialog = None
        self.status_var = tk.StringVar(
            root, value="Ready. Changes to observations are saved automatically."
        )
        self.record_year = tk.StringVar(root, value="All years")
        self.record_month = tk.StringVar(root, value="All months")
        self.record_query = tk.StringVar(root)
        self.analysis_year = tk.StringVar(
            root, value="2023" if 2023 in manager.years else str(max(manager.years))
        )
        initial_year = int(self.analysis_year.get())
        initial_month = (
            7
            if manager.select(initial_year, 7)
            else manager.select(initial_year)[0].timestamp.month
        )
        self.analysis_month = tk.StringVar(root, value=MONTH_OPTIONS[initial_month])
        self.overview_year = tk.StringVar(root, value=str(max(manager.years)))
        self.overview_metric = tk.StringVar(root, value="Temperature")
        self.forecast_cutoff = tk.StringVar(root, value=manager.records[-1].record_id)
        self.forecast_horizon = tk.StringVar(root, value="24")
        self.forecast_window = tk.StringVar(root, value="24")
        self.evaluation_year = tk.StringVar(
            root, value="2024" if 2024 in manager.years else str(max(manager.years))
        )
        self.event_year = tk.StringVar(root, value="All years")
        self.event_fields = [
            tk.StringVar(root, value=value) for value in ("35", "10", "0.3")
        ]
        self.export_folder = tk.StringVar(root, value=str(self.output_path))
        self.root.report_callback_exception = self._callback_exception
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._build_shell()
        self.navigate("overview")

    def _build_shell(self):
        self.sidebar = tk.Frame(self.root, background=COLORS["navy"], width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        logo = tk.Canvas(
            self.sidebar,
            width=54,
            height=48,
            background=COLORS["navy"],
            highlightthickness=0,
        )
        logo.pack(anchor="w", padx=26, pady=(30, 13))
        logo.create_oval(20, 3, 42, 25, fill="#68F176", outline="")
        for x, y, r in ((14, 24, 10), (26, 20, 12), (38, 25, 9)):
            logo.create_oval(x - r, y - r, x + r, y + r, fill="#EDF1EF", outline="")
        logo.create_rectangle(7, 23, 44, 33, fill="#EDF1EF", outline="")
        label(self.sidebar, "DHAKA", 19, "white", True).pack(anchor="w", padx=26)
        label(self.sidebar, "WEATHER STUDIO", 9, "#68F176", True).pack(
            anchor="w", padx=27, pady=(2, 30)
        )
        label(self.sidebar, "WORKSPACE", 8, "#B5C0BC", True).pack(
            anchor="w", padx=27, pady=(0, 12)
        )
        for key, title, number in NAVIGATION:
            button = tk.Button(
                self.sidebar,
                text=f" {number}    {title}",
                anchor="w",
                padx=15,
                pady=13,
                background=COLORS["navy"],
                foreground=COLORS["sidebar_text"],
                activebackground=COLORS["selected"],
                activeforeground="white",
                font=(FONTS["family"], 10),
                borderwidth=0,
                highlightthickness=0,
                relief="flat",
                cursor="hand2",
                command=lambda selected=key: self.navigate(selected),
            )
            button.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[key] = button
        bottom = tk.Frame(self.sidebar, background=COLORS["navy"])
        bottom.pack(side="bottom", fill="x", padx=25, pady=25)
        tk.Frame(bottom, height=1, background="#014600").pack(fill="x", pady=(0, 16))
        self.sidebar_count = label(
            bottom, f"{len(self.manager.records):,} observations", 10, "#EDF1EF", True
        )
        self.sidebar_count.pack(anchor="w")
        label(bottom, "SOURCE TIME  /  LST", 8, "#B5C0BC").pack(anchor="w", pady=(8, 0))
        self.sidebar_dates = label(bottom, self._year_span(), 9, "#B5C0BC")
        self.sidebar_dates.pack(anchor="w", pady=(4, 0))
        workspace = tk.Frame(self.root, background=COLORS["background"])
        workspace.pack(side="left", fill="both", expand=True)
        header = tk.Frame(workspace, background="white", height=67)
        header.pack(fill="x")
        header.pack_propagate(False)
        label(header, "Dhaka, Bangladesh", 11, bold=True).pack(side="left", padx=28)
        pill = tk.Frame(header, background=COLORS["teal_tint"])
        pill.pack(side="left", padx=8)
        label(pill, "HISTORICAL DATA", 8, COLORS["teal"], True).pack(padx=10, pady=6)
        ttk.Button(header, text="Reload data", command=self.reload_records).pack(
            side="right", padx=(8, 26), pady=13
        )
        ttk.Button(
            header,
            text="Export results",
            style="Accent.TButton",
            command=lambda: self.navigate("exports"),
        ).pack(side="right", pady=13)
        tk.Frame(workspace, height=1, background=COLORS["border"]).pack(fill="x")
        footer = tk.Frame(workspace, background="white")
        footer.pack(side="bottom", fill="x")
        tk.Label(
            footer,
            textvariable=self.status_var,
            anchor="w",
            background="white",
            foreground=COLORS["muted"],
            font=(FONTS["family"], 9),
            padx=26,
            pady=9,
        ).pack(fill="x")
        area = tk.Frame(workspace, background=COLORS["background"])
        area.pack(fill="both", expand=True)
        self.scroller = tk.Canvas(
            area, background=COLORS["background"], highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(area, orient="vertical", command=self.scroller.yview)
        self.scroller.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.scroller.pack(side="left", fill="both", expand=True)
        self.content = tk.Frame(self.scroller, background=COLORS["background"])
        self.content_window = self.scroller.create_window(
            (0, 0), window=self.content, anchor="nw"
        )
        self.content.bind(
            "<Configure>",
            lambda event: self.scroller.configure(
                scrollregion=self.scroller.bbox("all")
            ),
        )
        self.scroller.bind(
            "<Configure>",
            lambda event: self.scroller.itemconfigure(
                self.content_window, width=event.width
            ),
        )
        self.root.bind_all("<MouseWheel>", self._scroll)
        self.root.bind_all("<Button-4>", self._scroll)
        self.root.bind_all("<Button-5>", self._scroll)

    def _scroll(self, event):
        if event.widget.winfo_class() in (
            "Treeview",
            "TCombobox",
            "TSpinbox",
            "Entry",
            "TEntry",
        ):
            return
        # Linux reports wheel buttons 4/5; Windows reports a delta value.
        mouse_button = getattr(event, "num", None)
        if mouse_button == 4:
            direction = -1
        elif mouse_button == 5:
            direction = 1
        else:
            direction = -int(event.delta / 120)
        if direction:
            self.scroller.yview_scroll(direction, "units")

    def _year_span(self):
        return f"{self.manager.records[0].timestamp.year} - {self.manager.records[-1].timestamp.year}"

    def years(self, include_all=True):
        return (["All years"] if include_all else []) + [
            str(year) for year in sorted(self.manager.years)
        ]

    def set_status(self, text):
        self.status_var.set(text)

    def _callback_exception(self, kind, value, trace):
        self.callback_errors.append(str(value))
        traceback.print_exception(kind, value, trace)
        self.show_error("Operation failed", value)

    def show_error(self, title, error):
        self.set_status(str(error))
        messagebox.showerror(title, str(error), parent=self.root)

    def invalidate_data(self):
        """Discard cached calculations after the saved records change."""
        self.cached_summary = None
        self.cached_monthly = None
        self.sidebar_count.configure(text=f"{len(self.manager.records):,} observations")
        self.sidebar_dates.configure(text=self._year_span())

    def navigate(self, page):
        """Remove the previous screen and call the selected screen builder."""
        self.page = page
        for key, button in self.nav_buttons.items():
            button.configure(
                background=COLORS["selected"] if key == page else COLORS["navy"],
                foreground="white" if key == page else COLORS["sidebar_text"],
            )
        for widget in self.content.winfo_children():
            widget.destroy()
        self.scroller.yview_moveto(0)
        self.view = tk.Frame(self.content, background=COLORS["background"])
        self.view.pack(fill="both", expand=True, padx=26, pady=24)
        # A dictionary connects each sidebar action to its screen-building method.
        builders = {
            "overview": self.build_overview,
            "records": self.build_records,
            "analysis": self.build_analysis,
            "forecast": self.build_forecast,
            "events": self.build_events,
            "exports": self.build_exports,
        }
        builders[page]()

    def title(self, title, subtitle):
        label(self.view, title, 24, bold=True).pack(anchor="w")
        label(self.view, subtitle, 10, COLORS["muted"]).pack(anchor="w", pady=(6, 21))

    def metrics(self, parent, items):
        row = tk.Frame(parent, background=COLORS["background"])
        row.pack(fill="x", pady=(0, 18))
        for index, (title, value, detail, color) in enumerate(items):
            row.grid_columnconfigure(index, weight=1, uniform="metric")
            MetricCard(row, title, value, detail, color).grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=(0, 12 if index < len(items) - 1 else 0),
            )
        return row

    def control(self, parent, title, variable, values=None, width=18):
        frame = tk.Frame(parent, background=parent.cget("background"))
        frame.pack(side="left", padx=(0, 12))
        label(frame, title.upper(), 8, COLORS["muted"], True).pack(
            anchor="w", pady=(0, 6)
        )
        if values is not None:
            entry = ttk.Combobox(
                frame,
                textvariable=variable,
                values=values,
                state="readonly",
                width=width,
            )
        else:
            entry = ttk.Entry(frame, textvariable=variable, width=width)
        entry.pack(fill="x")
        return entry

    # Screen 1: dataset overview and monthly chart.
    def build_overview(self):
        self.title(
            "Dhaka weather overview",
            "Explore hourly observations, seasonal patterns and transparent forecast estimates.",
        )
        if self.cached_summary is None:
            self.cached_summary = selected_summary(self.manager)[0]
        summary = self.cached_summary
        stats = summary["statistics"]
        self.metrics(
            self.view,
            [
                (
                    "Mean temperature",
                    f"{stats['T2M']['mean']:.2f} C",
                    "All observed hours",
                    COLORS["orange"],
                ),
                (
                    "Mean humidity",
                    f"{stats['RH2M']['mean']:.1f}%",
                    "Relative humidity at 2 m",
                    COLORS["blue"],
                ),
                (
                    "Observed rainfall",
                    f"{summary['observed_rainfall_mm']:,.1f}",
                    "mm across the dataset",
                    COLORS["teal"],
                ),
                (
                    "Data completeness",
                    f"{summary['coverage_pct']:.1f}%",
                    f"{summary['count']:,} hourly records",
                    COLORS["text"],
                ),
            ],
        )
        middle = tk.Frame(self.view, background=COLORS["background"])
        middle.pack(fill="x", pady=(0, 18))
        middle.grid_columnconfigure(0, weight=3)
        middle.grid_columnconfigure(1, weight=1, minsize=260)
        chart_card = Card(middle)
        chart_card.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        top = tk.Frame(chart_card.body, background="white")
        top.pack(fill="x", pady=(0, 10))
        label(top, "Seasonal patterns", 14, bold=True).pack(side="left")
        year = ttk.Combobox(
            top,
            textvariable=self.overview_year,
            values=self.years(False),
            state="readonly",
            width=7,
        )
        year.pack(side="right", padx=(8, 0))
        metric = ttk.Combobox(
            top,
            textvariable=self.overview_metric,
            values=("Temperature", "Rainfall"),
            state="readonly",
            width=13,
        )
        metric.pack(side="right")
        self.overview_plot = PlotCanvas(chart_card.body, height=245)
        self.overview_plot.pack(fill="x")
        label(
            chart_card.body,
            "Monthly values calculated from the observed hours.",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(5, 0))
        year.bind("<<ComboboxSelected>>", lambda event: self.update_overview_plot())
        metric.bind("<<ComboboxSelected>>", lambda event: self.update_overview_plot())
        self.update_overview_plot()
        last_card = Card(middle, color="#E3F8E7")
        last_card.grid(row=0, column=1, sticky="nsew")
        latest = self.manager.records[-1]
        label(last_card.body, "LAST OBSERVATION", 9, "#014600", True).pack(anchor="w")
        label(
            last_card.body, f"{latest.temperature:.1f} C", 33, COLORS["navy"], True
        ).pack(anchor="w", pady=(15, 4))
        label(
            last_card.body, latest.timestamp.strftime("%d %B %Y"), 11, bold=True
        ).pack(anchor="w")
        label(
            last_card.body,
            latest.timestamp.strftime("%H:%M") + "  /  SOURCE LST",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(4, 17))
        for title, value in (
            ("Humidity", f"{latest.humidity:.1f}%"),
            ("Wind speed", f"{latest.wind_speed:.2f} m/s"),
            ("Surface pressure", f"{latest.pressure:.2f} kPa"),
            ("Hourly rain", f"{latest.rainfall:.2f} mm/h"),
        ):
            row = tk.Frame(last_card.body, background=last_card.color)
            row.pack(fill="x", pady=5)
            label(row, title, 9, COLORS["muted"]).pack(side="left")
            label(row, value, 10, bold=True).pack(side="right")
        label(last_card.body, "Historical observation", 9, COLORS["teal"]).pack(
            anchor="w", pady=(12, 0)
        )
        bottom = Card(self.view)
        bottom.pack(fill="x")
        label(bottom.body, "Dataset at a glance", 13, bold=True).pack(
            anchor="w", pady=(0, 12)
        )
        dates = tk.Frame(bottom.body, background="white")
        dates.pack(fill="x")
        for index, (title, value) in enumerate(
            (
                ("FIRST HOUR", self.manager.records[0].record_id),
                ("LAST HOUR", latest.record_id),
                ("MISSING HOURS", f"{summary['missing_hours']:,}"),
                ("SOURCE FIELDS", "5 weather parameters"),
            )
        ):
            col = tk.Frame(dates, background="white")
            col.pack(side="left", fill="x", expand=True)
            label(col, title, 8, COLORS["muted"], True).pack(anchor="w")
            label(col, value, 10, bold=True).pack(anchor="w", pady=(6, 0))
        label(
            bottom.body,
            "NASA POWER / MERRA-2 attribution follows the supplied CSV. Timestamps retain source LST.",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(17, 0))

    def update_overview_plot(self):
        try:
            year = int(self.overview_year.get())
            rows = trend_summaries(self.manager, "monthly", year)
            rain = self.overview_metric.get() == "Rainfall"
            key = "observed_rainfall_mm" if rain else "temperature_mean_c"
            series = [
                (calendar.month_abbr[int(row["period"][-2:])], row[key]) for row in rows
            ]
            self.overview_plot.set_data(
                series,
                "Observed rainfall (mm)" if rain else "Mean temperature (C)",
                "bar" if rain else "line",
            )
        except EXPECTED_ERRORS as exc:
            self.show_error("Chart unavailable", exc)

    # Screen 2: search, add, edit, delete and reload records.
    def build_records(self):
        self.title(
            "Weather records",
            "Search hourly observations and maintain the working dataset.",
        )
        card = Card(self.view)
        card.pack(fill="x", pady=(0, 16))
        controls = tk.Frame(card.body, background="white")
        controls.pack(fill="x")
        self.control(controls, "Year", self.record_year, self.years(), 10)
        self.control(controls, "Month", self.record_month, MONTH_OPTIONS, 13)
        entry = self.control(
            controls, "Exact date or hour", self.record_query, width=23
        )
        entry.bind("<Return>", lambda event: self.filter_records())
        ttk.Button(
            controls, text="Search", style="Accent.TButton", command=self.filter_records
        ).pack(side="left", anchor="s", padx=(0, 8))
        ttk.Button(controls, text="Reset", command=self.reset_record_filters).pack(
            side="left", anchor="s"
        )
        label(
            card.body,
            "Use YYYY-MM-DD or YYYY-MM-DD HH:00. All timestamps use source LST.",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(10, 0))
        result = Card(self.view)
        result.pack(fill="x")
        tools = tk.Frame(result.body, background="white")
        tools.pack(fill="x", pady=(0, 16))
        label(tools, "Observations", 14, bold=True).pack(side="left")
        ttk.Button(
            tools, text="Delete", style="Danger.TButton", command=self.delete_selected
        ).pack(side="right")
        ttk.Button(
            tools, text="Edit selected", command=lambda: self.open_editor(True)
        ).pack(side="right", padx=8)
        ttk.Button(
            tools,
            text="+ Add observation",
            style="Accent.TButton",
            command=self.open_editor,
        ).pack(side="right")
        self.records_table = PagedTable(result.body, RECORD_COLUMNS, height=10)
        self.records_table.pack(fill="both", expand=True)
        self.records_table.tree.bind("<Double-1>", lambda event: self.open_editor(True))
        self.records_table.tree.bind("<Delete>", lambda event: self.delete_selected())
        self.filter_records()
        label(
            self.view,
            "Successful changes are saved to the working CSV. The original source file is preserved.",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(12, 0))

    def filter_records(self):
        """Validate the filters and pass matching observations to the table."""
        try:
            year = (
                None
                if self.record_year.get() == "All years"
                else int(self.record_year.get())
            )
            month = (
                None
                if self.record_month.get() == "All months"
                else int(self.record_month.get()[:2])
            )
            self.filtered_records = filter_observations(
                self.manager, year, month, self.record_query.get()
            )
            self.records_table.set_rows(
                [
                    (
                        record.record_id,
                        (record.record_id,)
                        + tuple(f"{value:.2f}" for value in record.values()),
                    )
                    for record in self.filtered_records
                ]
            )
            self.set_status(
                f"Found {len(self.filtered_records):,} matching observations."
            )
            return True
        except EXPECTED_ERRORS as exc:
            self.show_error("Invalid search", exc)
            return False

    def reset_record_filters(self):
        self.record_year.set("All years")
        self.record_month.set("All months")
        self.record_query.set("")
        self.filter_records()

    def open_editor(self, edit=False):
        original = None
        if edit:
            identifier = self.records_table.selected_id()
            if identifier is None:
                self.show_error(
                    "Select an observation", "Select a row in the table to edit."
                )
                return None
            original = self.manager.find_hour(parse_timestamp(identifier))
        self.dialog = RecordDialog(self, original)
        return self.dialog

    def delete_selected(self):
        """Confirm the selected deletion before saving it through the manager."""
        identifier = self.records_table.selected_id()
        if identifier is None:
            self.show_error(
                "Select an observation", "Select a row in the table to delete."
            )
            return False
        if not messagebox.askyesno(
            "Delete observation",
            f"Delete {identifier} LST from the working dataset?\n\nThis change will be saved immediately.",
            parent=self.root,
        ):
            return False
        try:
            self.manager.delete(parse_timestamp(identifier))
        except EXPECTED_ERRORS as exc:
            self.show_error("Could not delete", exc)
            return False
        self.invalidate_data()
        self.filter_records()
        self.set_status(f"Deleted {identifier}. The change is saved.")
        return True

    def reload_records(self):
        try:
            self.manager.load(self.manager.store_path)
        except EXPECTED_ERRORS as exc:
            self.show_error("Reload failed", exc)
            return False
        self.invalidate_data()
        self.forecast_cutoff.set(self.manager.records[-1].record_id)
        if self.overview_year.get() not in self.years(False):
            self.overview_year.set(str(max(self.manager.years)))
        self.navigate(self.page)
        rejected = self.manager.load_info.get("rejected_rows", 0)
        self.set_status(
            f"Reloaded {len(self.manager.records):,} saved observations."
            + (f" Rejected {rejected} invalid rows." if rejected else "")
        )
        return True

    # Screen 3: monthly/yearly statistics and temperature charts.
    def build_analysis(self):
        self.title(
            "Climate analysis",
            "Compare periods with clear units, calendar coverage and descriptive statistics.",
        )
        card = Card(self.view)
        card.pack(fill="x", pady=(0, 17))
        controls = tk.Frame(card.body, background="white")
        controls.pack(fill="x")
        self.control(controls, "Year", self.analysis_year, self.years(), 16)
        self.control(controls, "Month", self.analysis_month, MONTH_OPTIONS, 22)
        ttk.Button(
            controls,
            text="Calculate summary",
            style="Accent.TButton",
            command=self.calculate_analysis,
        ).pack(side="left", anchor="s", padx=2)
        self.analysis_body = tk.Frame(self.view, background=COLORS["background"])
        self.analysis_body.pack(fill="x")
        self.calculate_analysis()

    def calculate_analysis(self):
        """Calculate the selected period and refresh its cards, table and chart."""
        try:
            year = (
                None
                if self.analysis_year.get() == "All years"
                else int(self.analysis_year.get())
            )
            month = (
                None
                if self.analysis_month.get() == "All months"
                else int(self.analysis_month.get()[:2])
            )
            summary, records = selected_summary(self.manager, year, month)
        except EXPECTED_ERRORS as exc:
            self.show_error("Summary unavailable", exc)
            return False
        self.analysis_result = summary
        for child in self.analysis_body.winfo_children():
            child.destroy()
        stats = summary["statistics"]
        self.metrics(
            self.analysis_body,
            [
                (
                    "Mean temperature",
                    f"{stats['T2M']['mean']:.2f} C",
                    "Selected observed hours",
                    COLORS["orange"],
                ),
                (
                    "Observed rainfall",
                    f"{summary['observed_rainfall_mm']:,.2f}",
                    "mm for this selection",
                    COLORS["teal"],
                ),
                (
                    "Observations",
                    f"{summary['count']:,}",
                    f"{summary['expected_hours']:,} calendar hours expected",
                    COLORS["blue"],
                ),
                (
                    "Coverage",
                    f"{summary['coverage_pct']:.1f}%",
                    f"{summary['missing_hours']:,} missing hours",
                    COLORS["text"],
                ),
            ],
        )
        card = Card(self.analysis_body)
        card.pack(fill="x", pady=(0, 17))
        label(card.body, "Descriptive statistics", 14, bold=True).pack(
            anchor="w", pady=(0, 5)
        )
        label(
            card.body,
            f"{summary['start_lst']} to {summary['end_lst']} LST",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(0, 12))
        columns = (
            ("parameter", "PARAMETER / UNIT", 230),
            ("mean", "MEAN", 105),
            ("median", "MEDIAN", 105),
            ("minimum", "MIN", 100),
            ("maximum", "MAX", 100),
            ("std", "STD  POP.", 110),
        )
        self.analysis_table = PagedTable(card.body, columns, page_size=10, height=5)
        self.analysis_table.pack(fill="x")
        rows = []
        for key in PARAMETERS:
            values = stats[key]
            name, unit = LABELS[key]
            rows.append(
                (
                    key,
                    (f"{name} ({unit})",)
                    + tuple(
                        f"{values[name]:.3f}"
                        for name in (
                            "mean",
                            "median",
                            "minimum",
                            "maximum",
                            "std_population",
                        )
                    ),
                )
            )
        self.analysis_table.set_rows(rows)
        self.analysis_table.caption.configure(
            text=f"5 parameters  |  Wet hours: {summary['wet_hours']:,} ({summary['wet_hour_fraction_pct']:.2f}%)"
        )
        card = Card(self.analysis_body)
        card.pack(fill="x")
        label(card.body, "Temperature through the selected period", 13, bold=True).pack(
            anchor="w", pady=(0, 10)
        )
        chart = PlotCanvas(card.body, height=210)
        chart.pack(fill="x")
        if month is not None:
            series = [(day[-2:], value) for day, value in daily_temperatures(records)]
            unit = "Daily mean temperature (C) / day of month"
        else:
            rows = trend_summaries(self.manager, "monthly", year)
            series = [
                (
                    (
                        row["period"]
                        if year is None
                        else calendar.month_abbr[int(row["period"][-2:])]
                    ),
                    row["temperature_mean_c"],
                )
                for row in rows
            ]
            unit = "Monthly mean temperature (C)"
        chart.set_data(series, unit)
        label(
            card.body,
            "Rainfall totals cover observed hours only. Missing hours are not filled. Population standard deviation uses ddof=0.",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(10, 0))
        self.set_status("Summary calculated from the selected observed records.")
        return True

    # Screen 4: rolling estimates and measured historical forecast errors.
    def build_forecast(self):
        self.title(
            "Forecast lab",
            "Explore a transparent statistical model and measure its historical errors.",
        )
        notebook = ttk.Notebook(self.view)
        notebook.pack(fill="x")
        prediction = tk.Frame(notebook, background=COLORS["background"])
        evaluation = tk.Frame(notebook, background=COLORS["background"])
        notebook.add(prediction, text="Rolling estimate")
        notebook.add(evaluation, text="Historical evaluation")
        self.forecast_notebook = notebook
        card = Card(prediction)
        card.pack(fill="x", pady=(16, 16))
        controls = tk.Frame(card.body, background="white")
        controls.pack(fill="x")
        self.control(controls, "Observed cutoff / LST", self.forecast_cutoff, width=24)
        self.control(controls, "Horizon / hours", self.forecast_horizon, width=10)
        self.control(controls, "Window / hours", self.forecast_window, width=10)
        ttk.Button(
            controls,
            text="Generate estimate",
            style="Accent.TButton",
            command=self.calculate_forecast,
        ).pack(side="left", anchor="s")
        label(
            card.body,
            "Horizon: 1-24 hours. Observed window: 2-168 consecutive hours. This is a historical estimate.",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(12, 0))
        self.forecast_body = tk.Frame(prediction, background=COLORS["background"])
        self.forecast_body.pack(fill="x")
        card = Card(evaluation)
        card.pack(fill="x", pady=(16, 16))
        controls = tk.Frame(card.body, background="white")
        controls.pack(fill="x")
        self.control(controls, "Evaluation year", self.evaluation_year, width=16)
        self.evaluate_button = ttk.Button(
            controls,
            text="Evaluate 24-hour forecasts",
            style="Accent.TButton",
            command=self.calculate_backtest,
        )
        self.evaluate_button.pack(side="left", anchor="s")
        label(
            card.body,
            "Daily rolling origins. Only observations available at each historical cutoff enter a forecast.",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(12, 0))
        self.evaluation_body = tk.Frame(evaluation, background=COLORS["background"])
        self.evaluation_body.pack(fill="x")
        note = Card(self.evaluation_body)
        note.pack(fill="x")
        label(note.body, "Compare with simple baselines", 16, bold=True).pack(
            anchor="w"
        )
        label(
            note.body,
            "Run an evaluation to inspect MAE and RMSE for all three temperature methods.",
            10,
            COLORS["muted"],
        ).pack(anchor="w", pady=(10, 4))
        self.calculate_forecast()

    def calculate_forecast(self):
        """Validate cutoff/window/horizon, calculate estimates and display them."""
        try:
            cutoff = parse_timestamp(self.forecast_cutoff.get())
            try:
                horizon, window = int(self.forecast_horizon.get()), int(
                    self.forecast_window.get()
                )
            except ValueError as exc:
                raise ValueError("Horizon and window must be whole numbers.") from exc
            result = RollingForecaster(self.manager).forecast(cutoff, horizon, window)
        except EXPECTED_ERRORS as exc:
            self.show_error("Forecast unavailable", exc)
            return False
        self.forecast_result = result
        for child in self.forecast_body.winfo_children():
            child.destroy()
        first = result["predictions"][0]
        self.metrics(
            self.forecast_body,
            [
                (
                    "First estimate",
                    f"{first['T2M']:.2f} C",
                    first["timestamp_lst"],
                    COLORS["orange"],
                ),
                (
                    "Recent wet hours",
                    f"{first['recent_wet_fraction_pct']:.1f}%",
                    "Observed fraction, not rain probability",
                    COLORS["teal"],
                ),
                (
                    "Prediction horizon",
                    f"{horizon} hours",
                    f"{window} observed hours in the input window",
                    COLORS["blue"],
                ),
            ],
        )
        card = Card(self.forecast_body)
        card.pack(fill="x")
        label(card.body, "Hourly estimates", 14, bold=True).pack(
            anchor="w", pady=(0, 12)
        )
        self.forecast_table = PagedTable(card.body, RECORD_COLUMNS, height=10)
        self.forecast_table.pack(fill="x")
        self.forecast_table.set_rows(
            [
                (
                    row["timestamp_lst"],
                    (row["timestamp_lst"],)
                    + tuple(f"{row[key]:.3f}" for key in PARAMETERS),
                )
                for row in result["predictions"]
            ]
        )
        label(
            card.body,
            "Recursive trailing moving average. Forecast values are estimates; they do not replace a live weather service.",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(10, 0))
        self.set_status(
            f"Generated {horizon} estimates using data through {result['cutoff_lst']} LST."
        )
        return True

    def run_background(self, title, work, success, button):
        """Run a slow calculation, then show its result on the Tkinter thread.

        work is a function that returns data. success is a function that displays
        that data. The worker never reads or changes Tkinter widgets.
        """
        if self.pending_jobs:
            self.set_status(
                "A calculation is already running. Please wait for it to finish."
            )
            return False
        self.pending_jobs += 1
        button.state(["disabled"])
        self.set_status(title)
        page = self.page
        future = self.executor.submit(work)

        def poll():
            # after schedules the next check; it does not pause the window.
            if self.closed:
                return
            if not future.done():
                self.root.after(60, poll)
                return
            self.pending_jobs -= 1
            if button.winfo_exists():
                button.state(["!disabled"])
            try:
                result = future.result()
            except Exception as exc:
                self.show_error("Calculation failed", exc)
                return
            if self.page == page:
                success(result)
            else:
                self.set_status("Background calculation completed.")

        self.root.after(60, poll)
        return True

    def calculate_backtest(self):
        try:
            year = int(self.evaluation_year.get())
            if not 2 <= year <= 9998:
                raise ValueError
        except ValueError:
            self.show_error(
                "Invalid evaluation year", "Enter a whole year from 2 to 9998."
            )
            return False
        snapshot = snapshot_manager(self.manager)
        return self.run_background(
            "Evaluating chronological forecasts...",
            lambda: RollingForecaster(snapshot).backtest(year),
            self.show_backtest,
            self.evaluate_button,
        )

    def show_backtest(self, result):
        self.backtest_result = result
        for child in self.evaluation_body.winfo_children():
            child.destroy()
        values = result["temperature_c"]
        self.metrics(
            self.evaluation_body,
            [
                (
                    "Evaluated hours",
                    f"{result['evaluated_hours']:,}",
                    f"{result['forecast_days']} forecast days",
                    COLORS["blue"],
                ),
                (
                    "Rolling mean MAE",
                    f"{values['rolling_mean']['mae']:.3f} C",
                    "Mean absolute temperature error",
                    COLORS["orange"],
                ),
                (
                    "Previous-day MAE",
                    f"{values['previous_day_same_hour']['mae']:.3f} C",
                    "Same hour on the previous day",
                    COLORS["teal"],
                ),
            ],
        )
        card = Card(self.evaluation_body)
        card.pack(fill="x", pady=(0, 16))
        label(card.body, "Temperature baseline comparison", 14, bold=True).pack(
            anchor="w", pady=(0, 12)
        )
        names = {
            "rolling_mean": "Recursive rolling mean",
            "last_observation": "Last observation repeated",
            "previous_day_same_hour": "Previous day at the same hour",
        }
        table = PagedTable(
            card.body,
            (
                ("method", "METHOD", 430),
                ("mae", "MAE  C", 140),
                ("rmse", "RMSE  C", 140),
            ),
            height=3,
        )
        table.pack(fill="x")
        table.set_rows(
            [
                (key, (names[key], f"{value['mae']:.3f}", f"{value['rmse']:.3f}"))
                for key, value in values.items()
            ]
        )
        table.caption.configure(
            text=f"{result['coverage_pct']:.2f}% evaluation coverage  |  {result['skipped_days']} skipped days  |  Lower errors are better"
        )
        chart = PlotCanvas(card.body, height=200)
        chart.pack(fill="x", pady=(12, 0))
        chart.set_data(
            [
                (name, value["mae"])
                for name, value in zip(
                    ("Rolling mean", "Last value", "Previous day"), values.values()
                )
            ],
            "Temperature MAE (C)",
            "bar",
        )
        rain = result["rainfall_mm_per_hour"]["rolling_mean"]
        label(
            card.body,
            f"Rain estimate: MAE {rain['mae']:.3f} mm/hour; RMSE {rain['rmse']:.3f} mm/hour. No parameter tuning is performed.",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(10, 0))
        self.set_status(f"Historical evaluation finished for {result['year']}.")

    # Screen 5: threshold-based historical event screening.
    def build_events(self):
        self.title(
            "Historical event screening",
            "Inspect project-defined thresholds. These are not official weather warnings.",
        )
        card = Card(self.view)
        card.pack(fill="x", pady=(0, 16))
        controls = tk.Frame(card.body, background="white")
        controls.pack(fill="x")
        self.control(controls, "Year", self.event_year, self.years(), 10)
        for title, variable in zip(
            ("Heat above / C", "Rain above / mm/h", "3-hour drop / kPa"),
            self.event_fields,
        ):
            self.control(controls, title, variable, width=11)
        ttk.Button(
            controls,
            text="Scan records",
            style="Accent.TButton",
            command=self.calculate_events,
        ).pack(side="left", anchor="s")
        self.event_body = tk.Frame(self.view, background=COLORS["background"])
        self.event_body.pack(fill="x")
        self.calculate_events()

    def calculate_events(self):
        try:
            year = (
                None
                if self.event_year.get() == "All years"
                else int(self.event_year.get())
            )
            thresholds = tuple(float(variable.get()) for variable in self.event_fields)
            events = screen_extremes(self.manager.select(year), thresholds)
        except EXPECTED_ERRORS as exc:
            self.show_error("Invalid screening input", exc)
            return False
        self.event_result = events
        for child in self.event_body.winfo_children():
            child.destroy()
        counts = {
            tag: sum(tag in row["tags"].split("; ") for row in events)
            for tag in ("High temperature", "Heavy hourly rain", "Pressure drop")
        }
        self.metrics(
            self.event_body,
            [
                (tag, f"{count:,}", "Flagged hours; tags may overlap", color)
                for (tag, count), color in zip(
                    counts.items(), (COLORS["orange"], COLORS["blue"], COLORS["teal"])
                )
            ],
        )
        card = Card(self.event_body)
        card.pack(fill="x")
        row = tk.Frame(card.body, background="white")
        row.pack(fill="x", pady=(0, 12))
        label(row, "Flagged historical hours", 14, bold=True).pack(side="left")
        ttk.Button(row, text="Export flagged hours", command=self.export_events).pack(
            side="right"
        )
        self.events_table = PagedTable(
            card.body,
            (
                ("timestamp", "TIMESTAMP  LST", 165),
                ("tags", "SCREENING TAGS", 300),
                ("temperature", "TEMP  C", 95),
                ("rain", "RAIN  mm/h", 105),
                ("drop", "3H DROP  kPa", 125),
            ),
            height=11,
        )
        self.events_table.pack(fill="x")
        self.events_table.set_rows(
            [
                (
                    row["timestamp_lst"],
                    (
                        row["timestamp_lst"],
                        row["tags"],
                        f"{row['temperature_c']:.2f}",
                        f"{row['rainfall_mm_per_hour']:.2f}",
                        row["pressure_drop_3h_kpa"],
                    ),
                )
                for row in events
            ]
        )
        label(
            card.body,
            "Pressure screening compares observations exactly three hours apart. Thresholds are educational rules.",
            9,
            COLORS["muted"],
        ).pack(anchor="w", pady=(10, 0))
        self.set_status(
            f"Screened historical data; {len(events):,} distinct hours were flagged."
        )
        return True

    def export_events(self):
        filename = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export flagged historical hours",
            defaultextension=".csv",
            initialfile="screened_events.csv",
            filetypes=(("CSV files", "*.csv"),),
        )
        if not filename:
            return False
        fields = (
            "timestamp_lst",
            "tags",
            "temperature_c",
            "rainfall_mm_per_hour",
            "pressure_kpa",
            "pressure_drop_3h_kpa",
        )
        try:
            write_csv_file(filename, self.event_result, fields)
        except EXPECTED_ERRORS as exc:
            self.show_error("Export failed", exc)
            return False
        self.set_status(
            f"Saved {len(self.event_result):,} flagged hours to {Path(filename).name}."
        )
        return True

    # Screen 6: choose a folder and export complete analysis files.
    def build_exports(self):
        self.title(
            "Export center",
            "Save complete, reusable analysis files from the current observation snapshot.",
        )
        card = Card(self.view)
        card.pack(fill="x", pady=(0, 18))
        label(card.body, "Analysis bundle", 16, bold=True).pack(anchor="w")
        label(
            card.body,
            "Summaries, monthly and yearly trends, screened events, forecasts and evaluation results.",
            10,
            COLORS["muted"],
        ).pack(anchor="w", pady=(7, 18))
        row = tk.Frame(card.body, background="white")
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.export_folder).pack(
            side="left", fill="x", expand=True, padx=(0, 10)
        )
        ttk.Button(row, text="Choose folder", command=self.choose_export_folder).pack(
            side="left", padx=(0, 10)
        )
        self.export_button = ttk.Button(
            row,
            text="Generate files",
            style="Accent.TButton",
            command=self.generate_exports,
        )
        self.export_button.pack(side="left")
        self.export_message = label(
            card.body,
            "The forecast uses the latest observation. Evaluation uses its calendar year.",
            9,
            COLORS["muted"],
        )
        self.export_message.pack(anchor="w", pady=(12, 0))
        card = Card(self.view)
        card.pack(fill="x")
        head = tk.Frame(card.body, background="white")
        head.pack(fill="x", pady=(0, 12))
        label(head, "Included files", 14, bold=True).pack(side="left")
        ttk.Button(
            head, text="Open output folder", command=self.open_export_folder
        ).pack(side="right")
        rows = (
            (
                "weather_summary_report.txt",
                "TXT",
                "Readable summary and forecast evaluation",
            ),
            ("summary.json", "JSON", "All-period statistics and coverage"),
            ("quality_report.json", "JSON", "Import diagnostics and source notes"),
            ("monthly_trends.csv", "CSV", "Monthly comparisons and observed rainfall"),
            ("yearly_trends.csv", "CSV", "Yearly comparisons and completeness"),
            ("extreme_events.csv", "CSV", "All threshold-screened hours"),
            ("correlations.json", "JSON", "Exploratory parameter relationships"),
            ("forecast.json", "JSON", "Forecast method, cutoff, values and notes"),
            ("forecast.csv", "CSV", "Hourly estimated measurements"),
            ("backtest_summary.json", "JSON", "Measured errors for the latest year"),
        )
        self.export_table = PagedTable(
            card.body,
            (
                ("file", "FILENAME", 265),
                ("format", "FORMAT", 90),
                ("description", "CONTENTS", 400),
            ),
            height=9,
        )
        self.export_table.pack(fill="x")
        self.export_table.set_rows(
            [(name, (name, kind, description)) for name, kind, description in rows]
        )
        self.export_table.caption.configure(
            text="Up to 10 files  |  Unavailable forecast/evaluation results are recorded explicitly"
        )

    def choose_export_folder(self):
        folder = filedialog.askdirectory(
            parent=self.root, title="Choose an export folder"
        )
        if folder:
            self.export_folder.set(folder)

    def generate_exports(self):
        """Validate the folder and export a consistent snapshot of the records."""
        text = self.export_folder.get().strip()
        if not text:
            self.show_error(
                "Choose an output folder", "Enter or choose an export folder."
            )
            return False
        directory = Path(text).expanduser()
        snapshot = snapshot_manager(self.manager)

        def finish(paths):
            self.last_export_paths = paths
            self.export_message.configure(
                text=f"Saved {len(paths)} files successfully to {directory}",
                foreground=COLORS["teal"],
            )
            self.set_status(f"Export complete: {len(paths)} analysis files written.")

        return self.run_background(
            "Generating the analysis bundle...",
            lambda: export_analysis(snapshot, directory),
            finish,
            self.export_button,
        )

    def open_export_folder(self):
        path = Path(self.export_folder.get()).expanduser()
        if not path.is_dir():
            self.show_error(
                "Folder unavailable",
                "Generate the files or choose an existing folder first.",
            )
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(
                    ["open", str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    ["xdg-open", str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except OSError as exc:
            self.show_error("Could not open folder", exc)

    def close(self):
        """Stop accepting background work and close the desktop window."""
        self.closed = True
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def launch_gui(args):
    """Load the working CSV, offer recovery if needed, and start Tkinter's event loop."""
    root = tk.Tk()
    root.withdraw()
    manager = WeatherManager(args["store"])
    if args["source"].resolve() == args["store"].resolve():
        messagebox.showerror(
            "Choose a working CSV",
            "Source and working CSV must use different paths.",
            parent=root,
        )
        root.destroy()
        return 1
    try:
        if args["store"].exists():
            manager.load(args["store"])
        else:
            manager.load(args["source"])
            manager.save()
    except EXPECTED_ERRORS as exc:
        use_source = messagebox.askyesno(
            "Dataset could not be loaded",
            f"{exc}\n\nOpen the bundled source and save future edits to a separate recovery CSV?",
            parent=root,
        )
        if not use_source:
            root.destroy()
            return 1
        try:
            manager.load(args["source"])
            manager.store_path = args["store"].with_name(
                args["store"].stem + "_recovered.csv"
            )
            manager.save()
        except EXPECTED_ERRORS as recovery_error:
            messagebox.showerror("Recovery failed", str(recovery_error), parent=root)
            root.destroy()
            return 1
    app = WeatherGUI(root, manager, args["output"], args["source"])
    root.deiconify()
    if manager.load_info.get("rejected_rows"):
        root.after(
            250,
            lambda: messagebox.showwarning(
                "Import diagnostics",
                f"{manager.load_info['rejected_rows']} invalid or duplicate rows were rejected.\nThe valid observations were loaded.",
                parent=root,
            ),
        )
    try:
        root.mainloop()
    except KeyboardInterrupt:
        if not app.closed:
            app.close()
    return 0
