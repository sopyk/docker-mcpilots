"""Web 路由与模板测试"""
from __future__ import annotations
from unittest.mock import MagicMock
from web.routes import env, register_web_routes


def test_containers_template_empty():
    """空容器列表渲染"""
    html = env.get_template("containers.html").render(
        user="admin", containers=[], csrf_token="tok", error=""
    )
    assert "暂无容器" in html


def test_containers_template_with_data():
    """有容器渲染状态徽章和操作按钮"""
    containers = [
        {"id": "abc123", "name": "web", "image": "nginx:latest", "status": "Up 2 hours"},
        {"id": "def456", "name": "db", "image": "postgres:15", "status": "Exited (0) 3 hours ago"},
    ]
    html = env.get_template("containers.html").render(
        user="admin", containers=containers, csrf_token="tok", error=""
    )
    assert "web" in html
    assert "nginx:latest" in html
    assert "badge-green" in html
    assert "badge-gray" in html
    assert "/ui/containers/abc123/start" in html
    assert "/ui/containers/def456/stop" in html
    assert "/ui/containers/abc123/restart" in html


def test_container_detail_template_success():
    """容器详情成功渲染"""
    detail = {
        "success": True,
        "id": "abc123",
        "name": "web",
        "status": "Up 2 hours",
        "image": "nginx:latest",
        "created": "2026-07-01T00:00:00Z",
        "state": {
            "running": True, "pid": 1234, "exit_code": 0,
            "restart_count": 1, "oom_killed": False,
            "started_at": "2026-07-01T00:00:00Z", "finished_at": "",
        },
        "network": {"ip_address": "172.17.0.2", "gateway": "172.17.0.1", "mac_address": "02:42:ac:11:00:02"},
        "mounts": [
            {"type": "bind", "source": "/data", "destination": "/var/lib/mysql", "rw": True}
        ],
    }
    html = env.get_template("container_detail.html").render(
        user="admin", container_id="abc123", detail=detail,
        logs="hello world", csrf_token="tok"
    )
    assert "web" in html
    assert "172.17.0.2" in html
    assert "/var/lib/mysql" in html
    assert "hello world" in html


def test_container_detail_template_failure():
    """容器详情失败渲染错误信息"""
    detail = {"success": False, "error": "Container not found"}
    html = env.get_template("container_detail.html").render(
        user="admin", container_id="xxx", detail=detail,
        logs="", csrf_token="tok"
    )
    assert "Container not found" in html


def test_register_web_routes_registers_all():
    """验证所有 Web 路由被注册（含容器管理路由）"""
    registered = []

    class MockMCP:
        def custom_route(self, path, methods=None):
            def decorator(func):
                registered.append((path, tuple(methods) if methods else ()))
                return func
            return decorator

    app_state = MagicMock()
    app_state.docker_client = None
    app_state.audit_logger = None
    admin_auth = MagicMock()
    session_mgr = MagicMock()
    session_mgr.validate_token.return_value = None
    csrf = MagicMock()
    csrf.generate_token.return_value = "tok"

    register_web_routes(MockMCP(), app_state, admin_auth, session_mgr, csrf)

    paths = {p for p, _ in registered}
    expected = {
        "/ui/login", "/ui/logout", "/ui/", "/ui/containers",
        "/ui/containers/{container_id}/start",
        "/ui/containers/{container_id}/stop",
        "/ui/containers/{container_id}/restart",
        "/ui/containers/{container_id}",
        "/ui/static/{filename}",
    }
    assert expected.issubset(paths), f"缺失路由: {expected - paths}"


def test_container_action_routes_are_post():
    """容器操作路由必须是 POST"""
    registered = []

    class MockMCP:
        def custom_route(self, path, methods=None):
            def decorator(func):
                registered.append((path, tuple(methods) if methods else ()))
                return func
            return decorator

    app_state = MagicMock()
    app_state.docker_client = None
    app_state.audit_logger = None
    session_mgr = MagicMock()
    session_mgr.validate_token.return_value = None
    csrf = MagicMock()

    register_web_routes(MockMCP(), app_state, MagicMock(), session_mgr, csrf)

    for path, methods in registered:
        if path.endswith("/start") or path.endswith("/stop") or path.endswith("/restart"):
            assert methods == ("POST",), f"{path} 应为 POST，实际 {methods}"


def test_users_template_with_data():
    """用户权限模板渲染 API Key 列表、角色、热加载按钮"""
    keys = [
        {"name": "admin-key", "role": "admin", "key": "sk-dm-a1234567890123456789012345678", "key_masked": "sk-d********", "scope": "全部", "scope_include": "", "scope_exclude": ""},
        {"name": "ci-key", "role": "operator", "key": "sk-dm-b1234567890123456789012345678", "key_masked": "sk-d********", "scope": "include: web,db", "scope_include": "web,db", "scope_exclude": ""},
    ]
    roles = [
        {"name": "admin", "description": "管理员", "permissions": ["*"]},
        {"name": "operator", "description": "操作员", "permissions": ["container:*", "image:list"]},
    ]
    html = env.get_template("users.html").render(
        user="admin", keys=keys, roles=roles, csrf_token="tok", error="", success=""
    )
    assert "admin-key" in html
    assert "sk-dm-a1234567890123456789012345678" in html
    assert "管理员" in html
    assert "container:*" in html
    assert "/ui/users/reload" in html
    assert "/ui/users/create" in html
    assert "热加载" in html


def test_users_template_empty():
    """空用户列表渲染"""
    html = env.get_template("users.html").render(
        user="admin", keys=[], roles=[], csrf_token="tok", error="", success=""
    )
    assert "暂无 API Key" in html
    assert "暂无角色" in html


def test_users_template_alert_messages():
    """成功/错误提示渲染"""
    html = env.get_template("users.html").render(
        user="admin", keys=[], roles=[], csrf_token="tok",
        error="加载失败", success="热加载成功",
    )
    assert "alert-error" in html
    assert "加载失败" in html
    assert "alert-success" in html
    assert "热加载成功" in html


def test_users_routes_registered():
    """验证用户管理路由被注册"""
    registered = []

    class MockMCP:
        def custom_route(self, path, methods=None):
            def decorator(func):
                registered.append(path)
                return func
            return decorator

    app_state = MagicMock()
    app_state.docker_client = None
    app_state.audit_logger = None
    session_mgr = MagicMock()
    session_mgr.validate_token.return_value = None
    csrf = MagicMock()

    register_web_routes(MockMCP(), app_state, MagicMock(), session_mgr, csrf)

    assert "/ui/users" in registered
    assert "/ui/users/reload" in registered
    assert "/ui/users/create" in registered
    assert "/ui/users/{name}/update" in registered
    assert "/ui/users/{name}/delete" in registered


def test_audit_template_with_data():
    """审计日志模板渲染日志条目"""
    from core.audit import AuditEntry
    logs = [
        AuditEntry(timestamp="2026-07-05T10:00:00Z", source="web", actor="admin",
                   action="container.start", target="abc123", detail={}, success=True),
        AuditEntry(timestamp="2026-07-05T10:01:00Z", source="mcp", actor="ci-key",
                   action="tools.call", target="list_containers", detail={}, success=False),
    ]
    html = env.get_template("audit.html").render(
        user="admin", logs=logs, csrf_token="tok",
        filter_source="", filter_actor="", filter_limit=100,
    )
    assert "container.start" in html
    assert "list_containers" in html
    assert "badge-green" in html
    assert "badge-red" in html
    assert "admin" in html
    assert "ci-key" in html


def test_audit_template_empty():
    """空审计日志渲染"""
    html = env.get_template("audit.html").render(
        user="admin", logs=[], csrf_token="tok",
        filter_source="", filter_actor="", filter_limit=100,
    )
    assert "暂无记录" in html


def test_audit_template_filter_form():
    """筛选表单保留筛选条件"""
    html = env.get_template("audit.html").render(
        user="admin", logs=[], csrf_token="tok",
        filter_source="mcp", filter_actor="ci-key", filter_limit=50,
    )
    assert 'value="mcp"' in html or 'value="mcp"' in html
    assert 'value="ci-key"' in html
    assert 'value="50"' in html


def test_audit_route_registered():
    """验证审计日志路由被注册"""
    registered = []

    class MockMCP:
        def custom_route(self, path, methods=None):
            def decorator(func):
                registered.append(path)
                return func
            return decorator

    app_state = MagicMock()
    app_state.docker_client = None
    app_state.audit_logger = None
    session_mgr = MagicMock()
    session_mgr.validate_token.return_value = None
    csrf = MagicMock()

    register_web_routes(MockMCP(), app_state, MagicMock(), session_mgr, csrf)

    assert "/ui/audit" in registered


def test_settings_template_with_data():
    """配置页面模板渲染当前配置和热加载按钮"""
    from core.config import Settings
    settings = Settings(
        host="0.0.0.0", port=8900, log_level="info",
        socket_path="/var/run/docker.sock",
        container_management=True, image_management=True,
        system_diagnostics=False, timezone="Asia/Shanghai",
    )
    html = env.get_template("settings.html").render(
        user="admin", settings=settings, raw_yaml="server:\n  host: 0.0.0.0",
        csrf_token="tok", error="", success="",
    )
    assert "0.0.0.0" in html
    assert "8900" in html
    assert "/ui/settings/reload" in html
    assert "/ui/settings/save" in html
    assert "timezone" in html
    assert "toggle-slider" in html
    assert "热加载" in html


def test_settings_template_raw_yaml():
    """配置页面显示 yaml 原始内容"""
    from core.config import Settings
    html = env.get_template("settings.html").render(
        user="admin", settings=Settings(),
        raw_yaml="# my config\nserver:\n  port: 8900",
        csrf_token="tok", error="", success="",
    )
    assert "# my config" in html
    assert "port: 8900" in html


def test_settings_routes_registered():
    """验证配置路由被注册"""
    registered = []

    class MockMCP:
        def custom_route(self, path, methods=None):
            def decorator(func):
                registered.append(path)
                return func
            return decorator

    app_state = MagicMock()
    app_state.docker_client = None
    app_state.audit_logger = None
    session_mgr = MagicMock()
    session_mgr.validate_token.return_value = None
    csrf = MagicMock()

    register_web_routes(MockMCP(), app_state, MagicMock(), session_mgr, csrf)

    assert "/ui/settings" in registered
    assert "/ui/settings/reload" in registered
    assert "/ui/settings/save" in registered
