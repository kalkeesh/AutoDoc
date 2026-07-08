import ctypes
import os
import threading
from ctypes import wintypes

from .config import (
    DRAW_HOTKEY_ID,
    DRAW_SHORTCUT_LABEL,
    HOTKEY_ID,
    MOD_CONTROL,
    SHOT_SHORTCUT_LABEL,
    SHOT_SINGLE_CLICK_DELAY_MS,
    VK_E,
    VK_Q,
    VK_W,
    WM_HOTKEY,
    WM_QUIT,
    WORKAREA_HOTKEY_ID,
    WORKAREA_SHORTCUT_LABEL,
)

class HotkeyManager:
    def __init__(self, app):
        self.app = app
        self.thread = None
        self.thread_id = None
        self.hotkey_registered = False
        self.workarea_hotkey_registered = False
        self.draw_hotkey_registered = False

    def start(self):
        if os.name != "nt":
            return
        self.thread = threading.Thread(target=self._hotkey_listener_loop, daemon=True)
        self.thread.start()

    def _hotkey_listener_loop(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self.thread_id = kernel32.GetCurrentThreadId()

        if user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL, VK_Q):
            self.hotkey_registered = True
        else:
            self.app.schedule(self.app.set_status, f"Global shortcut unavailable: {SHOT_SHORTCUT_LABEL}")

        if user32.RegisterHotKey(None, WORKAREA_HOTKEY_ID, MOD_CONTROL, VK_W):
            self.workarea_hotkey_registered = True
        else:
            self.app.schedule(self.app.set_status, f"Taskbar-free shortcut unavailable: {WORKAREA_SHORTCUT_LABEL}")

        if user32.RegisterHotKey(None, DRAW_HOTKEY_ID, MOD_CONTROL, VK_E):
            self.draw_hotkey_registered = True
        else:
            self.app.schedule(self.app.set_status, f"Draw shortcut unavailable: {DRAW_SHORTCUT_LABEL}")

        if not self.hotkey_registered and not self.workarea_hotkey_registered and not self.draw_hotkey_registered:
            return

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY:
                if msg.wParam == HOTKEY_ID:
                    self.app.schedule(self.app.take_screenshot)
                elif msg.wParam == WORKAREA_HOTKEY_ID:
                    self.app.schedule(self.app.take_screenshot, exclude_taskbar=True)
                elif msg.wParam == DRAW_HOTKEY_ID:
                    self.app.schedule(self.app.toggle_draw_mode)
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        self._unregister_hotkeys(user32)

    def _unregister_hotkeys(self, user32):
        if self.hotkey_registered:
            user32.UnregisterHotKey(None, HOTKEY_ID)
            self.hotkey_registered = False
        if self.workarea_hotkey_registered:
            user32.UnregisterHotKey(None, WORKAREA_HOTKEY_ID)
            self.workarea_hotkey_registered = False
        if self.draw_hotkey_registered:
            user32.UnregisterHotKey(None, DRAW_HOTKEY_ID)
            self.draw_hotkey_registered = False

    def stop(self):
        if os.name != "nt":
            return

        user32 = ctypes.windll.user32
        self._unregister_hotkeys(user32)

        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
            self.thread_id = None


class ButtonClickTracker:
    def __init__(self, root, single_command, double_command=None):
        self.root = root
        self.single_command = single_command
        self.double_command = double_command
        self.pending_id = None

    def bind(self, canvas, item):
        if self.double_command is None:
            canvas.tag_bind(item, "<Button-1>", self._single_click)
        else:
            canvas.tag_bind(item, "<Button-1>", self._schedule_single_click)
            canvas.tag_bind(item, "<Double-Button-1>", self._double_click)

    def _single_click(self, event):
        self.single_command()
        return "break"

    def _schedule_single_click(self, event):
        if self.pending_id is not None:
            self.root.after_cancel(self.pending_id)
        self.pending_id = self.root.after(SHOT_SINGLE_CLICK_DELAY_MS, self._execute_single)
        return "break"

    def _execute_single(self):
        self.pending_id = None
        self.single_command()

    def _double_click(self, event):
        if self.pending_id is not None:
            self.root.after_cancel(self.pending_id)
            self.pending_id = None
        self.double_command()
        return "break"


