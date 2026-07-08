"""系统设置管理工具函数

提供对 settings.yaml 的读写，支持热加载到 AppState。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


VALID_LOG_LEVELS = {"debug", "info", "warning", "error"}

COMMON_TIMEZONES = [
    "Asia/Shanghai",
    "Asia/Hong_Kong",
    "Asia/Tokyo",
    "Asia/Singapore",
    "UTC",
    "Europe/London",
    "America/New_York",
    "America/Los_Angeles",
    "America/Chicago",
    "Australia/Sydney",
]


def _load_settings_yaml(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise ValueError(f"Settings file not found: {path}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid settings format: {path}")
    return data


def _save_settings_yaml(path: str, data: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def update_settings_from_form(settings_yaml: str, form_data: dict[str, Any], app_state=None) -> dict[str, Any]:
    """从表单数据更新 settings.yaml

    form_data 来自 HTML 表单 POST，包含：
    - host, port, log_level (server 段)
    - socket_path (docker 段)
    - container_management, image_management, system_diagnostics (features 段, checkbox)
    - timezone
    """
    data = _load_settings_yaml(settings_yaml)

    server = data.setdefault("server", {})
    if "host" in form_data:
        server["host"] = str(form_data["host"]).strip() or "0.0.0.0"
    if "port" in form_data:
        try:
            server["port"] = int(form_data["port"])
        except (ValueError, TypeError):
            return {"success": False, "error": "端口必须是数字"}
    if "log_level" in form_data:
        level = str(form_data["log_level"]).strip().lower()
        if level not in VALID_LOG_LEVELS:
            return {"success": False, "error": f"无效的日志级别: {level}"}
        server["log_level"] = level
    if "host_origin_protection" in form_data:
        server["host_origin_protection"] = form_data["host_origin_protection"] in (True, "on", "1", "true")
    if "allowed_hosts" in form_data:
        hosts_str = str(form_data["allowed_hosts"]).strip()
        if hosts_str:
            server["allowed_hosts"] = [h.strip() for h in hosts_str.split(",") if h.strip()]
        else:
            server["allowed_hosts"] = []

    docker_cfg = data.setdefault("docker", {})
    if "socket_path" in form_data:
        docker_cfg["socket_path"] = str(form_data["socket_path"]).strip() or "/var/run/docker.sock"

    features = data.setdefault("features", {})
    features["container_management"] = form_data.get("container_management") in (True, "on", "1", "true")
    features["image_management"] = form_data.get("image_management") in (True, "on", "1", "true")
    features["system_diagnostics"] = form_data.get("system_diagnostics") in (True, "on", "1", "true")
    features["exec_enabled"] = form_data.get("exec_enabled") in (True, "on", "1", "true")

    if "timezone" in form_data:
        tz = str(form_data["timezone"]).strip()
        if tz:
            data["timezone"] = tz

    _save_settings_yaml(settings_yaml, data)

    if app_state is not None:
        app_state.reload_settings(settings_yaml)

    return {"success": True}
