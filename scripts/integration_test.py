#!/usr/bin/env python3
"""
DockerMaintainer MCP Server 容器集成测试脚本
在本地启动容器，自动验证所有核心功能，无需人工介入。
"""
import subprocess
import sys
import time
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
IMAGE_TAG = "docker-mcp-server:latest"
TEST_PORT = 18900  # 用非标准端口避免冲突
API_KEY = "sk-dm-CHANGE-THIS-KEY-IMMEDIATELY"
TIMEOUT = 60


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, msg):
        print(f"  [PASS] {msg}")
        self.passed += 1

    def fail(self, msg):
        print(f"  [FAIL] {msg}")
        self.failed += 1
        self.errors.append(msg)


def run_cmd(cmd, capture=True):
    """运行 shell 命令"""
    result = subprocess.run(
        cmd, shell=True, capture_output=capture, text=True, cwd=PROJECT_ROOT
    )
    return result


def wait_for_health(port, timeout=30):
    """等待健康检查端口就绪"""
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(f"http://localhost:{port}/health")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            time.sleep(0.5)
    return None


def mcp_request(port, payload, session_id=None):
    """发送 MCP HTTP 请求"""
    import urllib.request
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"http://localhost:{port}/mcp",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {API_KEY}",
        },
    )
    if session_id:
        req.add_header("Mcp-Session-Id", session_id)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            # 解析 SSE 格式
            for line in body.split("\n"):
                if line.startswith("data: "):
                    return json.loads(line[6:])
            return json.loads(body)
    except urllib.error.HTTPError as e:
        return {"error": {"code": e.code, "message": e.read().decode()}}
    except Exception as e:
        return {"error": {"code": -1, "message": str(e)}}


def extract_session_id(headers_str):
    """从 curl -v 输出中提取 session ID"""
    for line in headers_str.split("\n"):
        if "mcp-session-id:" in line.lower():
            return line.split(":", 1)[1].strip()
    return None


def test_version_consistency():
    """测试版本号一致性"""
    print("\n[1/5] 检查版本号一致性...")
    r = TestResult()

    # 从 main.py 提取版本号
    main_py = (PROJECT_ROOT / "main.py").read_text()
    main_version = None
    for line in main_py.split("\n"):
        if 'version="' in line and "DockerMaintainer" not in line:
            m = re.search(r'version="([^"]+)"', line)
            if m:
                main_version = m.group(1)
                break

    # 从 health check 提取版本号
    health_version = None
    for line in main_py.split("\n"):
        if '"version"' in line:
            m = re.search(r'"version":\s*"([^"]+)"', line)
            if m:
                health_version = m.group(1)
                break

    if main_version and health_version and main_version == health_version:
        r.ok(f"main.py 和 health check 版本一致: {main_version}")
    else:
        r.fail(f"版本不一致! main.py={main_version}, health={health_version}")

    return r


def test_image_size():
    """测试镜像大小合理性"""
    print("\n[2/5] 检查镜像大小...")
    r = TestResult()

    result = run_cmd(f"docker images {IMAGE_TAG} --format '{{{{.Size}}}}'")
    size_str = result.stdout.strip()
    if not size_str:
        r.fail(f"镜像 {IMAGE_TAG} 不存在")
        return r

    # 解析大小（GB/MB）
    if "GB" in size_str:
        num = float(size_str.replace("GB", "").strip())
        if num > 1:
            r.fail(f"镜像过大: {size_str}（可能 .dockerignore 未排除大文件）")
        else:
            r.ok(f"镜像大小: {size_str}")
    else:
        r.ok(f"镜像大小: {size_str}")

    return r


def test_container_startup():
    """测试容器启动和功能"""
    print(f"\n[3/5] 启动容器并测试功能 (端口 {TEST_PORT})...")
    r = TestResult()
    container_name = "dm-test-container"

    # 清理可能残留的旧容器
    run_cmd(f"docker rm -f {container_name} >/dev/null 2>&1")

    # 启动容器
    cmd = (
        f"docker run -d --name {container_name} "
        f"-p {TEST_PORT}:8900 "
        f"-e PUID=1000 -e PGID=1000 "
        f"-v /var/run/docker.sock:/var/run/docker.sock:ro "
        f"{IMAGE_TAG}"
    )
    result = run_cmd(cmd)
    if result.returncode != 0:
        r.fail(f"容器启动失败: {result.stderr}")
        return r

    try:
        # 等待健康检查
        print("  等待容器就绪...")
        health = wait_for_health(TEST_PORT, timeout=30)
        if not health:
            r.fail("健康检查超时")
            return r

        if health.get("status") == "ok":
            r.ok(f"健康检查通过: {health}")
        else:
            r.fail(f"健康检查异常: {health}")

        # MCP Initialize
        init_resp = mcp_request(
            TEST_PORT,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )

        if init_resp.get("result", {}).get("serverInfo", {}).get("name") == "DockerMaintainer":
            version = init_resp["result"]["serverInfo"].get("version", "unknown")
            r.ok(f"MCP Initialize 成功, serverInfo.version={version}")
        else:
            r.fail(f"MCP Initialize 失败: {init_resp}")
            return r

        # 获取 session ID（需要用 curl -v 抓响应头）
        print("  获取 session ID...")
        curl_cmd = (
            f"curl -s -v -X POST http://localhost:{TEST_PORT}/mcp "
            f'-H "Content-Type: application/json" '
            f'-H "Accept: application/json, text/event-stream" '
            f'-H "Authorization: Bearer {API_KEY}" '
            f'-d \'{{"jsonrpc":"2.0","id":1,"method":"initialize","params":{{"protocolVersion":"2025-03-26","capabilities":{{}},"clientInfo":{{"name":"test","version":"1.0"}}}}}}\' '
            f"2>&1"
        )
        result = run_cmd(curl_cmd)
        session_id = extract_session_id(result.stdout)

        if not session_id:
            r.fail(f"无法获取 session ID: {result.stdout[:500]}")
            return r
        r.ok(f"获取 session ID: {session_id[:16]}...")

        # 调用 list_containers
        print("  测试 list_containers...")
        resp = mcp_request(
            TEST_PORT,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "list_containers", "arguments": {"all": True}},
            },
            session_id=session_id,
        )

        if resp.get("result") and not resp.get("error"):
            r.ok("list_containers 调用成功")
        elif resp.get("error"):
            r.fail(f"list_containers 失败: {resp['error']}")
        else:
            r.fail(f"list_containers 返回异常: {resp}")

        # 调用 get_system_info
        print("  测试 get_system_info...")
        resp = mcp_request(
            TEST_PORT,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "get_system_info", "arguments": {}},
            },
            session_id=session_id,
        )

        result_content = resp.get("result", {}).get("content", [])
        if result_content and "hostname" in str(result_content):
            r.ok("get_system_info 调用成功")
        elif resp.get("error"):
            r.fail(f"get_system_info 失败: {resp['error']}")
        else:
            r.fail(f"get_system_info 返回异常: {resp}")

    finally:
        # 清理容器
        run_cmd(f"docker rm -f {container_name} >/dev/null 2>&1")
        print("  测试容器已清理")

    return r


def test_dockerignore():
    """测试 .dockerignore 是否排除了大文件"""
    print("\n[4/5] 检查 .dockerignore...")
    r = TestResult()

    ignore = (PROJECT_ROOT / ".dockerignore").read_text()
    required = ["*.tar.gz", "config/", "secrets/", ".git", "__pycache__"]
    for item in required:
        if item in ignore:
            r.ok(f".dockerignore 包含: {item}")
        else:
            r.fail(f".dockerignore 缺少: {item}")

    return r


def test_entrypoint_permissions():
    """测试 entrypoint.sh 是否可执行"""
    print("\n[5/5] 检查 entrypoint.sh 权限...")
    r = TestResult()

    entrypoint = PROJECT_ROOT / "entrypoint.sh"
    if not entrypoint.exists():
        r.fail("entrypoint.sh 不存在")
        return r

    if entrypoint.stat().st_mode & 0o111:
        r.ok("entrypoint.sh 有执行权限")
    else:
        r.fail("entrypoint.sh 缺少执行权限")

    return r


def main():
    print("=" * 60)
    print("DockerMaintainer MCP Server 集成测试")
    print("=" * 60)

    # 先检查镜像是否存在
    result = run_cmd(f"docker images {IMAGE_TAG} -q")
    if not result.stdout.strip():
        print(f"\n[ERROR] 镜像 {IMAGE_TAG} 不存在，请先构建")
        sys.exit(1)

    results = [
        test_version_consistency(),
        test_image_size(),
        test_container_startup(),
        test_dockerignore(),
        test_entrypoint_permissions(),
    ]

    print("\n" + "=" * 60)
    total_passed = sum(r.passed for r in results)
    total_failed = sum(r.failed for r in results)
    print(f"测试结果: {total_passed} 通过, {total_failed} 失败")

    if total_failed > 0:
        print("\n失败项:")
        for r in results:
            for err in r.errors:
                print(f"  - {err}")
        sys.exit(1)
    else:
        print("\n[OK] 所有测试通过，可以导出镜像")
        sys.exit(0)


if __name__ == "__main__":
    main()
