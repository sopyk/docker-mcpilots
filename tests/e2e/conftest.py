"""
Playwright E2E 测试基础配置（由 project-audit-init 生成）
"""
import os
import pytest

@pytest.fixture(scope='session')
def base_url() -> str:
    """返回本地开发服务地址"""
    port = os.environ.get('PORT', '8900')
    return f'http://localhost:{port}'
