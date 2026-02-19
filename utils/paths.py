import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOT_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(BOT_DIR, "data")

def data_path(filename: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, filename)
