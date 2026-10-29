"""依赖锁定一致性守卫。

背景：之前之所以"代码没改、行为变了"，就是因为 requirements.txt
只做范围锁定，镜像构建时装到了新版 fastmcp（4.0.3 → 4.1.4），
其默认会把 HTTP 会话改成 30 分钟空闲过期。

现在 Docker 构建从 requirements.lock 安装，本测试确保：
1. requirements.txt 里声明的每个直接依赖，都以相同版本出现在 lock 中；
2. lock 没有重复包；
3. Dockerfile 确实从 lock 安装（而不是退回 requirements.txt）。
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"
LOCK = PROJECT_ROOT / "requirements.lock"
DOCKERFILE = PROJECT_ROOT / "docker" / "Dockerfile"

_PIN_RE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*==\s*([^\s;#]+)")


def _parse_pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _PIN_RE.match(stripped)
        if match:
            pins[match.group(1).lower()] = match.group(2)
    return pins


def test_requirements_are_exactly_pinned():
    """直接依赖必须精确锁定，不能再用范围（>=、<）"""
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        assert "==" in stripped, f"requirements.txt 必须精确锁定：{stripped!r}"


def test_lock_covers_every_direct_requirement():
    """requirements.txt 的每个 pin 都必须在 lock 中以同版本存在（防止改 txt 忘更 lock）"""
    direct = _parse_pins(REQUIREMENTS)
    locked = _parse_pins(LOCK)

    assert direct, "requirements.txt 解析为空"
    missing = {name: ver for name, ver in direct.items() if name not in locked}
    assert not missing, f"这些直接依赖没写进 requirements.lock：{missing}"

    drifted = {
        name: (ver, locked[name])
        for name, ver in direct.items()
        if name in locked and locked[name] != ver
    }
    assert not drifted, f"requirements.txt 与 lock 版本不一致：{drifted}"


def test_lock_has_no_duplicate_packages():
    names = []
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _PIN_RE.match(stripped)
        if match:
            names.append(match.group(1).lower())
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"requirements.lock 有重复条目：{duplicates}"


def test_lock_pins_the_packages_that_matter():
    """本次事故相关的传递依赖必须被锁死"""
    locked = _parse_pins(LOCK)
    for name in ("fastmcp", "mcp", "starlette", "uvicorn"):
        assert name in locked, f"{name} 必须出现在 requirements.lock"


def test_dockerfile_installs_from_lock():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "-r requirements.lock" in dockerfile, "Dockerfile 必须从 requirements.lock 安装"
    assert "-r requirements.txt" not in dockerfile, (
        "Dockerfile 不应再从未锁定的 requirements.txt 安装"
    )
