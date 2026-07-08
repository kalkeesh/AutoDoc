import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from .capture import capture_image, get_workarea_bbox
from .config import CARD_BG, PREVIEW_BRUSH_LEVELS, TEXT_DARK

class DrawingManager:
    def __init__(self, app):
        self.app = app
        self.overlay = None
        self.toolbar = None
        self.canvas = None
        self.tool = "pencil"
        self.color = "#f61d2a"
        self.start_point = None
        self.last_point = None
        self.preview_item = None
        self.background_image = None
        self.background_photo = None
        self.annotation_image = None
        self.annotation_draw = None
        self.tool_buttons = {}
        self.color_buttons = {}
        self.highlight_size = PREVIEW_BRUSH_LEVELS[1]
        self.highlight_scale = None
        self.eraser_size = 24
        self.eraser_scale = None
        self.was_visible_for_capture = False

    def is_visible(self):
        return self.overlay is not None and self.overlay.winfo_exists() and self.overlay.state() != "withdrawn"

    def toggle(self):
        if self.is_visible():
            self.hide(clear=False)
            self.app.set_status("Draw hidden.")
        else:
            self.show()

    def show(self):
        self.app.root.withdraw()
        self.app.root.update()
        background = capture_image()

        if self.overlay is None or not self.overlay.winfo_exists():
            self._build_overlay(background)
        else:
            self._load_background(background)
        if self.toolbar is None or not self.toolbar.winfo_exists():
            self._build_toolbar()

        self.overlay.deiconify()
        self.overlay.lift()
        self.overlay.attributes("-topmost", True)
        self.overlay.focus_force()
        self.app.root.deiconify()
        self.app.root.lift()
        self.app.root.attributes("-topmost", True)
        self.toolbar.deiconify()
        self.toolbar.lift()
        self.toolbar.attributes("-topmost", True)
        self._bring_controls_to_front()
        self._apply_cursor()
        self._update_button_states()
        self.app.set_status("Draw mode on. Draw on the screen, then press Shot.")

    def hide(self, clear=False):
        if self.toolbar is not None and self.toolbar.winfo_exists():
            self.toolbar.withdraw()
        if self.overlay is not None and self.overlay.winfo_exists():
            self.overlay.withdraw()
        if clear and self.canvas is not None and self.canvas.winfo_exists():
            self.canvas.delete("all")
            self.annotation_image = None
            self.annotation_draw = None
            self.background_image = None
            self.background_photo = None
        self.start_point = None
        self.last_point = None
        self.preview_item = None

    def _build_overlay(self, background):
        screen_width, screen_height = background.size
        self.overlay = tk.Toplevel(self.app.root)
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)
        self.overlay.geometry(f"{screen_width}x{screen_height}+0+0")
        self.overlay.configure(bg="black")

        self.canvas = tk.Canvas(
            self.overlay,
            width=screen_width,
            height=screen_height,
            bg="black",
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.start_draw)
        self.canvas.bind("<B1-Motion>", self.drag_draw)
        self.canvas.bind("<ButtonRelease-1>", self.end_draw)
        self.overlay.bind("<Escape>", lambda _event: self.hide(clear=False))
        self._load_background(background)

    def _load_background(self, background):
        if self.canvas is None or not self.canvas.winfo_exists():
            return
        self.background_image = background.convert("RGBA")
        self.annotation_image = Image.new("RGBA", background.size, (0, 0, 0, 0))
        self.annotation_draw = ImageDraw.Draw(self.annotation_image)
        self.background_photo = ImageTk.PhotoImage(background)
        self.canvas.delete("all")
        self.canvas.config(width=background.width, height=background.height)
        self.canvas.create_image(0, 0, image=self.background_photo, anchor="nw", tags=("background",))
        self.canvas.tag_lower("background")

    def _render_annotation_overlay(self):
        if (
            self.canvas is None
            or not self.canvas.winfo_exists()
            or self.background_image is None
            or self.annotation_image is None
        ):
            return

        display_image = Image.alpha_composite(self.background_image, self.annotation_image)
        self.background_photo = ImageTk.PhotoImage(display_image.convert("RGB"))
        self.canvas.itemconfigure("background", image=self.background_photo)
        self.canvas.tag_lower("background")

    def _build_toolbar(self):
        self.toolbar = tk.Toplevel(self.app.root)
        self.toolbar.overrideredirect(True)
        self.toolbar.attributes("-topmost", True)
        self.toolbar.configure(bg=CARD_BG)
        self.toolbar.geometry("+80+80")

        frame = tk.Frame(self.toolbar, bg=CARD_BG, bd=1, relief="solid")
        frame.pack()

        tool_specs = (
            ("pencil", "\u270e"),
            ("highlight", "H"),
            ("line", "/"),
            ("rect", "\u25a1"),
            ("circle", "\u25cb"),
            ("eraser", "\u232b"),
        )
        for tool_name, icon in tool_specs:
            button = tk.Button(
                frame,
                text=icon,
                width=2,
                relief="flat",
                bd=0,
                bg=CARD_BG,
                fg=TEXT_DARK,
                activebackground="#eef2ff",
                command=lambda name=tool_name: self.set_tool(name),
            )
            button.pack(side="left", padx=2, pady=3)
            self.tool_buttons[tool_name] = button

        for color in ("#f61d2a", "#f7d038", "#188038", "#1a73e8", "#111827"):
            button = tk.Button(
                frame,
                width=2,
                relief="flat",
                bd=0,
                bg=color,
                activebackground=color,
                command=lambda value=color: self.set_color(value),
            )
            button.pack(side="left", padx=2, pady=3)
            self.color_buttons[color] = button

        tk.Label(
            frame,
            text="H",
            bg=CARD_BG,
            fg=TEXT_DARK,
            font=("Segoe UI Semibold", 9),
        ).pack(side="left", padx=(8, 0), pady=3)

        self.highlight_scale = tk.Scale(
            frame,
            from_=8,
            to=48,
            orient="horizontal",
            length=90,
            showvalue=False,
            bg=CARD_BG,
            highlightthickness=0,
            command=self.set_highlight_size,
        )
        self.highlight_scale.set(self.highlight_size)
        self.highlight_scale.pack(side="left", padx=(2, 4), pady=3)

        self.eraser_scale = tk.Scale(
            frame,
            from_=8,
            to=80,
            orient="horizontal",
            length=110,
            showvalue=False,
            bg=CARD_BG,
            highlightthickness=0,
            command=self.set_eraser_size,
        )
        self.eraser_scale.set(self.eraser_size)
        self.eraser_scale.pack(side="left", padx=(8, 4), pady=3)

    def set_tool(self, tool):
        self.tool = tool
        self._apply_cursor()
        self._update_button_states()
        self._bring_controls_to_front()

    def set_color(self, color):
        self.color = color
        self._update_button_states()
        self._bring_controls_to_front()

    def set_highlight_size(self, value):
        self.highlight_size = max(4, int(float(value)))
        self._bring_controls_to_front()

    def set_eraser_size(self, value):
        self.eraser_size = max(4, int(float(value)))
        self._bring_controls_to_front()

    def _update_button_states(self):
        for tool, button in self.tool_buttons.items():
            if button.winfo_exists():
                button.configure(bg="#e8edff" if tool == self.tool else CARD_BG)
        for color, button in self.color_buttons.items():
            if button.winfo_exists():
                button.configure(relief="solid" if color == self.color else "flat", bd=2 if color == self.color else 0)

    def _apply_cursor(self):
        if self.canvas is None or not self.canvas.winfo_exists():
            return
        cursor_by_tool = {
            "pencil": "pencil",
            "highlight": "pencil",
            "line": "crosshair",
            "rect": "crosshair",
            "circle": "crosshair",
            "eraser": "dotbox",
        }
        self.canvas.configure(cursor=cursor_by_tool.get(self.tool, "crosshair"))

    def _bring_controls_to_front(self):
        if self.overlay is not None and self.overlay.winfo_exists():
            self.overlay.attributes("-topmost", True)
            try:
                self.overlay.lower(self.app.root)
            except tk.TclError:
                pass
        if self.app.root is not None and self.app.root.winfo_exists():
            self.app.root.deiconify()
            self.app.root.attributes("-topmost", True)
            self.app.root.lift()
        if self.toolbar is not None and self.toolbar.winfo_exists():
            self.toolbar.deiconify()
            self.toolbar.attributes("-topmost", True)
            self.toolbar.lift()

    def start_draw(self, event):
        self.start_point = (event.x, event.y)
        self.last_point = (event.x, event.y)
        self.preview_item = None

    def drag_draw(self, event):
        if self.canvas is None or self.start_point is None:
            return

        if self.tool == "eraser":
            self._erase_annotation_line(self.last_point, (event.x, event.y))
            self.last_point = (event.x, event.y)
            self.canvas.delete("drawn")
            self._render_annotation_overlay()
            return

        if self.tool == "pencil":
            self.canvas.create_line(
                self.last_point[0],
                self.last_point[1],
                event.x,
                event.y,
                fill=self.color,
                width=3,
                capstyle=tk.ROUND,
                smooth=True,
                tags=("drawn",),
            )
            if self.annotation_draw is not None:
                self.annotation_draw.line(
                    (self.last_point[0], self.last_point[1], event.x, event.y),
                    fill=self.color,
                    width=3,
                )
            self.last_point = (event.x, event.y)
            return

        if self.tool == "highlight":
            if self.annotation_draw is None:
                return
            if self.last_point is None:
                self.last_point = (event.x, event.y)
                return
            self.annotation_draw.line(
                (self.last_point[0], self.last_point[1], event.x, event.y),
                fill=(255, 235, 59, 150),
                width=self.highlight_size,
            )
            self.last_point = (event.x, event.y)
            self._render_annotation_overlay()
            return

        if self.preview_item is not None:
            self.canvas.delete(self.preview_item)

        x1, y1 = self.start_point
        x2, y2 = event.x, event.y
        if self.tool == "line":
            self.preview_item = self.canvas.create_line(x1, y1, x2, y2, fill=self.color, width=3, tags=("drawn",))
        elif self.tool == "rect":
            if event.state & 0x0001:
                x2, y2 = self._square_endpoint(x1, y1, x2, y2)
            self.preview_item = self.canvas.create_rectangle(x1, y1, x2, y2, outline=self.color, width=3, tags=("drawn",))
        elif self.tool == "circle":
            x2, y2 = self._square_endpoint(x1, y1, x2, y2)
            self.preview_item = self.canvas.create_oval(x1, y1, x2, y2, outline=self.color, width=3, tags=("drawn",))

    def end_draw(self, event):
        if self.tool == "eraser":
            self._erase_annotation_line(self.last_point, (event.x, event.y))
            if self.canvas is not None and self.canvas.winfo_exists():
                self.canvas.delete("drawn")
            self._render_annotation_overlay()
        if self.tool not in ("pencil", "highlight", "eraser"):
            if self.preview_item is not None and self.canvas is not None and self.canvas.winfo_exists():
                self.canvas.delete(self.preview_item)
                self.preview_item = None
            if self.annotation_draw is not None and self.start_point is not None:
                x1, y1 = self.start_point
                x2, y2 = event.x, event.y
                if self.tool == "line":
                    self.annotation_draw.line((x1, y1, x2, y2), fill=self.color, width=3)
                elif self.tool == "rect":
                    if event.state & 0x0001:
                        x2, y2 = self._square_endpoint(x1, y1, x2, y2)
                    self.annotation_draw.rectangle(self._ordered_bbox(x1, y1, x2, y2), outline=self.color, width=3)
                elif self.tool == "circle":
                    x2, y2 = self._square_endpoint(x1, y1, x2, y2)
                    self.annotation_draw.ellipse(self._ordered_bbox(x1, y1, x2, y2), outline=self.color, width=3)
                if self.canvas is not None and self.canvas.winfo_exists():
                    self.canvas.delete("drawn")
                self._render_annotation_overlay()
        self.start_point = None
        self.last_point = None
        self.preview_item = None
        self._bring_controls_to_front()
        if self.overlay is not None and self.overlay.winfo_exists():
            self.overlay.after(80, self._bring_controls_to_front)

    def _erase_annotation_line(self, start, end):
        if self.annotation_image is None or start is None or end is None:
            return

        mask = Image.new("L", self.annotation_image.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.line((start[0], start[1], end[0], end[1]), fill=255, width=self.eraser_size)
        radius = max(1, self.eraser_size // 2)
        for x, y in (start, end):
            mask_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
        transparent = Image.new("RGBA", self.annotation_image.size, (0, 0, 0, 0))
        self.annotation_image.paste(transparent, (0, 0), mask)
        self.annotation_draw = ImageDraw.Draw(self.annotation_image)

    def _square_endpoint(self, x1, y1, x2, y2):
        side = max(abs(x2 - x1), abs(y2 - y1))
        x2 = x1 + side if x2 >= x1 else x1 - side
        y2 = y1 + side if y2 >= y1 else y1 - side
        return x2, y2

    def _ordered_bbox(self, x1, y1, x2, y2):
        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))
        return left, top, right, bottom

    def prepare_for_capture(self):
        self.was_visible_for_capture = self.is_visible()
        if self.toolbar is not None and self.toolbar.winfo_exists():
            self.toolbar.withdraw()
        if self.overlay is not None and self.overlay.winfo_exists():
            self.overlay.withdraw()
        self.app.root.update_idletasks()

    def apply_to_screenshot(self, screenshot, exclude_taskbar=False):
        if self.annotation_image is None:
            return screenshot

        annotation = self.annotation_image
        if exclude_taskbar:
            left, top, right, bottom = get_workarea_bbox()
            annotation = annotation.crop((left, top, right, bottom))

        base = screenshot.convert("RGBA")
        if annotation.size != base.size:
            annotation = annotation.resize(base.size, Image.Resampling.LANCZOS)
        return Image.alpha_composite(base, annotation).convert("RGB")

    def finish_capture(self):
        if self.was_visible_for_capture:
            self.hide(clear=True)
            self.was_visible_for_capture = False


