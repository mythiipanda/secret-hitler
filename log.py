import os
from datetime import datetime
from typing import Optional

LOG_FH: Optional[object] = None
LOG_PATH: Optional[str] = None

def init(log_dir: str = "logs") -> str:
    """Initialize logging: create directory and open a timestamped log file. Returns path."""
    global LOG_FH, LOG_PATH
    os.makedirs(log_dir, exist_ok=True)
    fname = datetime.utcnow().strftime("run_%Y%m%d_%H%M%S.txt")
    path = os.path.join(log_dir, fname)
    LOG_FH = open(path, "w", encoding="utf-8")
    LOG_PATH = path
    log(f"[LOG INIT] {datetime.utcnow().isoformat()} UTC", end="\n")
    return path

def log(msg: str = "", end: str = "\n") -> None:
    """Write message to stdout and append to the active log file if initialized."""
    print(msg, end=end)
    global LOG_FH
    if LOG_FH:
        try:
            if end:
                LOG_FH.write(msg + end)
            else:
                LOG_FH.write(msg)
            LOG_FH.flush()
        except Exception:
            pass

def close() -> None:
    """Close the active log file if open."""
    global LOG_FH
    if LOG_FH:
        try:
            LOG_FH.close()
        except Exception:
            pass
        LOG_FH = None