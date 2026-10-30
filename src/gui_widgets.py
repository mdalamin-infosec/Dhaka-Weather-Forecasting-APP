"""Tkinter/ttk styles, cards, paginated tables and charts drawn on a Canvas."""

import math
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# Green palette inspired by the current styles at https://techcrunch.com/.
COLORS = {
    "background": "#EDF1EF",
    "card": "#FFFFFF",
    "navy": "#012800",
    "sidebar_text": "#B5C0BC",
    "selected": "#0A8935",
    "text": "#212623",
    "muted": "#535554",
    "border": "#D2DCD7",
    "teal": "#0A8935",
    "teal_dark": "#014600",
    "teal_tint": "#E2F7E5",
    "blue": "#014600",
    "orange": "#0AA43E",
    "red": "#E21C1C",
    "red_tint": "#FDEEEE",
}
FONTS = {"family": "DejaVu Sans"}


def setup_styles(root):
    """Choose an installed font and apply shared colors and widget styles."""
    available = {}
    for name in tkfont.families(root):
        available[name.casefold()] = name

    FONTS["family"] = "sans serif"
    for name in ("Inter", "Segoe UI", "DejaVu Sans", "Arial", "Helvetica"):
        if name.casefold() in available:
            FONTS["family"] = available[name.casefold()]
            break
    root.option_add("*Font", (FONTS["family"], 10))
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name, root=root).configure(family=FONTS["family"], size=10)
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    style.configure(".", font=(FONTS["family"], 10))
    style.configure("TFrame", background=COLORS["background"])
    style.configure(
        "TLabel", background=COLORS["background"], foreground=COLORS["text"]
    )
    style.configure(
        "TButton",
        font=(FONTS["family"], 10),
        padding=(14, 9),
        borderwidth=1,
        relief="flat",
        background="white",
        foreground=COLORS["text"],
    )
    style.map(
        "TButton",
        background=[("active", "#E2F7E5"), ("disabled", "#EDF1EF")],
        foreground=[("disabled", "#6C7571")],
    )
    style.configure(
        "Accent.TButton",
        foreground=COLORS["navy"],
        background=COLORS["teal"],
        borderwidth=0,
    )
    style.map(
        "Accent.TButton",
        background=[("active", COLORS["teal_dark"]), ("disabled", "#D2DCD7")],
        foreground=[("disabled", COLORS["muted"])],
    )
    style.configure(
        "Danger.TButton", foreground=COLORS["red"], background=COLORS["red_tint"]
    )
    style.map("Danger.TButton", background=[("active", "#F9DADA")])
    style.configure(
        "TEntry", padding=8, fieldbackground="white", bordercolor=COLORS["border"]
    )
    style.configure(
        "TCombobox",
        padding=7,
        fieldbackground="white",
        background="white",
        arrowcolor=COLORS["muted"],
        bordercolor=COLORS["border"],
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", "white")],
        foreground=[("readonly", COLORS["text"])],
    )
    style.configure(
        "TSpinbox", padding=7, fieldbackground="white", bordercolor=COLORS["border"]
    )
    style.configure(
        "Weather.Treeview",
        rowheight=33,
        background="white",
        fieldbackground="white",
        foreground=COLORS["text"],
        borderwidth=0,
        font=(FONTS["family"], 10),
    )
    style.map(
        "Weather.Treeview",
        background=[("selected", "#CBF5D1")],
        foreground=[("selected", COLORS["text"])],
    )
    style.configure(
        "Weather.Treeview.Heading",
        background="#EDF1EF",
        foreground="#014600",
        relief="flat",
        padding=(10, 9),
        font=(FONTS["family"], 9, "bold"),
    )
    style.map("Weather.Treeview.Heading", background=[("active", "#DFF4E3")])
    style.configure("TNotebook", background=COLORS["background"], borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        padding=(18, 10),
        foreground=COLORS["muted"],
        background="#E2EAE5",
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", "white")],
        foreground=[("selected", COLORS["teal"])],
    )
    for orientation in ("Vertical", "Horizontal"):
        style.configure(
            orientation + ".TScrollbar",
            background="#B5C0BC",
            troughcolor=COLORS["background"],
            bordercolor=COLORS["background"],
            arrowcolor="#535554",
            arrowsize=12,
        )
    apply_button_gradient(root, style)
    return style


def apply_button_gradient(root, style):
    """Paint the existing accent buttons green-to-lime without changing their size."""
    # Existing button padding adds 18 pixels and its focus border adds 2 pixels.
    text_height = tkfont.Font(root=root, font=(FONTS["family"], 10)).metrics(
        "linespace"
    )
    height = text_height + 20
    normal = gradient_image(root, height, "#0AA43E", "#68F176")
    active = gradient_image(root, height, "#68F176", "#0AA43E")
    disabled = gradient_image(root, height, COLORS["border"], COLORS["border"])
    style.element_create(
        "Weather.Button.gradient",
        "image",
        normal,
        ("disabled", disabled),
        ("active", active),
        border=0,
        sticky="nswe",
    )
    # Reuse the original padding, focus indicator and text layout.
    layout = style.layout("Accent.TButton")
    options = layout[0][1]
    options.pop("border", None)
    style.layout("Accent.TButton", [("Weather.Button.gradient", options)])
    style.button_images = (normal, active, disabled)


def gradient_image(root, height, start_color, end_color):
    """Build a small native Tk image containing a vertical color gradient."""
    image = tk.PhotoImage(master=root, width=3, height=height)
    start = [int(start_color[index : index + 2], 16) for index in (1, 3, 5)]
    end = [int(end_color[index : index + 2], 16) for index in (1, 3, 5)]
    for row in range(height):
        amount = row / max(height - 1, 1)
        channels = []
        for first, last in zip(start, end):
            channels.append(round(first + (last - first) * amount))
        color = "#{:02x}{:02x}{:02x}".format(*channels)
        image.put(color, to=(0, row, 3, row + 1))
    return image


def label(parent, text="", size=10, color=None, bold=False, background=None, **kwargs):
    """Create a label using the application's shared font and colors."""
    return tk.Label(
        parent,
        text=text,
        font=(FONTS["family"], size, "bold" if bold else "normal"),
        foreground=color or COLORS["text"],
        background=background or parent.cget("background"),
        anchor="w",
        **kwargs,
    )


class Card(tk.Frame):
    """A simple rounded card using native Canvas polygons and an inner Frame."""

    def __init__(self, parent, padding=18, color=None, **kwargs):
        super().__init__(parent, background=parent.cget("background"), **kwargs)
        self.color = color or COLORS["card"]
        self.canvas = tk.Canvas(
            self,
            highlightthickness=0,
            borderwidth=0,
            background=parent.cget("background"),
        )
        self.canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.body = tk.Frame(self, background=self.color)
        self.body.pack(fill="both", expand=True, padx=padding, pady=padding)
        self.canvas.bind("<Configure>", self._paint)

    def _paint(self, event):
        self.canvas.delete("card")
        width, height, radius = event.width - 1, event.height - 1, 13
        points = [
            radius,
            1,
            width - radius,
            1,
            width,
            1,
            width,
            radius,
            width,
            height - radius,
            width,
            height,
            width - radius,
            height,
            radius,
            height,
            1,
            height,
            1,
            height - radius,
            1,
            radius,
            1,
            1,
        ]
        self.canvas.create_polygon(
            points,
            smooth=True,
            splinesteps=18,
            fill=self.color,
            outline=COLORS["border"],
            tags="card",
        )


class MetricCard(Card):
    """Display a title, a large value and a short description."""

    def __init__(self, parent, title, value, detail, accent=None):
        super().__init__(parent)
        accent = accent or COLORS["teal"]
        top = tk.Frame(self.body, background="white")
        top.pack(fill="x")
        label(top, title.upper(), 9, COLORS["muted"], True).pack(side="left")
        tk.Frame(top, background=accent, width=7, height=7).pack(side="right", padx=2)
        self.value_label = label(self.body, value, 25, accent, True)
        self.value_label.pack(anchor="w", pady=(9, 5))
        self.detail_label = label(
            self.body, detail, 9, COLORS["muted"], wraplength=190, justify="left"
        )
        self.detail_label.pack(anchor="w")

        def fit(event):
            size = 25
            while (
                size > 16
                and tkfont.Font(
                    root=self, font=(FONTS["family"], size, "bold")
                ).measure(value)
                > event.width
            ):
                size -= 1
            self.value_label.configure(font=(FONTS["family"], size, "bold"))
            self.detail_label.configure(wraplength=max(100, event.width))

        self.body.bind("<Configure>", fit)


class PlotCanvas(tk.Canvas):
    """Small numeric charts. All marks come from actual analysis values."""

    def __init__(self, parent, height=230):
        super().__init__(
            parent, height=height, background="white", highlightthickness=0
        )
        self.series = []
        self.kind = "line"
        self.unit = ""
        self.bind("<Configure>", lambda event: self.redraw())

    def set_data(self, series, unit="", kind="line"):
        self.series = list(series)
        self.unit, self.kind = unit, kind
        self.redraw()

    def redraw(self):
        self.delete("all")
        width, height = max(self.winfo_width(), 250), max(self.winfo_height(), 120)
        left, right, top, bottom = 57, width - 20, 28, height - 36
        if not self.series:
            self.create_text(
                width / 2,
                height / 2,
                text="No observations for this selection",
                fill=COLORS["muted"],
            )
            return
        values = [float(value) for _, value in self.series]
        minimum, maximum = min(values), max(values)
        if self.kind == "bar":
            minimum = min(0, minimum)
        span = maximum - minimum
        if span == 0:
            minimum -= 1
            maximum += 1
        else:
            minimum -= span * 0.14 if self.kind != "bar" else 0
            maximum += span * 0.18
        span = maximum - minimum
        self.create_text(
            left,
            10,
            text=self.unit,
            anchor="w",
            fill=COLORS["muted"],
            font=(FONTS["family"], 9),
        )
        for tick in range(5):
            value = minimum + span * tick / 4
            y = bottom - (bottom - top) * tick / 4
            self.create_line(left, y, right, y, fill="#E3EAE6", dash=(3, 4))
            self.create_text(
                left - 10,
                y,
                text=f"{value:.1f}" if abs(value) < 100 else f"{value:.0f}",
                anchor="e",
                fill=COLORS["muted"],
                font=(FONTS["family"], 8),
            )
        count = len(values)
        cell = (right - left) / max(count, 1)
        points = []
        for index, value in enumerate(values):
            x = left + cell * (index + 0.5)
            y = bottom - (value - minimum) / span * (bottom - top)
            points.extend((x, y))
            if self.kind == "bar":
                zero = bottom - (0 - minimum) / span * (bottom - top)
                self.create_rectangle(
                    x - cell * 0.29,
                    y,
                    x + cell * 0.29,
                    zero,
                    fill=COLORS["teal"],
                    outline="",
                )
            if (
                count <= 14
                or index % max(1, math.ceil(count / 8)) == 0
                or index == count - 1
            ):
                self.create_text(
                    x,
                    bottom + 19,
                    text=str(self.series[index][0]),
                    fill=COLORS["muted"],
                    font=(FONTS["family"], 8),
                )
        if self.kind != "bar":
            if count > 1:
                area = [points[0], bottom] + points + [points[-2], bottom]
                self.create_polygon(area, fill="#E7F8E9", outline="")
                self.create_line(
                    points, fill=COLORS["teal"], width=3, joinstyle="round"
                )
            for index in range(0, len(points), 2):
                x, y = points[index : index + 2]
                if count <= 32:
                    self.create_oval(
                        x - 3,
                        y - 3,
                        x + 3,
                        y + 3,
                        fill="white",
                        outline=COLORS["teal"],
                        width=2,
                    )
        self.create_line(left, bottom, right, bottom, fill=COLORS["border"])


class PagedTable(tk.Frame):
    """Only insert one page into Treeview so a large hourly dataset stays usable."""

    def __init__(self, parent, columns, page_size=200, height=12):
        super().__init__(parent, background="white")
        self.rows = []
        self.page_size, self.page = page_size, 0
        self.visible_rows = height
        self.tree = ttk.Treeview(
            self,
            columns=[key for key, _, _ in columns],
            show="headings",
            style="Weather.Treeview",
            height=height,
            selectmode="browse",
        )
        for key, title, width in columns:
            text_column = key in (
                "timestamp",
                "tags",
                "method",
                "parameter",
                "file",
                "description",
            )
            if text_column:
                anchor = "w"
            elif key == "format":
                anchor = "center"
            else:
                anchor = "e"
            self.tree.heading(key, text=title, anchor=anchor)
            self.tree.column(key, width=width, minwidth=70, anchor=anchor)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.tree.tag_configure("alternate", background="#F5FAF6")
        footer = tk.Frame(self, background="white")
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.caption = label(footer, "", 9, COLORS["muted"])
        self.caption.pack(side="left")
        self.next_button = ttk.Button(
            footer, text="Next  >", command=lambda: self.move(1)
        )
        self.next_button.pack(side="right")
        self.previous_button = ttk.Button(
            footer, text="<  Previous", command=lambda: self.move(-1)
        )
        self.previous_button.pack(side="right", padx=(0, 8))

    def set_rows(self, rows):
        """Store the results and display their first page."""
        self.rows = list(rows)
        self.page = 0
        self.render()

    def move(self, step):
        """Move one page while keeping the page number within valid bounds."""
        last = max(0, (len(self.rows) - 1) // self.page_size)
        self.page = max(0, min(last, self.page + step))
        self.render()

    def render(self):
        """Show at most page_size rows and update the page controls."""
        self.tree.delete(*self.tree.get_children())
        start = self.page * self.page_size
        for index, (identifier, values) in enumerate(
            self.rows[start : start + self.page_size]
        ):
            self.tree.insert(
                "",
                "end",
                iid=str(identifier),
                values=values,
                tags=("alternate",) if index % 2 else (),
            )
        total = len(self.rows)
        pages = max(1, math.ceil(total / self.page_size))
        self.tree.configure(height=min(self.visible_rows, max(1, total)))
        if pages == 1:
            self.next_button.pack_forget()
            self.previous_button.pack_forget()
        else:
            self.next_button.pack(side="right")
            self.previous_button.pack(side="right", padx=(0, 8))
        self.caption.configure(
            text=f"{total:,} records  |  Page {self.page+1} of {pages}"
        )
        self.previous_button.state(["!disabled"] if self.page else ["disabled"])
        self.next_button.state(["!disabled"] if self.page + 1 < pages else ["disabled"])

    def selected_id(self):
        selected = self.tree.selection()
        return selected[0] if selected else None
