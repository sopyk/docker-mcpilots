"""Web UI 路由注册"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Optional
from jinja2 import Environment, FileSystemLoader
from fastmcp import FastMCP
from core.app_state import AppState
from core.admin_auth import AdminAuth, SessionManager
from core.csrf import CSRFProtection


# 路径配置
TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)


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
        # 已登录直接跳
        user = require_login(request)
        if user:
            from fastmcp.responses import RedirectResponse
            return RedirectResponse("/ui/", status_code=303)
        token = csrf.generate_token()
        html = env.get_template("login.html").render(csrf_token=token, error="")
        from fastmcp.responses import Response
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
        # CSRF 校验
        if not csrf.validate_token(csrf_token):
            token2 = csrf.generate_token()
            html = env.get_template("login.html").render(
                csrf_token=token2, error="CSRF 校验失败"
            )
            from fastmcp.responses import Response
            resp = Response(html, media_type="text/html")
            resp.set_cookie("csrf_token", token2, httponly=True, samesite="strict")
            return resp
        # 密码校验
        if admin_auth.verify(username, password):
            token3 = session_mgr.create_token(username)
            from fastmcp.responses import RedirectResponse
            resp = RedirectResponse("/ui/", status_code=303)
            resp.set_cookie("session", token3, httponly=True, samesite="strict")
            # 审计日志
            if app_state.audit_logger:
                from datetime import datetime
                from core.audit import AuditEntry
                app_state.audit_logger.log(AuditEntry(
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    source="web",
                    actor=username,
                    action="auth.login",
                    target="",
                    detail={},
                    success=True
                ))
            return resp
        # 失败重渲染
        token4 = csrf.generate_token()
        html = env.get_template("login.html").render(
            csrf_token=token4, error="用户名或密码错误"
        )
        from fastmcp.responses import Response
        resp = Response(html, media_type="text/html")
        resp.set_cookie("csrf_token", token4, httponly=True, samesite="strict")
        return resp

    # 登出
    @mcp.custom_route("/ui/logout", methods=["GET"])
    async def logout_page(request):
        from fastmcp.responses import RedirectResponse
        resp = RedirectResponse("/ui/login", status_code=303)
        resp.delete_cookie("session")
        return resp

    # 仪表盘
    @mcp.custom_route("/ui/", methods=["GET"])
    async def dashboard_page(request):
        user = require_login(request)
        if not user:
            from fastmcp.responses import RedirectResponse
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
            recent_logs=recent_logs
        )
        from fastmcp.responses import Response
        return Response(html, media_type="text/html")

    # 静态文件
    @mcp.custom_route("/ui/static/{filename}", methods=["GET"])
    async def static_file(request):
        filename = request.path_params["filename"]
        f = STATIC_DIR / filename
        if not f.exists():
            from fastmcp.responses import Response
            return Response("Not Found", status_code=404)
        from fastmcp.responses import Response
        # 根据扩展名选 Content-Type
        ext = f.suffix.lower()
        media_map = {".css": "text/css", ".js": "application/javascript", ".svg": "image/svg+xml"}
        media = media_map.get(ext, "text/plain")
        return Response(f.read_bytes(), media_type=media)
