"""Docker 客户端封装测试（mock Docker SDK）"""
import pytest
from unittest.mock import MagicMock, patch

from core.docker_client import DockerClient


@pytest.fixture
def mock_docker_sdk():
    """Mock docker.DockerClient() 显式 socket 连接，返回 mock client"""
    with patch("core.docker_client.docker") as mock_docker_module:
        mock_client = MagicMock()
        mock_docker_module.DockerClient.return_value = mock_client
        mock_docker_module.errors.NotFound = type("NotFound", (Exception,), {})
        mock_docker_module.errors.APIError = type("APIError", (Exception,), {})
        yield mock_client


class TestListContainers:
    def test_list_running_containers(self, mock_docker_sdk):
        """列出运行中的容器"""
        mock_container = MagicMock()
        mock_container.short_id = "abc123"
        mock_container.name = "web-server"
        mock_container.status = "running"
        mock_container.image.tags = ["nginx:latest"]
        mock_docker_sdk.containers.list.return_value = [mock_container]

        client = DockerClient()
        result = client.list_containers(status="running")

        assert len(result) == 1
        assert result[0]["name"] == "web-server"
        assert result[0]["status"] == "running"

    def test_list_all_containers(self, mock_docker_sdk):
        """列出所有容器"""
        c1 = MagicMock()
        c1.short_id = "a"
        c1.name = "web"
        c1.status = "running"
        c1.image.tags = ["nginx"]
        c2 = MagicMock()
        c2.short_id = "b"
        c2.name = "db"
        c2.status = "exited"
        c2.image.tags = ["postgres"]
        mock_docker_sdk.containers.list.return_value = [c1, c2]

        client = DockerClient()
        result = client.list_containers(all=True)

        assert len(result) == 2
        mock_docker_sdk.containers.list.assert_called_with(all=True, filters={})


class TestContainerOperations:
    def test_start_container(self, mock_docker_sdk):
        """启动容器"""
        mock_container = MagicMock()
        mock_docker_sdk.containers.get.return_value = mock_container

        client = DockerClient()
        result = client.start_container("web-server")

        mock_container.start.assert_called_once()
        assert result["success"] is True

    def test_stop_container(self, mock_docker_sdk):
        """停止容器"""
        mock_container = MagicMock()
        mock_docker_sdk.containers.get.return_value = mock_container

        client = DockerClient()
        result = client.stop_container("web-server")

        mock_container.stop.assert_called_once()
        assert result["success"] is True

    def test_container_not_found(self, mock_docker_sdk):
        """容器不存在时返回错误"""
        from core.docker_client import DockerNotFound
        mock_docker_sdk.containers.get.side_effect = DockerNotFound("not found")

        client = DockerClient()
        result = client.start_container("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestContainerLogs:
    def test_get_logs(self, mock_docker_sdk):
        """获取容器日志"""
        mock_container = MagicMock()
        mock_container.logs.return_value = b"line1\nline2\n"
        mock_docker_sdk.containers.get.return_value = mock_container

        client = DockerClient()
        result = client.get_container_logs("web-server", tail=10)

        mock_container.logs.assert_called_with(tail=10, stdout=True, stderr=True, timestamps=False)
        assert result["success"] is True
        assert result["logs"] == "line1\nline2\n"


class TestContainerStats:
    def test_get_stats(self, mock_docker_sdk):
        """获取容器资源统计"""
        mock_container = MagicMock()
        mock_container.stats.return_value = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 1000000},
                "system_cpu_usage": 5000000,
                "online_cpus": 4,
            },
            "memory_stats": {"usage": 104857600, "limit": 524288000},
            "networks": {"eth0": {"rx_bytes": 1000, "tx_bytes": 2000}},
        }
        mock_docker_sdk.containers.get.return_value = mock_container

        client = DockerClient()
        result = client.get_container_stats("web-server")

        assert "cpu_percent" in result
        assert "memory_percent" in result
        assert result["memory_percent"] == 20.0


class TestImageOperations:
    def test_list_images(self, mock_docker_sdk):
        """列出镜像"""
        mock_image = MagicMock()
        mock_image.short_id = "sha256:abc123"
        mock_image.tags = ["nginx:latest"]
        mock_image.attrs = {"Size": 142000000}
        mock_docker_sdk.images.list.return_value = [mock_image]

        client = DockerClient()
        result = client.list_images()

        assert len(result) == 1
        assert result[0]["tags"] == ["nginx:latest"]

    def test_pull_image(self, mock_docker_sdk):
        """拉取镜像"""
        mock_image = MagicMock()
        mock_image.tags = ["nginx:latest"]
        mock_docker_sdk.images.pull.return_value = mock_image

        client = DockerClient()
        result = client.pull_image("nginx", tag="latest")

        mock_docker_sdk.images.pull.assert_called_with("nginx", tag="latest")
        assert result["success"] is True


class TestExecContainer:
    def test_exec_success(self, mock_docker_sdk):
        """在容器内执行命令成功"""
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_container.id = "abc123"
        mock_container.name = "toolbox"
        mock_container.client = mock_docker_sdk
        mock_docker_sdk.containers.get.return_value = mock_container
        mock_docker_sdk.api.exec_create.return_value = "exec-id-123"
        mock_docker_sdk.api.exec_start.return_value = (b"hello world\n", b"")
        mock_docker_sdk.api.exec_inspect.return_value = {"ExitCode": 0}

        client = DockerClient()
        result = client.exec_container("toolbox", "echo hello")

        assert result["success"] is True
        assert result["exit_code"] == 0
        assert result["stdout"] == "hello world\n"
        assert result["stderr"] == ""
        assert result["container_name"] == "toolbox"

    def test_exec_container_not_running(self, mock_docker_sdk):
        """容器未运行时拒绝执行"""
        mock_container = MagicMock()
        mock_container.status = "exited"
        mock_docker_sdk.containers.get.return_value = mock_container

        client = DockerClient()
        result = client.exec_container("stopped", "echo hi")

        assert result["success"] is False
        assert "not running" in result["error"].lower()

    def test_exec_container_not_found(self, mock_docker_sdk):
        """容器不存在时返回错误"""
        from core.docker_client import DockerNotFound
        mock_docker_sdk.containers.get.side_effect = DockerNotFound("not found")

        client = DockerClient()
        result = client.exec_container("nonexistent", "echo hi")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_exec_with_workdir(self, mock_docker_sdk):
        """执行命令时指定工作目录"""
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_container.id = "abc123"
        mock_container.name = "toolbox"
        mock_container.client = mock_docker_sdk
        mock_docker_sdk.containers.get.return_value = mock_container
        mock_docker_sdk.api.exec_create.return_value = "exec-id-456"
        mock_docker_sdk.api.exec_start.return_value = (b"/tmp\n", b"")
        mock_docker_sdk.api.exec_inspect.return_value = {"ExitCode": 0}

        client = DockerClient()
        result = client.exec_container("toolbox", "pwd", workdir="/tmp")

        mock_docker_sdk.api.exec_create.assert_called_once()
        call_kwargs = mock_docker_sdk.api.exec_create.call_args
        assert call_kwargs[1]["workdir"] == "/tmp"
        assert result["success"] is True


class TestContainerLogs:
    """get_container_logs：tail 传参类型 + 超大日志体积控制

    历史 bug：tail 以字符串传给 docker-py 会被静默降级成 "all"；
    超大日志会让 MCP 响应超过客户端 1 MiB 的 SSE 单事件上限。
    """

    def _make(self, mock_docker_sdk, payload: bytes):
        container = MagicMock()
        container.logs.return_value = payload
        mock_docker_sdk.containers.get.return_value = container
        return DockerClient(), container

    @pytest.mark.parametrize(
        ("tail", "expected"),
        [(50, 50), ("50", 50), (0, 0), ("all", "all"), (-1, "all")],
    )
    def test_tail_is_passed_as_int(self, mock_docker_sdk, tail, expected):
        """docker-py 7.x 只在 tail 是 int 时生效，字符串会被静默降级为 all"""
        client, container = self._make(mock_docker_sdk, b"line1\n")
        client.get_container_logs("c", tail=tail)
        kwargs = container.logs.call_args.kwargs
        assert kwargs["tail"] == expected
        if isinstance(expected, int):
            assert isinstance(kwargs["tail"], int)

    def test_small_log_is_not_truncated(self, mock_docker_sdk):
        payload = b"a\nb\nc\n"
        client, _ = self._make(mock_docker_sdk, payload)
        result = client.get_container_logs("c", tail=10)
        assert result["success"] is True
        assert result["truncated"] is False
        assert result["bytes_total"] == len(payload)
        assert result["logs"] == payload.decode()

    def test_huge_log_keeps_tail_with_notice(self, mock_docker_sdk):
        """超大日志：保留末尾、带提示、体积远小于客户端 1 MiB 上限"""
        lines = [f"line-{i}-" + "x" * 60 for i in range(40000)]
        payload = ("\n".join(lines) + "\n").encode()
        client, _ = self._make(mock_docker_sdk, payload)

        result = client.get_container_logs("c")

        assert result["success"] is True
        assert result["truncated"] is True
        assert result["bytes_total"] == len(payload)
        assert "已截断" in result["logs"]
        assert "line-39999-" in result["logs"]      # 末尾保留
        assert "line-0-" not in result["logs"]      # 开头丢弃
        assert len(result["logs"].encode()) <= 360_000

    def test_estimated_mcp_response_stays_under_limit(self, mock_docker_sdk):
        """估算的 MCP 响应（content + structuredContent）必须低于 1 MiB"""
        payload = ("\n".join(f"line-{i}-" + "y" * 60 for i in range(40000)) + "\n").encode()
        client, _ = self._make(mock_docker_sdk, payload)
        result = client.get_container_logs("c")

        from core.docker_client import MAX_MCP_RESPONSE_BYTES, _estimate_mcp_response_bytes

        estimate = _estimate_mcp_response_bytes(result)
        assert estimate <= MAX_MCP_RESPONSE_BYTES < 1_048_576

    def test_single_gigantic_line_does_not_crash(self, mock_docker_sdk):
        """没有换行的超长单行也要能截断"""
        payload = b"x" * 2_000_000
        client, _ = self._make(mock_docker_sdk, payload)
        result = client.get_container_logs("c")
        assert result["success"] is True
        assert result["truncated"] is True
        assert len(result["logs"].encode()) <= 360_000
