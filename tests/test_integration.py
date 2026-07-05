"""集成测试 - 验证 server 启动流程和模块集成"""
import sys
from unittest.mock import patch, MagicMock

# Mock 未安装的第三方模块（必须在导入 core/main 之前注入）
if 'psutil' not in sys.modules:
    sys.modules['psutil'] = MagicMock()

if 'fastmcp' not in sys.modules:
    _mock_fastmcp = MagicMock()
    _mock_fastmcp.FastMCP = MagicMock
    _mock_fastmcp.server = MagicMock()
    _mock_fastmcp.server.middleware = MagicMock()
    _mock_fastmcp.server.middleware.Middleware = object
    _mock_fastmcp.server.middleware.MiddlewareContext = MagicMock
    _mock_fastmcp.server.dependencies = MagicMock()
    sys.modules['fastmcp'] = _mock_fastmcp
    sys.modules['fastmcp.server'] = _mock_fastmcp.server
    sys.modules['fastmcp.server.middleware'] = _mock_fastmcp.server.middleware
    sys.modules['fastmcp.server.dependencies'] = _mock_fastmcp.server.dependencies

if 'mcp' not in sys.modules:
    _mock_mcp = MagicMock()
    sys.modules['mcp'] = _mock_mcp
    sys.modules['mcp.types'] = MagicMock()

if 'starlette' not in sys.modules:
    _mock_starlette = MagicMock()
    sys.modules['starlette'] = _mock_starlette
    sys.modules['starlette.responses'] = MagicMock()

import tempfile
import yaml
from pathlib import Path


class TestInitConfigFiles:
    def test_generates_default_settings(self):
        """首次启动时自动生成 settings.yaml 模板"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            secrets_dir = Path(tmpdir) / "secrets"
            template_dir = Path(tmpdir) / "templates"
            template_dir.mkdir()

            # 创建模板文件
            (template_dir / "settings.yaml").write_text("server:\n  host: 0.0.0.0\n")
            (template_dir / "auth.yaml").write_text("roles:\n  admin:\n    permissions: ['*']\nkeys:\n  - key: sk-test\n    role: admin\n")
            (template_dir / "admin.yaml").write_text("username: admin\npassword_hash: ''\n")

            with patch("main.CONFIG_DIR", config_dir), \
                 patch("main.SECRETS_DIR", secrets_dir), \
                 patch("main.TEMPLATE_DIR", template_dir):
                from main import _init_config_files
                _init_config_files()

            assert (config_dir / "settings.yaml").exists()
            assert (secrets_dir / "auth.yaml").exists()

    def test_skips_existing_files(self):
        """配置文件已存在时不再覆盖"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            secrets_dir = Path(tmpdir) / "secrets"
            config_dir.mkdir()
            secrets_dir.mkdir()

            existing_settings = "server:\n  host: 127.0.0.1\n"
            (config_dir / "settings.yaml").write_text(existing_settings)
            (secrets_dir / "auth.yaml").write_text("roles:\nkeys:\n")

            with patch("main.CONFIG_DIR", config_dir), \
                 patch("main.SECRETS_DIR", secrets_dir):
                from main import _init_config_files
                _init_config_files()

            content = (config_dir / "settings.yaml").read_text()
            assert "127.0.0.1" in content


class TestCreateApp:
    @patch("main.FastMCP")
    @patch("main.DockerClient")
    @patch("main.SystemDiag")
    @patch("main.register_container_tools")
    @patch("main.register_image_tools")
    @patch("main.register_diag_tools")
    def test_app_creation_registers_tools(
        self, mock_diag_tools, mock_img_tools, mock_ct_tools,
        mock_sysdiag, mock_docker, mock_fastmcp
    ):
        """验证 create_app 正确注册所有 Tools"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            secrets_dir = Path(tmpdir) / "secrets"
            template_dir = Path(tmpdir) / "templates"
            config_dir.mkdir()
            secrets_dir.mkdir()
            template_dir.mkdir()

            # 写入配置
            settings = {"server": {"host": "0.0.0.0", "port": 8900, "log_level": "info"}}
            auth = {
                "roles": {"admin": {"description": "a", "permissions": ["*"]}},
                "keys": [{"key": "sk-admin", "name": "admin", "role": "admin"}],
            }
            (config_dir / "settings.yaml").write_text(yaml.dump(settings))
            (secrets_dir / "auth.yaml").write_text(yaml.dump(auth))
            (template_dir / "settings.yaml").write_text("")
            (template_dir / "auth.yaml").write_text("")
            (template_dir / "admin.yaml").write_text("username: admin\npassword_hash: ''\n")

            mcp_instance = MagicMock()
            mock_fastmcp.return_value = mcp_instance

            with patch("main.CONFIG_DIR", config_dir), \
                 patch("main.SECRETS_DIR", secrets_dir), \
                 patch("main.TEMPLATE_DIR", template_dir):
                from main import create_app
                app = create_app()

            # 验证 FastMCP 被创建
            mock_fastmcp.assert_called_once()
            # 验证中间件被注册
            mcp_instance.add_middleware.assert_called_once()
            # 验证各 tool 注册函数被调用
            mock_ct_tools.assert_called_once()
            mock_img_tools.assert_called_once()
            mock_diag_tools.assert_called_once()
