#!/usr/bin/env python3
"""端到端测试 MCP Server - 模拟真实 MCP 客户端调用所有工具"""
import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8900/mcp"
API_KEY = "sk-dm-CHANGE-THIS-KEY-IMMEDIATELY"


class MCPClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.api_key = api_key
        self.session_id = None
        self._next_id = 0

    def _next_msg_id(self):
        self._next_id += 1
        return str(self._next_id)

    def _post(self, payload):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.base_url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Accept", "application/json, text/event-stream")
        if self.session_id:
            req.add_header("mcp-session-id", self.session_id)

        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read().decode("utf-8")
                sid = resp.headers.get("mcp-session-id")
                if sid:
                    self.session_id = sid
                return self._parse_sse(raw)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            sid = e.headers.get("mcp-session-id")
            if sid:
                self.session_id = sid
            print(f"  HTTP {e.code}: {body[:200]}")
            return None

    def _parse_sse(self, raw):
        for line in raw.strip().split("\n"):
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        try:
            return json.loads(raw)
        except Exception:
            return raw

    def initialize(self):
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_msg_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "e2e-test", "version": "1.0"},
            },
        }
        return self._post(payload)

    def initialized(self):
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        return self._post(payload)

    def list_tools(self):
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_msg_id(),
            "method": "tools/list",
        }
        return self._post(payload)

    def call_tool(self, name, arguments=None):
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_msg_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
        return self._post(payload)


def test_tool(client, name, args=None, expect_success=True):
    print(f"\n  [{name}]...", end=" ")
    resp = client.call_tool(name, args or {})
    if resp is None:
        print("❌ HTTP ERROR")
        return False
    if "error" in resp:
        print(f"❌ {resp['error']['message'][:80]}")
        return False
    result = resp.get("result", {})
    is_error = result.get("isError", False)
    content = result.get("content", [])

    # 工具层返回 {"success": false, "error": ...} 时 MCP 协议 isError 仍为 false
    # 需要解析内容判断业务层是否成功
    business_failed = False
    if content:
        text = content[0].get("text", "")
        try:
            parsed = json.loads(text) if text else {}
            if isinstance(parsed, dict) and parsed.get("success") is False:
                business_failed = True
        except (json.JSONDecodeError, ValueError):
            pass

    if is_error and expect_success:
        if content:
            print(f"❌ {content[0].get('text', '')[:80]}")
        else:
            print("❌ 未知错误")
        return False
    if not expect_success and not is_error and not business_failed:
        print("⚠️  意外成功")
        return False
    if expect_success and business_failed:
        if content:
            print(f"❌ 业务失败: {content[0].get('text', '')[:80]}")
        return False

    if business_failed and not expect_success:
        print(f"✅ 业务层返回失败（预期）")
        return True
    if content:
        text = content[0].get("text", "")
        preview = text[:60].replace("\n", " ")
        print(f"✅ {preview}...")
    else:
        sc = result.get("structuredContent", {})
        print(f"✅ (结构化数据, keys: {list(sc.keys())[:3]})")
    return True


def main():
    print("=" * 60)
    print("MCP Server 端到端测试")
    print("=" * 60)

    client = MCPClient(BASE_URL, API_KEY)

    # ── 握手 ──
    print("\n[1/5] MCP 握手...")
    init_resp = client.initialize()
    if init_resp and "result" in init_resp:
        info = init_resp["result"]["serverInfo"]
        print(f"  ✅ {info['name']} v{info['version']}")
    else:
        print("  ❌ 握手失败")
        return

    client.initialized()
    print("  ✅ initialized notification")

    # ── 工具列表 ──
    print("\n[2/5] 工具列表...")
    tools_resp = client.list_tools()
    tools = tools_resp["result"]["tools"]
    print(f"  ✅ 共 {len(tools)} 个工具:")
    for t in tools:
        print(f"    - {t['name']}")

    # ── 系统诊断工具 ──
    print("\n[3/5] 系统诊断工具测试...")
    diag_ok = 0
    diag_total = 0
    for tool in ["get_system_info", "get_cpu_info", "get_memory_info", "get_disk_info", "get_network_info"]:
        diag_total += 1
        if test_tool(client, tool):
            diag_ok += 1
    print(f"  结果: {diag_ok}/{diag_total} 通过")

    # ── 容器工具测试（本地有 Docker） ──
    print("\n[4/5] 容器工具测试...")
    cont_ok = 0
    cont_total = 0

    cont_total += 1
    if test_tool(client, "list_containers", {"status": "running"}):
        cont_ok += 1

    cont_total += 1
    if test_tool(client, "list_containers", {"all": True}):
        cont_ok += 1

    list_resp = client.call_tool("list_containers", {"all": True})
    result = list_resp.get("result", {})
    containers = []
    content = result.get("content", [])
    if content:
        text = content[0].get("text", "[]")
        containers = json.loads(text) if text else []
    if not containers:
        sc = result.get("structuredContent", {})
        if isinstance(sc, dict) and "result" in sc:
            containers = sc["result"]
        elif isinstance(sc, list):
            containers = sc

    if containers:
        cid = containers[0]["id"]
        cname = containers[0]["name"]
        print(f"\n  使用测试容器: {cname} ({cid[:12]})")

        for tool, args in [
            ("inspect_container", {"container_id": cid}),
            ("get_container_logs", {"container_id": cid, "tail": 5}),
            ("get_container_logs", {"container_id": cid, "tail": 5, "timestamps": True}),
            ("get_container_logs", {"container_id": cid, "since": "1h"}),
            ("get_container_stats", {"container_id": cid}),
            # 新增容器诊断工具
            ("get_container_processes", {"container_id": cid}),
            ("get_container_health", {"container_id": cid}),
            ("get_container_networks", {"container_id": cid}),
            ("get_container_mounts", {"container_id": cid}),
            ("get_container_changes", {"container_id": cid}),
        ]:
            cont_total += 1
            if test_tool(client, tool, args):
                cont_ok += 1
    else:
        print("\n  ⚠️  本地无容器，跳过部分容器测试")

    cont_total += 1
    if test_tool(client, "inspect_container", {"container_id": "nonexistent-12345"}, expect_success=False):
        cont_ok += 1

    cont_total += 1
    if test_tool(client, "get_container_logs", {"container_id": "nonexistent-12345"}, expect_success=False):
        cont_ok += 1

    cont_total += 1
    if test_tool(client, "get_container_stats", {"container_id": "nonexistent-12345"}, expect_success=False):
        cont_ok += 1

    print(f"\n  结果: {cont_ok}/{cont_total} 通过")

    # ── 镜像工具测试 ──
    print("\n[5/6] 镜像工具测试...")
    img_ok = 0
    img_total = 0

    img_total += 1
    if test_tool(client, "list_images"):
        img_ok += 1

    # 找一个真实镜像做 inspect_image
    list_resp = client.call_tool("list_images", {})
    result = list_resp.get("result", {})
    images = []
    content = result.get("content", [])
    if content:
        text = content[0].get("text", "[]")
        try:
            images = json.loads(text) if text else []
        except json.JSONDecodeError:
            images = []
    if images:
        first = images[0]
        ref = (first.get("tags") or [None])[0] or first.get("id")
        if ref:
            img_total += 1
            if test_tool(client, "inspect_image", {"image_name": ref}):
                img_ok += 1

    print(f"  结果: {img_ok}/{img_total} 通过")

    # ── Docker 资源诊断（网络/卷） ──
    print("\n[6/6] Docker 资源诊断测试...")
    res_ok = 0
    res_total = 0

    res_total += 1
    if test_tool(client, "list_networks"):
        res_ok += 1

    res_total += 1
    if test_tool(client, "list_volumes"):
        res_ok += 1

    print(f"  结果: {res_ok}/{res_total} 通过")

    # ── 汇总 ──
    total = diag_total + cont_total + img_total + res_total
    ok = diag_ok + cont_ok + img_ok + res_ok
    print("\n" + "=" * 60)
    print(f"总计: {ok}/{total} 通过")
    if ok == total:
        print("🎉 全部通过!")
    else:
        print(f"⚠️  {total - ok} 个失败")
    print("=" * 60)


if __name__ == "__main__":
    main()
