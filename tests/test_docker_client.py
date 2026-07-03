"""Docker 客户端封装测试（mock Docker SDK）"""
import pytest
from unittest.mock import MagicMock, patch

from core.docker_client import DockerClient


@pytest.fixture
def mock_docker_sdk():
    """Mock docker.from_env()"""
    with patch("core.docker_client.docker") as mock_docker_module:
        mock_client = MagicMock()
        mock_docker_module.from_env.return_value = mock_client
        mock_docker_module.errors.NotFound = Exception
        mock_docker_module.errors.APIError = Exception
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
        mock_docker_sdk.containers.get.side_effect = Exception("not found")

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

        mock_container.logs.assert_called_with(tail="10", stdout=True, stderr=True)
        assert result == "line1\nline2\n"


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
