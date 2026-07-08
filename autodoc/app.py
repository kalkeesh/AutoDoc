import math
import os
import queue
import ctypes
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox

from PIL import ImageTk

from .capture import capture_image
from .config import (
    APP_BG,
    BASE_HEIGHT,
    BASE_WIDTH,
    BUTTON_SHADOW,
    CAPTURE_HIDE_DELAY_MS,
    CARD_BG,
    DRAW_SHORTCUT_LABEL,
    MAX_SCALE,
    MIN_SCALE,
    PRIMARY_BLUE,
    PRIMARY_RED,
    SHOT_SHORTCUT_LABEL,
    TESTCASE_STATUS_OPTIONS,
    TEXT_DARK,
    TRANSPARENT_KEY,
    WORKAREA_SHORTCUT_LABEL,
)
from .document import DocumentManager
from .drawing import DrawingManager
from .hotkeys import ButtonClickTracker, HotkeyManager
from .notes import NoteManager
from .preview import PreviewManager
from .storage import clear_screenshot_dir, ensure_screenshot_backup, ensure_screenshot_dir, get_screenshot_backup_path, set_preview_note

class App:
    def __init__(self):
        self._enable_dpi_awareness()
        self.root = tk.Tk()
        self.root.title("Tester Tool")
        self.ui_scale = 0.80
        self.status_var = tk.StringVar(value="")
        self.canvas = None
        self.status_card = None
        self.status_label = None
        self.size_window = None
        self.size_slider = None
        self.testcase_status_window = None
        self.tooltip_window = None
        self.toast_window = None
        self.toast_after_id = None
        self.capture_in_progress = False
        self.close_in_progress = False

        self.document_manager = DocumentManager(self)
        self.note_manager = NoteManager(self, self.document_manager)
        self.preview_manager = PreviewManager(self, self.document_manager)
        self.drawing_manager = DrawingManager(self)
        self.hotkey_manager = HotkeyManager(self)
        self._main_thread_actions = queue.Queue()

        self._build_root_window()
        self.render_main_ui()
        self.root.after_idle(self._finish_startup_render)
        self._process_main_thread_actions()
        self.hotkey_manager.start()

    def _enable_dpi_awareness(self):
        if os.name != "nt":
            return
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass

    def _build_root_window(self):
        self.root.geometry(f"{self.scaled(BASE_WIDTH)}x{self.scaled(BASE_HEIGHT)}+500+120")
        self.root.configure(bg=TRANSPARENT_KEY)
        self._apply_window_chrome()

        self.canvas = tk.Canvas(self.root, width=420, height=680, bg=TRANSPARENT_KEY, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.root.bind_all("<Control-e>", self.toggle_draw_mode)
        self.root.bind_all("<Control-E>", self.toggle_draw_mode)

    def _apply_window_chrome(self):
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        try:
            self.root.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            pass

    def _finish_startup_render(self):
        self.root.update_idletasks()
        self._apply_window_chrome()
        self.render_main_ui()
        self.root.lift()

    def scaled(self, value):
        return max(1, int(value * self.ui_scale))

    def take_region_screenshot(self):
        self.take_screenshot(use_region_selector=True)

    def toggle_draw_mode(self, _event=None):
        self.drawing_manager.toggle()
        return "break"

    def schedule(self, callback, *args, **kwargs):
        self._main_thread_actions.put((callback, args, kwargs))

    def _process_main_thread_actions(self):
        while True:
            try:
                callback, args, kwargs = self._main_thread_actions.get_nowait()
            except queue.Empty:
                break
            try:
                callback(*args, **kwargs)
            except Exception:
                pass
        self.root.after(50, self._process_main_thread_actions)

    def render_main_ui(self):
        current_x = self.root.winfo_x() if self.root.winfo_ismapped() else 500
        current_y = self.root.winfo_y() if self.root.winfo_ismapped() else 120
        self.root.geometry(f"{self.scaled(BASE_WIDTH)}x{self.scaled(BASE_HEIGHT)}+{current_x}+{current_y}")

        self.canvas.config(width=self.scaled(BASE_WIDTH), height=self.scaled(BASE_HEIGHT))
        self.canvas.delete("all")
        self._draw_background()
        if self.status_card is not None and self.status_card.winfo_exists():
            self.status_card.destroy()

        center_x = 182
        center_y = 318
        shot_size = 132
        satellite_size = 72
        shot_left = center_x - (shot_size / 2)
        shot_top = center_y - (shot_size / 2)
        self._draw_circle_button(
            shot_left,
            shot_top,
            shot_size,
            PRIMARY_RED,
            "Shot",
            self.take_screenshot,
            "",
            label_size=17,
            double_command=self.take_region_screenshot,
        )

        radius = 144
        button_specs = [
            ("Note", self.note_manager.open_window, "Open the note window.", 0, 10, False),
            ("Preview", self.preview_manager.open_window, "Browse earlier screenshots and add yellow highlights.", 51, 8, False),
            ("Draw", self.drawing_manager.toggle, "", 103, 9, False),
            ("Close", self.close_app, "Close the floating tool. Double-click to close with testcase status.", 154, 9, False),
            ("Move", None, "Drag this button to move the floating tool.", 206, 8, True),
            ("New", self.create_new_document, "Create a new Word document.", 257, 10, False),
            ("File", self.document_manager.select_document, "Open an existing Word document.", 309, 10, False),
        ]

        for label, command, tooltip_text, angle_deg, label_size, is_move in button_specs:
            radians = math.radians(angle_deg)
            button_center_x = center_x + radius * math.cos(radians)
            button_center_y = center_y + radius * math.sin(radians)
            button_left = button_center_x - (satellite_size / 2)
            button_top = button_center_y - (satellite_size / 2)

            if is_move:
                self._draw_move_button(button_left, button_top, satellite_size, PRIMARY_BLUE, label, tooltip_text, label_size=label_size)
            else:
                double_command = self.open_testcase_status_window if label == "Close" else None
                self._draw_circle_button(
                    button_left,
                    button_top,
                    satellite_size,
                    PRIMARY_BLUE,
                    label,
                    command,
                    tooltip_text,
                    label_size=label_size,
                    double_command=double_command,
                )

    def _draw_background(self):
        self.canvas.create_rectangle(
            0,
            0,
            self.scaled(BASE_WIDTH),
            self.scaled(BASE_HEIGHT),
            fill=TRANSPARENT_KEY,
            outline=TRANSPARENT_KEY,
        )

    def _draw_circle_button(self, x, y, size, fill, label, command, tooltip_text, label_size=11, double_command=None):
        x = self.scaled(x)
        y = self.scaled(y)
        size = self.scaled(size)
        label_size = self.scaled(label_size)
        shadow_offset = 6
        shadow = self.canvas.create_oval(
            x + self.scaled(shadow_offset),
            y + self.scaled(shadow_offset),
            x + size + self.scaled(shadow_offset),
            y + size + self.scaled(shadow_offset),
            fill=BUTTON_SHADOW,
            outline="",
        )
        oval = self.canvas.create_oval(x, y, x + size, y + size, fill=fill, outline="")
        text = self.canvas.create_text(
            x + size / 2,
            y + size / 2,
            text=label,
            fill="white",
            font=("Segoe UI Semibold", label_size),
            justify="center",
        )

        tracker = ButtonClickTracker(self.root, command, double_command=double_command)
        tracker.bind(self.canvas, shadow)
        tracker.bind(self.canvas, oval)
        tracker.bind(self.canvas, text)
        self._bind_tooltip((shadow, oval, text), tooltip_text)

    def _draw_move_button(self, x, y, size, fill, label, tooltip_text, label_size=11):
        x = self.scaled(x)
        y = self.scaled(y)
        size = self.scaled(size)
        label_size = self.scaled(label_size)
        shadow_offset = 6
        shadow = self.canvas.create_oval(
            x + self.scaled(shadow_offset),
            y + self.scaled(shadow_offset),
            x + size + self.scaled(shadow_offset),
            y + size + self.scaled(shadow_offset),
            fill=BUTTON_SHADOW,
            outline="",
        )
        oval = self.canvas.create_oval(x, y, x + size, y + size, fill=fill, outline="")
        text = self.canvas.create_text(
            x + size / 2,
            y + size / 2,
            text=label,
            fill="white",
            font=("Segoe UI Semibold", label_size),
            justify="center",
        )

        for item in (shadow, oval, text):
            self.canvas.tag_bind(item, "<Button-1>", self.start_move)
            self.canvas.tag_bind(item, "<B1-Motion>", self.on_motion)
            self.canvas.tag_bind(item, "<Button-3>", lambda event: self.open_size_window(event))
        self._bind_tooltip((shadow, oval, text), tooltip_text)

    def _bind_tooltip(self, items, tooltip_text):
        if not tooltip_text:
            return
        for item in items:
            self.canvas.tag_bind(
                item,
                "<Enter>",
                lambda event, text=tooltip_text: self.show_tooltip(text, event.x_root, event.y_root),
            )
            self.canvas.tag_bind(item, "<Leave>", lambda _event: self.hide_tooltip())

    def start_move(self, event):
        self.root.x = event.x_root - self.root.winfo_x()
        self.root.y = event.y_root - self.root.winfo_y()
        return "break"

    def on_motion(self, event):
        x = event.x_root - self.root.x
        y = event.y_root - self.root.y
        self.root.geometry(f"+{x}+{y}")
        return "break"

    def open_size_window(self, _event=None):
        if self.size_window is not None and self.size_window.winfo_exists():
            self.size_window.deiconify()
            self.size_window.lift()
            self.size_window.focus_force()
            return

        self.size_window = tk.Toplevel(self.root)
        self.size_window.title("Resize Tool")
        self.size_window.geometry(f"320x140+{self.root.winfo_x() + self.scaled(460)}+{self.root.winfo_y() + 40}")
        self.size_window.configure(bg=CARD_BG)
        self.size_window.attributes("-topmost", True)

        tk.Label(
            self.size_window,
            text="Adjust floating tool size",
            bg=CARD_BG,
            fg=TEXT_DARK,
            font=("Segoe UI Semibold", 11),
        ).pack(anchor="w", padx=16, pady=(14, 8))

        self.size_slider = tk.Scale(
            self.size_window,
            from_=int(MIN_SCALE * 100),
            to=int(MAX_SCALE * 100),
            orient="horizontal",
            command=self.apply_scale_from_slider,
            bg=CARD_BG,
            fg=TEXT_DARK,
            highlightthickness=0,
            length=260,
        )
        self.size_slider.pack(padx=16, fill="x")
        self.size_slider.set(int(self.ui_scale * 100))

        tk.Label(
            self.size_window,
            text="Tip: right-click the floating tool anytime to resize it.",
            bg=CARD_BG,
            fg="#5d6880",
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=16, pady=(6, 10))

        self.size_window.protocol("WM_DELETE_WINDOW", self.close_size_window)

    def close_size_window(self):
        if self.size_window is not None and self.size_window.winfo_exists():
            self.size_window.destroy()
        self.size_window = None
        self.size_slider = None

    def apply_scale_from_slider(self, value):
        self.apply_ui_scale(float(value))

    def apply_ui_scale(self, new_scale):
        self.ui_scale = max(MIN_SCALE, min(MAX_SCALE, new_scale))
        if self.size_slider is not None and self.size_slider.winfo_exists():
            current = int(float(self.size_slider.get()))
            target = int(self.ui_scale * 100)
            if current != target:
                self.size_slider.set(target)
        self.render_main_ui()

    def show_tooltip(self, text, x, y):
        self.hide_tooltip()
        self.tooltip_window = tk.Toplevel(self.root)
        self.tooltip_window.overrideredirect(True)
        self.tooltip_window.attributes("-topmost", True)
        self.tooltip_window.configure(bg="#182235")
        self.tooltip_window.geometry(f"+{x + 14}+{y + 10}")

        label = tk.Label(
            self.tooltip_window,
            text=text,
            bg="#182235",
            fg="white",
            font=("Segoe UI", 9),
            padx=10,
            pady=6,
            justify="left",
        )
        label.pack()

    def hide_tooltip(self):
        if self.tooltip_window is not None and self.tooltip_window.winfo_exists():
            self.tooltip_window.destroy()
        self.tooltip_window = None

    def show_toast(self, message, duration_ms=3000):
        self.close_toast()
        self.toast_window = tk.Toplevel(self.root)
        self.toast_window.overrideredirect(True)
        self.toast_window.attributes("-topmost", True)
        self.toast_window.configure(bg="#188038")

        label = tk.Label(
            self.toast_window,
            text=message,
            bg="#188038",
            fg="white",
            font=("Segoe UI Semibold", 12),
            padx=22,
            pady=14,
        )
        label.pack()

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.toast_window.update_idletasks()
        width = self.toast_window.winfo_width()
        height = self.toast_window.winfo_height()
        x = int((screen_width - width) / 2)
        y = max(24, int(screen_height * 0.08))
        self.toast_window.geometry(f"+{x}+{y}")

        self.toast_after_id = self.root.after(duration_ms, self.close_toast)

    def close_toast(self):
        if self.toast_after_id is not None:
            self.root.after_cancel(self.toast_after_id)
            self.toast_after_id = None
        if self.toast_window is not None and self.toast_window.winfo_exists():
            self.toast_window.destroy()
        self.toast_window = None
        try:
            if self.root.winfo_exists():
                self.root.update_idletasks()
        except tk.TclError:
            pass

    def create_new_document(self):
        folder = filedialog.askdirectory(title="Select folder to save the new document")
        if not folder:
            self.set_status("New document cancelled.")
            return

        title_window = tk.Toplevel(self.root)
        title_window.title("New Document Title")
        title_window.geometry("480x240+1020+160")
        title_window.configure(bg=CARD_BG)
        title_window.attributes("-topmost", True)

        tk.Label(
            title_window,
            text="Enter document title",
            bg=CARD_BG,
            fg=TEXT_DARK,
            font=("Segoe UI Semibold", 12),
        ).pack(anchor="w", padx=18, pady=(16, 8))

        tk.Label(
            title_window,
            text=f"Folder: {folder}",
            bg=CARD_BG,
            fg="#5d6880",
            font=("Segoe UI", 9),
            wraplength=430,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 8))

        title_textbox = tk.Text(
            title_window,
            height=4,
            width=40,
            wrap="word",
            font=("Segoe UI", 12),
            bd=1,
            relief="solid",
            padx=12,
            pady=12,
            fg=TEXT_DARK,
            highlightthickness=1,
            highlightbackground="#d9deea",
        )
        title_textbox.pack(fill="x", padx=18, pady=(0, 14))
        title_textbox.insert("1.0", datetime.now().strftime("TestDoc_%Y%m%d_%H%M%S"))
        title_textbox.focus_set()

        def save_new_document(_event=None):
            title = title_textbox.get("1.0", tk.END).strip()
            if not title:
                self.set_status("Enter a title for the new document.")
                return "break"

            if self.document_manager.create_new_document_file(folder, title):
                title_window.destroy()
            return "break"

        title_textbox.bind("<Return>", save_new_document)

        action_bar = tk.Frame(title_window, bg=CARD_BG)
        action_bar.pack(fill="x", padx=18, pady=(0, 16))

        tk.Button(
            action_bar,
            text="Create",
            command=save_new_document,
            bg=PRIMARY_BLUE,
            fg="white",
            relief="flat",
            padx=14,
            pady=6,
        ).pack(side="right")

        title_window.protocol("WM_DELETE_WINDOW", title_window.destroy)

    def open_info_window(self):
        info_window = tk.Toplevel(self.root)
        info_window.title("How To Use")
        info_window.geometry("500x440+1040+140")
        info_window.configure(bg=CARD_BG)
        info_window.attributes("-topmost", True)

        tk.Label(
            info_window,
            text="How to use",
            bg=CARD_BG,
            fg=TEXT_DARK,
            font=("Segoe UI Semibold", 12),
        ).pack(anchor="w", padx=18, pady=(16, 8))

        content_frame = tk.Frame(info_window, bg=CARD_BG)
        content_frame.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        scrollbar = tk.Scrollbar(content_frame)
        scrollbar.pack(side="right", fill="y")

        info_text = tk.Text(
            content_frame,
            bg=CARD_BG,
            fg=TEXT_DARK,
            font=("Segoe UI", 10),
            wrap="word",
            relief="flat",
            bd=0,
            padx=4,
            pady=4,
            yscrollcommand=scrollbar.set,
        )
        info_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=info_text.yview)

        instructions = (
            "How this tool works\n\n"
            "New button\n"
            "- Opens folder selection first.\n"
            "- Then shows a larger title box where you can enter the document title.\n"
            "- After clicking Create, a new Word document is created in that folder.\n\n"
            "File button\n"
            "- Opens an existing Word document.\n"
            "- The selected file becomes the active document for future screenshots.\n\n"
            "Note button\n"
            "- Opens the note window.\n"
            "- You can type text, use Bold or Italic, and then click Save & Close.\n"
            "- The saved note is attached to the next screenshot entry in the document.\n\n"
            "Shot button\n"
            "- Hides the floating tool, preview window, and note window before capture.\n"
            "- Takes the screenshot with the taskbar visible.\n"
            "- Double-click Shot to drag and capture only the required screen region.\n"
            "- Adds the note text first, then the screenshot image into the active document.\n"
            "- Saves the image into the screenshots folder also.\n"
            "- Clears the note after the capture is saved.\n"
            f"- Keyboard shortcut: {SHOT_SHORTCUT_LABEL}\n"
            f"- Taskbar-free shortcut: {WORKAREA_SHORTCUT_LABEL}\n\n"
            "Draw button\n"
            "- Shows drawing tools for the next screenshot.\n"
            f"- Keyboard shortcut: {DRAW_SHORTCUT_LABEL}\n\n"
            "Preview button\n"
            "- Opens a compact screenshot preview window.\n"
            "- Lets you move through saved screenshots one by one.\n"
            "- You can drag a yellow marker on top of the selected screenshot.\n"
            "- Save Highlight updates the selected screenshot instead of creating a duplicate copy.\n"
            "- Delete removes the selected screenshot from the preview list and screenshots folder.\n\n"
            "Close button\n"
            "- Click Close to finish normally.\n"
            "- Double-click Close to choose Passed, Failed, or Pending before closing.\n"
            "- The selected testcase status is added at the end of the active document in a designed format.\n"
            "- Before closing, if any note text is still pending, it is added at the end of the active document.\n"
            "- All temporary images in the screenshots folder are deleted after the save step completes.\n"
            "- Then the floating tool closes.\n\n"
            "General flow\n"
            "1. Click New or File.\n"
            "2. Add your note if needed.\n"
            "3. Click Shot.\n"
            "4. Repeat as many times as needed.\n\n"
            "By Tester/Developer\n"
            "Kalkeesh Jami\n"
            "email: kalkeesh.jami@accenture.com\n"
            "ph no: 7702726236\n"
            "lovely regards"
        )
        info_text.insert("1.0", instructions)
        info_text.configure(state="disabled")

        tk.Button(
            info_window,
            text="Close",
            command=info_window.destroy,
            bg=PRIMARY_BLUE,
            fg="white",
            relief="flat",
            padx=14,
            pady=6,
        ).pack(anchor="e", padx=18, pady=(0, 16))

    def take_screenshot(self, exclude_taskbar=False, use_region_selector=False):
        if self.capture_in_progress:
            self.set_status("Capture already running. Please wait.")
            return

        if not self.document_manager.has_document():
            messagebox.showwarning("No document", "Create or select a Word document first.")
            return

        self.capture_in_progress = True
        self.close_toast()
        self.hide_tooltip()
        try:
            hidden_windows = self._hide_autodoc_windows_for_capture()
        except Exception as exc:
            self.capture_in_progress = False
            messagebox.showerror("Capture failed", f"Could not prepare the screen for capture.\n\n{exc}")
            return
        self.root.after(CAPTURE_HIDE_DELAY_MS, lambda: self._capture_after_hide(exclude_taskbar, use_region_selector, hidden_windows))

    def _hide_autodoc_windows_for_capture(self):
        if self.note_manager.is_visible():
            self.note_manager.save(close_after=False)
        if self.preview_manager.is_visible():
            self.preview_manager.save_metadata()
            self.preview_manager.save_current_note()
        self.drawing_manager.prepare_for_capture()

        hidden_windows = []
        for window in self.root.winfo_children():
            if not isinstance(window, tk.Toplevel):
                continue
            if window is self.drawing_manager.overlay:
                continue
            try:
                if window.winfo_exists() and window.state() != "withdrawn":
                    hidden_windows.append(window)
                    window.withdraw()
            except tk.TclError:
                continue

        self.hide_tooltip()
        self.close_toast()
        self.root.withdraw()
        self.root.update_idletasks()
        return hidden_windows

    def _capture_after_hide(self, exclude_taskbar, use_region_selector, hidden_windows):
        note_runs = self.note_manager.get_note_runs()
        screenshot_dir = ensure_screenshot_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = "_notaskbar" if exclude_taskbar else ""
        img_path = os.path.join(screenshot_dir, f"screenshot_{timestamp}{suffix}.png")

        try:
            screenshot = capture_image(exclude_taskbar=exclude_taskbar)
            clean_screenshot = screenshot.copy()
            screenshot = self.drawing_manager.apply_to_screenshot(screenshot, exclude_taskbar=exclude_taskbar)
            if use_region_selector:
                region = self.select_capture_region(screenshot)
                if region is None:
                    self.set_status("Region capture cancelled.")
                    return
                screenshot = screenshot.crop(region)
                clean_screenshot = clean_screenshot.crop(region)

            screenshot.save(img_path)
            clean_screenshot.save(get_screenshot_backup_path(img_path))
            ensure_screenshot_backup(img_path)

            note_element = None
            note_text = "".join(text for text, _style in note_runs).strip()
            if note_runs:
                note_element = self.document_manager.add_note_runs(note_runs)

            self.document_manager.append_image(img_path, note_element=note_element)
            set_preview_note(img_path, note_text)
            self.document_manager.save()
        except Exception as exc:
            messagebox.showerror("Capture failed", f"Could not save screenshot.\n\n{exc}")
            self.set_status("Screenshot failed.")
        else:
            self.note_manager.clear()
            self.preview_manager.refresh_paths()
            if self.preview_manager.is_visible():
                self.preview_manager.show_at(len(self.preview_manager.paths) - 1)
            self.show_toast("Screenshot added")
            capture_mode = "selected region" if use_region_selector else ("without taskbar" if exclude_taskbar else "with taskbar")
            self.set_status(f"Saved screenshot {capture_mode} to {img_path}")
        finally:
            self.drawing_manager.finish_capture()
            self._restore_after_capture(hidden_windows)
            self.capture_in_progress = False

    def _restore_after_capture(self, hidden_windows):
        self.root.deiconify()
        for window in hidden_windows:
            try:
                if window.winfo_exists():
                    window.deiconify()
            except tk.TclError:
                continue
        if self.note_manager.is_visible():
            self.note_manager.show()
        if self.preview_manager.is_visible():
            self.preview_manager.show()

    def select_capture_region(self, base_image):
        selection = {"start": None, "end": None, "result": None}
        overlay = tk.Toplevel(self.root)
        overlay.overrideredirect(True)
        overlay.attributes("-topmost", True)
        overlay.geometry(f"{base_image.width}x{base_image.height}+0+0")
        overlay.configure(bg="black")

        overlay_photo = ImageTk.PhotoImage(base_image)
        canvas_overlay = tk.Canvas(overlay, width=base_image.width, height=base_image.height, highlightthickness=0, cursor="crosshair")
        canvas_overlay.pack(fill="both", expand=True)
        canvas_overlay.create_image(0, 0, image=overlay_photo, anchor="nw")
        rect = canvas_overlay.create_rectangle(0, 0, 0, 0, outline="#f7d038", width=2)
        hint = canvas_overlay.create_text(
            24,
            24,
            anchor="nw",
            text="Drag to capture a region. Press Esc to cancel.",
            fill="white",
            font=("Segoe UI Semibold", 12),
        )
        size_hint = canvas_overlay.create_text(
            24,
            52,
            anchor="nw",
            text="",
            fill="#ffe89a",
            font=("Segoe UI Semibold", 10),
        )
        canvas_overlay.tag_raise(rect)
        canvas_overlay.tag_raise(hint)
        canvas_overlay.tag_raise(size_hint)

        def on_press(event):
            selection["start"] = (event.x, event.y)
            selection["end"] = (event.x, event.y)
            canvas_overlay.coords(rect, event.x, event.y, event.x, event.y)

        def on_drag(event):
            if selection["start"] is None:
                return
            selection["end"] = (event.x, event.y)
            x1, y1 = selection["start"]
            x2, y2 = selection["end"]
            canvas_overlay.coords(rect, x1, y1, x2, y2)
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            canvas_overlay.itemconfigure(size_hint, text=f"Size: {width} x {height}")

        def finish_selection(_event=None):
            if selection["start"] is None or selection["end"] is None:
                selection["result"] = None
            else:
                x1, y1 = selection["start"]
                x2, y2 = selection["end"]
                left, right = sorted((max(0, x1), min(base_image.width, x2)))
                top, bottom = sorted((max(0, y1), min(base_image.height, y2)))
                if right - left < 4 or bottom - top < 4:
                    selection["result"] = None
                else:
                    selection["result"] = (left, top, right, bottom)
            overlay.destroy()

        def cancel_selection(_event=None):
            selection["result"] = None
            overlay.destroy()

        canvas_overlay.bind("<ButtonPress-1>", on_press)
        canvas_overlay.bind("<B1-Motion>", on_drag)
        canvas_overlay.bind("<ButtonRelease-1>", finish_selection)
        overlay.bind("<Escape>", cancel_selection)
        overlay.grab_set()
        overlay.focus_force()
        overlay.wait_window()
        return selection["result"]

    def set_status(self, message):
        self.status_var.set(message)

    def open_testcase_status_window(self):
        if self.close_in_progress:
            self.set_status("Close already running. Please wait.")
            return

        if not self.document_manager.has_document():
            messagebox.showwarning("No document", "Create or select a Word document first.")
            return

        if self.testcase_status_window is not None and self.testcase_status_window.winfo_exists():
            self.testcase_status_window.deiconify()
            self.testcase_status_window.lift()
            self.testcase_status_window.focus_force()
            return

        x = self.root.winfo_x() + self.scaled(92)
        y = self.root.winfo_y() + self.scaled(250)
        self.testcase_status_window = tk.Toplevel(self.root)
        self.testcase_status_window.title("Testcase Status")
        self.testcase_status_window.geometry(f"330x170+{x}+{y}")
        self.testcase_status_window.configure(bg=CARD_BG)
        self.testcase_status_window.attributes("-topmost", True)
        self.testcase_status_window.resizable(False, False)

        tk.Label(
            self.testcase_status_window,
            text="End document as",
            bg=CARD_BG,
            fg=TEXT_DARK,
            font=("Segoe UI Semibold", 13),
        ).pack(anchor="w", padx=18, pady=(16, 4))

        tk.Label(
            self.testcase_status_window,
            text="Choose testcase result before save and close.",
            bg=CARD_BG,
            fg="#5d6880",
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=18, pady=(0, 14))

        button_frame = tk.Frame(self.testcase_status_window, bg=CARD_BG)
        button_frame.pack(fill="x", padx=18)

        for status_key in ("passed", "failed", "pending"):
            status = TESTCASE_STATUS_OPTIONS[status_key]
            tk.Button(
                button_frame,
                text=status["label"],
                command=lambda key=status_key: self.close_app(testcase_status=key),
                bg=status["button_bg"],
                fg="white",
                activebackground=status["button_bg"],
                activeforeground="white",
                relief="flat",
                bd=0,
                padx=10,
                pady=10,
                font=("Segoe UI Semibold", 9),
            ).pack(side="left", expand=True, fill="x", padx=(0, 8) if status_key != "pending" else (0, 0))

        tk.Button(
            self.testcase_status_window,
            text="Cancel",
            command=self.testcase_status_window.destroy,
            bg="#eef1f6",
            fg=TEXT_DARK,
            relief="flat",
            bd=0,
            padx=12,
            pady=5,
            font=("Segoe UI", 9),
        ).pack(anchor="e", padx=18, pady=(14, 0))

        self.testcase_status_window.protocol("WM_DELETE_WINDOW", self.testcase_status_window.destroy)
        self.testcase_status_window.focus_force()
        self.set_status("Choose testcase status to save and close.")

    def close_app(self, testcase_status=None):
        if self.close_in_progress:
            self.set_status("Close already running. Please wait.")
            return

        self.close_in_progress = True
        self.set_status("Saving and closing...")
        self.root.update_idletasks()
        try:
            self.preview_manager.save_metadata()
            self.preview_manager.save_current_note()
            self.note_manager.append_pending_note_to_document()
            if testcase_status is not None:
                self.document_manager.append_testcase_status(testcase_status)
            clear_screenshot_dir()
        except Exception as exc:
            self.close_in_progress = False
            messagebox.showerror("Close failed", f"Could not finish saving/cleanup before closing.\n\n{exc}")
            return
        self.close_toast()
        if self.testcase_status_window is not None and self.testcase_status_window.winfo_exists():
            self.testcase_status_window.destroy()
        self.preview_manager.close_window()
        if self.note_manager.window is not None and self.note_manager.window.winfo_exists():
            self.note_manager.window.destroy()
        self.hotkey_manager.stop()
        self.drawing_manager.hide(clear=True)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


