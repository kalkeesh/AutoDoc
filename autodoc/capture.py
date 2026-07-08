import ctypes
import os
from ctypes import wintypes

from .config import SPI_GETWORKAREA


def _take_screenshot():
    import pyautogui

    return pyautogui.screenshot()

def get_workarea_bbox():
    if os.name != "nt":
        screenshot = _take_screenshot()
        return 0, 0, screenshot.width, screenshot.height

    rect = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top, rect.right, rect.bottom


def capture_image(exclude_taskbar=False):
    screenshot = _take_screenshot()
    if not exclude_taskbar:
        return screenshot

    left, top, right, bottom = get_workarea_bbox()
    return screenshot.crop((left, top, right, bottom))


