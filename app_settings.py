import json
import os

SETTINGS_PATH = 'settings.json'

def load_settings():
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_settings(settings):
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2) 