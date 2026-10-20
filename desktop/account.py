"""Start the local account service without showing it in the window."""

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8787"
ROOT = Path(__file__).resolve().parent.parent


def auth_data_dir() -> Path:
    root = os.environ.get("APPDATA") or str(Path.home())
    path = Path(root) / "Novel" / "auth_data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _healthy() -> bool:
    try:
        response = httpx.get(f"{BASE}/health", timeout=0.4)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def ensure_account_service() -> None:
    if _healthy():
        return
    env = os.environ.copy()
    env["NOVEL_AUTH_DATA"] = str(auth_data_dir())
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [sys.executable, "-m", "auth"],
        cwd=str(ROOT),
        env=env,
        creationflags=flags,
    )
    for _ in range(40):
        if _healthy():
            return
        time.sleep(0.25)
