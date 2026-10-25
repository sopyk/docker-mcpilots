"""关于页 MCP 配置复制按钮 E2E 测试（真实 Chromium）。

覆盖 issue #1：内网 HTTP（非安全上下文）下 `navigator.clipboard` 为 undefined，
复制按钮必须走 `document.execCommand('copy')` 兜底，而不是同步抛 TypeError。

同时覆盖 `copyToClipboard` 的失败路径契约：无论 clipboard API 同步抛错、
返回 rejected Promise，还是 execCommand 返回 false，都只能 resolve 成 boolean，
绝不 reject（否则页面会出现未捕获异常）。以及用户页 API Key 复制的同款兜底。

不依赖运行中的 MCP 服务：测试内部用临时目录渲染模板并起一个本地 HTTP 服务。
"""
from __future__ import annotations

import shutil
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from jinja2 import Environment, FileSystemLoader  # noqa: E402
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import expect, sync_playwright  # noqa: E402

from core.version import VERSION  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = ROOT / "web" / "templates"
STATIC_DIR = ROOT / "web" / "static"

# 模拟非安全上下文（内网 HTTP）：navigator.clipboard 不存在
NO_CLIPBOARD_API = (
    "Object.defineProperty(navigator, 'clipboard', "
    "{value: undefined, configurable: true});"
)

# clipboard API 同步抛异常（部分浏览器/权限策略下 writeText 会直接 throw）
CLIPBOARD_THROWS_SYNC = """
Object.defineProperty(navigator, 'clipboard', {
    value: {writeText: function () { throw new Error('sync boom'); }},
    configurable: true
});
"""

# clipboard API 返回 rejected Promise（用户拒绝授权 / 文档未聚焦）
CLIPBOARD_REJECTS = """
Object.defineProperty(navigator, 'clipboard', {
    value: {writeText: function () { return Promise.reject(new Error('denied')); }},
    configurable: true
});
"""

# 探针：记录 execCommand('copy') 被调用、被复制的文本，并返回成功
# 避免依赖 CI 的剪贴板能力（headless 下 execCommand 结果不可靠）
EXEC_COMMAND_PROBE = """
window.__execCopyCalls = 0;
window.__lastCopiedText = null;
(function () {
    var original = document.execCommand.bind(document);
    document.execCommand = function (cmd) {
        if (cmd === 'copy') {
            window.__execCopyCalls += 1;
            // fallbackCopy 调用 execCommand 前已 select() 临时 textarea
            window.__lastCopiedText = document.activeElement
                ? document.activeElement.value
                : null;
            return true;
        }
        return original(cmd);
    };
})();
"""

# 探针：execCommand('copy') 抛异常（DOM 环境异常）
EXEC_COMMAND_THROWS = """
window.__execCopyCalls = 0;
(function () {
    var original = document.execCommand.bind(document);
    document.execCommand = function (cmd) {
        if (cmd === 'copy') {
            window.__execCopyCalls += 1;
            throw new Error('exec boom');
        }
        return original(cmd);
    };
})();
"""

# 探针：execCommand('copy') 返回 false（浏览器拒绝复制）
EXEC_COMMAND_FAILS = """
window.__execCopyCalls = 0;
(function () {
    var original = document.execCommand.bind(document);
    document.execCommand = function (cmd) {
        if (cmd === 'copy') {
            window.__execCopyCalls += 1;
            return false;
        }
        return original(cmd);
    };
})();
"""


class _QuietHandler(SimpleHTTPRequestHandler):
    """静默的静态文件服务，避免测试输出被访问日志淹没"""

    def log_message(self, *args):  # noqa: D401
        pass


@pytest.fixture(scope="module")
def site_urls(tmp_path_factory):
    """渲染关于页与用户页并返回其 HTTP 地址"""
    site = tmp_path_factory.mktemp("ui-site")
    ui_dir = site / "ui"
    ui_dir.mkdir()

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    env.globals["app_version"] = VERSION
    (ui_dir / "about.html").write_text(
        env.get_template("about.html").render(user=None), encoding="utf-8"
    )
    # users.html 所需变量很少（dict 即可），可低成本覆盖「内网 HTTP 复制 API Key」场景
    (ui_dir / "users.html").write_text(
        env.get_template("users.html").render(
            user="admin",
            keys=[{
                "name": "test-key",
                "role": "admin",
                "key": "sk-dm-0123456789abcdef",
                "scope_include": "",
                "scope_exclude": "",
            }],
            roles=[],
            csrf_token="test-csrf-token",
            error="",
            success="",
        ),
        encoding="utf-8",
    )

    try:
        (ui_dir / "static").symlink_to(STATIC_DIR, target_is_directory=True)
    except OSError:  # Windows 无符号链接权限
        shutil.copytree(STATIC_DIR, ui_dir / "static")

    handler = partial(_QuietHandler, directory=str(site))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        yield {
            "origin": origin,
            "about": f"{origin}/ui/about.html",
            "users": f"{origin}/ui/users.html",
        }
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(scope="module")
def about_url(site_urls):
    """关于页地址（兼容既有用例）"""
    return site_urls["about"]


@pytest.fixture(scope="module")
def chromium():
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except PlaywrightError as exc:  # 未执行 playwright install chromium
            pytest.skip(f"Chromium 不可用，跳过 E2E: {exc}")
        try:
            yield browser
        finally:
            browser.close()


def test_copy_falls_back_without_clipboard_api(chromium, about_url):
    """非安全上下文（内网 HTTP）：走 execCommand 兜底，不抛异常，提示复制成功"""
    context = chromium.new_context()
    context.add_init_script(NO_CLIPBOARD_API + EXEC_COMMAND_PROBE)
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        page.goto(about_url)
        assert page.evaluate("typeof navigator.clipboard") == "undefined"
        assert page.evaluate("typeof window.copyToClipboard") == "function"

        btn = page.locator(".copy-btn")
        btn.click()

        expect(btn).to_have_text("✅ 已复制")
        assert page.evaluate("window.__execCopyCalls") == 1, "未走 execCommand 兜底"
        copied = page.evaluate("window.__lastCopiedText")
        assert copied and '"mcpServers"' in copied, "兜底复制的文本不是 MCP 配置"
        assert errors == [], f"复制过程抛出页面异常: {errors}"
    finally:
        context.close()


def test_copy_writes_mcp_config_to_clipboard(chromium, about_url):
    """安全上下文：剪贴板内容应为完整的 MCP 配置 JSON"""
    origin = about_url.split("/ui/")[0]
    context = chromium.new_context()
    context.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        page.goto(about_url)
        btn = page.locator(".copy-btn")
        btn.click()

        expect(btn).to_have_text("✅ 已复制")
        assert errors == []

        copied = page.evaluate("navigator.clipboard.readText()")
        assert '"mcpServers"' in copied
        assert '"docker-mcpilots"' in copied
        assert "@modelcontextprotocol/transport-http" in copied
    finally:
        context.close()


def test_copy_resolves_false_when_write_text_throws_sync(chromium, site_urls):
    """clipboard.writeText 同步抛异常：copyToClipboard 不得 reject，应 resolve(false)"""
    context = chromium.new_context()
    context.add_init_script(CLIPBOARD_THROWS_SYNC)
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        page.goto(site_urls["about"])

        result = page.evaluate("copyToClipboard('hello')")
        assert result is False, f"同步抛错应 resolve(false)，实际 {result!r}"

        btn = page.locator(".copy-btn")
        btn.click()
        expect(btn).to_have_text("❌ 复制失败")
        assert errors == [], f"复制过程抛出未捕获异常: {errors}"
    finally:
        context.close()


def test_copy_falls_back_when_write_text_rejects(chromium, site_urls):
    """clipboard.writeText 返回 rejected Promise：回退 execCommand，最终 resolve(true)"""
    context = chromium.new_context()
    context.add_init_script(CLIPBOARD_REJECTS + EXEC_COMMAND_PROBE)
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        page.goto(site_urls["about"])

        result = page.evaluate("copyToClipboard('hello')")
        assert result is True, f"writeText 拒绝后应回退成功，实际 {result!r}"
        assert page.evaluate("window.__execCopyCalls") == 1, "writeText 拒绝后未回退 execCommand"
        assert page.evaluate("window.__lastCopiedText") == "hello"

        btn = page.locator(".copy-btn")
        btn.click()
        expect(btn).to_have_text("✅ 已复制")
        assert errors == [], f"复制过程抛出未捕获异常: {errors}"
    finally:
        context.close()


def test_copy_resolves_false_when_exec_command_fails(chromium, site_urls):
    """非安全上下文 + execCommand 返回 false：resolve(false)，UI 提示复制失败"""
    context = chromium.new_context()
    context.add_init_script(NO_CLIPBOARD_API + EXEC_COMMAND_FAILS)
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        page.goto(site_urls["about"])
        assert page.evaluate("typeof navigator.clipboard") == "undefined"

        result = page.evaluate("copyToClipboard('hello')")
        assert result is False, f"execCommand 失败应 resolve(false)，实际 {result!r}"
        assert page.evaluate("window.__execCopyCalls") == 1

        btn = page.locator(".copy-btn")
        btn.click()
        expect(btn).to_have_text("❌ 复制失败")
        assert errors == [], f"复制过程抛出未捕获异常: {errors}"
    finally:
        context.close()


def test_users_page_copy_works_on_insecure_http(chromium, site_urls):
    """用户页 API Key 复制按钮在内网 HTTP（非安全上下文）下同样可用"""
    context = chromium.new_context()
    context.add_init_script(NO_CLIPBOARD_API + EXEC_COMMAND_PROBE)
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        page.goto(site_urls["users"])
        assert page.evaluate("typeof navigator.clipboard") == "undefined"
        assert page.evaluate("typeof window.copyToClipboard") == "function"

        btn = page.locator(".btn-copy").first
        btn.click()

        expect(btn).to_have_text("已复制!")
        assert page.evaluate("window.__execCopyCalls") == 1, "未走 execCommand 兜底"
        assert page.evaluate("window.__lastCopiedText") == "sk-dm-0123456789abcdef", (
            "复制的不是该行的 API Key"
        )
        assert errors == [], f"复制过程抛出页面异常: {errors}"
    finally:
        context.close()


def test_copy_resolves_false_when_exec_command_throws(chromium, site_urls):
    """execCommand 抛异常（DOM 环境异常）：兜底内部捕获，仍 resolve(false)"""
    context = chromium.new_context()
    context.add_init_script(NO_CLIPBOARD_API + EXEC_COMMAND_THROWS)
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        page.goto(site_urls["about"])

        result = page.evaluate("copyToClipboard('hello')")
        assert result is False, f"execCommand 抛异常应 resolve(false)，实际 {result!r}"
        assert page.evaluate("window.__execCopyCalls") == 1, "未进入 execCommand 兜底路径"

        btn = page.locator(".copy-btn")
        btn.click()
        expect(btn).to_have_text("❌ 复制失败")
        assert errors == [], f"兜底逻辑未捕获异常: {errors}"
    finally:
        context.close()
