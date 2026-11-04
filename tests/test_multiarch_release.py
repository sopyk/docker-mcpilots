"""多架构镜像发布流程守卫（ROADMAP #6：linux/arm64 多架构镜像）。

背景：此前 Docker 镜像仅构建 linux/amd64（ARM 架构 NAS 无法运行），
ROADMAP #6 已完成 —— CI 新增 docker-build-arm64 job（ubuntu-24.04-arm 原生 runner
构建 + /health + MCP initialize smoke test），发布链路新增 release workflow
（docker buildx build --platform linux/amd64,linux/arm64 发布 manifest list）。

本测试确保：
1. CI 的 docker-build-arm64 job 存在，平台为 linux/arm64，且执行 /health + MCP initialize smoke test；
2. release workflow 构建 linux/amd64 + linux/arm64 并 push 到 ghcr.io；
3. ROADMAP.md 多架构项已标记完成，不再残留"仅 amd64"口径；
4. Dockerfile 基础镜像仍按 multi-arch digest 固定。
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CI_YML = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
RELEASE_YML = PROJECT_ROOT / ".github" / "workflows" / "release.yml"
ROADMAP_MD = PROJECT_ROOT / "ROADMAP.md"
DOCKERFILE = PROJECT_ROOT / "docker" / "Dockerfile"


def _load_workflow(path: Path) -> dict:
    """加载 GitHub workflow YAML（`on:` 在 YAML 1.1 下会被解析为布尔键，此处只取 jobs）"""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def _ci_jobs() -> dict:
    return _load_workflow(CI_YML).get("jobs") or {}


def _release_jobs() -> dict:
    return _load_workflow(RELEASE_YML).get("jobs") or {}


def _build_push_step(steps: list) -> dict:
    """从步骤列表中找出 docker/build-push-action 的步骤"""
    builds = [s for s in steps if (s.get("uses") or "").startswith("docker/build-push-action")]
    assert builds, "workflow 中缺少 docker/build-push-action 步骤"
    return builds[0]


# ──────────────────────────────────────────────────────────
# CI：docker-build-arm64 job
# ──────────────────────────────────────────────────────────

def test_ci_docker_build_arm64_job_exists():
    """CI 必须存在 docker-build-arm64 job（ubuntu-24.04-arm 原生 runner）"""
    jobs = _ci_jobs()
    assert "docker-build-arm64" in jobs, "CI 缺少 docker-build-arm64 job"
    job = jobs["docker-build-arm64"]
    assert job.get("runs-on") == "ubuntu-24.04-arm", (
        f"docker-build-arm64 应运行在 ubuntu-24.04-arm（原生 arm64 runner），实际: {job.get('runs-on')}"
    )
    assert job.get("needs") == "test", "docker-build-arm64 应在 test job 之后运行"


def test_ci_docker_build_arm64_builds_linux_arm64_only():
    """arm64 job 应构建 linux/arm64 镜像（push 不上云、load 到本地便于 smoke test）"""
    steps = _ci_jobs()["docker-build-arm64"].get("steps") or []
    build = _build_push_step(steps)
    with_ = build.get("with") or {}
    assert with_.get("platforms") == "linux/arm64", (
        f"docker-build-arm64 应只构建 linux/arm64，实际: {with_.get('platforms')}"
    )
    assert with_.get("push") is False, "arm64 CI 构建不应 push"
    assert with_.get("load") is True, "arm64 CI 构建应 load 到本地镜像便于 docker run"
    assert with_.get("tags") == "docker-mcpilots:arm64-test"
    assert (with_.get("context") or ".") == "."
    assert (with_.get("file") or "docker/Dockerfile") == "docker/Dockerfile"


def test_ci_docker_build_arm64_smoke_tests_health_and_mcp_initialize():
    """arm64 job 的 smoke test 必须覆盖 /health 与 MCP initialize（serverInfo）"""
    steps = _ci_jobs()["docker-build-arm64"].get("steps") or []
    smoke = [
        s
        for s in steps
        if s.get("uses") is None and (s.get("name") or "") == "MCP initialize smoke test"
    ]
    assert smoke, "docker-build-arm64 缺少 MCP initialize smoke test 步骤"
    run = smoke[0].get("run") or ""
    assert "dm-test-arm" in run, "smoke test 应针对 dm-test-arm 容器"
    assert "/health" in run, "smoke test 应校验 /health 健康检查"
    assert "initialize" in run, "smoke test 应执行 MCP initialize（serverInfo 校验）"


# ──────────────────────────────────────────────────────────
# release workflow：多架构构建
# ──────────────────────────────────────────────────────────

def test_release_build_multi_arch_job():
    """release workflow 的 build-multi-arch job 必须声明权限与运行环境"""
    jobs = _release_jobs()
    assert "build-multi-arch" in jobs, "release workflow 缺少 build-multi-arch job"
    job = jobs["build-multi-arch"]
    assert job.get("runs-on") == "ubuntu-latest"
    perms = job.get("permissions") or {}
    assert perms.get("contents") == "read"
    assert perms.get("packages") == "write"


def test_release_build_multi_arch_platforms_m_and_qemu_order():
    """release 应用 buildx + QEMU 构建 linux/amd64 + linux/arm64 并 push"""
    job = _release_jobs()["build-multi-arch"]
    steps = job.get("steps") or []
    uses = [s.get("uses") or "" for s in steps]
    assert "docker/setup-qemu-action@v3" in uses, "release 缺少 docker/setup-qemu-action（arm64 交叉编译必需）"
    assert "docker/setup-buildx-action@v3" in uses, "release 缺少 docker/setup-buildx-action"
    # QEMU 必须在 buildx 之前
    assert uses.index("docker/setup-qemu-action@v3") < uses.index("docker/setup-buildx-action@v3")

    build = _build_push_step(steps)
    with_ = build.get("with") or {}
    assert with_.get("platforms") == "linux/amd64,linux/arm64", (
        f"release 应构建 linux/amd64 + linux/arm64，实际: {with_.get('platforms')}"
    )
    assert with_.get("push") is True, "release 构建应 push 到 ghcr.io"
    assert with_.get("context") == "."
    assert with_.get("file") == "docker/Dockerfile"


def test_release_metadata_publishes_semver_and_latest():
    """release metadata 应输出 semver tag + latest，发布到 ghcr.io"""
    steps = _release_jobs()["build-multi-arch"].get("steps") or []
    meta = [s for s in steps if s.get("uses") == "docker/metadata-action@v5"]
    assert meta, "release workflow 缺少 docker/metadata-action@v5"
    with_ = meta[0].get("with") or {}
    images = with_.get("images") or ""
    assert "ghcr.io/sopyk/docker-mcpilots" in images
    tags = with_.get("tags") or ""
    assert "type=semver,pattern={{version}}" in tags, f"metadata tags 缺少 semver version tag: {tags!r}"
    assert "type=semver,pattern={{major}}.{{minor}" in tags, f"metadata tags 缺少 semver major.minor tag: {tags!r}"
    assert "type=raw,value=latest" in tags, f"metadata tags 缺少 latest tag: {tags!r}"


# ──────────────────────────────────────────────────────────
# Dockerfile / ROADMAP
# ──────────────────────────────────────────────────────────

def test_dockerfile_base_image_is_multiarch_digest():
    """Dockerfile 基础镜像应为含 amd64 + arm64 的 multi-arch digest 清单"""
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    froms = [
        line.strip()
        for line in dockerfile.splitlines()
        if line.strip().upper().startswith("FROM ")
    ]
    assert froms, "Dockerfile 中未找到 FROM 指令"
    for line in froms:
        assert "@sha256:" in line, f"基础镜像必须按 digest 固定（FROM ...@sha256:...）：{line}"
    # digest 固定 + manifest list：注释或指令应同时指向 amd64 / arm64
    assert "amd64" in dockerfile and "arm64" in dockerfile, (
        "Dockerfile 未体现 multi-arch（amd64 / arm64）基础镜像"
    )


def test_roadmap_multiarch_marked_completed():
    """ROADMAP #6 应标记已完成，且不再残留"仅构建 linux/amd64"的旧口径"""
    text = ROADMAP_MD.read_text(encoding="utf-8")
    assert "### 6. 多架构镜像（linux/arm64）✅ 已完成" in text, (
        "ROADMAP #6 应标注为 ✅ 已完成"
    )
    assert "仅构建" not in text, "ROADMAP 不应再有'仅构建 linux/amd64'的旧状态描述"
