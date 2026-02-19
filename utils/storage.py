import json
import os
from typing import Any
from .paths import data_path

def load_json(filename: str, default: Any):
    path = data_path(filename)
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return default
    except Exception:
        return default

def save_json(filename: str, obj: Any):
    path = data_path(filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def exists_file(filename: str) -> bool:
    path = data_path(filename)
    return os.path.exists(path) and os.path.isfile(path)

def abs_path(filename: str) -> str:
    return data_path(filename)
