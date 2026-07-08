"""Web UI 路由注册"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote, unquote
from jinja2 import Environment, FileSystemLoader
from fastmcp import FastMCP
from starlette.responses import Response, RedirectResponse
from core.app_state import AppState
from core.admin_auth import AdminAuth, SessionManager
from core.csrf import CSRFProtection
from core.audit import AuditEntry
from tools.user_mgmt_tools import list_api_keys, create_api_key, update_api_key, delete_api_key
from tools.settings_tools import update_settings_from_form, change_admin_password
from core.admin_auth import AdminConfig


# 路径配置
TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
env.filters["urlencode"] = quote
env.filters["tz"] = lambda s, tz: _convert_to_tz(s, tz)


def _now_iso() -> str:
    """当前 UTC 时间的 ISO 格式字符串（带 Z 后缀）"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _convert_to_tz(utc_str: str, timezone_str: str = "Asia/Shanghai") -> str:
    """把 UTC ISO 时间转换为指定时区的本地化时间字符串"""
    try:
        # 解析带 Z 或带偏移的 UTC 时间
        if utc_str.endswith("Z"):
            dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(utc_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        tz = ZoneInfo(timezone_str)
        local_dt = dt.astimezone(tz)
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return utc_str


def _human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _format_images_for_web(images: list[dict]) -> list[dict]:
    result = []
    for img in images:
        tags = img.get("tags") or []
        if not tags:
            result.append({
                "repository": "<none>",
                "tag": "<none>",
                "size_human": _human_size(img.get("size", 0)),
                "created_human": img.get("created", "")[:10] if img.get("created") else "",
                "id": img.get("id", ""),
            })
        else:
            for tag in tags:
                if ":" in tag:
                    repo, tag_name = tag.rsplit(":", 1)
                else:
                    repo, tag_name = tag, "latest"
                result.append({
                    "repository": repo,
                    "tag": tag_name,
                    "size_human": _human_size(img.get("size", 0)),
                    "created_human": img.get("created", "")[:10] if img.get("created") else "",
                    "id": img.get("id", ""),
                })
    return result


def register_web_routes(
    mcp: FastMCP,
    app_state: AppState,
    admin_auth: AdminAuth,
    session_mgr: SessionManager,
    csrf: CSRFProtection,
) -> None:
    """注册所有 Web UI 路由"""

    def require_login(request: Any) -> Optional[str]:
        """鉴权检查，返回 username 或 None（未登录）"""
        token = request.cookies.get("session")
        if not token:
            return None
        return session_mgr.validate_token(token)

    # 登录页 GET
    @mcp.custom_route("/ui/login", methods=["GET"])
    async def login_page_get(request):
        user = require_login(request)
        if user:
            return RedirectResponse("/ui/", status_code=303)
        token = csrf.generate_token()
        success_msg = unquote(request.query_params.get("success", ""))
        html = env.get_template("login.html").render(
            csrf_token=token, error="", success=success_msg,
        )
        resp = Response(html, media_type="text/html")
        resp.set_cookie("csrf_token", token, httponly=True, samesite="strict")
        return resp

    # 登录页 POST
    @mcp.custom_route("/ui/login", methods=["POST"])
    async def login_page_post(request):
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")
        csrf_token = form.get("csrf_token", "")
        if not csrf.validate_token(csrf_token):
            token2 = csrf.generate_token()
            html = env.get_template("login.html").render(
                csrf_token=token2, error="CSRF 校验失败"
            )
            resp = Response(html, media_type="text/html")
            resp.set_cookie("csrf_token", token2, httponly=True, samesite="strict")
            return resp
        if admin_auth.verify(username, password):
            token3 = session_mgr.create_token(username)
            resp = RedirectResponse("/ui/", status_code=303)
            resp.set_cookie("session", token3, httponly=True, samesite="strict")
            if app_state.audit_logger:
                app_state.audit_logger.log(AuditEntry(
                    timestamp=_now_iso(),
                    source="web",
                    actor=username,
                    action="auth.login",
                    target="",
                    detail={},
                    success=True
                ))
            return resp
        token4 = csrf.generate_token()
        html = env.get_template("login.html").render(
            csrf_token=token4, error="用户名或密码错误"
        )
        resp = Response(html, media_type="text/html")
        resp.set_cookie("csrf_token", token4, httponly=True, samesite="strict")
        return resp

    # 根路径重定向到 Web UI
    @mcp.custom_route("/", methods=["GET"])
    async def root_redirect(request):
        return RedirectResponse("/ui/", status_code=303)

    # 登出
    @mcp.custom_route("/ui/logout", methods=["GET"])
    async def logout_page(request):
        resp = RedirectResponse("/ui/login", status_code=303)
        resp.delete_cookie("session")
        return resp

    # 仪表盘
    @mcp.custom_route("/ui/", methods=["GET"])
    async def dashboard_page(request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/ui/login", status_code=303)
        docker = app_state.docker_client
        sysdiag = app_state.system_diag
        containers = docker.list_containers(all=True) if docker else []
        running = [c for c in containers if c.get("status", "").startswith("Up")]
        images = docker.list_images() if docker else []
        cpu = sysdiag.get_cpu_info() if sysdiag else {}
        mem = sysdiag.get_memory_info() if sysdiag else {}
        disk = sysdiag.get_disk_info() if sysdiag else {}
        recent_logs = app_state.audit_logger.recent(10) if app_state.audit_logger else []
        html = env.get_template("dashboard.html").render(
            user=user,
            container_total=len(containers),
            container_running=len(running),
            image_count=len(images),
            cpu_percent=cpu.get("percent", 0),
            mem_percent=mem.get("virtual", {}).get("percent", 0),
            disk_percent=disk.get("partitions", [{}])[0].get("percent", 0) if disk.get("partitions") else 0,
            recent_logs=recent_logs,
            settings=app_state.settings,
        )
        return Response(html, media_type="text/html")

    # 关于页面（无需登录）
    @mcp.custom_route("/ui/about", methods=["GET"])
    async def about_page(request):
        token = request.cookies.get("session")
        user = session_mgr.validate_token(token) if token else None
        html = env.get_template("about.html").render(user=user)
        return Response(html, media_type="text/html")

    # ── 容器管理页面 ──

    @mcp.custom_route("/ui/containers", methods=["GET"])
    async def containers_page(request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/ui/login", status_code=303)
        docker = app_state.docker_client
        containers = docker.list_containers(all=True) if docker else []
        token = csrf.generate_token()
        html = env.get_template("containers.html").render(
            user=user, containers=containers, csrf_token=token, error=""
        )
        resp = Response(html, media_type="text/html")
        resp.set_cookie("csrf_token", token, httponly=True, samesite="strict")
        return resp

    async def _container_action(request, action_name: str, docker_method: str):
        user = require_login(request)
        if not user:
            return RedirectResponse("/ui/login", status_code=303)
        form = await request.form()
        if not csrf.validate_token(form.get("csrf_token", "")):
            return RedirectResponse("/ui/containers", status_code=303)
        container_id = request.path_params["container_id"]
        docker = app_state.docker_client
        success = False
        if docker:
            result = getattr(docker, docker_method)(container_id)
            success = result.get("success", False)
        if app_state.audit_logger:
            app_state.audit_logger.log(AuditEntry(
                timestamp=_now_iso(),
                source="web",
                actor=user,
                action=f"container.{action_name}",
                target=container_id,
                detail={},
                success=success,
            ))
        return RedirectResponse("/ui/containers", status_code=303)

    @mcp.custom_route("/ui/containers/{container_id}/start", methods=["POST"])
    async def container_start(request):
        return await _container_action(request, "start", "start_container")

    @mcp.custom_route("/ui/containers/{container_id}/stop", methods=["POST"])
    async def container_stop(request):
        return await _container_action(request, "stop", "stop_container")

    @mcp.custom_route("/ui/containers/{container_id}/restart", methods=["POST"])
    async def container_restart(request):
        return await _container_action(request, "restart", "restart_container")

    @mcp.custom_route("/ui/containers/{container_id}", methods=["GET"])
    async def container_detail_page(request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/ui/login", status_code=303)
        container_id = request.path_params["container_id"]
        docker = app_state.docker_client
        detail = docker.get_container(container_id) if docker else {"success": False, "error": "Docker 不可用"}
        logs_result = docker.get_container_logs(container_id, tail=200) if docker else {"success": False, "logs": ""}
        if logs_result.get("success"):
            logs_text = logs_result.get("logs", "")
        else:
            logs_text = logs_result.get("error", "无日志或容器不存在")
        token = csrf.generate_token()
        html = env.get_template("container_detail.html").render(
            user=user, container_id=container_id, detail=detail,
            logs=logs_text, csrf_token=token,
        )
        resp = Response(html, media_type="text/html")
        resp.set_cookie("csrf_token", token, httponly=True, samesite="strict")
        return resp

    # ── 镜像管理页面 ──

    @mcp.custom_route("/ui/images", methods=["GET"])
    async def images_page(request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/ui/login", status_code=303)
        docker = app_state.docker_client
        images_raw = docker.list_images() if docker else []
        images = _format_images_for_web(images_raw)
        token = csrf.generate_token()
        html = env.get_template("images.html").render(
            user=user, images=images, csrf_token=token, error=""
        )
        resp = Response(html, media_type="text/html")
        resp.set_cookie("csrf_token", token, httponly=True, samesite="strict")
        return resp

    # ── 用户权限管理页面 ──

    @mcp.custom_route("/ui/users", methods=["GET"])
    async def users_page(request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/ui/login", status_code=303)
        auth_yaml = app_state.auth_yaml_path or str(Path("dev-secrets") / "auth.yaml")
        keys_view = list_api_keys(auth_yaml)
        roles_view = [
            {"name": n, "description": r.description, "permissions": r.permissions}
            for n, r in app_state.auth_config.roles.items()
        ]
        token = csrf.generate_token()
        html = env.get_template("users.html").render(
            user=user, keys=keys_view, roles=roles_view, csrf_token=token,
            error=unquote(request.query_params.get("error", "")),
            success=unquote(request.query_params.get("success", "")),
        )
        resp = Response(html, media_type="text/html")
        resp.set_cookie("csrf_token", token, httponly=True, samesite="strict")
        return resp

    @mcp.custom_route("/ui/users/reload", methods=["POST"])
    async def users_reload(request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/ui/login", status_code=303)
        form = await request.form()
        if not csrf.validate_token(form.get("csrf_token", "")):
            return RedirectResponse("/ui/users?error=" + quote("CSRF校验失败"), status_code=303)
        success = True
        err_msg = ""
        try:
            app_state.reload_auth()
        except Exception as e:
            success = False
            err_msg = str(e)
        if app_state.audit_logger:
            app_state.audit_logger.log(AuditEntry(
                timestamp=_now_iso(),
                source="web",
                actor=user,
                action="auth.reload",
                target="auth.yaml",
                detail={},
                success=success,
            ))
        if success:
            return RedirectResponse("/ui/users?success=" + quote("热加载成功"), status_code=303)
        return RedirectResponse("/ui/users?error=" + quote(err_msg), status_code=303)

    @mcp.custom_route("/ui/users/create", methods=["POST"])
    async def users_create(request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/ui/login", status_code=303)
        form = await request.form()
        if not csrf.validate_token(form.get("csrf_token", "")):
            return RedirectResponse("/ui/users?error=" + quote("CSRF校验失败"), status_code=303)
        auth_yaml = app_state.auth_yaml_path or str(Path("dev-secrets") / "auth.yaml")
        result = create_api_key(
            auth_yaml=auth_yaml,
            name=form.get("name", "").strip(),
            role=form.get("role", "").strip(),
            key=form.get("key", "").strip(),
            scope_include=form.get("scope_include", ""),
            scope_exclude=form.get("scope_exclude", ""),
            app_state=app_state,
        )
        if app_state.audit_logger:
            app_state.audit_logger.log(AuditEntry(
                timestamp=_now_iso(),
                source="web",
                actor=user,
                action="user.create",
                target=form.get("name", "").strip(),
                detail=result,
                success=result.get("success", False),
            ))
        if result.get("success"):
            msg = f"创建成功: {result.get('name')}"
            if result.get("key"):
                msg += f"，Key: {result.get('key')}"
            return RedirectResponse("/ui/users?success=" + quote(msg), status_code=303)
        return RedirectResponse("/ui/users?error=" + quote(result.get("error", "创建失败")), status_code=303)

    @mcp.custom_route("/ui/users/{name}/update", methods=["POST"])
    async def users_update(request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/ui/login", status_code=303)
        form = await request.form()
        if not csrf.validate_token(form.get("csrf_token", "")):
            return RedirectResponse("/ui/users?error=" + quote("CSRF校验失败"), status_code=303)
        auth_yaml = app_state.auth_yaml_path or str(Path("dev-secrets") / "auth.yaml")
        name = unquote(request.path_params["name"])
        new_name = form.get("new_name", "").strip()
        submitted_name = form.get("name", "").strip()
        final_new_name = submitted_name if submitted_name and submitted_name != name else (new_name or None)
        key_value = form.get("key", "").strip()
        result = update_api_key(
            auth_yaml=auth_yaml,
            name=name,
            role=form.get("role", "").strip() or None,
            key=key_value if key_value else None,
            scope_include=form.get("scope_include", ""),
            scope_exclude=form.get("scope_exclude", ""),
            new_name=final_new_name,
            app_state=app_state,
        )
        final_name = result.get("name", name)
        if app_state.audit_logger:
            app_state.audit_logger.log(AuditEntry(
                timestamp=_now_iso(),
                source="web",
                actor=user,
                action="user.update",
                target=final_name,
                detail=result,
                success=result.get("success", False),
            ))
        if result.get("success"):
            if result.get("renamed"):
                return RedirectResponse("/ui/users?success=" + quote(f"更新成功，已重命名为 {final_name}"), status_code=303)
            return RedirectResponse("/ui/users?success=" + quote(f"更新成功: {final_name}"), status_code=303)
        return RedirectResponse("/ui/users?error=" + quote(result.get("error", "更新失败")), status_code=303)

    @mcp.custom_route("/ui/users/{name}/delete", methods=["POST"])
    async def users_delete(request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/ui/login", status_code=303)
        form = await request.form()
        if not csrf.validate_token(form.get("csrf_token", "")):
            return RedirectResponse("/ui/users?error=" + quote("CSRF校验失败"), status_code=303)
        auth_yaml = app_state.auth_yaml_path or str(Path("dev-secrets") / "auth.yaml")
        name = unquote(request.path_params["name"])
        result = delete_api_key(auth_yaml=auth_yaml, name=name, app_state=app_state)
        if app_state.audit_logger:
            app_state.audit_logger.log(AuditEntry(
                timestamp=_now_iso(),
                source="web",
                actor=user,
                action="user.delete",
                target=name,
                detail=result,
                success=result.get("success", False),
            ))
        if result.get("success"):
            return RedirectResponse("/ui/users?success=" + quote(f"删除成功: {name}"), status_code=303)
        return RedirectResponse("/ui/users?error=" + quote(result.get("error", "删除失败")), status_code=303)

    # ── 审计日志页面 ──

    @mcp.custom_route("/ui/audit", methods=["GET"])
    async def audit_page(request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/ui/login", status_code=303)
        source = request.query_params.get("source", "")
        actor = request.query_params.get("actor", "")
        try:
            limit = int(request.query_params.get("limit", "100"))
        except ValueError:
            limit = 100
        audit = app_state.audit_logger
        if audit:
            logs = audit.query(source=source or None, actor=actor or None, limit=limit)
        else:
            logs = []
        logs = list(reversed(logs))
        token = csrf.generate_token()
        html = env.get_template("audit.html").render(
            user=user, logs=logs, csrf_token=token,
            filter_source=source, filter_actor=actor, filter_limit=limit,
            settings=app_state.settings,
        )
        resp = Response(html, media_type="text/html")
        resp.set_cookie("csrf_token", token, httponly=True, samesite="strict")
        return resp

    # ── 配置页面 ──

    @mcp.custom_route("/ui/settings", methods=["GET"])
    async def settings_page(request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/ui/login", status_code=303)
        settings = app_state.settings
        raw_yaml = ""
        if app_state.settings_yaml_path:
            try:
                raw_yaml = Path(app_state.settings_yaml_path).read_text(encoding="utf-8")
            except Exception:
                raw_yaml = "（无法读取配置文件）"
        admin_username = user
        if app_state.admin_yaml_path:
            try:
                ac = AdminConfig.from_yaml(app_state.admin_yaml_path)
                admin_username = ac.username
            except Exception:
                pass
        token = csrf.generate_token()
        html = env.get_template("settings.html").render(
            user=user, settings=settings, raw_yaml=raw_yaml, csrf_token=token,
            admin_username=admin_username,
            error=unquote(request.query_params.get("error", "")),
            success=unquote(request.query_params.get("success", "")),
        )
        resp = Response(html, media_type="text/html")
        resp.set_cookie("csrf_token", token, httponly=True, samesite="strict")
        return resp

    @mcp.custom_route("/ui/settings/reload", methods=["POST"])
    async def settings_reload(request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/ui/login", status_code=303)
        form = await request.form()
        if not csrf.validate_token(form.get("csrf_token", "")):
            return RedirectResponse("/ui/settings?error=" + quote("CSRF校验失败"), status_code=303)
        success = True
        err_msg = ""
        try:
            app_state.reload_settings()
        except Exception as e:
            success = False
            err_msg = str(e)
        if app_state.audit_logger:
            app_state.audit_logger.log(AuditEntry(
                timestamp=_now_iso(),
                source="web",
                actor=user,
                action="settings.reload",
                target="settings.yaml",
                detail={},
                success=success,
            ))
        if success:
            return RedirectResponse("/ui/settings?success=" + quote("热加载成功"), status_code=303)
        return RedirectResponse("/ui/settings?error=" + quote(err_msg), status_code=303)

    @mcp.custom_route("/ui/settings/save", methods=["POST"])
    async def settings_save(request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/ui/login", status_code=303)
        form = await request.form()
        if not csrf.validate_token(form.get("csrf_token", "")):
            return RedirectResponse("/ui/settings?error=" + quote("CSRF校验失败"), status_code=303)
        settings_yaml = app_state.settings_yaml_path or str(Path("dev-config") / "settings.yaml")

        form_dict: dict[str, Any] = {}
        for key in ["host", "port", "log_level", "socket_path", "timezone", "allowed_hosts"]:
            val = form.get(key)
            if val is not None:
                form_dict[key] = val
        for key in ["container_management", "image_management", "system_diagnostics", "exec_enabled", "host_origin_protection"]:
            form_dict[key] = form.get(key, "off")

        result = update_settings_from_form(settings_yaml, form_dict, app_state=app_state)

        if app_state.audit_logger:
            app_state.audit_logger.log(AuditEntry(
                timestamp=_now_iso(),
                source="web",
                actor=user,
                action="settings.save",
                target="settings.yaml",
                detail=form_dict,
                success=result.get("success", False),
            ))
        if result.get("success"):
            return RedirectResponse("/ui/settings?success=" + quote("设置已保存并热加载"), status_code=303)
        return RedirectResponse("/ui/settings?error=" + quote(result.get("error", "保存失败")), status_code=303)

    @mcp.custom_route("/ui/settings/password", methods=["POST"])
    async def settings_password(request):
        user = require_login(request)
        if not user:
            return RedirectResponse("/ui/login", status_code=303)
        form = await request.form()
        if not csrf.validate_token(form.get("csrf_token", "")):
            return RedirectResponse("/ui/settings?error=" + quote("CSRF校验失败"), status_code=303)
        admin_yaml = app_state.admin_yaml_path or str(Path("dev-secrets") / "admin.yaml")
        old_pw = form.get("old_password", "")
        new_pw = form.get("new_password", "")
        confirm_pw = form.get("confirm_password", "")
        new_username = form.get("admin_username", "").strip()

        if new_pw != confirm_pw:
            return RedirectResponse("/ui/settings?error=" + quote("两次输入的新密码不一致"), status_code=303)

        result = change_admin_password(
            admin_yaml=admin_yaml,
            old_password=old_pw,
            new_password=new_pw,
            new_username=new_username if new_username else None,
            app_state=app_state,
        )

        if app_state.audit_logger:
            app_state.audit_logger.log(AuditEntry(
                timestamp=_now_iso(),
                source="web",
                actor=user,
                action="admin.password_change",
                target="admin.yaml",
                detail={"username_changed": bool(new_username and new_username != user)},
                success=result.get("success", False),
            ))
        if result.get("success"):
            msg = "管理员密码已更新"
            if result.get("username") and result["username"] != user:
                msg += f"，用户名已改为 {result['username']}"
            resp = RedirectResponse("/ui/login?success=" + quote(msg + "，请重新登录"), status_code=303)
            resp.delete_cookie("session")
            return resp
        return RedirectResponse("/ui/settings?error=" + quote(result.get("error", "修改失败")), status_code=303)

    # 静态文件（支持子目录）
    @mcp.custom_route("/ui/static/{path:path}", methods=["GET"])
    async def static_file(request):
        path = request.path_params["path"]
        f = STATIC_DIR / path
        if not f.exists() or not f.is_file():
            return Response("Not Found", status_code=404)
        ext = f.suffix.lower()
        media_map = {
            ".css": "text/css",
            ".js": "application/javascript",
            ".svg": "image/svg+xml",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".ico": "image/x-icon",
        }
        media = media_map.get(ext, "text/plain")
        headers = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
        return Response(f.read_bytes(), media_type=media, headers=headers)
