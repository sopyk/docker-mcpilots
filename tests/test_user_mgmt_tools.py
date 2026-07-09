"""API Key 管理工具函数测试"""
from __future__ import annotations

import pytest
import yaml
from pathlib import Path

from tools.user_mgmt_tools import (
    generate_api_key,
    list_api_keys,
    create_api_key,
    update_api_key,
    delete_api_key,
    batch_delete_api_keys,
)


@pytest.fixture
def seed_auth(tmp_path):
    def _write(extra_keys=None):
        path = tmp_path / "auth.yaml"
        data = {
            "roles": {
                "admin": {"description": "admin", "permissions": ["*"]},
                "observer": {"description": "observer", "permissions": ["container:list"]},
            },
            "keys": [
                {
                    "key": "sk-dm-oldkey1234567890123456789012",
                    "name": "old",
                    "role": "admin",
                }
            ],
        }
        if extra_keys:
            data["keys"].extend(extra_keys)
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return str(path)
    return _write


class TestGenerateApiKey:
    def test_generates_correct_format(self):
        key = generate_api_key()
        assert key.startswith("sk-dm-")
        assert len(key) == len("sk-dm-") + 32


class TestListApiKeys:
    def test_lists_existing_keys(self, seed_auth):
        path = seed_auth()
        keys = list_api_keys(path)
        assert len(keys) == 1
        assert keys[0]["name"] == "old"
        assert keys[0]["role"] == "admin"
        assert keys[0]["key_masked"].startswith("sk-d")


class TestCreateApiKey:
    def test_create_with_auto_generated_key(self, seed_auth):
        path = seed_auth()
        result = create_api_key(path, name="new", role="observer")
        assert result["success"] is True
        assert result["name"] == "new"
        assert result["key"].startswith("sk-dm-")

        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        names = [k["name"] for k in data["keys"]]
        assert "new" in names

    def test_create_with_custom_key(self, seed_auth):
        path = seed_auth()
        custom = "sk-dm-" + "a" * 32
        result = create_api_key(path, name="custom", role="admin", key=custom)
        assert result["success"] is True
        assert result["key"] == custom

    def test_create_duplicate_name_fails(self, seed_auth):
        path = seed_auth()
        result = create_api_key(path, name="old", role="admin")
        assert result["success"] is False
        assert "已存在" in result["error"]

    def test_create_with_invalid_key_format_fails(self, seed_auth):
        path = seed_auth()
        result = create_api_key(path, name="bad", role="admin", key="not-valid")
        assert result["success"] is False

    def test_create_with_scope(self, seed_auth):
        path = seed_auth()
        result = create_api_key(
            path, name="scoped", role="observer",
            scope_include="home-*,plex", scope_exclude="home-db",
        )
        assert result["success"] is True
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        scoped = next(k for k in data["keys"] if k["name"] == "scoped")
        assert scoped["scope"]["containers"]["include"] == ["home-*", "plex"]
        assert scoped["scope"]["containers"]["exclude"] == ["home-db"]


class TestUpdateApiKey:
    def test_update_role(self, seed_auth):
        path = seed_auth()
        result = update_api_key(path, name="old", role="observer")
        assert result["success"] is True
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        old = next(k for k in data["keys"] if k["name"] == "old")
        assert old["role"] == "observer"

    def test_update_key(self, seed_auth):
        path = seed_auth()
        new_key = "sk-dm-" + "b" * 32
        result = update_api_key(path, name="old", key=new_key)
        assert result["success"] is True
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        old = next(k for k in data["keys"] if k["name"] == "old")
        assert old["key"] == new_key

    def test_update_not_found(self, seed_auth):
        path = seed_auth()
        result = update_api_key(path, name="missing", role="admin")
        assert result["success"] is False

    def test_update_removes_scope(self, seed_auth):
        path = seed_auth([
            {
                "key": "sk-dm-" + "c" * 32,
                "name": "scoped",
                "role": "observer",
                "scope": {"containers": {"include": ["home-*"]}},
            }
        ])
        result = update_api_key(path, name="scoped", scope_include="", scope_exclude="")
        assert result["success"] is True
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        scoped = next(k for k in data["keys"] if k["name"] == "scoped")
        assert "scope" not in scoped


class TestDeleteApiKey:
    def test_delete_existing(self, seed_auth):
        path = seed_auth()
        result = delete_api_key(path, name="old")
        assert result["success"] is True
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert all(k["name"] != "old" for k in data["keys"])

    def test_delete_not_found(self, seed_auth):
        path = seed_auth()
        result = delete_api_key(path, name="missing")
        assert result["success"] is False


class TestBatchDeleteApiKeys:
    def test_batch_delete_multiple(self, seed_auth):
        path = seed_auth(extra_keys=[
            {"key": "sk-dm-key000000000000000000000a", "name": "a", "role": "admin"},
            {"key": "sk-dm-key000000000000000000000b", "name": "b", "role": "admin"},
            {"key": "sk-dm-key000000000000000000000c", "name": "c", "role": "admin"},
        ])
        result = batch_delete_api_keys(path, names=["a", "c"])
        assert result["success"] is True
        assert set(result["removed"]) == {"a", "c"}
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        remaining = {k["name"] for k in data["keys"]}
        assert remaining == {"old", "b"}

    def test_batch_delete_with_missing(self, seed_auth):
        path = seed_auth(extra_keys=[
            {"key": "sk-dm-key000000000000000000000a", "name": "a", "role": "admin"},
        ])
        result = batch_delete_api_keys(path, names=["a", "ghost"])
        assert result["success"] is True
        assert result["removed"] == ["a"]
        assert "ghost" in result["missing"]

    def test_batch_delete_none_found(self, seed_auth):
        path = seed_auth()
        result = batch_delete_api_keys(path, names=["ghost1", "ghost2"])
        assert result["success"] is False

    def test_batch_delete_empty(self, seed_auth):
        path = seed_auth()
        result = batch_delete_api_keys(path, names=[])
        assert result["success"] is False

    def test_batch_delete_reloads_app_state(self, seed_auth):
        path = seed_auth(extra_keys=[
            {"key": "sk-dm-key000000000000000000000a", "name": "a", "role": "admin"},
        ])
        calls = []
        app_state = type("S", (), {"reload_auth": lambda self, p=None: calls.append(p)})()
        result = batch_delete_api_keys(path, names=["a"], app_state=app_state)
        assert result["success"] is True
        assert len(calls) == 1
