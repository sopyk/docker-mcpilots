"""Docker SDK 封装 - 统一 Docker 容器和镜像操作的接口层"""
from __future__ import annotations

try:
    import docker
    from docker.errors import NotFound as DockerNotFound, APIError as DockerAPIError
except ImportError:
    docker = None
    DockerNotFound = Exception
    DockerAPIError = Exception


class DockerClient:
    """Docker 客户端封装（延迟连接，首次调用时才连接 Docker daemon）"""

    def __init__(self, socket_path: str = "/var/run/docker.sock"):
        if docker is None:
            raise RuntimeError(
                "Docker SDK for Python is not installed. "
                "Run: pip install docker"
            )
        self._socket_path = socket_path
        self._client = None

    def _ensure_connected(self):
        """延迟连接 Docker daemon，仅首次调用时建立连接"""
        if self._client is None:
            self._client = docker.from_env()

    # ── 容器操作 ──

    def list_containers(self, status: str | None = None, all: bool = False) -> list[dict]:
        """列出容器"""
        self._ensure_connected()
        filters = {}
        if status and status != "all":
            filters["status"] = status
        if all or status == "all":
            containers = self._client.containers.list(all=True, filters=filters if status != "all" else {})
        else:
            containers = self._client.containers.list(filters=filters)

        return [self._format_container(c) for c in containers]

    def get_container(self, container_id: str) -> dict:
        """获取单个容器详情"""
        self._ensure_connected()
        container = self._client.containers.get(container_id)
        return self._format_container_detail(container)

    def start_container(self, container_id: str) -> dict:
        """启动容器"""
        self._ensure_connected()
        try:
            container = self._client.containers.get(container_id)
            container.start()
            container.reload()
            return {"success": True, "container": self._format_container(container)}
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    def stop_container(self, container_id: str) -> dict:
        """停止容器"""
        self._ensure_connected()
        try:
            container = self._client.containers.get(container_id)
            container.stop()
            container.reload()
            return {"success": True, "container": self._format_container(container)}
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    def restart_container(self, container_id: str) -> dict:
        """重启容器"""
        self._ensure_connected()
        try:
            container = self._client.containers.get(container_id)
            container.restart()
            container.reload()
            return {"success": True, "container": self._format_container(container)}
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    def remove_container(self, container_id: str, force: bool = False) -> dict:
        """删除容器"""
        self._ensure_connected()
        try:
            container = self._client.containers.get(container_id)
            container.remove(force=force)
            return {"success": True, "removed": container_id}
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    def get_container_logs(
        self, container_id: str, tail: int | None = None
    ) -> str:
        """获取容器日志"""
        self._ensure_connected()
        container = self._client.containers.get(container_id)
        kwargs = {"stdout": True, "stderr": True}
        if tail is not None:
            kwargs["tail"] = str(tail)
        logs = container.logs(**kwargs)
        return logs.decode("utf-8", errors="replace") if isinstance(logs, bytes) else str(logs)

    def get_container_stats(self, container_id: str) -> dict:
        """获取容器实时资源统计（单次采样）"""
        self._ensure_connected()
        container = self._client.containers.get(container_id)
        raw = container.stats(stream=False, decode=True)

        cpu_percent = 0.0
        cpu_usage = raw.get("cpu_stats", {}).get("cpu_usage", {})
        system_cpu = raw.get("cpu_stats", {}).get("system_cpu_usage", 0)
        online_cpus = raw.get("cpu_stats", {}).get("online_cpus", 1)
        total_usage = cpu_usage.get("total_usage", 0)

        if system_cpu > 0:
            cpu_percent = round((total_usage / system_cpu) * online_cpus * 100.0, 2)

        mem_stats = raw.get("memory_stats", {})
        mem_usage = mem_stats.get("usage", 0)
        mem_limit = mem_stats.get("limit", 1)
        mem_percent = round((mem_usage / mem_limit) * 100.0, 2)

        networks = raw.get("networks", {})
        net_rx = sum(n.get("rx_bytes", 0) for n in networks.values())
        net_tx = sum(n.get("tx_bytes", 0) for n in networks.values())

        return {
            "container_id": container_id,
            "cpu_percent": cpu_percent,
            "memory_usage": mem_usage,
            "memory_limit": mem_limit,
            "memory_percent": mem_percent,
            "network_rx_bytes": net_rx,
            "network_tx_bytes": net_tx,
        }

    # ── 镜像操作 ──

    def list_images(self, name_filter: str | None = None) -> list[dict]:
        """列出镜像"""
        self._ensure_connected()
        images = self._client.images.list(name=name_filter)
        return [self._format_image(img) for img in images]

    def pull_image(self, image_name: str, tag: str | None = None) -> dict:
        """拉取镜像"""
        self._ensure_connected()
        try:
            image = self._client.images.pull(image_name, tag=tag or "latest")
            return {
                "success": True,
                "image": self._format_image(image),
                "message": f"Pulled {image_name}:{tag or 'latest'}",
            }
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    def remove_image(self, image_id: str, force: bool = False) -> dict:
        """删除镜像"""
        self._ensure_connected()
        try:
            self._client.images.remove(image_id, force=force)
            return {"success": True, "removed": image_id}
        except DockerNotFound:
            return {"success": False, "error": f"Image '{image_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    # ── 内部格式化方法 ──

    @staticmethod
    def _format_container(container) -> dict:
        return {
            "id": container.short_id,
            "name": container.name,
            "status": container.status,
            "image": container.image.tags[0] if container.image.tags else str(container.image.id[:12]),
        }

    @staticmethod
    def _format_container_detail(container) -> dict:
        return {
            "id": container.short_id,
            "name": container.name,
            "status": container.status,
            "image": container.image.tags[0] if container.image.tags else str(container.image.id[:12]),
            "created": container.attrs.get("Created", ""),
            "ports": container.attrs.get("NetworkSettings", {}).get("Ports", {}),
            "labels": container.labels,
        }

    @staticmethod
    def _format_image(image) -> dict:
        return {
            "id": image.short_id,
            "tags": image.tags,
            "size": image.attrs.get("Size", 0),
            "created": image.attrs.get("Created", ""),
        }
