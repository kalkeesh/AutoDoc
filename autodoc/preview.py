import os
import threading
import re
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageTk

from .ai import CopilotAIProvider, CopilotConfigurationError
from .config import CARD_BG, PREVIEW_BRUSH_LEVELS, PRIMARY_BLUE, TEST_METADATA_FIELDS, TEXT_DARK
from .storage import (
    ensure_screenshot_backup,
    get_preview_metadata,
    get_preview_note,
    get_preview_tables,
    get_screenshot_backup_path,
    list_saved_screenshots,
    load_preview_notes,
    remove_preview_note,
    remove_preview_tables,
    set_preview_metadata,
    set_preview_note,
    set_preview_tables,
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
        self.note_textbox_frame = None
        self.note_textbox = None
        self.note_scrollbar = None
        self.note_resize_grip = None
        self.note_resize_drag = None
        self.table_preview_frame = None
        self.table_preview_textbox = None
        self.table_preview_grip = None
        self.note_save_after_id = None
        self.table_save_after_id = None
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
        self.current_tables_cache = []
        self.inline_table_widgets = []
        self.table_window = None
        self.table_canvas = None
        self.table_inner = None
        self.table_rows_var = None
        self.table_columns_var = None
        self.table_widgets = []
        self.selected_table_index = None
        self.table_resize_drag = None
        self.current_metadata_cache = None
        self.canvas_update_after_id = None
        self.is_interacting = False
        self.copilot_enabled = False
        self.copilot_provider = CopilotAIProvider.from_env()
        self.copilot_suggestion_pending = False
        self.copilot_log_messages = []
        self.copilot_log_window = None

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

        self.buttons["table"] = tk.Button(
            top_bar,
            text="\u25a6",
            command=self.open_table_editor,
            relief="flat",
            bg=CARD_BG,
            activebackground="#eef2ff",
            fg=TEXT_DARK,
            font=("Segoe UI Symbol", 13),
            bd=0,
            width=2,
            pady=1,
        )
        self.buttons["table"].pack(side="left", padx=(8, 0))

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
        self.buttons["copilot_action"] = tk.Button(
            top_bar,
            text="Generate",
            command=self.apply_copilot_comment,
            relief="flat",
            bg="#eef2ff",
            activebackground="#dfe8ff",
            fg="#6b7280",
            font=("Segoe UI Semibold", 9),
            bd=0,
            padx=8,
            pady=3,
            state="disabled",
        )
        self.buttons["copilot_action"].pack(side="right", padx=(8, 0))

        self.buttons["copilot_logs"] = tk.Button(
            top_bar,
            text="Logs",
            command=self.open_copilot_logs,
            relief="flat",
            bg="#eef2ff",
            activebackground="#dfe8ff",
            fg=TEXT_DARK,
            font=("Segoe UI Semibold", 9),
            bd=0,
            padx=8,
            pady=3,
            state="normal",
        )
        self.buttons["copilot_logs"].pack(side="right", padx=(8, 0))

        self.buttons["copilot_toggle"] = tk.Button(
            top_bar,
            text="Copilot OFF",
            command=self.toggle_copilot,
            relief="flat",
            bg="#eef2ff",
            activebackground="#dfe8ff",
            fg=TEXT_DARK,
            font=("Segoe UI Semibold", 10),
            bd=0,
            padx=8,
            pady=3,
        )
        self.buttons["copilot_toggle"].pack(side="right", padx=(8, 0))
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
            self.configure_text_shortcuts(textbox, self.schedule_metadata_save)
            textbox.bind("<KeyRelease>", self.schedule_metadata_save)
            textbox.bind("<FocusOut>", self.save_metadata)
            self.metadata_textboxes[key] = textbox

        self.note_textbox_frame = tk.Frame(self.window, bg=CARD_BG)
        self.note_scrollbar = tk.Scrollbar(self.note_textbox_frame, orient="vertical")
        self.note_textbox = tk.Text(
            self.note_textbox_frame,
            height=8,
            wrap="word",
            font=("Segoe UI", 10),
            bd=1,
            relief="solid",
            padx=10,
            pady=7,
            fg=TEXT_DARK,
            highlightthickness=1,
            highlightbackground="#d9deea",
            yscrollcommand=self.note_scrollbar.set,
        )
        self.note_scrollbar.configure(command=self.note_textbox.yview)
        self.note_scrollbar.pack(side="right", fill="y")
        self.note_textbox.pack(side="left", fill="both", expand=True)
        self.note_textbox_frame.pack(fill="x", padx=14, pady=(0, 10))
        self.note_resize_grip = tk.Label(
            self.note_textbox_frame,
            text="\u25e2",
            bg="white",
            fg="#7b8497",
            cursor="sb_v_double_arrow",
            font=("Segoe UI Symbol", 9),
            padx=1,
            pady=0,
        )
        self.note_resize_grip.place(relx=1.0, rely=1.0, anchor="se")
        self.note_resize_grip.bind("<ButtonPress-1>", self.start_note_textbox_resize)
        self.note_resize_grip.bind("<B1-Motion>", self.drag_note_textbox_resize)
        self.configure_text_shortcuts(self.note_textbox, self.schedule_note_save)
        self.note_textbox.bind("<KeyRelease>", self.schedule_note_save)
        self.note_textbox.bind("<FocusOut>", self.save_current_note)
        self.note_textbox.tag_configure("table_anchor", elide=True)

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
        self.save_current_tables()
        if self.window is not None and self.window.winfo_exists():
            self.window.destroy()
        self._reset_state(preserve_table_editor=self.table_window is not None and self.table_window.winfo_exists())

    def _reset_state(self, preserve_table_editor=False):
        if self.canvas_update_after_id is not None and self.window is not None and self.window.winfo_exists():
            self.window.after_cancel(self.canvas_update_after_id)
        if self.note_save_after_id is not None and self.window is not None and self.window.winfo_exists():
            self.window.after_cancel(self.note_save_after_id)
        if self.table_save_after_id is not None and self.window is not None and self.window.winfo_exists():
            self.window.after_cancel(self.table_save_after_id)
        if self.metadata_save_after_id is not None and self.window is not None and self.window.winfo_exists():
            self.window.after_cancel(self.metadata_save_after_id)
        self.window = None
        self.canvas = None
        self.action_bar = None
        self.metadata_frame = None
        self.metadata_textboxes.clear()
        self.note_textbox_frame = None
        self.note_textbox = None
        self.note_scrollbar = None
        self.note_resize_grip = None
        self.note_resize_drag = None
        self.table_preview_frame = None
        self.table_preview_textbox = None
        self.table_preview_grip = None
        self.note_save_after_id = None
        self.table_save_after_id = None
        self.metadata_save_after_id = None
        self.index_var = None
        delete_table_button = self.buttons.get("delete_table") if preserve_table_editor else None
        self.buttons.clear()
        if delete_table_button is not None and delete_table_button.winfo_exists():
            self.buttons["delete_table"] = delete_table_button
        if not preserve_table_editor:
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
        if not preserve_table_editor:
            self.current_note_cache = ""
            self.current_tables_cache = []
            self.inline_table_widgets = []
            self.table_window = None
            self.table_canvas = None
            self.table_inner = None
            self.table_rows_var = None
            self.table_columns_var = None
            self.table_widgets = []
            self.selected_table_index = None
            self.table_resize_drag = None
        else:
            self.inline_table_widgets = []
            self._update_delete_table_button()
        self.current_metadata_cache = None
        self.canvas_update_after_id = None
        self.is_interacting = False
        self.copilot_enabled = False
        self.copilot_provider = CopilotAIProvider.from_env()
        self.copilot_suggestion_pending = False

    def show_at(self, index):
        if self.current_index == -1:
            self.save_metadata()
        else:
            self.save_current_note()
            self.save_current_tables()
        self.current_index = max(-1, min(index, len(self.paths) - 1)) if self.paths else -1
        self.update_canvas()

    def zoom_view(self, delta):
        self.zoom = max(1.0, min(3.0, self.zoom + delta))
        if self.zoom == 1.0:
            self.pan_x = 0
            self.pan_y = 0
        self.update_canvas()

    def start_note_textbox_resize(self, event):
        if self.note_textbox is None or not self.note_textbox.winfo_exists():
            return
        self.note_resize_drag = (event.y_root, int(self.note_textbox.cget("height")))
        return "break"

    def drag_note_textbox_resize(self, event):
        if self.note_resize_drag is None or self.note_textbox is None or not self.note_textbox.winfo_exists():
            return "break"
        start_y, start_height = self.note_resize_drag
        row_delta = int((event.y_root - start_y) / 18)
        self.note_textbox.configure(height=max(3, min(24, start_height + row_delta)))
        return "break"

    def configure_text_shortcuts(self, widget, change_callback=None):
        style_options = {
            "bold": "bold",
            "italic": "italic",
            "underline": "underline",
        }
        for tag_name, font_option in style_options.items():
            widget.tag_configure(tag_name, font=("Segoe UI", 10, font_option))

        def toggle(style_name):
            if not widget.tag_ranges("sel"):
                self.app.set_status("Select text first.")
                return "break"
            start = widget.index("sel.first")
            end = widget.index("sel.last")
            has_style = self._text_range_has_tag(widget, style_name, start, end)
            if has_style:
                widget.tag_remove(style_name, start, end)
            else:
                widget.tag_add(style_name, start, end)
            if change_callback is not None:
                change_callback()
            return "break"

        widget.bind("<Control-b>", lambda _event: toggle("bold"))
        widget.bind("<Control-B>", lambda _event: toggle("bold"))
        widget.bind("<Control-i>", lambda _event: toggle("italic"))
        widget.bind("<Control-I>", lambda _event: toggle("italic"))
        widget.bind("<Control-u>", lambda _event: toggle("underline"))
        widget.bind("<Control-U>", lambda _event: toggle("underline"))

    def _text_range_has_tag(self, widget, tag_name, start, end):
        ranges = widget.tag_ranges(tag_name)
        for index in range(0, len(ranges), 2):
            tag_start = ranges[index]
            tag_end = ranges[index + 1]
            if widget.compare(tag_end, ">", start) and widget.compare(tag_start, "<", end):
                return True
        return False

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

    def toggle_copilot(self):
        self.copilot_enabled = not self.copilot_enabled
        self._update_copilot_ui()
        if self.copilot_enabled:
            status = "Copilot enabled."
            if self.copilot_provider.github_token is None:
                status += " Sign in with the Copilot CLI or set COPILOT_GITHUB_TOKEN, GH_TOKEN, or GITHUB_TOKEN to authenticate."
        else:
            status = "Copilot disabled."
        self.app.set_status(status)

    def add_copilot_log(self, message: str) -> None:
        self.copilot_log_messages.append(message)
        self.app.schedule(self._refresh_copilot_logs_ui)

    def _refresh_copilot_logs_ui(self):
        if self.copilot_log_window is None or not self.copilot_log_window.winfo_exists():
            return
        text_widget = self.copilot_log_window.children.get("log_text")
        if text_widget is None:
            return
        text_widget.configure(state="normal")
        text_widget.delete("1.0", tk.END)
        text_widget.insert("1.0", "\n".join(self.copilot_log_messages[-200:]))
        text_widget.configure(state="disabled")

    def open_copilot_logs(self):
        if self.copilot_log_window is not None and self.copilot_log_window.winfo_exists():
            self.copilot_log_window.lift()
            return

        self.copilot_log_window = tk.Toplevel(self.window or self.app.root)
        self.copilot_log_window.title("Copilot Logs")
        self.copilot_log_window.geometry("560x360+820+140")
        self.copilot_log_window.configure(bg=CARD_BG)
        self.copilot_log_window.attributes("-topmost", True)

        text_widget = tk.Text(
            self.copilot_log_window,
            name="log_text",
            wrap="word",
            font=("Segoe UI", 9),
            bd=1,
            relief="solid",
            padx=10,
            pady=10,
            fg=TEXT_DARK,
            highlightthickness=1,
            highlightbackground="#d9deea",
            state="normal",
        )
        text_widget.pack(fill="both", expand=True, padx=12, pady=12)
        text_widget.insert("1.0", "\n".join(self.copilot_log_messages[-200:]))
        text_widget.configure(state="disabled")

        self.copilot_log_window.protocol("WM_DELETE_WINDOW", self.copilot_log_window.destroy)

    def _update_copilot_ui(self):
        toggle_button = self.buttons.get("copilot_toggle")
        if toggle_button is not None and toggle_button.winfo_exists():
            toggle_button.configure(
                text="Copilot ON" if self.copilot_enabled else "Copilot OFF",
                bg=PRIMARY_BLUE if self.copilot_enabled else "#eef2ff",
                fg="white" if self.copilot_enabled else TEXT_DARK,
            )

        action_button = self.buttons.get("copilot_action")
        if action_button is None or not action_button.winfo_exists():
            return

        if not self.copilot_enabled or self.current_image_path is None:
            action_button.configure(state="disabled", text="Generate", bg="#eef2ff", fg="#6b7280")
            return

        current_note = ""
        if self.note_textbox is not None and self.note_textbox.winfo_exists():
            current_note = self.note_textbox.get("1.0", tk.END)
        elif self.current_note_cache:
            current_note = self.current_note_cache

        mode = self._get_copilot_action_mode(current_note)
        action_button.configure(
            state="normal",
            text="Rewrite" if mode == "rewrite" else "Generate",
            bg=PRIMARY_BLUE,
            fg="white",
        )

    def _get_copilot_action_mode(self, note_text: str | None = None) -> str:
        return "rewrite" if (note_text or "").strip() else "generate"

    def _get_copilot_metadata_context(self):
        metadata = {}
        for key in ("scenario", "expected_result", "test_data"):
            textbox = self.metadata_textboxes.get(key)
            if textbox is None or not textbox.winfo_exists():
                metadata[key] = ""
            else:
                metadata[key] = textbox.get("1.0", tk.END).strip()
        return metadata

    def _get_previous_comments_for_context(self):
        notes = load_preview_notes()
        current_key = os.path.basename(self.current_image_path) if self.current_image_path else None
        previous_comments = []
        for key, value in notes.items():
            if key in {"__test_metadata__", current_key} or not isinstance(value, str):
                continue
            cleaned = value.strip()
            if cleaned:
                previous_comments.append(cleaned)
        return previous_comments

    def apply_copilot_comment(self):
        if not self.copilot_enabled:
            return

        if self.note_textbox is None or not self.note_textbox.winfo_exists() or self.current_image_path is None:
            self.app.set_status("Open a screenshot first to use Copilot.")
            return

        existing_comment = self.note_textbox.get("1.0", tk.END).strip()
        metadata = self._get_copilot_metadata_context()
        previous_comments = self._get_previous_comments_for_context()
        mode = self._get_copilot_action_mode(existing_comment)

        self.add_copilot_log(f"Copilot request: mode={mode}, image={os.path.basename(self.current_image_path) if self.current_image_path else 'none'}")
        self.buttons["copilot_action"].configure(state="disabled", text="Working...", bg="#94b8ff", fg="white")
        self.app.set_status("Copilot generating comment...")

        thread = threading.Thread(
            target=self._run_copilot_generation,
            args=(
                mode,
                metadata.get("scenario", ""),
                metadata.get("expected_result", ""),
                metadata.get("test_data", ""),
                existing_comment or None,
                previous_comments,
                self.current_image_path,
            ),
            daemon=True,
        )
        thread.start()

    def _run_copilot_generation(
        self,
        mode,
        test_scenario,
        expected_result,
        test_data,
        existing_comment,
        previous_comments,
        screenshot_path,
    ):
        try:
            generated_comment = self.copilot_provider.generate_test_evidence_comment_sync(
                mode=mode,
                test_scenario=test_scenario,
                expected_result=expected_result,
                test_data=test_data,
                existing_comment=existing_comment,
                previous_comments=previous_comments,
                screenshot_path=screenshot_path,
            )
        except CopilotConfigurationError as exc:
            self.add_copilot_log(f"Copilot auth failed: {exc}")
            self.app.schedule(self._on_copilot_failure, str(exc), "Copilot unavailable.")
            return
        except Exception as exc:
            self.add_copilot_log(f"Copilot call failed: {exc}")
            self.app.schedule(self._on_copilot_failure, f"Could not generate a comment.\n\n{exc}", "Copilot comment generation failed.")
            return

        self.add_copilot_log("Copilot response received.")
        self.app.schedule(self._on_copilot_success, generated_comment)

    def _on_copilot_failure(self, dialog_message: str, status_message: str):
        if self.window is None or not self.window.winfo_exists():
            return
        self.buttons["copilot_action"].configure(state="normal")
        messagebox.showerror("Copilot error", dialog_message)
        self.app.set_status(status_message)
        self._update_copilot_ui()

    def _on_copilot_success(self, generated_comment: str):
        if self.window is None or not self.window.winfo_exists():
            return
        self.note_textbox.delete("1.0", tk.END)
        self.note_textbox.insert("1.0", generated_comment)
        self.copilot_suggestion_pending = True
        self._update_copilot_ui()
        self.note_textbox.focus_set()
        self.app.set_status("Copilot suggestion inserted. Review and save it when ready.")

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
        if self.note_textbox_frame is not None and self.note_textbox_frame.winfo_manager():
            self.note_textbox_frame.pack_forget()
        if self.table_preview_frame is not None and self.table_preview_frame.winfo_manager():
            self.table_preview_frame.pack_forget()
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
        if self.note_textbox_frame is not None and not self.note_textbox_frame.winfo_manager():
            self.note_textbox_frame.pack(fill="x", padx=14, pady=(0, 10))
        self.update_table_preview()
        if self.canvas is not None and not self.canvas.winfo_manager():
            self.canvas.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        if self.action_bar is not None and not self.action_bar.winfo_manager():
            self.action_bar.pack(fill="x", padx=14, pady=(0, 12))

    def _set_metadata_controls(self):
        for key in ("zoom_in", "zoom_out", "table", "pan", "highlight", "eraser", "brush_S", "brush_M", "brush_L", "brush_XL", "delete"):
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
            self.current_tables_cache = get_preview_tables(self.current_image_path)
        else:
            self.current_note_cache = ""
            self.current_tables_cache = []
        self.loading_note = False
        self.copilot_suggestion_pending = False
        self.update_table_preview()
        if self.table_window is not None and self.table_window.winfo_exists():
            self.build_table_editor_grid()
        self._update_copilot_ui()

    def update_table_preview(self):
        self.render_inline_tables()

    def _table_token(self, table_index):
        return f"[[AUTODOC_TABLE:{table_index}]]"

    def _table_token_pattern(self):
        return re.compile(r"\[\[AUTODOC_TABLE:(\d+)\]\]")

    def _ensure_table_tokens(self, note_text):
        token_pattern = self._table_token_pattern()
        existing = {int(match.group(1)) for match in token_pattern.finditer(note_text)}
        cleaned = token_pattern.sub(lambda match: match.group(0) if int(match.group(1)) < len(self.current_tables_cache) else "", note_text)
        missing = [index for index in range(len(self.current_tables_cache)) if index not in existing]
        if not missing:
            return cleaned
        spacer = "" if not cleaned.strip() else "\n\n"
        return cleaned.rstrip() + spacer + "\n\n".join(self._table_token(index) for index in missing)

    def _visible_note_text(self, note_text):
        return self._table_token_pattern().sub("", note_text).strip()

    def _remove_table_token(self, deleted_index):
        if self.note_textbox is None or not self.note_textbox.winfo_exists():
            return
        raw_note = self.note_textbox.get("1.0", "end-1c")

        def replace(match):
            table_index = int(match.group(1))
            if table_index == deleted_index:
                return ""
            if table_index > deleted_index:
                return self._table_token(table_index - 1)
            return match.group(0)

        note_text = self._table_token_pattern().sub(replace, raw_note)
        self.loading_note = True
        self.note_textbox.delete("1.0", tk.END)
        self.note_textbox.insert("1.0", note_text)
        self.loading_note = False

    def render_inline_tables(self):
        if self.note_textbox is None or not self.note_textbox.winfo_exists() or self.loading_note:
            return

        cursor = self.note_textbox.index(tk.INSERT)
        raw_note = self.note_textbox.get("1.0", "end-1c")
        note_with_tokens = self._ensure_table_tokens(raw_note)
        self.current_note_cache = note_with_tokens
        self.inline_table_widgets = []

        self.loading_note = True
        self.note_textbox.configure(state="normal")
        self.note_textbox.delete("1.0", tk.END)
        position = 0
        for match in self._table_token_pattern().finditer(note_with_tokens):
            self.note_textbox.insert(tk.END, note_with_tokens[position:match.start()])
            table_index = int(match.group(1))
            token = match.group(0)
            self.note_textbox.insert(tk.END, token, ("table_anchor",))
            if table_index < len(self.current_tables_cache):
                frame = self.create_inline_table_frame(table_index)
                self.note_textbox.window_create(tk.END, window=frame, padx=2, pady=5)
                self.inline_table_widgets.append(frame)
            position = match.end()
        self.note_textbox.insert(tk.END, note_with_tokens[position:])
        try:
            self.note_textbox.mark_set(tk.INSERT, cursor)
        except tk.TclError:
            self.note_textbox.mark_set(tk.INSERT, tk.END)
        self.loading_note = False

    def create_inline_table_frame(self, table_index):
        table = self.current_tables_cache[table_index]
        frame = tk.Frame(self.note_textbox, bg="black", bd=0, padx=1, pady=1)
        frame.bind("<Button-1>", lambda _event, idx=table_index: self.open_table_editor_for(idx))
        rows = table.get("rows", 1)
        columns = table.get("columns", 1)
        data = table.get("data", [])
        widths = table.get("column_widths", [140 for _column in range(columns)])
        heights = table.get("row_heights", [36 for _row in range(rows)])
        for row_index in range(rows):
            for column_index in range(columns):
                value = ""
                if row_index < len(data) and isinstance(data[row_index], list) and column_index < len(data[row_index]):
                    value = str(data[row_index][column_index])
                label = tk.Label(
                    frame,
                    text=value,
                    bg="white",
                    fg=TEXT_DARK,
                    justify="left",
                    anchor="nw",
                    font=("Segoe UI", 10),
                    padx=6,
                    pady=4,
                    wraplength=max(60, int(widths[column_index]) - 12),
                    width=max(6, int(widths[column_index] / 9)),
                    height=max(1, int(heights[row_index] / 20)),
                )
                label.grid(row=row_index, column=column_index, sticky="nsew", padx=(0, 1), pady=(0, 1))
                label.bind("<Button-1>", lambda _event, idx=table_index: self.open_table_editor_for(idx))
        return frame

    def open_table_editor_for(self, table_index):
        self.selected_table_index = table_index
        self.open_table_editor()

    def open_table_editor(self):
        if self.current_image_path is None:
            self.app.set_status("Open a screenshot first to add a table.")
            return

        if self.table_window is not None and self.table_window.winfo_exists():
            self.table_window.lift()
            self.table_window.focus_force()
            return

        self.table_window = tk.Toplevel(self.app.root)
        self.table_window.title("Edit Tables")
        self.table_window.geometry("820x520+820+150")
        self.table_window.minsize(560, 360)
        self.table_window.configure(bg=CARD_BG)
        self.table_window.attributes("-topmost", True)

        toolbar = tk.Frame(self.table_window, bg=CARD_BG)
        toolbar.pack(fill="x", padx=12, pady=(12, 8))

        tk.Label(toolbar, text="Rows", bg=CARD_BG, fg=TEXT_DARK, font=("Segoe UI Semibold", 9)).pack(side="left")
        self.table_rows_var = tk.IntVar(value=3)
        tk.Spinbox(toolbar, from_=1, to=20, textvariable=self.table_rows_var, width=4).pack(side="left", padx=(4, 12))
        tk.Label(toolbar, text="Columns", bg=CARD_BG, fg=TEXT_DARK, font=("Segoe UI Semibold", 9)).pack(side="left")
        self.table_columns_var = tk.IntVar(value=3)
        tk.Spinbox(toolbar, from_=1, to=12, textvariable=self.table_columns_var, width=4).pack(side="left", padx=(4, 12))

        tk.Button(toolbar, text="Add Table", command=self.add_table, relief="flat", bg=PRIMARY_BLUE, fg="white", padx=10, pady=4).pack(side="left")
        tk.Button(toolbar, text="Clear", command=self.clear_tables, relief="flat", bg="#eef2ff", fg=TEXT_DARK, padx=10, pady=4).pack(side="left", padx=(8, 0))
        self.buttons["delete_table"] = tk.Button(
            toolbar,
            text="Delete Table",
            command=self.delete_selected_table,
            relief="flat",
            bg="#ffecef",
            fg="#8b1e2d",
            padx=10,
            pady=4,
            state="disabled",
        )
        self.buttons["delete_table"].pack(side="left", padx=(8, 0))

        shell = tk.Frame(self.table_window, bg=CARD_BG)
        shell.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.table_canvas = tk.Canvas(shell, bg="#fbfcff", highlightthickness=1, highlightbackground="#d9deea")
        y_scroll = tk.Scrollbar(shell, orient="vertical", command=self.table_canvas.yview)
        x_scroll = tk.Scrollbar(shell, orient="horizontal", command=self.table_canvas.xview)
        self.table_canvas.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.table_canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        shell.grid_rowconfigure(0, weight=1)
        shell.grid_columnconfigure(0, weight=1)

        self.table_inner = tk.Frame(self.table_canvas, bg="#fbfcff")
        self.table_canvas.create_window((0, 0), window=self.table_inner, anchor="nw")
        self.table_inner.bind("<Configure>", lambda _event: self.table_canvas.configure(scrollregion=self.table_canvas.bbox("all")))
        self.table_window.protocol("WM_DELETE_WINDOW", self.close_table_editor)
        self.build_table_editor_grid()

    def close_table_editor(self):
        self.save_current_tables()
        if self.table_window is not None and self.table_window.winfo_exists():
            self.table_window.destroy()
        self.table_window = None
        self.table_canvas = None
        self.table_inner = None
        self.table_widgets = []
        self.selected_table_index = None

    def add_table(self):
        rows = self._safe_int_var(self.table_rows_var, 3)
        columns = self._safe_int_var(self.table_columns_var, 3)
        table_index = len(self.current_tables_cache)
        self.current_tables_cache.append(
            {
                "rows": rows,
                "columns": columns,
                "data": [["" for _column in range(columns)] for _row in range(rows)],
                "column_widths": [140 for _column in range(columns)],
                "row_heights": [36 for _row in range(rows)],
            }
        )
        self.selected_table_index = table_index
        if self.note_textbox is not None and self.note_textbox.winfo_exists():
            self.note_textbox.insert(tk.INSERT, "\n")
            self.note_textbox.insert(tk.INSERT, self._table_token(table_index), ("table_anchor",))
            self.note_textbox.insert(tk.INSERT, "\n")
        self.build_table_editor_grid()
        self.schedule_table_save()

    def _safe_int_var(self, variable, default):
        try:
            return max(1, int(variable.get()))
        except (tk.TclError, TypeError, ValueError):
            return default

    def build_table_editor_grid(self):
        if self.table_inner is None or not self.table_inner.winfo_exists():
            return

        for child in self.table_inner.winfo_children():
            child.destroy()
        self.table_widgets = []

        if not self.current_tables_cache:
            tk.Label(
                self.table_inner,
                text="Choose rows and columns, then click Add Table.",
                bg="#fbfcff",
                fg="#6d7891",
                font=("Segoe UI", 10),
            ).pack(padx=18, pady=18, anchor="w")
            self._update_delete_table_button()
            return

        for table_index, table in enumerate(self.current_tables_cache):
            frame = tk.LabelFrame(
                self.table_inner,
                text=f"Table {table_index + 1}",
                bg="#fbfcff",
                fg=TEXT_DARK,
                font=("Segoe UI Semibold", 10),
                bd=1,
                relief="solid",
                padx=8,
                pady=8,
            )
            frame.pack(fill="x", expand=True, padx=10, pady=(10, 6), anchor="nw")
            frame.bind("<Button-1>", lambda _event, idx=table_index: self.select_table(idx))
            if table_index == self.selected_table_index:
                frame.configure(bg="#eef2ff")

            table_widgets = []
            rows = table.get("rows", 1)
            columns = table.get("columns", 1)
            data = table.get("data", [])
            widths = table.get("column_widths", [140 for _column in range(columns)])
            heights = table.get("row_heights", [36 for _row in range(rows)])

            for row_index in range(rows):
                row_widgets = []
                for column_index in range(columns):
                    cell_frame = tk.Frame(frame, bg="black", bd=0)
                    cell_frame.grid(row=row_index * 2, column=column_index * 2, sticky="nsew")
                    text = tk.Text(
                        cell_frame,
                        width=1,
                        height=1,
                        wrap="word",
                        font=("Segoe UI", 10),
                        bd=0,
                        padx=6,
                        pady=4,
                        fg=TEXT_DARK,
                        bg="white",
                    )
                    text.pack(fill="both", expand=True, padx=1, pady=1)
                    text.insert(
                        "1.0",
                        str(data[row_index][column_index])
                        if row_index < len(data) and column_index < len(data[row_index])
                        else "",
                    )
                    text.configure(width=max(6, int(widths[column_index] / 9)), height=max(1, int(heights[row_index] / 20)))
                    self.configure_text_shortcuts(
                        text,
                        lambda t=table_index, r=row_index, c=column_index, widget=text: self.update_table_cell_value(widget, t, r, c),
                    )
                    text.bind("<FocusIn>", lambda _event, idx=table_index: self.select_table(idx))
                    text.bind("<KeyRelease>", lambda event, t=table_index, r=row_index, c=column_index: self.on_table_cell_change(event, t, r, c))
                    row_widgets.append(text)

                    if column_index < columns - 1:
                        handle = tk.Frame(frame, bg="black", width=2, cursor="sb_h_double_arrow")
                        handle.grid(row=row_index * 2, column=column_index * 2 + 1, sticky="ns")
                        handle.bind("<ButtonPress-1>", lambda event, t=table_index, c=column_index: self.start_column_resize(event, t, c))
                        handle.bind("<B1-Motion>", self.drag_column_resize)
                if columns:
                    outer_handle = tk.Frame(frame, bg="black", width=3, cursor="sb_h_double_arrow")
                    outer_handle.grid(row=row_index * 2, column=columns * 2 - 1, sticky="ns")
                    outer_handle.bind("<ButtonPress-1>", lambda event, t=table_index, c=columns - 1: self.start_column_resize(event, t, c))
                    outer_handle.bind("<B1-Motion>", self.drag_column_resize)
                table_widgets.append(row_widgets)

                if row_index < rows - 1:
                    handle = tk.Frame(frame, bg="black", height=2, cursor="sb_v_double_arrow")
                    handle.grid(row=row_index * 2 + 1, column=0, columnspan=max(1, columns * 2), sticky="ew")
                    handle.bind("<ButtonPress-1>", lambda event, t=table_index, r=row_index: self.start_row_resize(event, t, r))
                    handle.bind("<B1-Motion>", self.drag_row_resize)
            if rows:
                outer_handle = tk.Frame(frame, bg="black", height=3, cursor="sb_v_double_arrow")
                outer_handle.grid(row=rows * 2 - 1, column=0, columnspan=max(1, columns * 2), sticky="ew")
                outer_handle.bind("<ButtonPress-1>", lambda event, t=table_index, r=rows - 1: self.start_row_resize(event, t, r))
                outer_handle.bind("<B1-Motion>", self.drag_row_resize)

            self.table_widgets.append(table_widgets)

        self._update_delete_table_button()
        self.update_table_preview()

    def select_table(self, table_index):
        self.selected_table_index = table_index
        self._update_delete_table_button()

    def _update_delete_table_button(self):
        button = self.buttons.get("delete_table")
        if button is not None and button.winfo_exists():
            button.configure(state="normal" if self.selected_table_index is not None else "disabled")

    def clear_tables(self):
        for table in self.current_tables_cache:
            for row in table.get("data", []):
                for column_index in range(len(row)):
                    row[column_index] = ""
        self.build_table_editor_grid()
        self.schedule_table_save()

    def delete_selected_table(self):
        if self.selected_table_index is None:
            return
        if 0 <= self.selected_table_index < len(self.current_tables_cache):
            deleted_index = self.selected_table_index
            self.current_tables_cache.pop(self.selected_table_index)
            self._remove_table_token(deleted_index)
        self.selected_table_index = None
        self.build_table_editor_grid()
        self.schedule_table_save()

    def on_table_cell_change(self, event, table_index, row_index, column_index):
        self.update_table_cell_value(event.widget, table_index, row_index, column_index)

    def update_table_cell_value(self, widget, table_index, row_index, column_index):
        if table_index >= len(self.current_tables_cache):
            return
        table = self.current_tables_cache[table_index]
        value = widget.get("1.0", "end-1c")
        table["data"][row_index][column_index] = value
        self.expand_cell_to_content(widget, table_index, row_index, column_index)
        self.update_table_preview()
        self.schedule_table_save()

    def expand_cell_to_content(self, widget, table_index, row_index, column_index):
        table = self.current_tables_cache[table_index]
        value = widget.get("1.0", "end-1c")
        longest_line = max((len(line) for line in value.splitlines()), default=0)
        needed_width = max(table["column_widths"][column_index], min(420, max(70, longest_line * 8 + 30)))
        line_count = max(1, value.count("\n") + 1)
        needed_height = max(table["row_heights"][row_index], min(240, max(30, line_count * 22 + 12)))
        table["column_widths"][column_index] = needed_width
        table["row_heights"][row_index] = needed_height
        self.apply_table_dimensions(table_index)

    def apply_table_dimensions(self, table_index):
        if table_index >= len(self.table_widgets):
            return
        table = self.current_tables_cache[table_index]
        for row_index, row_widgets in enumerate(self.table_widgets[table_index]):
            for column_index, widget in enumerate(row_widgets):
                widget.configure(
                    width=max(6, int(table["column_widths"][column_index] / 9)),
                    height=max(1, int(table["row_heights"][row_index] / 20)),
                )

    def start_column_resize(self, event, table_index, column_index):
        width = self.current_tables_cache[table_index]["column_widths"][column_index]
        self.table_resize_drag = ("column", table_index, column_index, event.x_root, width)
        self.select_table(table_index)

    def drag_column_resize(self, event):
        if not self.table_resize_drag or self.table_resize_drag[0] != "column":
            return
        _kind, table_index, column_index, start_x, start_width = self.table_resize_drag
        width = max(70, min(420, start_width + event.x_root - start_x))
        self.current_tables_cache[table_index]["column_widths"][column_index] = width
        self.apply_table_dimensions(table_index)
        self.update_table_preview()
        self.schedule_table_save()

    def start_row_resize(self, event, table_index, row_index):
        height = self.current_tables_cache[table_index]["row_heights"][row_index]
        self.table_resize_drag = ("row", table_index, row_index, event.y_root, height)
        self.select_table(table_index)

    def drag_row_resize(self, event):
        if not self.table_resize_drag or self.table_resize_drag[0] != "row":
            return
        _kind, table_index, row_index, start_y, start_height = self.table_resize_drag
        height = max(30, min(240, start_height + event.y_root - start_y))
        self.current_tables_cache[table_index]["row_heights"][row_index] = height
        self.apply_table_dimensions(table_index)
        self.update_table_preview()
        self.schedule_table_save()

    def schedule_table_save(self):
        scheduler = self._table_save_scheduler()
        if scheduler is None:
            return
        if self.table_save_after_id is not None:
            try:
                scheduler.after_cancel(self.table_save_after_id)
            except tk.TclError:
                pass
        self.table_save_after_id = scheduler.after(500, self.save_current_tables)

    def save_current_tables(self):
        scheduler = self._table_save_scheduler()
        if self.table_save_after_id is not None and scheduler is not None:
            try:
                scheduler.after_cancel(self.table_save_after_id)
            except tk.TclError:
                pass
            self.table_save_after_id = None
        if self.current_image_path is None:
            return
        if self.note_textbox is not None and self.note_textbox.winfo_exists():
            note_text = self._ensure_table_tokens(self.note_textbox.get("1.0", "end-1c"))
            set_preview_note(self.current_image_path, note_text)
            self.document_manager.set_image_note(self.current_image_path, self._visible_note_text(note_text))
            self.current_note_cache = note_text
        set_preview_tables(self.current_image_path, self.current_tables_cache)
        self.document_manager.set_image_tables(self.current_image_path, self.current_tables_cache)
        self.update_table_preview()

    def _table_save_scheduler(self):
        if self.window is not None and self.window.winfo_exists():
            return self.window
        if self.table_window is not None and self.table_window.winfo_exists():
            return self.table_window
        return None

    def schedule_note_save(self, _event=None):
        if self.loading_note or self.window is None or not self.window.winfo_exists():
            return
        if self.copilot_suggestion_pending:
            self.copilot_suggestion_pending = False
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
        if self.copilot_suggestion_pending:
            return

        note_text = self.note_textbox.get("1.0", tk.END).strip()
        if note_text == self.current_note_cache:
            return
        set_preview_note(self.current_image_path, note_text)
        self.document_manager.set_image_note(self.current_image_path, self._visible_note_text(note_text))
        self.current_note_cache = note_text
        self._update_copilot_ui()

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
            "table",
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
            remove_preview_tables(self.current_image_path)
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


