"""Docker SDK 封装 - 统一 Docker 容器和镜像操作的接口层"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

try:
    import docker
    from docker.errors import NotFound as DockerNotFound, APIError as DockerAPIError
except ImportError:
    docker = None
    DockerNotFound = Exception
    DockerAPIError = Exception


def _parse_since_until(value: str) -> datetime | None:
    """把 since/until 字符串解析成 datetime。

    支持格式：
    - RFC3339: "2026-07-04T00:00:00" / "2026-07-04T00:00:00Z"
    - 相对时间: "1h" / "30m" / "2d"（向前推 N 时间）
    """
    if not value:
        return None

    # 相对时间格式：数字 + 单位（s/m/h/d）
    if len(value) >= 2 and value[-1] in "smhd" and value[:-1].isdigit():
        n = int(value[:-1])
        delta = {"s": timedelta(seconds=n), "m": timedelta(minutes=n),
                 "h": timedelta(hours=n), "d": timedelta(days=n)}[value[-1]]
        return datetime.now(timezone.utc) - delta

    # RFC3339 / ISO 格式
    try:
        # 兼容带 Z 结尾的时间
        v = value.replace("Z", "+00:00") if value.endswith("Z") else value
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _extract_mounts(attrs: dict) -> list[dict]:
    """从容器 attrs 提取挂载信息"""
    mounts = []
    for m in attrs.get("Mounts", []):
        mounts.append({
            "type": m.get("Type", ""),
            "source": m.get("Source", ""),
            "destination": m.get("Destination", ""),
            "mode": m.get("Mode", ""),
            "rw": m.get("RW", True),
            "name": m.get("Name", ""),
            "driver": m.get("Driver", ""),
        })
    return mounts


def _extract_health(state: dict) -> dict:
    """从容器 state 提取健康检查信息"""
    health = state.get("Health", {})
    if not health:
        return {"status": "none", "failing_streak": 0, "log": []}
    return {
        "status": health.get("Status", "none"),
        "failing_streak": health.get("FailingStreak", 0),
        "log": [
            {
                "start": e.get("Start", ""),
                "end": e.get("End", ""),
                "exit_code": e.get("ExitCode", 0),
                "output": e.get("Output", ""),
            }
            for e in health.get("Log", [])
        ],
    }


def _change_kind_str(kind: int) -> str:
    """Docker 文件变更类型 0/1/2 转可读字符串"""
    return {0: "modified", 1: "added", 2: "deleted"}.get(kind, f"unknown({kind})")


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
            self._client = docker.DockerClient(base_url=f"unix://{self._socket_path}")

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
        try:
            container = self._client.containers.get(container_id)
            return self._format_container_detail(container)
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

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
        self,
        container_id: str,
        tail: int | None = None,
        since: str | None = None,
        until: str | None = None,
        timestamps: bool = False,
    ) -> dict:
        """获取容器日志（支持时间范围过滤和时间戳）"""
        self._ensure_connected()
        try:
            container = self._client.containers.get(container_id)
            kwargs = {"stdout": True, "stderr": True, "timestamps": timestamps}
            if tail is not None:
                kwargs["tail"] = str(tail)
            if since:
                parsed = _parse_since_until(since)
                if parsed is not None:
                    kwargs["since"] = parsed
            if until:
                parsed = _parse_since_until(until)
                if parsed is not None:
                    kwargs["until"] = parsed
            logs = container.logs(**kwargs)
            return {
                "success": True,
                "container_id": container_id,
                "logs": logs.decode("utf-8", errors="replace") if isinstance(logs, bytes) else str(logs),
            }
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    def get_container_stats(self, container_id: str) -> dict:
        """获取容器实时资源统计（单次采样）"""
        self._ensure_connected()
        try:
            container = self._client.containers.get(container_id)
            raw = container.stats(stream=False)

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
                "success": True,
                "container_id": container_id,
                "cpu_percent": cpu_percent,
                "memory_usage": mem_usage,
                "memory_limit": mem_limit,
                "memory_percent": mem_percent,
                "network_rx_bytes": net_rx,
                "network_tx_bytes": net_tx,
            }
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

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

    def remove_image(self, image_name: str, force: bool = False) -> dict:
        """删除镜像"""
        self._ensure_connected()
        try:
            self._client.images.remove(image_name, force=force)
            return {"success": True, "removed": image_name}
        except DockerNotFound:
            return {"success": False, "error": f"Image '{image_name}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    # ── 容器诊断 ──

    def get_container_processes(self, container_id: str) -> dict:
        """获取容器内运行的进程列表"""
        self._ensure_connected()
        try:
            container = self._client.containers.get(container_id)
            processes = container.top()
            return {
                "success": True,
                "container_id": container_id,
                "titles": processes.get("Titles", []),
                "processes": processes.get("Processes", []),
            }
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    def get_container_health(self, container_id: str) -> dict:
        """获取容器健康检查状态（排查"容器为什么不健康"）"""
        self._ensure_connected()
        try:
            container = self._client.containers.get(container_id)
            state = container.attrs.get("State", {})
            health = state.get("Health", {})
            return {
                "success": True,
                "container_id": container_id,
                "status": health.get("Status", "none"),
                "failing_streak": health.get("FailingStreak", 0),
                "log": [
                    {
                        "start": e.get("Start", ""),
                        "end": e.get("End", ""),
                        "exit_code": e.get("ExitCode", 0),
                        "output": e.get("Output", ""),
                    }
                    for e in health.get("Log", [])
                ],
            }
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    def get_container_networks(self, container_id: str) -> dict:
        """获取容器网络详情（排查"容器连不上网"）"""
        self._ensure_connected()
        try:
            container = self._client.containers.get(container_id)
            container.reload()
            net_settings = container.attrs.get("NetworkSettings", {})
            networks = {}
            for name, n in net_settings.get("Networks", {}).items():
                networks[name] = {
                    "ip": n.get("IPAddress", ""),
                    "gateway": n.get("Gateway", ""),
                    "mac": n.get("MacAddress", ""),
                    "dns": n.get("DNSNames", []),
                }
            return {
                "success": True,
                "container_id": container_id,
                "ip_address": net_settings.get("IPAddress", ""),
                "ports": net_settings.get("Ports", {}),
                "networks": networks,
            }
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    def get_container_mounts(self, container_id: str) -> dict:
        """获取容器挂载卷详情（排查"数据丢失/权限不对"）"""
        self._ensure_connected()
        try:
            container = self._client.containers.get(container_id)
            mounts = _extract_mounts(container.attrs)
            return {
                "success": True,
                "container_id": container_id,
                "mounts": mounts,
            }
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    def get_container_changes(self, container_id: str) -> dict:
        """获取容器文件系统变更（排查"容器里改了什么"）"""
        self._ensure_connected()
        try:
            container = self._client.containers.get(container_id)
            # Docker SDK for Python 的方法名是 diff()，对应 /containers/{id}/changes API
            # 注意：某些 Docker 版本/平台下 diff() 可能返回 None，需兜底
            changes = container.diff() or []
            return {
                "success": True,
                "container_id": container_id,
                "changes": [
                    {"path": c.get("Path", ""), "kind": _change_kind_str(c.get("Kind", 0))}
                    for c in changes
                ],
            }
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    # ── 网络管理 ──

    def list_networks(self) -> list[dict]:
        """列出所有 Docker 网络"""
        self._ensure_connected()
        networks = self._client.networks.list()
        return [
            {
                "id": n.short_id,
                "name": n.name,
                "driver": n.attrs.get("Driver", ""),
                "scope": n.attrs.get("Scope", ""),
                "subnet": n.attrs.get("IPAM", {}).get("Config", [{}])[0].get("Subnet", "") if n.attrs.get("IPAM", {}).get("Config") else "",
                "containers": list(n.attrs.get("Containers", {}).values()),
            }
            for n in networks
        ]

    # ── 卷管理 ──

    def list_volumes(self) -> list[dict]:
        """列出所有 Docker 卷"""
        self._ensure_connected()
        volumes = self._client.volumes.list()
        return [
            {
                "name": v.name,
                "driver": v.attrs.get("Driver", ""),
                "mountpoint": v.attrs.get("Mountpoint", ""),
                "created": v.attrs.get("CreatedAt", ""),
                "size": v.attrs.get("Options", {}).get("size", ""),
                "in_use": v.attrs.get("InUse", False),
            }
            for v in volumes
        ]

    # ── 镜像诊断 ──

    def inspect_image(self, image_name: str) -> dict:
        """获取镜像详细信息（排查"镜像有没有问题"）"""
        self._ensure_connected()
        try:
            image = self._client.images.get(image_name)
            attrs = image.attrs
            config = attrs.get("Config", {})
            return {
                "success": True,
                "id": image.short_id,
                "tags": image.tags,
                "size": attrs.get("Size", 0),
                "created": attrs.get("Created", ""),
                "architecture": attrs.get("Architecture", ""),
                "os": attrs.get("Os", ""),
                "config": {
                    "cmd": config.get("Cmd"),
                    "entrypoint": config.get("Entrypoint"),
                    "env": config.get("Env", []),
                    "working_dir": config.get("WorkingDir", ""),
                    "user": config.get("User", ""),
                    "exposed_ports": config.get("ExposedPorts", {}),
                    "volumes": config.get("Volumes"),
                    "labels": config.get("Labels", {}),
                },
                "history": [
                    {"created": h.get("Created", ""), "created_by": h.get("CreatedBy", "")[:100]}
                    for h in attrs.get("History", [])
                ],
            }
        except DockerNotFound:
            return {"success": False, "error": f"Image '{image_name}' not found"}
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
        attrs = container.attrs or {}
        state = attrs.get("State", {})
        config = attrs.get("Config", {})
        net_settings = attrs.get("NetworkSettings", {})

        return {
            "id": container.short_id,
            "name": container.name,
            "status": container.status,
            "image": container.image.tags[0] if container.image.tags else str(container.image.id[:12]),
            "created": attrs.get("Created", ""),
            "labels": container.labels,
            # 诊断关键字段
            "state": {
                "status": state.get("Status", ""),
                "running": state.get("Running", False),
                "paused": state.get("Paused", False),
                "restarting": state.get("Restarting", False),
                "oom_killed": state.get("OOMKilled", False),
                "dead": state.get("Dead", False),
                "pid": state.get("Pid", 0),
                "exit_code": state.get("ExitCode", 0),
                "error": state.get("Error", ""),
                "started_at": state.get("StartedAt", ""),
                "finished_at": state.get("FinishedAt", ""),
                "restart_count": state.get("RestartCount", 0),
            },
            "health": _extract_health(state),
            "config": {
                "cmd": config.get("Cmd"),
                "entrypoint": config.get("Entrypoint"),
                "env": config.get("Env", []),
                "image": config.get("Image", ""),
                "working_dir": config.get("WorkingDir", ""),
            },
            "network": {
                "ip_address": net_settings.get("IPAddress", ""),
                "gateway": net_settings.get("Gateway", ""),
                "mac_address": net_settings.get("MacAddress", ""),
                "ports": net_settings.get("Ports", {}),
                "networks": {
                    name: {"ip": n.get("IPAddress", ""), "gateway": n.get("Gateway", ""), "mac": n.get("MacAddress", "")}
                    for name, n in net_settings.get("Networks", {}).items()
                },
            },
            "mounts": _extract_mounts(attrs),
        }

    @staticmethod
    def _format_image(image) -> dict:
        return {
            "id": image.short_id,
            "tags": image.tags,
            "size": image.attrs.get("Size", 0),
            "created": image.attrs.get("Created", ""),
        }
