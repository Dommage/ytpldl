import json
import os
from typing import Any, Dict


CONFIG_DIR = "config"
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "download_dir": "downloads",
    "cookies_path": "./cookies.txt",
    "max_quality_height": 1080,
    "archive_path": "logs/download_archive.txt",
}


def load_config() -> Dict[str, Any]:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = {**DEFAULT_CONFIG, **data}
        # Migration : ancien chemin par défaut "config/cookies.txt" vers "./cookies.txt"
        if merged.get("cookies_path") == "config/cookies.txt":
            merged["cookies_path"] = DEFAULT_CONFIG["cookies_path"]
        return merged
    except (json.JSONDecodeError, OSError):
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
