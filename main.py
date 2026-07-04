"""DockerMaintainer MCP Server 主入口"""
from __future__ import annotations

import os
import shutil
import logging
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext

from core.config import Settings, AuthConfig
from core.auth import PermissionChecker, AuthenticationError
from core.docker_client import DockerClient
from core.system_diag import SystemDiag
from tools.container_tools import register_container_tools
from tools.image_tools import register_image_tools
from tools.diag_tools import register_diag_tools

logger = logging.getLogger("docker-mcp-server")

# ── 常量 ──
CONFIG_DIR = Path(os.environ.get("MCP_CONFIG_DIR", "/app/config"))
SECRETS_DIR = Path(os.environ.get("MCP_SECRETS_DIR", "/app/secrets"))
TEMPLATE_DIR = Path(__file__).parent / "templates"


class AuthMiddleware(Middleware):
    """API Key 认证中间件 — 从 HTTP 请求头提取 Bearer Token 并存入 session state"""

    def __init__(self, permission_checker: PermissionChecker):
        self._checker = permission_checker

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
                key_config = self._checker.authenticate(api_key)
                await ctx.set_state("auth_key_config", key_config, serializable=True)
            except AuthenticationError as e:
                from mcp import McpError
                from mcp.types import ErrorData
                raise McpError(ErrorData(code=-32001, message=str(e)))

        return await call_next(context)


def _init_config_files() -> None:
    """首次启动时自动生成默认配置模板（自动处理挂载卷权限）"""
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
    permission_checker = PermissionChecker(auth_config)

    # 配置日志
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 创建 FastMCP 实例
    mcp = FastMCP(
        name="DockerMaintainer",
        instructions="Docker container and image management server with system diagnostics for Synology NAS.",
        version="0.1.3",
    )

    # 注册认证中间件
    mcp.add_middleware(AuthMiddleware(permission_checker))

    # 创建客户端
    docker_client = DockerClient(socket_path=settings.socket_path)
    system_diag = SystemDiag()

    # 注册 MCP Tools
    if settings.container_management:
        register_container_tools(mcp, docker_client)
    if settings.image_management:
        register_image_tools(mcp, docker_client)
    if settings.system_diagnostics:
        register_diag_tools(mcp, system_diag)

    # 健康检查端点
    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request):
        from starlette.responses import JSONResponse
        return JSONResponse({"status": "ok", "version": "0.1.3"})

    logger.info(f"DockerMaintainer MCP Server ready on {settings.host}:{settings.port}")
    logger.info(f"Registered {len(auth_config.keys)} API key(s)")
    for key_cfg in auth_config.keys:
        logger.info(f"  - {key_cfg.name} (role: {key_cfg.role})")

    return mcp


if __name__ == "__main__":
    mcp = create_app()
    settings = Settings.from_yaml(str(CONFIG_DIR / "settings.yaml"))
    mcp.run(transport="http", host=settings.host, port=settings.port)
