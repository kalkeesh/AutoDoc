from docx.shared import RGBColor

APP_BG = "#f3f3f3"
PRIMARY_BLUE = "#4f6ff0"
PRIMARY_RED = "#f61d2a"
PRIMARY_GREEN = "#12a150"
PRIMARY_GREY = "#7a8494"
BUTTON_SHADOW = "#d3d3d3"
SCREENSHOT_DIR = "screenshots"
PREVIEW_NOTES_FILE = "preview_notes.json"
TEST_METADATA_KEY = "__test_metadata__"
PREVIEW_TABLES_KEY = "__preview_tables__"
TEST_METADATA_FIELDS = (
    ("scenario", "Test Scenario"),
    ("expected_result", "Expected Result"),
    ("test_data", "Test Data"),
)
CARD_BG = "#ffffff"
TEXT_DARK = "#20304a"
BASE_WIDTH = 420
BASE_HEIGHT = 680
MIN_SCALE = 0.70
MAX_SCALE = 1.25
TRANSPARENT_KEY = "#00ff00"
SHOT_SHORTCUT_LABEL = "Ctrl+Q"
WORKAREA_SHORTCUT_LABEL = "Ctrl+W"
DRAW_SHORTCUT_LABEL = "Ctrl+E"
PREVIEW_BRUSH_LEVELS = [8, 14, 22, 32]
SHOT_SINGLE_CLICK_DELAY_MS = 420
CAPTURE_HIDE_DELAY_MS = 700
HOTKEY_ID = 1
WORKAREA_HOTKEY_ID = 2
DRAW_HOTKEY_ID = 3
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
SPI_GETWORKAREA = 0x0030
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
VK_Q = 0x51
VK_W = 0x57
VK_E = 0x45
TESTCASE_STATUS_OPTIONS = {
    "passed": {
        "label": "Passed",
        "document_text": "TESTCASE : PASSED",
        "button_bg": PRIMARY_GREEN,
        "text_color": RGBColor(18, 122, 67),
    },
    "failed": {
        "label": "Failed",
        "document_text": "TESTCASE : FAILED",
        "button_bg": PRIMARY_RED,
        "text_color": RGBColor(188, 28, 43),
    },
    "pending": {
        "label": "Pending",
        "document_text": "TESTCASE : PENDING - YET TO WORK",
        "button_bg": PRIMARY_GREY,
        "text_color": RGBColor(99, 108, 123),
    },
}
