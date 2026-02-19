from datetime import datetime

def human_delta(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"

def utc_ts_filename(prefix: str, ext: str) -> str:
    ts = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S_UTC")
    return f"{prefix}_{ts}.{ext}"
