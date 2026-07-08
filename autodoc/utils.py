from datetime import datetime

def clean_filename(value):
    cleaned = "".join("_" if char in '<>:"/\\|?*' else char for char in value).strip(" .")
    return cleaned or datetime.now().strftime("TestDoc_%Y%m%d_%H%M%S")

