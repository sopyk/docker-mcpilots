"""E2E Web UI 测试 - 完整 HTTP 流程验证

测试覆盖：
- 登录页 GET → 200 + CSRF cookie
- 登录 POST（正确/错误密码/CSRF 失败）
- 未登录访问受保护页面 → 303 重定向到登录页
- 登录后访问仪表盘/容器/用户/审计/配置页面 → 200
- 容器详情页 → 200
- 静态资源 → 200 / 404
- 按钮操作：用户热加载/配置热加载/容器启停 → 303
- 登出 → 303 + 登出后重定向
"""
from __future__ import annotations
import sys
import unittest.mock

if "fastmcp" in sys.modules:
    _mod = sys.modules["fastmcp"]
    if isinstance(_mod, unittest.mock.MagicMock) or "mock" in type(_mod).__module__:
        for _m in list(sys.modules):
            if _m == "fastmcp" or _m.startswith("fastmcp."):
                del sys.modules[_m]

import pytest
from starlette.testclient import TestClient

import main
from core.admin_auth import AdminAuth
from core.version import VERSION
from core.config import AuthConfig


@pytest.fixture()
def web_client(tmp_path, monkeypatch):
    """创建带临时配置的 Web UI 测试客户端（Docker 不可用时优雅降级）"""
    config_dir = tmp_path / "config"
    secrets_dir = tmp_path / "secrets"
    config_dir.mkdir()
    secrets_dir.mkdir()

    import main
    monkeypatch.setattr(main, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(main, "SECRETS_DIR", secrets_dir)

    mcp = main.create_app()

    admin_yaml = secrets_dir / "admin.yaml"
    auth = AdminAuth(admin_yaml=str(admin_yaml), session_secret="change-me")
    auth.set_password("admin", "demo123")

    return TestClient(mcp.http_app(), follow_redirects=False)


def _login(client: TestClient, username: str = "admin", password: str = "demo123"):
    """辅助：完成登录流程，返回登录 POST 响应"""
    client.get("/ui/login")
    csrf_token = client.cookies.get("csrf_token")
    return client.post("/ui/login", data={
        "username": username,
        "password": password,
        "csrf_token": csrf_token,
    })


class TestLoginPage:
    """登录页测试"""

    def test_get_login_page(self, web_client):
        """GET /ui/login → 200 + CSRF cookie + HTML"""
        r = web_client.get("/ui/login")
        assert r.status_code == 200
        assert "csrf_token" in web_client.cookies
        assert "<html" in r.text.lower()

    def test_already_logged_in_redirects(self, web_client):
        """已登录时访问登录页 → 303 重定向到仪表盘"""
        _login(web_client)
        r = web_client.get("/ui/login")
        assert r.status_code == 303
        assert r.headers["location"] == "/ui/"

    def test_login_success(self, web_client):
        """正确密码 → 303 重定向到 /ui/"""
        r = _login(web_client)
        assert r.status_code == 303
        assert r.headers["location"] == "/ui/"

    def test_login_wrong_password(self, web_client):
        """错误密码 → 200 + 错误提示"""
        web_client.get("/ui/login")
        csrf = web_client.cookies.get("csrf_token")
        r = web_client.post("/ui/login", data={
            "username": "admin", "password": "wrong", "csrf_token": csrf,
        })
        assert r.status_code == 200
        assert "错误" in r.text

    def test_login_bad_csrf(self, web_client):
        """CSRF token 无效 → 200 + CSRF 错误提示"""
        r = web_client.post("/ui/login", data={
            "username": "admin", "password": "demo123", "csrf_token": "bad",
        })
        assert r.status_code == 200
        assert "CSRF" in r.text


class TestUnauthenticatedRedirect:
    """未登录访问受保护页面 → 303 重定向到 /ui/login"""

    @pytest.mark.parametrize("path", [
        "/ui/",
        "/ui/containers",
        "/ui/users",
        "/ui/audit",
        "/ui/settings",
    ])
    def test_redirect_to_login(self, web_client, path):
        r = web_client.get(path)
        assert r.status_code == 303
        assert r.headers["location"] == "/ui/login"


class TestAuthenticatedPages:
    """登录后各页面返回 200"""

    @pytest.fixture(autouse=True)
    def _login(self, web_client):
        _login(web_client)

    @pytest.mark.parametrize("path", [
        "/ui/",
        "/ui/containers",
        "/ui/users",
        "/ui/audit",
        "/ui/settings",
    ])
    def test_page_returns_200(self, web_client, path):
        r = web_client.get(path)
        assert r.status_code == 200, f"{path} → {r.status_code}"
        assert "<html" in r.text.lower()

    def test_container_detail_page(self, web_client):
        """容器详情页（Docker 不可用时也能渲染错误信息）"""
        r = web_client.get("/ui/containers/abc12345")
        assert r.status_code == 200

    def test_dashboard_has_ring_progress(self, web_client):
        """仪表盘 CPU/内存用 SVG 环形进度图渲染"""
        r = web_client.get("/ui/")
        assert r.status_code == 200
        assert "<svg" in r.text, "仪表盘缺少 SVG 环形图"
        assert "ring-fg" in r.text, "缺少环形进度圆环"
        assert "ring-bg" in r.text, "缺少环形背景圆"
        assert "CPU" in r.text
        assert "内存" in r.text
        assert "stroke-dasharray" in r.text, "环形图缺少进度参数"

    def test_dashboard_ring_color_levels(self, web_client):
        """环形颜色按占用率分级（low/mid/high class 存在）"""
        r = web_client.get("/ui/")
        assert r.status_code == 200
        has_level = ("ring-low" in r.text or "ring-mid" in r.text or "ring-high" in r.text)
        assert has_level, "环形图缺少颜色分级 class"

    def test_nav_links_enlarged(self, web_client):
        """导航栏子页面链接字体放大（CSS 中 15px）"""
        r = web_client.get("/ui/static/style.css")
        assert r.status_code == 200
        css = r.text
        assert "font-size: 15px" in css, "导航链接字体未放大到 15px"
        assert "border-bottom" in css, "导航链接缺少 hover 下划线"

    def test_static_css(self, web_client):
        """静态 CSS 文件可访问"""
        r = web_client.get("/ui/static/style.css")
        assert r.status_code == 200
        assert "text/css" in r.headers.get("content-type", "")

    def test_static_not_found(self, web_client):
        """不存在的静态文件 → 404"""
        r = web_client.get("/ui/static/nonexistent.css")
        assert r.status_code == 404

    def test_static_clipboard_js(self, web_client):
        """剪贴板工具脚本可访问（关于页/用户页复制依赖它）"""
        r = web_client.get("/ui/static/clipboard.js")
        assert r.status_code == 200
        assert "javascript" in r.headers.get("content-type", "")
        assert "copyToClipboard" in r.text

    def test_static_path_traversal_blocked(self, web_client):
        """静态路由不得越出 static 目录（防任意文件读取）"""
        r = web_client.get("/ui/static/%2e%2e/templates/base.html")
        assert r.status_code == 404
        assert "app_version" not in r.text

    def test_static_nested_asset_served(self, web_client):
        """正对照：`{path:path}` 子目录仍能正常提供文件（防止守卫把功能一起禁掉）"""
        r = web_client.get("/ui/static/assets/logo.jpg")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/")
        assert len(r.content) > 0

    def test_static_traversal_to_existing_file_blocked(self, web_client):
        """越界指向真实存在的仓库文件（main.py）时必须 404，且不泄露其内容"""
        r = web_client.get("/ui/static/..%2fmain.py")
        assert r.status_code == 404
        assert r.text == "Not Found", "守卫应直接返回 404，而不是回落到文件内容"
        assert "FastMCP" not in r.text and "VERSION" not in r.text


class TestAboutPage:
    """关于页版本号（单一数据源）"""

    def test_about_page_shows_version(self, web_client):
        r = web_client.get("/ui/about")
        assert r.status_code == 200
        assert f"v{VERSION}" in r.text, "关于页未显示当前版本号"

    def test_health_reports_version(self, web_client):
        r = web_client.get("/health")
        assert r.status_code == 200
        assert r.json()["version"] == VERSION


class TestInitialApiKeys:
    """INITIAL_API_KEYS 幂等初始化"""

    def test_initial_api_keys_updates_existing_key(self, tmp_path, monkeypatch):
        """已有同名 key 时应被 INITIAL_API_KEYS 的值覆盖，而不是静默跳过"""
        config_dir = tmp_path / "config"
        secrets_dir = tmp_path / "secrets"
        config_dir.mkdir()
        secrets_dir.mkdir()

        monkeypatch.setattr(main, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(main, "SECRETS_DIR", secrets_dir)
        monkeypatch.setenv("INITIAL_API_KEYS", "default-admin:sk-dm-rc-999:admin")
        main.create_app()

        auth_yaml = secrets_dir / "auth.yaml"
        auth_cfg = AuthConfig.from_yaml(str(auth_yaml))

        # 新 key 已生效
        assert auth_cfg.find_key("sk-dm-rc-999") is not None
        # 旧 key 已被覆盖
        assert auth_cfg.find_key("sk-dm-CHANGE-THIS-KEY-IMMEDIATELY") is None


class TestButtonActions:
    """按钮操作测试（POST → 303 重定向）"""

    @pytest.fixture(autouse=True)
    def _login(self, web_client):
        _login(web_client)

    @staticmethod
    def _get_csrf(web_client, page_path):
        """访问页面获取最新的 CSRF token"""
        web_client.get(page_path)
        return web_client.cookies.get("csrf_token")

    def test_users_reload(self, web_client):
        """用户管理 → 热加载按钮 → 303"""
        csrf = self._get_csrf(web_client, "/ui/users")
        r = web_client.post("/ui/users/reload", data={"csrf_token": csrf})
        assert r.status_code == 303

    def test_settings_reload(self, web_client):
        """配置页面 → 热加载按钮 → 303"""
        csrf = self._get_csrf(web_client, "/ui/settings")
        r = web_client.post("/ui/settings/reload", data={"csrf_token": csrf})
        assert r.status_code == 303

    def test_container_start(self, web_client):
        """容器 → 启动按钮（Docker 不可用也返回 303）"""
        csrf = self._get_csrf(web_client, "/ui/containers")
        r = web_client.post("/ui/containers/abc12345/start", data={"csrf_token": csrf})
        assert r.status_code == 303

    def test_container_stop(self, web_client):
        """容器 → 停止按钮"""
        csrf = self._get_csrf(web_client, "/ui/containers")
        r = web_client.post("/ui/containers/abc12345/stop", data={"csrf_token": csrf})
        assert r.status_code == 303

    def test_container_restart(self, web_client):
        """容器 → 重启按钮"""
        csrf = self._get_csrf(web_client, "/ui/containers")
        r = web_client.post("/ui/containers/abc12345/restart", data={"csrf_token": csrf})
        assert r.status_code == 303

    def test_container_action_bad_csrf(self, web_client):
        """容器操作 CSRF 失效 → 303 重定向回容器列表"""
        r = web_client.post("/ui/containers/abc12345/start", data={"csrf_token": "bad"})
        assert r.status_code == 303
        assert r.headers["location"] == "/ui/containers"


class TestLogout:
    """登出测试"""

    def test_logout(self, web_client):
        """登出 → 303 重定向到登录页"""
        _login(web_client)
        r = web_client.get("/ui/logout")
        assert r.status_code == 303
        assert r.headers["location"] == "/ui/login"

    def test_access_after_logout_redirects(self, web_client):
        """登出后访问受保护页面 → 303 重定向到登录页"""
        _login(web_client)
        web_client.get("/ui/logout")
        r = web_client.get("/ui/")
        assert r.status_code == 303
        assert r.headers["location"] == "/ui/login"
