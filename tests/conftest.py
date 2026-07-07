"""pytest 全局配置 - 确保真实第三方模块优先导入

各测试模块顶部有条件性 mock（if 'xxx' not in sys.modules），
在模块已安装的环境中会被跳过。conftest.py 先于测试模块加载，
这里导入真实模块后，那些条件性 mock 就不会触发，
避免 e2e 测试中 TestClient 拿到 MagicMock。
"""
import fastmcp  # noqa: F401
import starlette  # noqa: F401
import psutil  # noqa: F401
