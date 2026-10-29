# 测试报告 — 版本号单一数据源 / 剪贴板兜底

日期：2026-10-25
范围：`core/version.py` 版本号单一数据源、`web/static/clipboard.js` 非安全上下文复制兜底、
`/ui/about` 与 `/ui/users` 复制按钮、静态路由路径穿越防护。

---

## 1. 执行的命令

```bash
# 基线
python3 -m pytest tests/ -q

# 回归有效性验证（临时改业务代码 → 跑测试 → 还原并校验 sha256）
sha256sum web/routes.py web/static/clipboard.js            # 改动前快照
sed -i 's|^env.globals\["app_version"\] = VERSION$|# ...|' web/routes.py
python3 -m pytest tests/test_version_consistency.py -q
cp /tmp/opencode/regr/routes.py.bak web/routes.py && sha256sum -c ...

# 用「直接调用 navigator.clipboard.writeText」的朴素实现替换 clipboard.js
python3 -m pytest tests/e2e/test_about_copy.py -q
cp /tmp/opencode/regr/clipboard.js.bak web/static/clipboard.js && sha256sum -c ...

# 覆盖率（pytest-cov 未安装，使用 coverage.py）
python3 -m coverage run --source=core,web,tools,main --omit="*/tests/*" -m pytest tests/ -q
python3 -m coverage report -m

# 最终全量
python3 -m pytest tests/ -q
```

> 未运行 `scripts/` 下的脚本（需要真实服务）。未执行任何发布/构建命令，未提交 git。

## 2. 测试结果

| 阶段 | 结果 |
| --- | --- |
| 基线（改动前） | **149 passed**（40.35s） |
| 最终（新增测试后） | **157 passed**（52.35s） |
| 失败 / 跳过 / 报错 | 0 / 0 / 0 |

新增 8 个用例：`tests/e2e/test_about_copy.py` 2 → 7、`tests/test_version_consistency.py` 5 → 6、
`tests/test_e2e_web_ui.py` 33 → 35。

## 3. 回归有效性验证（关键：证明断言不是恒真）

### 3.1 版本号：注释掉 `env.globals["app_version"] = VERSION`

`web/routes.py:25` 被临时注释后：

```
FAILED tests/test_version_consistency.py::test_web_env_exposes_version
       AssertionError: assert None == '2.1.2'
FAILED tests/test_version_consistency.py::test_rendered_pages_show_current_version
       AssertionError: 导航栏未显示当前版本号
2 failed, 3 passed
```

✅ **有效**。两条断言分别从「环境注入」和「真实渲染结果」两个层面捕获回归，
后者是端到端意义上的用户可见症状（导航栏/关于页版本号变空）。
还原后 `sha256sum -c` 全部 OK。

### 3.2 剪贴板：把 `clipboard.js` 改回直接调用 `navigator.clipboard.writeText`

```js
function copyToClipboard(text) {
    return navigator.clipboard.writeText(text).then(function () { return true; });
}
```

```
FAILED test_copy_falls_back_without_clipboard_api
       Locator expected to have text '✅ 已复制'  Actual: 📋 复制
FAILED test_copy_resolves_false_when_write_text_throws_sync
FAILED test_copy_falls_back_when_write_text_rejects
FAILED test_copy_resolves_false_when_exec_command_fails
FAILED test_users_page_copy_works_on_insecure_http
5 failed, 1 passed        # 唯一通过的是安全上下文的 happy path
```

✅ **有效**。非安全上下文用例确实依赖 `execCommand` 兜底：去掉兜底后按钮停在「📋 复制」
（同步抛 TypeError，`.then` 根本没执行）。还原后 `sha256sum -c` 全部 OK。

### 3.3 附加验证：Web 层硬编码版本号守卫

临时在 `web/routes.py` 末尾追加 `_LEGACY_VERSION = "2.1.0"`：

```
FAILED tests/test_version_consistency.py::test_web_layer_has_no_hardcoded_version
       assert not ['web/routes.py:753: 2.1.0']
```

✅ 新增守卫有效（历史 bug 正是这一层写死了旧版本号）。已还原。

### 3.4 附带排查：静态路由穿越测试是否「被路由层提前 404」

用 ASGI 中间件抓 `scope["path"]` + `route.matches()` 复核：

```
sent=/ui/static/%2e%2e/templates/base.html
  asgi_path=['/ui/static/../templates/base.html'] status=404
MATCHED route: /ui/static/{path:path} path_params: {'path': '../templates/base.html'}
OUTSIDE static (guard blocks): .../web/templates/base.html
```

✅ 路由确实匹配、`path` 参数为 `../templates/base.html`，是 `resolve()/relative_to()`
守卫返回的 404，不是 Starlette 路由层的 404 —— 原测试**不是**恒真。
（注意：`http://.../ui/static/../x` 这种未编码写法会被 httpx/浏览器先规范化，
必须用 `%2e%2e` / `..%2f` 编码形式才能穿透到处理函数。）

## 4. 覆盖缺口与新增测试

### 4.1 已识别缺口

| 缺口 | 说明 |
| --- | --- |
| `copyToClipboard` 同步抛异常路径 | `writeText` 直接 throw 时外层 `catch` → `resolve(false)`，此前无用例 |
| `writeText` 返回 rejected Promise | 只会走到 `.then` 的失败分支 → `fallbackCopy`，此前该分支无覆盖（非安全上下文用例走的是 `clipboard === undefined` 分支） |
| `execCommand` 返回 false / 抛异常 | 兜底失败时 `resolve(false)` 与 UI「❌ 复制失败」，此前无覆盖 |
| `users.html` 复制按钮 | 仅 about 页有 E2E；用户页是同一 JS 的第二个调用点，回归风险独立 |
| Web 层硬编码版本号 | 原守卫只扫 `templates/*.html`，`web/routes.py`、`web/static/*.js` 写死版本号不会被发现 |
| 静态路由正向对照 | 只有 404 断言，缺少「子目录仍可访问」的正对照，守卫写过头也测不出来 |

### 4.2 新增用例

`tests/e2e/test_about_copy.py`（+5）
- `test_copy_resolves_false_when_write_text_throws_sync` — `writeText` 同步抛错 → `resolve(false)`、无 pageerror、UI 显示失败
- `test_copy_falls_back_when_write_text_rejects` — rejected Promise → 回退 `execCommand`、`resolve(true)`、复制的文本正确
- `test_copy_resolves_false_when_exec_command_fails` — `execCommand` 返回 false → `resolve(false)`
- `test_copy_resolves_false_when_exec_command_throws` — `execCommand` 抛异常 → 仍 `resolve(false)`、无未捕获异常
- `test_users_page_copy_works_on_insecure_http` — 用户页 API Key 复制在内网 HTTP 下可用，且复制的是该行 key
- 同时强化既有用例：`test_copy_falls_back_without_clipboard_api` 增加「兜底复制的文本是 MCP 配置」断言

`tests/test_version_consistency.py`（+1）
- `test_web_layer_has_no_hardcoded_version` — 扫描 `web/routes.py` 与 `web/static/**/*.js`

`tests/test_e2e_web_ui.py`（+2）
- `test_static_nested_asset_served` — 正对照：`/ui/static/assets/logo.jpg` 200
- `test_static_traversal_to_existing_file_blocked` — `/ui/static/..%2fmain.py` → 404 且不泄露内容

### 4.3 跳过项

无。`users.html` 渲染成本很低（只需 `user/keys/roles/csrf_token`，`keys` 用 dict 即可），
已按建议实现 E2E，未跳过。

## 5. 覆盖率（coverage.py 7.15.2，pytest-cov 未安装）

全量 `tests/` 统计（`--source=core,web,tools,main`）：

| 模块 | 覆盖率 | 备注 |
| --- | --- | --- |
| **TOTAL** | **61%** | 1934 语句 / 745 未覆盖 |
| `core/version.py` | **100%** | 单一数据源本体 |
| `core/audit.py` / `core/csrf.py` | 100% | |
| `core/admin_auth.py` | 92% | |
| `core/config.py` / `core/system_diag.py` | 91% | |
| `core/app_state.py` | 96% | |
| `core/auth.py` | 84% | |
| `main.py` | 68% | 启动/信号处理分支未被单测覆盖 |
| `web/routes.py` | **57%** | 未覆盖集中在 users/settings 的 POST 变更路由（`287-332`、`428-459`、`463-500`、`649-723`） |
| `tools/*` | 25%–92% | 工具层大量为 Docker 薄封装，需真实 Docker |

本次改动的三个函数行级覆盖（`web/routes.py`）：

| 函数 | 行范围 | 行覆盖 |
| --- | --- | --- |
| `about_page` | 209–216 | **5/5 (100%)** |
| `users_page` | 377–400 | **16/16 (100%)** |
| `static_file` | 727–751 | **15/15 (100%)** |

浏览器端 JS（`web/static/clipboard.js`）不计入 coverage.py；其分支由 7 个 E2E 行为覆盖：

| clipboard.js 分支 | 覆盖用例 |
| --- | --- |
| `clipboard` 不存在 → `fallbackCopy` | `test_copy_falls_back_without_clipboard_api` |
| `writeText` 成功 → `true` | `test_copy_writes_mcp_config_to_clipboard` |
| `writeText` 同步 throw → `resolve(false)` | `test_copy_resolves_false_when_write_text_throws_sync` |
| `writeText` reject → `fallbackCopy` | `test_copy_falls_back_when_write_text_rejects` |
| `execCommand` 成功 / 返回 false / 抛异常 | 兜底用例、`..._exec_command_fails`、`..._exec_command_throws` |
| 用户页第二个调用点 | `test_users_page_copy_works_on_insecure_http` |

## 6. 文件清单

新增：
- `docs/test-report.md`（本文件）

修改（仅测试）：
- `tests/e2e/test_about_copy.py`（fixture 泛化为 `site_urls`，+5 用例，新增 4 个 clipboard/execCommand 桩）
- `tests/test_version_consistency.py`（+1 用例：Web 层硬编码版本号守卫）
- `tests/test_e2e_web_ui.py`（+2 用例：静态子目录正对照、穿越到真实文件的守卫验证）

业务代码：**未修改**。`web/routes.py` 与 `web/static/clipboard.js` 仅用于临时回归探针，
已还原并通过 sha256 校验（`fca33b34…` / `29b0d26d…`）。

## 7. 结论

- 全量 157 passed，基线 149 无回归。
- 两个修复对应的测试均**能真实捕获回归**（版本号注入移除 → 2 失败；剪贴板兜底移除 → 5 失败），
  不是恒真断言；路径穿越测试经 ASGI 层复核确认命中守卫而非路由层 404。
- 补齐了 `copyToClipboard` 的失败路径契约（永不 reject、恒 resolve boolean）、用户页复制、
  Web 层版本号守卫与静态路由正对照共 8 个用例。
- 遗留低覆盖区（`web/routes.py` 的变更类 POST 路由、`tools/*`、`core/docker_client.py`）
  与本次修复无关，属既有缺口；如需提升建议后续为 users/settings 的增删改路由补 TestClient 用例。
