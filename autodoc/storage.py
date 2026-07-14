import json
import os
import shutil

from .config import PREVIEW_NOTES_FILE, PREVIEW_TABLES_KEY, SCREENSHOT_DIR, TEST_METADATA_FIELDS, TEST_METADATA_KEY

def ensure_screenshot_dir():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    return SCREENSHOT_DIR


def ensure_screenshot_backup_dir():
    backup_dir = os.path.join(ensure_screenshot_dir(), ".originals")
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def get_screenshot_backup_path(image_path):
    return os.path.join(ensure_screenshot_backup_dir(), os.path.basename(image_path))


def ensure_screenshot_backup(image_path):
    backup_path = get_screenshot_backup_path(image_path)
    if os.path.exists(image_path) and not os.path.exists(backup_path):
        shutil.copyfile(image_path, backup_path)
    return backup_path


def get_preview_notes_path():
    return os.path.join(ensure_screenshot_dir(), PREVIEW_NOTES_FILE)


def load_preview_notes():
    notes_path = get_preview_notes_path()
    if not os.path.exists(notes_path):
        return {}
    try:
        with open(notes_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_preview_notes(notes):
    notes_path = get_preview_notes_path()
    try:
        with open(notes_path, "w", encoding="utf-8") as file:
            json.dump(notes, file, ensure_ascii=False, indent=2)
    except OSError:
        pass


def set_preview_note(image_path, note_text):
    if not image_path:
        return
    notes = load_preview_notes()
    key = os.path.basename(image_path)
    if note_text:
        notes[key] = note_text
    else:
        notes.pop(key, None)
    save_preview_notes(notes)


def get_preview_note(image_path):
    if not image_path:
        return ""
    return load_preview_notes().get(os.path.basename(image_path), "")


def remove_preview_note(image_path):
    if not image_path:
        return
    notes = load_preview_notes()
    if notes.pop(os.path.basename(image_path), None) is not None:
        save_preview_notes(notes)


def _blank_table(rows, columns):
    return {
        "rows": max(1, int(rows)),
        "columns": max(1, int(columns)),
        "data": [["" for _column in range(max(1, int(columns)))] for _row in range(max(1, int(rows)))],
        "column_widths": [140 for _column in range(max(1, int(columns)))],
        "row_heights": [36 for _row in range(max(1, int(rows)))],
    }


def normalize_preview_table(table):
    if not isinstance(table, dict):
        return _blank_table(2, 2)

    rows = max(1, int(table.get("rows") or 1))
    columns = max(1, int(table.get("columns") or 1))
    raw_data = table.get("data") if isinstance(table.get("data"), list) else []
    data = []
    for row_index in range(rows):
        raw_row = raw_data[row_index] if row_index < len(raw_data) and isinstance(raw_data[row_index], list) else []
        data.append([str(raw_row[column_index]) if column_index < len(raw_row) else "" for column_index in range(columns)])

    raw_widths = table.get("column_widths") if isinstance(table.get("column_widths"), list) else []
    column_widths = []
    for column_index in range(columns):
        value = raw_widths[column_index] if column_index < len(raw_widths) else 140
        try:
            width = int(value)
        except (TypeError, ValueError):
            width = 140
        column_widths.append(max(70, min(420, width)))

    raw_heights = table.get("row_heights") if isinstance(table.get("row_heights"), list) else []
    row_heights = []
    for row_index in range(rows):
        value = raw_heights[row_index] if row_index < len(raw_heights) else 36
        try:
            height = int(value)
        except (TypeError, ValueError):
            height = 36
        row_heights.append(max(30, min(240, height)))

    return {
        "rows": rows,
        "columns": columns,
        "data": data,
        "column_widths": column_widths,
        "row_heights": row_heights,
    }


def get_preview_tables(image_path):
    if not image_path:
        return []
    tables_by_image = load_preview_notes().get(PREVIEW_TABLES_KEY, {})
    if not isinstance(tables_by_image, dict):
        return []
    tables = tables_by_image.get(os.path.basename(image_path), [])
    if not isinstance(tables, list):
        return []
    return [normalize_preview_table(table) for table in tables]


def set_preview_tables(image_path, tables):
    if not image_path:
        return
    notes = load_preview_notes()
    tables_by_image = notes.get(PREVIEW_TABLES_KEY, {})
    if not isinstance(tables_by_image, dict):
        tables_by_image = {}

    cleaned = [normalize_preview_table(table) for table in tables if isinstance(table, dict)]
    key = os.path.basename(image_path)
    if cleaned:
        tables_by_image[key] = cleaned
    else:
        tables_by_image.pop(key, None)

    if tables_by_image:
        notes[PREVIEW_TABLES_KEY] = tables_by_image
    else:
        notes.pop(PREVIEW_TABLES_KEY, None)
    save_preview_notes(notes)


def remove_preview_tables(image_path):
    if not image_path:
        return
    notes = load_preview_notes()
    tables_by_image = notes.get(PREVIEW_TABLES_KEY, {})
    if not isinstance(tables_by_image, dict):
        return
    if tables_by_image.pop(os.path.basename(image_path), None) is not None:
        if tables_by_image:
            notes[PREVIEW_TABLES_KEY] = tables_by_image
        else:
            notes.pop(PREVIEW_TABLES_KEY, None)
        save_preview_notes(notes)


def get_preview_metadata():
    metadata = load_preview_notes().get(TEST_METADATA_KEY, {})
    if not isinstance(metadata, dict):
        return {key: "" for key, _label in TEST_METADATA_FIELDS}
    return {key: str(metadata.get(key, "")) for key, _label in TEST_METADATA_FIELDS}


def set_preview_metadata(metadata):
    notes = load_preview_notes()
    cleaned = {key: str(metadata.get(key, "")).strip() for key, _label in TEST_METADATA_FIELDS}
    if any(cleaned.values()):
        notes[TEST_METADATA_KEY] = cleaned
    else:
        notes.pop(TEST_METADATA_KEY, None)
    save_preview_notes(notes)


def clear_screenshot_dir():
    screenshot_dir = ensure_screenshot_dir()
    removed_count = 0

    for name in os.listdir(screenshot_dir):
        path = os.path.join(screenshot_dir, name)
        if not os.path.isfile(path):
            continue
        if name == PREVIEW_NOTES_FILE:
            os.remove(path)
            continue
        if not name.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        os.remove(path)
        removed_count += 1

    backup_dir = ensure_screenshot_backup_dir()
    for name in os.listdir(backup_dir):
        path = os.path.join(backup_dir, name)
        if not os.path.isfile(path):
            continue
        if not name.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        os.remove(path)

    return removed_count


def list_saved_screenshots():
    screenshot_dir = ensure_screenshot_dir()
    paths = []
    for entry in os.scandir(screenshot_dir):
        if not entry.is_file():
            continue
        lower_name = entry.name.lower()
        if lower_name.endswith((".png", ".jpg", ".jpeg")):
            paths.append((entry.path, entry.stat().st_mtime))
    return [path for path, _mtime in sorted(paths, key=lambda item: item[1])]


