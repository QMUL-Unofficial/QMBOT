import json
import os
from typing import Any

# Put your JSON files in a persistent folder if set (Railway volume recommended)
DATA_DIR = os.getenv("DATA_DIR", ".")

def path(name: str) -> str:
    return os.path.join(DATA_DIR, name)

def load_json(filename: str, default: Any):
    fp = path(filename)
    if not os.path.exists(fp):
        return default
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return default

def save_json(filename: str, obj: Any):
    fp = path(filename)
    os.makedirs(os.path.dirname(fp) or ".", exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def ensure_file(filename: str, default: Any):
    fp = path(filename)
    if not os.path.exists(fp):
        save_json(filename, default)
