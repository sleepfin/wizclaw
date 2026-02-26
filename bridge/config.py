"""Configuration management for wizclaw bridge daemon.

Config lives at:
    - Windows: %APPDATA%\\wizclaw\\config.yaml
    - Unix:    ~/.wizclaw/config.yaml
"""

import os
import platform
from pathlib import Path

import yaml


def _get_config_dir() -> Path:
    """Return the platform-appropriate config directory."""
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "wizclaw"
    return Path.home() / ".wizclaw"


CONFIG_DIR = _get_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.yaml"

_DEFAULTS = {
    "cloud_url": "ws://stackme.cloud/ws/bridge",
    "api_key": "",
    "openclaw_url": "http://localhost:18789",
    "openclaw_token": "",
    "openclaw_agent_id": "main",
    "openclaw_auto_start": True,
    "reconnect_interval_max": 30,
    "request_timeout": 120,
}


def load_config() -> dict:
    """Load config from disk, falling back to defaults for missing keys."""
    if not CONFIG_FILE.exists():
        return dict(_DEFAULTS)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        user_cfg = yaml.safe_load(f) or {}
    known_keys = set(_DEFAULTS.keys())
    merged = dict(_DEFAULTS)
    merged.update({k: v for k, v in user_cfg.items() if v is not None and k in known_keys})
    return merged


def save_config(cfg: dict) -> None:
    """Persist config to disk with owner-only permissions."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        CONFIG_DIR.chmod(0o700)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
    if os.name != "nt":
        CONFIG_FILE.chmod(0o600)


def get_config_path() -> str:
    return str(CONFIG_FILE)


def detect_openclaw_config() -> dict:
    """Auto-detect OpenClaw settings from its config file.

    Reads ~/.openclaw/openclaw.json and extracts gateway port and auth token.
    Returns dict with keys: url, token, port (any may be absent).
    """
    import json

    config_path = Path.home() / ".openclaw" / "openclaw.json"
    if not config_path.exists():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        result = {}
        gateway = data.get("gateway", {})
        port = gateway.get("port")
        if port:
            result["port"] = port
            result["url"] = f"http://localhost:{port}"
        token = gateway.get("auth", {}).get("token")
        if token:
            result["token"] = token
        return result
    except Exception:
        return {}
