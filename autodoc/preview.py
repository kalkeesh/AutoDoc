import os
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageTk

from .config import CARD_BG, PREVIEW_BRUSH_LEVELS, PRIMARY_BLUE, TEST_METADATA_FIELDS, TEXT_DARK
from .storage import (
    ensure_screenshot_backup,
    get_preview_metadata,
    get_preview_note,
    get_screenshot_backup_path,
    list_saved_screenshots,
    remove_preview_note,
    set_preview_metadata,
    set_preview_note,
)

class PreviewManager:
    def __init__(self, app, document_manager):
        self.app = app
        self.document_manager = document_manager
        self.window = None
        self.canvas = None
        self.action_bar = None
        self.metadata_frame = None
        self.metadata_textboxes = {}
        self.note_textbox = None
        self.note_save_after_id = None
        self.metadata_save_after_id = None
        self.index_var = None
        self.buttons = {}
        self.paths = []
        self.current_index = 0
        self.current_image_path = None
        self.base_image = None
        self.annotated_image = None
        self.annotation_draw = None
        self.dirty = False
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.tool_mode = "pan"
        self.brush_index = 1
        self.brush_size = PREVIEW_BRUSH_LEVELS[self.brush_index]
        self.eraser_size = 24
        self.eraser_scale = None
        self.display_size = (0, 0)
        self.preview_photo = None
        self.preview_drag_origin = None
        self.last_point = None
        self.loading_note = False
        self.loading_metadata = False
        self.current_note_cache = ""
        self.current_metadata_cache = None
        self.canvas_update_after_id = None
        self.is_interacting = False

    def is_visible(self):
        return self.window is not None and self.window.winfo_exists() and self.window.state() != "withdrawn"

    def show(self):
        if self.window is not None and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            self.update_canvas()

    def hide(self):
        if self.window is not None and self.window.winfo_exists():
            self.window.withdraw()

    def refresh_paths(self):
        self.paths = list_saved_screenshots()
        if self.paths:
            if self.current_index >= len(self.paths):
                self.current_index = len(self.paths) - 1
            if self.current_index < -1:
                self.current_index = -1
        else:
            self.current_index = -1
        return self.paths

    def _current_path(self):
        return self.paths[self.current_index] if self.paths and self.current_index >= 0 else None

    def open_window(self):
        if self.window is not None and self.window.winfo_exists():
            self.show()
            return

        self.window = tk.Toplevel(self.app.root)
        self.window.title("Screenshot Preview")
        self.window.geometry("980x760+760+100")
        self.window.minsize(860, 680)
        self.window.configure(bg=CARD_BG)
        self.window.attributes("-topmost", True)

        top_bar = tk.Frame(self.window, bg=CARD_BG)
        top_bar.pack(fill="x", padx=14, pady=(14, 8))

        self.buttons["prev"] = tk.Button(
            top_bar,
            text="\u2190",
            command=lambda: self.show_at(self.current_index - 1),
            relief="flat",
            bg=CARD_BG,
            activebackground="#eef2ff",
            fg=TEXT_DARK,
            font=("Segoe UI Symbol", 13),
            bd=0,
            width=2,
            pady=1,
        )
        self.buttons["prev"].pack(side="left")

        self.index_var = tk.StringVar(value="0 / 0")
        tk.Label(
            top_bar,
            textvariable=self.index_var,
            bg=CARD_BG,
            fg=TEXT_DARK,
            font=("Segoe UI Semibold", 12),
        ).pack(side="left", padx=10)

        self.buttons["next"] = tk.Button(
            top_bar,
            text="\u2192",
            command=lambda: self.show_at(self.current_index + 1),
            relief="flat",
            bg=CARD_BG,
            activebackground="#eef2ff",
            fg=TEXT_DARK,
            font=("Segoe UI Symbol", 13),
            bd=0,
            width=2,
            pady=1,
        )
        self.buttons["next"].pack(side="left")

        self.buttons["zoom_out"] = tk.Button(
            top_bar,
            text="-",
            command=lambda: self.zoom_view(-0.25),
            relief="flat",
            bg=CARD_BG,
            activebackground="#eef2ff",
            fg=TEXT_DARK,
            font=("Segoe UI Semibold", 12),
            bd=0,
            width=2,
            pady=1,
        )
        self.buttons["zoom_out"].pack(side="left", padx=(16, 0))

        self.buttons["zoom_in"] = tk.Button(
            top_bar,
            text="+",
            command=lambda: self.zoom_view(0.25),
            relief="flat",
            bg=CARD_BG,
            activebackground="#eef2ff",
            fg=TEXT_DARK,
            font=("Segoe UI Semibold", 12),
            bd=0,
            width=2,
            pady=1,
        )
        self.buttons["zoom_in"].pack(side="left", padx=(8, 0))

        self.buttons["pan"] = tk.Button(
            top_bar,
            text="\u270b",
            command=lambda: self.set_tool_mode("pan"),
            relief="flat",
            bg=CARD_BG,
            activebackground="#eef2ff",
            fg=PRIMARY_BLUE,
            font=("Segoe UI Symbol", 12),
            bd=0,
            width=2,
            pady=1,
        )
        self.buttons["pan"].pack(side="left", padx=(16, 0))

        self.buttons["highlight"] = tk.Button(
            top_bar,
            text="\u270e",
            command=lambda: self.set_tool_mode("highlight"),
            relief="flat",
            bg=CARD_BG,
            activebackground="#fff6d8",
            fg=TEXT_DARK,
            font=("Segoe UI Symbol", 12),
            bd=0,
            width=2,
            pady=1,
        )
        self.buttons["highlight"].pack(side="left", padx=(8, 0))

        self.buttons["eraser"] = tk.Button(
            top_bar,
            text="\u232b",
            command=lambda: self.set_tool_mode("eraser"),
            relief="flat",
            bg=CARD_BG,
            activebackground="#eef2ff",
            fg=TEXT_DARK,
            font=("Segoe UI Symbol", 12),
            bd=0,
            width=2,
            pady=1,
        )
        self.buttons["eraser"].pack(side="left", padx=(8, 0))

        self.eraser_scale = tk.Scale(
            top_bar,
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
        self.eraser_scale.pack(side="left", padx=(6, 0))

        tk.Label(
            top_bar,
            bg=CARD_BG,
            fg="#6d7891",
            font=("Segoe UI Semibold", 9),
            text="Brush",
        ).pack(side="left", padx=(16, 4))

        for index, label in enumerate(("S", "M", "L", "XL")):
            self.buttons[f"brush_{label}"] = tk.Button(
                top_bar,
                text=label,
                command=lambda idx=index: self.set_brush_level(idx),
                relief="flat",
                bg=CARD_BG,
                activebackground="#fff6d8",
                fg=TEXT_DARK,
                font=("Segoe UI Semibold", 9),
                bd=0,
                width=3,
                pady=2,
            )
            self.buttons[f"brush_{label}"].pack(side="left", padx=(4 if index else 0, 0))

        self.buttons["delete"] = tk.Button(
            top_bar,
            text="\U0001F5D1",
            command=self.delete_current_image,
            relief="flat",
            bg=CARD_BG,
            activebackground="#ffecef",
            fg="#8b1e2d",
            font=("Segoe UI Symbol", 12),
            bd=0,
            width=2,
            pady=1,
        )
        self.buttons["delete"].pack(side="right")

        self.metadata_frame = tk.Frame(self.window, bg=CARD_BG)
        for key, label in TEST_METADATA_FIELDS:
            tk.Label(
                self.metadata_frame,
                text=label,
                bg=CARD_BG,
                fg=TEXT_DARK,
                font=("Segoe UI Semibold", 10),
            ).pack(anchor="w", padx=14, pady=(8 if key == "scenario" else 10, 4))
            textbox = tk.Text(
                self.metadata_frame,
                height=4,
                wrap="word",
                font=("Segoe UI", 10),
                bd=1,
                relief="solid",
                padx=10,
                pady=7,
                fg=TEXT_DARK,
                highlightthickness=1,
                highlightbackground="#d9deea",
            )
            textbox.pack(fill="x", padx=14)
            textbox.bind("<KeyRelease>", self.schedule_metadata_save)
            textbox.bind("<FocusOut>", self.save_metadata)
            self.metadata_textboxes[key] = textbox

        self.note_textbox = tk.Text(
            self.window,
            height=3,
            wrap="word",
            font=("Segoe UI", 10),
            bd=1,
            relief="solid",
            padx=10,
            pady=7,
            fg=TEXT_DARK,
            highlightthickness=1,
            highlightbackground="#d9deea",
        )
        self.note_textbox.pack(fill="x", padx=14, pady=(0, 10))
        self.note_textbox.bind("<KeyRelease>", self.schedule_note_save)
        self.note_textbox.bind("<FocusOut>", self.save_current_note)

        self.canvas = tk.Canvas(
            self.window,
            width=920,
            height=590,
            bg="#eff3ff",
            highlightthickness=1,
            highlightbackground="#d9deea",
            cursor="fleur",
        )
        self.canvas.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.canvas.bind("<Configure>", lambda _event: self.update_canvas())
        self.canvas.bind("<ButtonPress-1>", self.start_interaction)
        self.canvas.bind("<B1-Motion>", self.drag_interaction)
        self.canvas.bind("<ButtonRelease-1>", self.end_interaction)

        self.action_bar = tk.Frame(self.window, bg=CARD_BG)
        self.action_bar.pack(fill="x", padx=14, pady=(0, 12))

        tk.Button(
            self.action_bar,
            text="Reset",
            command=self.reset_highlight,
            relief="flat",
            bg="#fff4c2",
            fg="#7a5b00",
            padx=10,
            pady=4,
        ).pack(side="left")

        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
        self.set_tool_mode("pan")
        self._update_brush_buttons()
        self.show_at(len(self.refresh_paths()) - 1)

    def close_window(self):
        self.save_metadata()
        self.save_current_note()
        if self.window is not None and self.window.winfo_exists():
            self.window.destroy()
        self._reset_state()

    def _reset_state(self):
        if self.canvas_update_after_id is not None and self.window is not None and self.window.winfo_exists():
            self.window.after_cancel(self.canvas_update_after_id)
        if self.note_save_after_id is not None and self.window is not None and self.window.winfo_exists():
            self.window.after_cancel(self.note_save_after_id)
        if self.metadata_save_after_id is not None and self.window is not None and self.window.winfo_exists():
            self.window.after_cancel(self.metadata_save_after_id)
        self.window = None
        self.canvas = None
        self.action_bar = None
        self.metadata_frame = None
        self.metadata_textboxes.clear()
        self.note_textbox = None
        self.note_save_after_id = None
        self.metadata_save_after_id = None
        self.index_var = None
        self.buttons.clear()
        self.paths = []
        self.current_index = 0
        self.current_image_path = None
        self.base_image = None
        self.annotated_image = None
        self.annotation_draw = None
        self.dirty = False
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.tool_mode = "pan"
        self.brush_index = 1
        self.brush_size = PREVIEW_BRUSH_LEVELS[self.brush_index]
        self.eraser_size = 24
        self.eraser_scale = None
        self.display_size = (0, 0)
        self.preview_photo = None
        self.preview_drag_origin = None
        self.last_point = None
        self.loading_note = False
        self.loading_metadata = False
        self.current_note_cache = ""
        self.current_metadata_cache = None
        self.canvas_update_after_id = None
        self.is_interacting = False

    def show_at(self, index):
        if self.current_index == -1:
            self.save_metadata()
        else:
            self.save_current_note()
        self.current_index = max(-1, min(index, len(self.paths) - 1)) if self.paths else -1
        self.update_canvas()

    def zoom_view(self, delta):
        self.zoom = max(1.0, min(3.0, self.zoom + delta))
        if self.zoom == 1.0:
            self.pan_x = 0
            self.pan_y = 0
        self.update_canvas()

    def set_brush_level(self, index):
        self.brush_index = max(0, min(len(PREVIEW_BRUSH_LEVELS) - 1, index))
        self.brush_size = PREVIEW_BRUSH_LEVELS[self.brush_index]
        self._update_brush_buttons()

    def set_eraser_size(self, value):
        self.eraser_size = max(4, int(float(value)))

    def _update_brush_buttons(self):
        for index, label in enumerate(("S", "M", "L", "XL")):
            button = self.buttons.get(f"brush_{label}")
            if button is None or not button.winfo_exists():
                continue
            is_active = index == self.brush_index
            button.configure(
                bg="#ffe89a" if is_active else CARD_BG,
                fg="#7a5b00" if is_active else TEXT_DARK,
            )

    def set_tool_mode(self, mode):
        self.tool_mode = mode
        if self.canvas is not None and self.canvas.winfo_exists():
            cursor = "fleur" if mode == "pan" else ("dotbox" if mode == "eraser" else "pencil")
            self.canvas.configure(cursor=cursor)

        pan_button = self.buttons.get("pan")
        highlight_button = self.buttons.get("highlight")
        eraser_button = self.buttons.get("eraser")
        if pan_button is not None and pan_button.winfo_exists():
            pan_button.configure(fg=PRIMARY_BLUE if mode == "pan" else TEXT_DARK)
        if highlight_button is not None and highlight_button.winfo_exists():
            highlight_button.configure(fg="#b58900" if mode == "highlight" else TEXT_DARK)
        if eraser_button is not None and eraser_button.winfo_exists():
            eraser_button.configure(fg="#8b1e2d" if mode == "eraser" else TEXT_DARK)

    def start_interaction(self, event):
        self.is_interacting = True
        self.preview_drag_origin = (event.x, event.y)
        if self.tool_mode in ("highlight", "eraser"):
            self.last_point = self._canvas_to_image_coords(event)
        else:
            self.last_point = None

    def drag_interaction(self, event):
        if self.tool_mode == "eraser":
            point = self._canvas_to_image_coords(event)
            if point is None:
                self.last_point = None
                return
            if self.last_point is None:
                self.last_point = point
                return
            self._erase_at(self.last_point, point)
            self.last_point = point
            self.dirty = True
            self.request_canvas_update()
            return

        if self.tool_mode == "highlight":
            if self.annotation_draw is None:
                return
            point = self._canvas_to_image_coords(event)
            if point is None:
                self.last_point = None
                return
            if self.last_point is None:
                self.last_point = point
                return
            draw = ImageDraw.Draw(self.annotation_draw)
            draw.line(
                (self.last_point[0], self.last_point[1], point[0], point[1]),
                fill=(255, 235, 59, 150),
                width=self.brush_size,
            )
            self.last_point = point
            self.dirty = True
            self.request_canvas_update()
            return

        if self.preview_drag_origin is None:
            self.preview_drag_origin = (event.x, event.y)
            return

        dx = event.x - self.preview_drag_origin[0]
        dy = event.y - self.preview_drag_origin[1]
        self.preview_drag_origin = (event.x, event.y)
        self.pan_x += dx
        self.pan_y += dy
        self.request_canvas_update()

    def end_interaction(self, _event):
        self.preview_drag_origin = None
        if self.tool_mode == "eraser" and self.last_point is not None:
            self._erase_at(self.last_point, self.last_point)
            self.dirty = True
        self.last_point = None
        self.is_interacting = False
        if self.tool_mode in ("highlight", "eraser") and self.dirty:
            self.save_highlight()
        else:
            self.update_canvas()

    def request_canvas_update(self):
        if self.window is None or not self.window.winfo_exists():
            return
        if self.canvas_update_after_id is not None:
            return
        self.canvas_update_after_id = self.window.after(33, self._run_canvas_update)

    def _run_canvas_update(self):
        self.canvas_update_after_id = None
        self.update_canvas()

    def update_canvas(self):
        if self.window is None or not self.window.winfo_exists() or self.canvas is None:
            return
        if self.canvas_update_after_id is not None:
            self.window.after_cancel(self.canvas_update_after_id)
            self.canvas_update_after_id = None

        self.refresh_paths()
        if self.current_index == -1:
            self._show_metadata_page()
            return

        self._show_screenshot_page()
        if not self.paths:
            self.canvas.delete("all")
            self.canvas.create_text(
                190,
                150,
                text="No screenshots yet.\nTake one and it will appear here.",
                fill="#5d6880",
                font=("Segoe UI", 11),
                justify="center",
            )
            if self.index_var is not None:
                self.index_var.set("0 / 0")
            self.current_image_path = None
            self.base_image = None
            self.annotated_image = None
            self.annotation_draw = None
            self.dirty = False
            self.load_note_for_current_image()
            self._set_controls_enabled(False)
            return

        image_path = self._current_path()
        if image_path != self.current_image_path or self.base_image is None:
            self.save_current_note()
            base_image = Image.open(image_path).convert("RGBA")
            self.base_image = base_image
            self.annotated_image = base_image.copy()
            self.annotation_draw = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
            self.current_image_path = image_path
            self.dirty = False
            self.pan_x = 0
            self.pan_y = 0
            self.load_note_for_current_image()

        canvas_width = max(240, self.canvas.winfo_width())
        canvas_height = max(180, self.canvas.winfo_height())
        display_image = Image.alpha_composite(self.annotated_image, self.annotation_draw)
        viewport_width = max(80, canvas_width - 16)
        viewport_height = max(80, canvas_height - 16)
        base_scale = min(viewport_width / display_image.width, viewport_height / display_image.height)
        render_scale = base_scale * self.zoom
        scaled_width = max(1, int(display_image.width * render_scale))
        scaled_height = max(1, int(display_image.height * render_scale))
        resample_filter = Image.Resampling.BILINEAR if self.is_interacting else Image.Resampling.LANCZOS
        scaled_image = display_image.resize((scaled_width, scaled_height), resample_filter)

        max_pan_x = max(0, (scaled_width - viewport_width) / 2)
        max_pan_y = max(0, (scaled_height - viewport_height) / 2)
        self.pan_x = max(-max_pan_x, min(max_pan_x, self.pan_x))
        self.pan_y = max(-max_pan_y, min(max_pan_y, self.pan_y))

        viewport = Image.new("RGBA", (viewport_width, viewport_height), (239, 243, 255, 255))
        paste_x = int((viewport_width - scaled_width) / 2 + self.pan_x)
        paste_y = int((viewport_height - scaled_height) / 2 + self.pan_y)
        viewport.paste(scaled_image, (paste_x, paste_y), scaled_image)

        self.display_size = (scaled_width, scaled_height)
        self.preview_photo = ImageTk.PhotoImage(viewport)

        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, canvas_width, canvas_height, fill="#eff3ff", outline="")
        self.canvas.create_image(canvas_width / 2, canvas_height / 2, image=self.preview_photo)
        self.canvas.create_rectangle(8, 8, canvas_width - 8, canvas_height - 8, outline="#cfd7ef", width=1)

        if self.index_var is not None:
            self.index_var.set(f"{self.current_index + 1} / {len(self.paths)}")
        self._set_controls_enabled(True)

    def _show_metadata_page(self):
        self.current_image_path = None
        self.base_image = None
        self.annotated_image = None
        self.annotation_draw = None
        self.dirty = False
        if self.note_textbox is not None and self.note_textbox.winfo_manager():
            self.note_textbox.pack_forget()
        if self.canvas is not None and self.canvas.winfo_manager():
            self.canvas.pack_forget()
        if self.action_bar is not None and self.action_bar.winfo_manager():
            self.action_bar.pack_forget()
        if self.metadata_frame is not None and not self.metadata_frame.winfo_manager():
            self.metadata_frame.pack(fill="both", expand=True, padx=0, pady=(0, 10))
        self.load_metadata()
        if self.index_var is not None:
            self.index_var.set("Details")
        self._set_metadata_controls()

    def _show_screenshot_page(self):
        if self.metadata_frame is not None and self.metadata_frame.winfo_manager():
            self.metadata_frame.pack_forget()
        if self.note_textbox is not None and not self.note_textbox.winfo_manager():
            self.note_textbox.pack(fill="x", padx=14, pady=(0, 10))
        if self.canvas is not None and not self.canvas.winfo_manager():
            self.canvas.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        if self.action_bar is not None and not self.action_bar.winfo_manager():
            self.action_bar.pack(fill="x", padx=14, pady=(0, 12))

    def _set_metadata_controls(self):
        for key in ("zoom_in", "zoom_out", "pan", "highlight", "eraser", "brush_S", "brush_M", "brush_L", "brush_XL", "delete"):
            button = self.buttons.get(key)
            if button is not None and button.winfo_exists():
                button.configure(state="disabled")
        if self.eraser_scale is not None and self.eraser_scale.winfo_exists():
            self.eraser_scale.configure(state="disabled")
        prev_button = self.buttons.get("prev")
        if prev_button is not None and prev_button.winfo_exists():
            prev_button.configure(state="disabled")
        next_button = self.buttons.get("next")
        if next_button is not None and next_button.winfo_exists():
            next_button.configure(state="normal" if self.paths else "disabled")

    def load_note_for_current_image(self):
        if self.note_textbox is None or not self.note_textbox.winfo_exists():
            return

        self.loading_note = True
        self.note_textbox.configure(state="normal")
        self.note_textbox.delete("1.0", tk.END)
        if self.current_image_path is not None:
            self.current_note_cache = get_preview_note(self.current_image_path)
            self.note_textbox.insert("1.0", self.current_note_cache)
        else:
            self.current_note_cache = ""
        self.loading_note = False

    def schedule_note_save(self, _event=None):
        if self.loading_note or self.window is None or not self.window.winfo_exists():
            return
        if self.note_save_after_id is not None:
            self.window.after_cancel(self.note_save_after_id)
        self.note_save_after_id = self.window.after(800, self.save_current_note)

    def save_current_note(self, _event=None):
        if self.note_save_after_id is not None and self.window is not None and self.window.winfo_exists():
            self.window.after_cancel(self.note_save_after_id)
            self.note_save_after_id = None
        if self.note_textbox is None or not self.note_textbox.winfo_exists() or self.current_image_path is None:
            return

        note_text = self.note_textbox.get("1.0", tk.END).strip()
        if note_text == self.current_note_cache:
            return
        set_preview_note(self.current_image_path, note_text)
        self.document_manager.set_image_note(self.current_image_path, note_text)
        self.current_note_cache = note_text

    def load_metadata(self):
        if not self.metadata_textboxes:
            return
        if self.loading_metadata:
            return

        metadata = get_preview_metadata()
        self.loading_metadata = True
        for key, textbox in self.metadata_textboxes.items():
            if textbox is None or not textbox.winfo_exists():
                continue
            textbox.delete("1.0", tk.END)
            textbox.insert("1.0", metadata.get(key, ""))
        self.current_metadata_cache = metadata
        self.loading_metadata = False

    def schedule_metadata_save(self, _event=None):
        if self.loading_metadata or self.window is None or not self.window.winfo_exists():
            return
        if self.metadata_save_after_id is not None:
            self.window.after_cancel(self.metadata_save_after_id)
        self.metadata_save_after_id = self.window.after(800, self.save_metadata)

    def save_metadata(self, _event=None):
        if self.metadata_save_after_id is not None and self.window is not None and self.window.winfo_exists():
            self.window.after_cancel(self.metadata_save_after_id)
            self.metadata_save_after_id = None
        if not self.metadata_textboxes:
            return

        metadata = {}
        for key, textbox in self.metadata_textboxes.items():
            if textbox is None or not textbox.winfo_exists():
                metadata[key] = self.current_metadata_cache.get(key, "") if self.current_metadata_cache is not None else ""
                continue
            metadata[key] = textbox.get("1.0", tk.END).strip()

        if self.current_metadata_cache is None:
            return
        if metadata == self.current_metadata_cache:
            return
        set_preview_metadata(metadata)
        self.document_manager.set_test_metadata(metadata)
        self.current_metadata_cache = metadata

    def _set_controls_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for key in (
            "prev",
            "next",
            "delete",
            "zoom_in",
            "zoom_out",
            "pan",
            "highlight",
            "eraser",
            "brush_S",
            "brush_M",
            "brush_L",
            "brush_XL",
        ):
            button = self.buttons.get(key)
            if button is not None and button.winfo_exists():
                button.configure(state=state)
        if self.eraser_scale is not None and self.eraser_scale.winfo_exists():
            self.eraser_scale.configure(state=state)
        if self.note_textbox is not None and self.note_textbox.winfo_exists():
            self.note_textbox.configure(state="normal" if enabled else "disabled")

    def _canvas_to_image_coords(self, event):
        if self.base_image is None or self.canvas is None or self.preview_photo is None:
            return None

        canvas_width = max(240, self.canvas.winfo_width())
        canvas_height = max(180, self.canvas.winfo_height())
        viewport_width = max(80, canvas_width - 16)
        viewport_height = max(80, canvas_height - 16)
        display_width, display_height = self.display_size
        origin_x = 8 + (viewport_width - display_width) / 2 + self.pan_x
        origin_y = 8 + (viewport_height - display_height) / 2 + self.pan_y

        if not (origin_x <= event.x <= origin_x + display_width and origin_y <= event.y <= origin_y + display_height):
            return None

        scale_x = self.base_image.width / display_width
        scale_y = self.base_image.height / display_height
        image_x = int((event.x - origin_x) * scale_x)
        image_y = int((event.y - origin_y) * scale_y)
        return image_x, image_y

    def _erase_at(self, start, end):
        if self.base_image is None or self.annotated_image is None or start is None or end is None:
            return

        mask = Image.new("L", self.base_image.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.line((start[0], start[1], end[0], end[1]), fill=255, width=self.eraser_size)
        radius = max(1, self.eraser_size // 2)
        for x, y in (start, end):
            mask_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)

        if self.annotation_draw is not None:
            transparent = Image.new("RGBA", self.annotation_draw.size, (0, 0, 0, 0))
            self.annotation_draw.paste(transparent, (0, 0), mask)

        backup_path = get_screenshot_backup_path(self.current_image_path)
        if os.path.exists(backup_path):
            original = Image.open(backup_path).convert("RGBA")
            if original.size != self.annotated_image.size:
                original = original.resize(self.annotated_image.size, Image.Resampling.LANCZOS)
            self.annotated_image.paste(original, (0, 0), mask)

    def reset_highlight(self):
        if self.current_image_path is None:
            self.app.set_status("Reset needs an original backup for this screenshot.")
            return

        backup_path = get_screenshot_backup_path(self.current_image_path)
        if os.path.exists(backup_path):
            restored_image = Image.open(backup_path).convert("RGB")
            restored_image.save(self.current_image_path)
            self.base_image = restored_image.convert("RGBA")
            self.annotated_image = self.base_image.copy()
            self.annotation_draw = Image.new("RGBA", self.base_image.size, (0, 0, 0, 0))
            self.dirty = False
            if self.document_manager.has_document():
                note_element = self.document_manager.tracked_notes.get(self.document_manager._normalize_path(self.current_image_path))
                self.document_manager.remove_tracked_image(self.current_image_path, remove_note=False)
                self.document_manager.append_image(self.current_image_path, note_element=note_element)
                self.document_manager.save()
            self.update_canvas()
            self.app.set_status(
                f"Reset screenshot to original in {os.path.basename(self.document_manager.path)}"
                if self.document_manager.has_document()
                else "Reset screenshot to original."
            )
            return

        if self.dirty:
            self.annotation_draw = Image.new("RGBA", self.base_image.size, (0, 0, 0, 0))
            self.dirty = False
            self.update_canvas()
            self.app.set_status("Unsaved highlight cleared.")
            return

        self.app.set_status("Reset needs an original backup for this screenshot.")

    def save_highlight(self):
        if not self.document_manager.has_document():
            messagebox.showwarning("No document", "Create or select a Word document first.")
            return

        if self.base_image is None or self.current_image_path is None:
            self.app.set_status("No screenshot selected in preview.")
            return

        if not self.dirty:
            self.app.set_status("Add a yellow highlight first, then save it.")
            return

        ensure_screenshot_backup(self.current_image_path)
        highlighted_image = Image.alpha_composite(self.annotated_image, self.annotation_draw).convert("RGB")
        highlighted_image.save(self.current_image_path)
        self.base_image = highlighted_image.convert("RGBA")
        self.annotated_image = self.base_image.copy()
        self.annotation_draw = Image.new("RGBA", self.base_image.size, (0, 0, 0, 0))
        note_element = self.document_manager.tracked_notes.get(self.document_manager._normalize_path(self.current_image_path))
        self.document_manager.remove_tracked_image(self.current_image_path, remove_note=False)
        self.document_manager.append_image(self.current_image_path, note_element=note_element)
        self.document_manager.save()
        self.dirty = False
        self.refresh_paths()
        self.update_canvas()
        self.app.set_status(f"Saved highlighted screenshot to {os.path.basename(self.document_manager.path)}")

    def delete_current_image(self):
        if self.current_image_path is None:
            self.app.set_status("No screenshot selected to delete.")
            return

        image_name = os.path.basename(self.current_image_path)
        backup_path = get_screenshot_backup_path(self.current_image_path)
        try:
            if self.document_manager.has_document():
                self.document_manager.remove_tracked_image(self.current_image_path)
                self.document_manager.save()
            os.remove(self.current_image_path)
            if os.path.exists(backup_path):
                os.remove(backup_path)
            remove_preview_note(self.current_image_path)
        except Exception as exc:
            messagebox.showerror("Delete failed", f"Could not delete screenshot.\n\n{exc}")
            return

        self.refresh_paths()
        if self.paths:
            self.show_at(min(self.current_index, len(self.paths) - 1))
        else:
            self.current_index = 0
            self.update_canvas()

        self.app.show_toast("Screenshot deleted")
        self.app.set_status(f"Deleted screenshot: {image_name}")


