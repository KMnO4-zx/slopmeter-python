from __future__ import annotations

import json
import os
import platform
import socket
import sys
import uuid
from datetime import datetime
from pathlib import Path


DEVICE_FILE_NAME = "device.json"


def get_slopmeter_config_dir() -> Path:
    if sys.platform == "win32":
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
        if xdg_config_home:
            return Path(xdg_config_home) / "slopmeter"
        app_data = os.environ.get("APPDATA", "").strip()
        base_dir = Path(app_data) if app_data else Path.home() / "AppData" / "Roaming"
        return base_dir / "slopmeter"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "slopmeter"

    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if not xdg_config_home:
        xdg_config_home = str(Path.home() / ".config")
    return Path(xdg_config_home) / "slopmeter"


def get_device_metadata_path() -> Path:
    return get_slopmeter_config_dir() / DEVICE_FILE_NAME


def get_default_device_name() -> str:
    hostname = (
        os.environ.get("SLOPMETER_DEVICE_NAME", "").strip()
        or os.environ.get("COMPUTERNAME", "").strip()
        or os.environ.get("HOSTNAME", "").strip()
        or socket.gethostname().strip()
        or platform.node().strip()
    )
    return hostname or "device"


def get_platform_label() -> str:
    if sys.platform == "win32":
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return sys.platform


def get_timezone_name() -> str:
    tzinfo = datetime.now().astimezone().tzinfo
    if tzinfo is None:
        return "UTC"
    zone_name = getattr(tzinfo, "key", None) or str(tzinfo)
    return zone_name or "UTC"


def get_or_create_device_metadata() -> dict[str, str]:
    path = get_device_metadata_path()
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        existing = {}

    device_id = str(existing.get("id") or "").strip() or str(uuid.uuid4())
    device_name = str(existing.get("name") or "").strip() or get_default_device_name()
    metadata = {
        "id": device_id,
        "name": device_name,
        "platform": str(existing.get("platform") or get_platform_label()),
        "timeZone": str(existing.get("timeZone") or get_timezone_name()),
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata
