"""API Key 管理工具函数

提供对 auth.yaml 中 API Key 的增删改查，并支持热加载到 AppState。
"""
from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

import yaml


def _load_auth_yaml(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise ValueError(f"Auth config file not found: {path}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid auth config format: {path}")
    return data


def _save_auth_yaml(path: str, data: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    try:
        import os

        os.chmod(p, 0o600)
    except OSError:
        pass


def _normalize_scope(scope_include: str = "", scope_exclude: str = "") -> dict[str, Any] | None:
    include = [s.strip() for s in scope_include.split(",") if s.strip()]
    exclude = [s.strip() for s in scope_exclude.split(",") if s.strip()]
    if not include and not exclude:
        return None
    scope: dict[str, Any] = {"containers": {}}
    if include:
        scope["containers"]["include"] = include
    if exclude:
        scope["containers"]["exclude"] = exclude
    return scope


def generate_api_key() -> str:
    """按照项目格式生成随机 API Key: sk-dm-<32位十六进制>"""
    return "sk-dm-" + secrets.token_hex(16)


def list_api_keys(auth_yaml: str) -> list[dict[str, Any]]:
    """读取 auth.yaml 中所有 API Key 信息（对 key 做掩码处理）"""
    data = _load_auth_yaml(auth_yaml)
    keys = data.get("keys", [])
    result = []
    for k in keys:
        key_value = k.get("key", "")
        masked = (key_value[:4] + "*" * 8) if len(key_value) > 4 else "****"
        scope = k.get("scope")
        scope_info = "全部"
        if scope and isinstance(scope, dict):
            parts = []
            containers = scope.get("containers", {})
            if containers.get("include"):
                parts.append("include: " + ",".join(containers["include"]))
            if containers.get("exclude"):
                parts.append("exclude: " + ",".join(containers["exclude"]))
            scope_info = "; ".join(parts) if parts else "全部"
        result.append({
            "name": k.get("name", ""),
            "role": k.get("role", ""),
            "key": key_value,
            "key_masked": masked,
            "scope": scope_info,
            "scope_include": ",".join(scope.get("containers", {}).get("include", [])) if scope else "",
            "scope_exclude": ",".join(scope.get("containers", {}).get("exclude", [])) if scope else "",
        })
    return result


def create_api_key(
    auth_yaml: str,
    name: str,
    role: str,
    key: str = "",
    scope_include: str = "",
    scope_exclude: str = "",
    app_state=None,
) -> dict[str, Any]:
    """创建新的 API Key。若未提供 key，则自动生成。"""
    if not name or not role:
        return {"success": False, "error": "名称和角色不能为空"}

    data = _load_auth_yaml(auth_yaml)
    keys = data.setdefault("keys", [])

    if any(k.get("name") == name for k in keys):
        return {"success": False, "error": f"已存在名为 '{name}' 的 API Key"}

    new_key = key.strip() if key.strip() else generate_api_key()
    if not new_key.startswith("sk-dm-"):
        return {"success": False, "error": "API Key 格式应为 sk-dm-<随机字符串>"}

    entry: dict[str, Any] = {
        "key": new_key,
        "name": name,
        "role": role,
    }
    scope = _normalize_scope(scope_include, scope_exclude)
    if scope:
        entry["scope"] = scope

    keys.append(entry)
    _save_auth_yaml(auth_yaml, data)

    if app_state is not None:
        app_state.reload_auth(auth_yaml)

    return {"success": True, "key": new_key, "name": name}


def update_api_key(
    auth_yaml: str,
    name: str,
    role: str | None = None,
    key: str | None = None,
    scope_include: str = "",
    scope_exclude: str = "",
    new_name: str | None = None,
    app_state=None,
) -> dict[str, Any]:
    """更新现有 API Key。name 用于定位，new_name 非空则重命名。"""
    if not name:
        return {"success": False, "error": "名称不能为空"}

    data = _load_auth_yaml(auth_yaml)
    keys = data.get("keys", [])

    target = None
    for k in keys:
        if k.get("name") == name:
            target = k
            break

    if target is None:
        return {"success": False, "error": f"未找到名为 '{name}' 的 API Key"}

    final_name = name
    if new_name is not None:
        nn = new_name.strip()
        if not nn:
            return {"success": False, "error": "名称不能为空"}
        if nn != name and any(k.get("name") == nn for k in keys):
            return {"success": False, "error": f"已存在名为 '{nn}' 的 API Key"}
        target["name"] = nn
        final_name = nn

    if role is not None:
        target["role"] = role

    if key is not None:
        new_key = key.strip()
        if new_key and not new_key.startswith("sk-dm-"):
            return {"success": False, "error": "API Key 格式应为 sk-dm-<随机字符串>"}
        if new_key:
            target["key"] = new_key

    scope = _normalize_scope(scope_include, scope_exclude)
    if scope:
        target["scope"] = scope
    else:
        target.pop("scope", None)

    _save_auth_yaml(auth_yaml, data)

    if app_state is not None:
        app_state.reload_auth(auth_yaml)

    return {"success": True, "name": final_name, "renamed": final_name != name}


def delete_api_key(auth_yaml: str, name: str, app_state=None) -> dict[str, Any]:
    """删除指定名称的 API Key。"""
    if not name:
        return {"success": False, "error": "名称不能为空"}

    data = _load_auth_yaml(auth_yaml)
    keys = data.get("keys", [])
    before = len(keys)
    data["keys"] = [k for k in keys if k.get("name") != name]

    if len(data["keys"]) == before:
        return {"success": False, "error": f"未找到名为 '{name}' 的 API Key"}

    _save_auth_yaml(auth_yaml, data)

    if app_state is not None:
        app_state.reload_auth(auth_yaml)

    return {"success": True, "removed": name}
