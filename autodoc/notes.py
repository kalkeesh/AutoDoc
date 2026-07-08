import tkinter as tk

from .config import CARD_BG, PRIMARY_BLUE, TEXT_DARK

class NoteManager:
    def __init__(self, app, document_manager):
        self.app = app
        self.document_manager = document_manager
        self.current_note_text = ""
        self.window = None
        self.textbox = None
        self.bold_button = None
        self.italic_button = None

    def get_note_text(self):
        if self.window and self.window.winfo_exists() and self.textbox:
            return self.textbox.get("1.0", tk.END).strip()
        return self.current_note_text

    def save(self, close_after=False):
        self.current_note_text = self.get_note_text()
        if self.current_note_text:
            self.app.set_status("Note saved. Press Shot to use it.")
        else:
            self.app.set_status("Note cleared.")

        if close_after:
            self.hide()

    def clear(self):
        self.current_note_text = ""
        if self.textbox is not None:
            self.textbox.delete("1.0", tk.END)
            for tag_name in ("bold", "italic", "bold_italic"):
                self.textbox.tag_remove(tag_name, "1.0", tk.END)
        self.update_style_buttons()
        self.app.set_status("Note cleared.")

    def is_visible(self):
        return self.window is not None and self.window.winfo_exists() and self.window.state() != "withdrawn"

    def hide(self):
        if self.window is not None and self.window.winfo_exists():
            self.window.withdraw()

    def show(self):
        if self.window is not None and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()

    def open_window(self):
        if self.window is not None and self.window.winfo_exists():
            self.show()
            return

        self.window = tk.Toplevel(self.app.root)
        self.window.title("Add Note")
        self.window.geometry("420x320+1020+170")
        self.window.configure(bg=CARD_BG)
        self.window.attributes("-topmost", True)

        header = tk.Label(
            self.window,
            text="Write your note",
            bg=CARD_BG,
            fg=TEXT_DARK,
            font=("Segoe UI Semibold", 12),
        )
        header.pack(anchor="w", padx=16, pady=(14, 6))

        toolbar = tk.Frame(self.window, bg=CARD_BG)
        toolbar.pack(fill="x", padx=16, pady=(0, 8))

        self.bold_button = tk.Button(toolbar, text="Bold", width=8, command=self.toggle_bold, relief="flat")
        self.bold_button.pack(side="left", padx=(0, 8))

        self.italic_button = tk.Button(toolbar, text="Italic", width=8, command=self.toggle_italic, relief="flat")
        self.italic_button.pack(side="left", padx=(0, 8))

        clear_button = tk.Button(
            toolbar,
            text="Clear",
            width=8,
            command=self.clear,
            relief="flat",
            bg="#ffe4e6",
            fg="#8b1e2d",
        )
        clear_button.pack(side="left")

        self.textbox = tk.Text(
            self.window,
            wrap="word",
            font=("Segoe UI", 10),
            bd=1,
            relief="solid",
            padx=10,
            pady=10,
            fg=TEXT_DARK,
            highlightthickness=1,
            highlightbackground="#d9deea",
        )
        self.textbox.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self.textbox.insert("1.0", self.current_note_text)
        self.configure_text_tags()
        self.textbox.bind("<<Selection>>", lambda _event: self.update_style_buttons())
        self.textbox.bind("<ButtonRelease-1>", lambda _event: self.update_style_buttons())
        self.textbox.bind("<KeyRelease>", lambda _event: self.update_style_buttons())

        action_bar = tk.Frame(self.window, bg=CARD_BG)
        action_bar.pack(fill="x", padx=16, pady=(0, 14))

        save_button = tk.Button(
            action_bar,
            text="Save & Close",
            command=lambda: self.save(close_after=True),
            bg=PRIMARY_BLUE,
            fg="white",
            relief="flat",
            padx=12,
            pady=6,
        )
        save_button.pack(side="right")

        self.window.protocol("WM_DELETE_WINDOW", lambda: self.save(close_after=True))
        self.update_style_buttons()
        self.textbox.focus_set()
        self.app.set_status("Type your note, then save and close the note window.")

    def configure_text_tags(self):
        if self.textbox is None:
            return
        self.textbox.tag_configure("bold", font=("Segoe UI", 10, "bold"))
        self.textbox.tag_configure("italic", font=("Segoe UI", 10, "italic"))
        self.textbox.tag_configure("bold_italic", font=("Segoe UI", 10, "bold italic"))

    def update_style_buttons(self):
        if self.window is None or not self.window.winfo_exists() or self.textbox is None:
            return
        has_selection = bool(self.textbox.tag_ranges("sel"))
        state = "normal" if has_selection else "disabled"
        self.bold_button.configure(bg="#e8edff", fg=TEXT_DARK, state=state)
        self.italic_button.configure(bg="#e8edff", fg=TEXT_DARK, state=state)

    def toggle_bold(self):
        self._toggle_selected_text_style("bold")

    def toggle_italic(self):
        self._toggle_selected_text_style("italic")

    def _toggle_selected_text_style(self, style_name):
        if self.textbox is None or not self.textbox.tag_ranges("sel"):
            self.app.set_status("Select text in the note box first.")
            self.update_style_buttons()
            return

        start = self.textbox.index("sel.first")
        end = self.textbox.index("sel.last")
        has_bold = self._style_range_has_tag("bold", start, end) or self._style_range_has_tag("bold_italic", start, end)
        has_italic = self._style_range_has_tag("italic", start, end) or self._style_range_has_tag("bold_italic", start, end)

        if style_name == "bold":
            wants_bold = not has_bold
            wants_italic = has_italic
        else:
            wants_bold = has_bold
            wants_italic = not has_italic

        for tag_name in ("bold", "italic", "bold_italic"):
            self.textbox.tag_remove(tag_name, start, end)

        if wants_bold and wants_italic:
            self.textbox.tag_add("bold_italic", start, end)
        elif wants_bold:
            self.textbox.tag_add("bold", start, end)
        elif wants_italic:
            self.textbox.tag_add("italic", start, end)

        self.update_style_buttons()
        self.textbox.focus_set()

    def _style_range_has_tag(self, tag_name, start, end):
        ranges = self.textbox.tag_ranges(tag_name)
        for i in range(0, len(ranges), 2):
            tag_start = ranges[i]
            tag_end = ranges[i + 1]
            if self.textbox.compare(tag_end, ">", start) and self.textbox.compare(tag_start, "<", end):
                return True
        return False

    def get_note_runs(self):
        if self.textbox is None or not self.window or not self.window.winfo_exists():
            return [(self.current_note_text, "normal")] if self.current_note_text else []

        end = self.textbox.index("end-1c")
        index = "1.0"
        runs = []
        current_style = None
        buffer = []

        while self.textbox.compare(index, "<", end):
            next_index = self.textbox.index(f"{index} +1c")
            char = self.textbox.get(index, next_index)
            tags = set(self.textbox.tag_names(index))

            if "bold_italic" in tags:
                style = "bold_italic"
            elif "bold" in tags:
                style = "bold"
            elif "italic" in tags:
                style = "italic"
            else:
                style = "normal"

            if current_style is None:
                current_style = style

            if style != current_style:
                runs.append(("".join(buffer), current_style))
                buffer = []
                current_style = style

            buffer.append(char)
            index = next_index

        if buffer:
            runs.append(("".join(buffer), current_style))

        return runs

    def append_pending_note_to_document(self):
        if not self.document_manager.has_document():
            return

        runs = self.get_note_runs()
        if not runs:
            return

        self.document_manager.add_note_runs(runs)
        self.document_manager.save()
        self.clear()


