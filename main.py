"""Docker-MCPilotS MCP Server 主入口"""
from __future__ import annotations

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext

from core.config import Settings, AuthConfig
from core.auth import PermissionChecker, AuthenticationError
from core.docker_client import DockerClient
from core.system_diag import SystemDiag
from core.app_state import AppState
from core.audit import AuditLogger, AuditEntry
from core.admin_auth import AdminAuth, SessionManager
from core.csrf import CSRFProtection
from tools.container_tools import register_container_tools
from tools.image_tools import register_image_tools
from tools.diag_tools import register_diag_tools
from tools.docker_diag_tools import register_docker_diag_tools
from tools.exec_tools import register_exec_tools

logger = logging.getLogger("docker-mcpilots")


def _now_iso() -> str:
    """当前 UTC 时间的 ISO 格式字符串（带 Z 后缀，兼容 Python 3.14+）"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── 常量 ──
CONFIG_DIR = Path(os.environ.get("MCP_CONFIG_DIR", "/app/config"))
SECRETS_DIR = Path(os.environ.get("MCP_SECRETS_DIR", "/app/secrets"))
TEMPLATE_DIR = Path(__file__).parent / "templates"


class AuthMiddleware(Middleware):
    """API Key 认证中间件 — 从 HTTP 请求头提取 Bearer Token 并存入 session state"""

    def __init__(self, app_state: AppState):
        self._app_state = app_state

    async def on_request(self, context: MiddlewareContext, call_next):
        ctx = context.fastmcp_context
        if ctx and ctx.request_context:
            # 尝试从 session state 获取已认证的 key（同一会话内缓存）
            cached = await ctx.get_state("auth_key_config")
            if cached is not None:
                return await call_next(context)

            # 从 HTTP 请求头提取 API Key
            # 注意：get_http_headers() 默认会过滤 authorization，必须显式 include
            try:
                from fastmcp.server.dependencies import get_http_headers
                headers = get_http_headers(include={"authorization"})
                auth_header = headers.get("authorization", "")
                if not auth_header.startswith("Bearer "):
                    from mcp import McpError
                    from mcp.types import ErrorData
                    raise McpError(ErrorData(code=-32001, message="Missing or invalid authorization header. Format: Bearer <api_key>"))

                api_key = auth_header[7:]
                key_config = self._app_state.permission_checker.authenticate(api_key)
                await ctx.set_state("auth_key_config", key_config)

            except AuthenticationError as e:
                if self._app_state.audit_logger:
                    self._app_state.audit_logger.log(AuditEntry(
                        timestamp=_now_iso(),
                        source="mcp",
                        actor="unknown",
                        action="auth.failed",
                        target="",
                        detail={},
                        success=False,
                    ))
                from mcp import McpError
                from mcp.types import ErrorData
                raise McpError(ErrorData(code=-32001, message=str(e)))

        return await call_next(context)

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Tool 调用审计：记录 tool 名、调用者、成功/失败"""
        ctx = context.fastmcp_context
        message = context.message
        tool_name = getattr(message, "name", "") if message else ""
        actor = "unknown"
        if ctx and ctx.request_context:
            key_config = await ctx.get_state("auth_key_config")
            if key_config is not None:
                if isinstance(key_config, dict):
                    actor = key_config.get("name", str(key_config))
                else:
                    actor = getattr(key_config, "name", str(key_config))
        success = True
        try:
            return await call_next(context)
        except Exception:
            success = False
            raise
        finally:
            if self._app_state.audit_logger:
                self._app_state.audit_logger.log(AuditEntry(
                    timestamp=_now_iso(),
                    source="mcp",
                    actor=actor,
                    action="tools.call",
                    target=tool_name,
                    detail={},
                    success=success,
                ))


def _init_config_files() -> None:
    """首次启动时自动生成默认配置模板（自动处理挂载卷权限，支持环境变量初始化）"""
    # 确保 config 目录存在
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logger.error(
            f"Permission denied creating {CONFIG_DIR}. "
            "If running on Synology NAS, set PUID/PGID in docker-compose.yml to match your DSM user."
        )
        raise

    try:
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logger.error(
            f"Permission denied creating {SECRETS_DIR}. "
            "If running on Synology NAS, set PUID/PGID in docker-compose.yml to match your DSM user."
        )
        raise

    # 处理 settings.yaml
    settings_file = CONFIG_DIR / "settings.yaml"
    if not settings_file.exists():
        template = TEMPLATE_DIR / "settings.yaml"
        try:
            shutil.copy2(template, settings_file)
            logger.info(f"Generated default settings: {settings_file}")
        except PermissionError:
            logger.error(
                f"Permission denied writing to {settings_file}. "
                "Ensure the mounted config directory is writable by the container user (check PUID/PGID)."
            )
            raise

    # 处理 auth.yaml，支持 INITIAL_API_KEYS 环境变量
    auth_file = SECRETS_DIR / "auth.yaml"
    if not auth_file.exists():
        template = TEMPLATE_DIR / "auth.yaml"
        try:
            shutil.copy2(template, auth_file)
            logger.warning(
                f"Generated default auth config: {auth_file}. "
                "IMPORTANT: Edit this file immediately to set your own API keys!"
            )
            # 设置文件权限为 600
            try:
                os.chmod(auth_file, 0o600)
            except OSError:
                logger.warning(f"Could not set permissions on {auth_file}")
        except PermissionError:
            logger.error(
                f"Permission denied writing to {auth_file}. "
                "Ensure the mounted secrets directory is writable by the container user (check PUID/PGID)."
            )
            raise

    # 从环境变量 INITIAL_API_KEYS 初始化 API Key（格式：name1:key1:role1,name2:key2:role2）
    initial_api_keys = os.environ.get("INITIAL_API_KEYS", "")
    if initial_api_keys and initial_api_keys.strip():
        auth_config = AuthConfig.from_yaml(str(auth_file))
        for pair in initial_api_keys.strip().split(","):
            parts = pair.strip().split(":")
            if len(parts) == 3:
                name, key, role = parts[0], parts[1], parts[2]
                # 检查是否已存在同名 key
                existing = next((k for k in auth_config.keys if k.name == name), None)
                if existing:
                    logger.warning(f"API key '{name}' already exists, skipping")
                    continue
                # 添加新 key
                auth_config.keys.append(
                    AuthConfig.Key(name=name, key=key, role=role)
                )
                logger.info(f"Created API key from environment: {name} (role: {role})")
        auth_config.to_yaml(str(auth_file))
        logger.info(f"Updated auth config with initial API keys: {auth_file}")

    # 处理 admin.yaml，支持 ADMIN_USERNAME、ADMIN_PASSWORD 环境变量
    admin_file = SECRETS_DIR / "admin.yaml"
    if not admin_file.exists():
        template = TEMPLATE_DIR / "admin.yaml"
        try:
            shutil.copy2(template, admin_file)
            logger.warning(
                f"Generated default admin config: {admin_file}. "
                "IMPORTANT: Set admin password immediately!"
            )
            # 设置文件权限为 600
            try:
                os.chmod(admin_file, 0o600)
            except OSError:
                logger.warning(f"Could not set permissions on {admin_file}")
        except PermissionError:
            logger.error(
                f"Permission denied writing to {admin_file}. "
                "Ensure the mounted secrets directory is writable by the container user (check PUID/PGID)."
            )
            raise

    # 从环境变量设置管理员用户名和密码
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    from core.admin_auth import AdminAuth, AdminConfig
    admin_auth = AdminAuth(str(admin_file), session_secret="temp-secret-just-for-init")
    # 读取当前 config
    try:
        current_config = AdminConfig.from_yaml(str(admin_file))
    except Exception:
        current_config = None

    if admin_password and admin_password.strip():
        # 如果密码不为空，设置/更新密码
        admin_auth.set_password(admin_username, admin_password.strip())
        logger.info(f"Set admin password from environment: {admin_file}")
    else:
        # 如果没有密码（无论是新文件还是旧文件密码为空），都检查一下
        if current_config and not current_config.password_hash:
            # 密码为空，生成随机密码并警告
            import secrets
            random_password = secrets.token_urlsafe(16)
            admin_auth.set_password(admin_username, random_password)
            logger.warning(f"Generated random admin password: '{random_password}'. Please change this immediately!")

    # 确保 secrets 目录下所有文件权限为 600
    try:
        for f in SECRETS_DIR.iterdir():
            if f.is_file():
                try:
                    os.chmod(f, 0o600)
                except OSError:
                    pass
    except PermissionError:
        logger.warning(f"Could not enumerate secrets directory {SECRETS_DIR}")


def create_app() -> FastMCP:
    """创建并配置 FastMCP 应用"""
    # 初始化配置文件
    _init_config_files()

    # 加载配置
    settings = Settings.from_yaml(str(CONFIG_DIR / "settings.yaml"))
    auth_config = AuthConfig.from_yaml(str(SECRETS_DIR / "auth.yaml"))
    admin_yaml = SECRETS_DIR / "admin.yaml"

    # 创建 AppState 作为全局状态容器，支持热加载
    docker_client = DockerClient(socket_path=settings.socket_path)
    system_diag = SystemDiag()
    audit_log_path = SECRETS_DIR / "audit.log"
    audit_logger = AuditLogger(log_file=str(audit_log_path), memory_size=200)
    app_state = AppState(
        settings=settings,
        auth_config=auth_config,
        audit_logger=audit_logger,
        auth_yaml_path=str(SECRETS_DIR / "auth.yaml"),
        settings_yaml_path=str(CONFIG_DIR / "settings.yaml"),
        admin_yaml_path=str(admin_yaml),
    )
    # 手动设置 docker_client 和 system_diag，因为 AppState 初始化时还没它们
    app_state.docker_client = docker_client  # type: ignore
    app_state.system_diag = system_diag    # type: ignore

    # 配置日志
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 创建 FastMCP 实例
    mcp = FastMCP(
        name="Docker-MCPilotS",
        instructions="Docker container and image management server with system diagnostics for Synology NAS.",
        version="2.0.2",
    )

    # 注册认证中间件
    mcp.add_middleware(AuthMiddleware(app_state))

    # 注册 MCP Tools
    if settings.container_management:
        register_container_tools(mcp, docker_client, app_state)
    if settings.image_management:
        register_image_tools(mcp, docker_client, app_state)
    if settings.system_diagnostics:
        register_diag_tools(mcp, system_diag, app_state)
    # Docker 资源诊断（网络、卷等）始终注册，用于排查容器问题
    register_docker_diag_tools(mcp, docker_client, app_state)

    # exec 工具（高风险，默认关闭，需 exec_enabled=true 且有 exec:run 权限）
    if settings.exec_enabled:
        register_exec_tools(mcp, docker_client, app_state)
        logger.info("Exec tools enabled (high risk — use with scope restrictions)")

    # 健康检查端点
    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request):
        from starlette.responses import JSONResponse
        return JSONResponse({"status": "ok", "version": "2.0.2"})

    # Web UI 初始化
    admin_yaml = SECRETS_DIR / "admin.yaml"
    web_cfg = settings.get("web", {})
    admin_auth = AdminAuth(
        admin_yaml=str(admin_yaml),
        session_secret=web_cfg.get("csrf_secret", "change-me"),
    )
    session_mgr = SessionManager(
        secret=web_cfg.get("csrf_secret", "change-me"),
        timeout=web_cfg.get("session_timeout", 28800),
    )
    csrf = CSRFProtection(secret=web_cfg.get("csrf_secret", "change-me"))

    from web.routes import register_web_routes
    register_web_routes(mcp, app_state, admin_auth, session_mgr, csrf)

    logger.info(f"Docker-MCPilotS MCP Server ready on {settings.host}:{settings.port}")
    logger.info(f"Registered {len(auth_config.keys)} API key(s)")
    for key_cfg in auth_config.keys:
        logger.info(f"  - {key_cfg.name} (role: {key_cfg.role})")

    return mcp


if __name__ == "__main__":
    mcp = create_app()
    settings = Settings.from_yaml(str(CONFIG_DIR / "settings.yaml"))
    # 禁用 FastMCP 的 host origin guard，允许从任意地址访问（NAS场景安全）
    mcp.run(
        transport="http",
        host=settings.host,
        port=settings.port,
        host_origin_protection=False,
        uvicorn_config={"forwarded_allow_ips": "*", "proxy_headers": False},
    )
