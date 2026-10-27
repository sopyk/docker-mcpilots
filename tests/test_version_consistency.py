"""版本号单一数据源一致性测试。

历史问题：`about.html` 曾长期停在旧版本号（ROADMAP #3 / issue #2）。
现在版本号只允许定义在 `core/version.py`，模板通过 `{{ app_version }}` 注入，
本测试用于阻止版本号在别处被重新硬编码。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from core.version import VERSION
from web.routes import env as web_env

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "web" / "templates"
WEB_DIR = ROOT / "web"
MAIN_PY = ROOT / "main.py"

# 匹配 x.y.z / vx.y.z，支持 -rc.1 之类预发布后缀，但排除 IP 地址（如 0.0.0.0）
VERSION_RE = re.compile(
    r"(?<![\d.])v?\d+\.\d+\.\d+(?:-[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*)?(?![\d.])"
)


def test_version_format():
    """版本号必须是 x.y.z 形式"""
    assert VERSION_RE.fullmatch(VERSION), f"版本号格式不合法: {VERSION!r}"


def test_web_env_exposes_version():
    """真实 Jinja 环境必须注入 app_version（防止模板渲染出空版本号）"""
    assert web_env.globals.get("app_version") == VERSION


def test_templates_have_no_hardcoded_version():
    """模板中不允许出现硬编码版本号，应使用 {{ app_version }}"""
    offenders = []
    for tpl in sorted(TEMPLATE_DIR.glob("*.html")):
        for lineno, line in enumerate(tpl.read_text(encoding="utf-8").splitlines(), 1):
            for match in VERSION_RE.finditer(line):
                offenders.append(f"{tpl.name}:{lineno}: {match.group(0)}")
    assert not offenders, (
        "模板中出现硬编码版本号，请改用 {{ app_version }}：\n" + "\n".join(offenders)
    )


def test_rendered_pages_show_current_version():
    """使用真实环境渲染后，导航栏与关于页都显示当前版本号"""
    base_html = web_env.get_template("base.html").render(user=None)
    about_html = web_env.get_template("about.html").render(user=None)

    assert f"v{VERSION}" in base_html, "导航栏未显示当前版本号"
    assert f"v{VERSION}" in about_html, "关于页未显示当前版本号"


def test_main_py_uses_version_constant():
    """main.py 的 FastMCP 元信息引用单一数据源，且不存在硬编码版本号"""
    src = MAIN_PY.read_text(encoding="utf-8")
    tree = ast.parse(src)

    fastmcp_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "FastMCP"
    ]
    assert fastmcp_calls, "main.py 中未找到 FastMCP(...) 调用"
    for call in fastmcp_calls:
        version_kwargs = [kw for kw in call.keywords if kw.arg == "version"]
        assert version_kwargs, "FastMCP 未显式传入 version"
        for kw in version_kwargs:
            assert isinstance(kw.value, ast.Name) and kw.value.id == "VERSION", (
                "FastMCP 的 version 必须引用 core.version.VERSION"
            )

    literals = [m.group(0) for m in VERSION_RE.finditer(src)]
    assert not literals, f"main.py 中出现硬编码版本号: {literals}"


def test_web_layer_has_no_hardcoded_version():
    """Web 层（routes.py 与 static/*.js）也不允许硬编码版本号

    历史 bug 正是发生在这一层（about.html 硬编码了旧版本号）。模板已有守卫，
    这里补上路由与前端脚本的守卫，防止有人绕开 `{{ app_version }}` 直接写死。
    """
    candidates = [WEB_DIR / "routes.py", *sorted((WEB_DIR / "static").rglob("*.js"))]
    assert candidates[0].exists(), "web/routes.py 不存在，测试路径已失效"

    offenders = []
    for f in candidates:
        for lineno, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for match in VERSION_RE.finditer(line):
                offenders.append(f"{f.relative_to(ROOT)}:{lineno}: {match.group(0)}")
    assert not offenders, (
        "Web 层出现硬编码版本号，请引用 core.version.VERSION / {{ app_version }}：\n"
        + "\n".join(offenders)
    )
