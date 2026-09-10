# Contributing to JMComic AI

感谢你对 JMComic AI 的关注！我们欢迎各种形式的贡献。

## 开发环境搭建

### 前置条件

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (推荐) 或 pip

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/hect0x7/jmcomic-ai.git
cd jmcomic-ai

# 2. 使用 uv 同步依赖 (创建虚拟环境并安装所有开发依赖)
uv sync

# 3. 安装 pre-commit hooks (可选但推荐，用于自动执行代码规范检查)
uv run pre-commit install

# 4. 获取参考源码 (可选，用于辅助开发)
# 推荐将 jmcomic 源码克隆到 reference/jmcomic_src
git clone --depth 1 https://github.com/hect0x7/JMComic-Crawler-Python.git reference/jmcomic_src
```

## 📂 项目结构说明

- `src/jmcomic_ai`: 核心代码目录。
- `reference/`: **开发参考源码库**。
    - **作用**：由于 `jmcomic` 上游库更新频繁且逻辑复杂，为了方便开发者在没有互联网或需要快速查阅底层实现时进行调试方案设计，项目包含了上游库的源码副本。
    - **使用方式**：如果你在开发 MCP Tool 时不确定 `jmcomic` 某个实体的属性（如 `JmAlbumDetail` 有哪些字段），直接查阅 `reference/jmcomic_src/` 下的代码。
    - **注意**：此处代码**仅供参考**，修改它不会影响运行时行为（运行时使用的是 PyPI 依赖包）。
- `tests/`: 测试用例，包含 MCP 协议集成测试。
- `src/jmcomic_ai/skills/`: AI 技能手册与资源定义。

## 开发工作流

### 分支策略与命名规范

- `master`: 稳定主分支，仅用于正式发布
- `dev`: 开发主分支，日常功能与修复合并在此进行
- `feat/*` 或 `feature/*`: 新功能分支
- `fix/*`: 问题修复分支

### 提交代码

#### 1. 开发与提交流程

1. **Fork 本仓库**，并在你自己 Fork 的仓库页面启用 GitHub Actions。
2. **规范分支命名**：基于上游对应分支拉取最新代码并创建本地开发分支。**推荐按规范命名为 `feat/*`、`feature/*`、`fix/*` 或直接使用 `dev`**（推送到你的 Fork 时会自动触发 Actions 运行全平台测试与 MyPy 检查，便于在提 PR 前及早发现问题）。
3. **在 Fork 中验证**：将分支推送到自己的 Fork (`git push origin feat/xxx`)，进入 Fork 的 Actions 页面确认 `Run Tests`（全平台）和 `Run Mypy Checks` 全部通过；若使用了其他分支名未自动触发，可在 Actions 页面手动点击 `Run workflow` 运行。
4. **发起 Pull Request**：
   - 向官方仓库发起 PR，目标分支根据下表选择；
   - 在 PR 描述中说明是否准备随本次贡献发版，并附上 Fork 中的 CI 运行链接。

#### 2. PR 目标分支选择（由你决定是否随本次贡献发版）

贡献者可以**自行决定是否随本次贡献发布新版本**，不同的选择对应不同的责任分工：

- **只想改代码，不想操心发版（推荐大多数贡献者）👉 目标分支选 `dev`**：
  你只需专注于代码逻辑、测试用例和文档本身，**完全无需关心版本号和发版事宜**。改动合并后，后续由项目维护者统一规划版本、整理更新日志并择期发版。
- **希望改动合并后立即发布新版本 👉 目标分支选 `master`**：
  如果你希望本次 PR 合并后立即发布到 PyPI，则需要**承担起完整的发版准备责任**，确保 PR 中已按规范完成版本号递增、更新日志编写与锁文件校验（详见下方[发版准备](#发版准备)）。

| 目标分支 | 你的责任分工 | 适用场景 |
| :--- | :--- | :--- |
| **`dev`**（默认推荐） | **仅关注代码本身**：完成功能或修复并补充测试，不修改版本号，发版交给维护者。 | 绝大多数日常功能添加、Bug 修复、文档改进 |
| **`master`** | **承担发版全套准备**：除代码外，一并完成版本号提升、Changelog、锁文件及构建验证。 | 贡献者明确需要改动合并后立即发布新版本 |

#### 3. PR 检查与自动发布机制

- **自动 CI 检查**：
  - 无论目标是 `master` 还是 `dev`，在创建 PR、追加提交或重新打开 PR 时，都会自动运行全平台测试与 MyPy 检查（首次贡献者的 Actions 可能需维护者手动批准后运行）。
  - 该检查验证的是模拟合并后的代码，不会触发发布，也不能替代提交前在个人 Fork 中的自测。
- **发布触发规则**：
  - 推送到 `dev` 或创建 PR 均不会触发发布，**发布仅在代码合并到 `master` 分支后触发**。
  - **合并发版 PR 时的命名要求**：合并到 `master` 后的**最新提交标题必须符合 `v{version}: 摘要`**，且版本号必须与源码一致：
    - **Squash merge**：将最终的 Squash 提交标题填写为该格式；
    - **Merge commit**：将合并提交标题填写为该格式；
    - **Rebase merge**：确保 PR 的最后一条提交为该格式的发版提交；
    - *注意：仅在 PR 中间包含发版提交、或只在网页上修改 PR 标题，均无法触发自动发布。*
  - **维护者发版流程**：维护者从 `dev` 发版时，先在 `dev` 分支完成发版准备并验证，再发起 `dev` → `master` 的 PR 进行合并发布。

### 代码规范

我们使用以下工具来保证代码质量：

- **ruff**: 代码风格检查与自动修复
- **mypy**: 静态类型检查

运行检查：

```bash
# Linting
uv run ruff check src/

# Type checking
uv run mypy src/
```

### 单元测试与集成测试

```bash
# 运行所有验证测试
uv run python -m unittest discover tests

# 运行 MCP 集成测试 (会启动真实的 MCP Server 并模拟 Client 连接)
uv run python tests/test_mcp_integration.py
```

## 构建与本地验证

在准备发布或需要完全模拟安装环境时，可以执行本地构建与安装验证：

### 1. 构建包

使用 `uv` 构建分发包（wheel 和 sdist）：

```bash
uv build
```

构建产物将存放在 `dist/` 目录下。

### 2. 本地安装与开发调试

为了方便在开发过程中验证功能，我们推荐以下几种安装方式：

#### 方案 0：使用 `uv run` —— **免安装，最推荐** 🏆
这是 `uv` 用户最推荐的工作流。无需执行任何安装命令，直接运行即可。`uv` 会自动处理依赖同步、环境隔离，并确保你运行的是当前目录下的源码：
```bash
uv run jmai --help
```
*   **优势**：零污染、零安装时间、源码修改即刻生效。

#### 方案 A：开发模式 (Editable Mode) —— **高效开发**
如果你习惯直接输入 `jmai` 而不是 `uv run jmai`，建议在虚拟环境中进行 Editable 安装：
```bash
# 确保已执行 uv sync 同步环境
uv pip install -e .
```
*   **优势**：源码修改实时生效，符合传统开发习惯。请尽量避免在 `--system` 环境下使用。

#### 方案 B：全局工具安装 (uv tool) —— **作为稳定工具使用**
如果你已经完成了开发，希望把 `jmai` 作为一个稳定的系统工具在任何路径下使用：
```bash
uv tool install . --force
```
*   **用途**：这种方式会创建一个完全隔离的虚拟环境。注意：安装后对源码的修改**不会**生效，除非重新执行该命令。

#### 方案 C：手动安装构建产物 (Wheel)
验证打包出来的 wheel 文件是否可以正常安装：
```bash
# 构建并安装最新的 wheel
uv build
uv pip install dist/*.whl --force-reinstall
```

### 3. 验证命令

安装完成后，可以在命令行直接运行 `jmai` 验证包是否正确注册了 entry points：

```bash
# 检查 CLI 是否可用
jmai --help

# 检查 MCP 服务器能否正常导出帮助信息
jmai mcp --help
```


### 调试建议

1. **查阅参考源码**：如前文所述，善用 `reference/` 目录。
2. **实时日志与热重载**：
    - 使用 `tail -f ~/.jmcomic-ai/jmcomic_ai.log` 观察全局日志，或通过 `JM_LOG_PATH` 指定开发日志文件。
    - 下载工具会在 `~/.jmcomic-ai/logs/` 写入任务专属日志；可通过 `JM_TASK_LOG_DIR` 指定目录。
    - stdio 模式的 stdout 仅用于 MCP JSON-RPC，普通日志不会写入 stdout/stderr。
    - **热重载调试**：使用 `jmai mcp --reload` 启动服务。在该模式下，你对 `src/` 目录下代码的任何修改都会触发服务器自动重启，无需反复手动开关服务。
3. **本地 AI 智能体/编辑器调试**：在你的客户端（如 Claude Code, Cursor, Antigravity 等）中添加本地开发配置。
   
   以 **Claude Code** 为例（最推荐的调试方式），在 `~/.claude.json` (User) 或项目根目录 `.mcp.json` (Project) 中配置：
   ```json
   {
     "mcpServers": {
       "jmcomic-ai-dev": {
         "command": "uv",
         "args": [
           "--directory",
           "/path/to/your/jmcomic-ai",
           "run",
           "jmai",
           "mcp",
           "stdio" 
         ]
       }
     }
   }
   ```
   **验证方式**：修改代码后，在终端运行以下命令检查连接状态：
   ```bash
   claude mcp list
   ```

   **其他客户端 (Cursor/Windsurf)**：
   推荐使用 SSE 模式进行热重载调试：
   1. 在终端运行：`uv run jmai mcp sse --reload`
   2. 在编辑器中配置 Server URL：`http://127.0.0.1:8000/sse`
   如果是 Cursor 或其他支持 MCP 的编辑器，通常在设置界面添加类似的 `command` 和 `args` 即可。

## 发版准备

1. **确定版本号**：遵循语义化版本规范，仅需修改 `src/jmcomic_ai/__init__.py` 中的 `__version__`（构建工具与 CLI 均从此读取，Skill 目录不单独维护版本）。
2. **更新更新日志**：在 `CHANGELOG.md` 中新增 `## [x.y.z] - YYYY-MM-DD` 段落记录本次改动（无需保留 `Unreleased` 占位）。
3. **更新依赖与完整验证**：

   ```bash
   uv lock
   uv run python -m unittest discover tests
   uv run ruff check src tests
   uv run mypy src
   uv run jmai --version
   uv build
   ```

4. **发版提交格式**：提交信息使用 `v{version}: 摘要` 格式（版本号必须与 `__init__.py` 保持一致，冒号后的摘要可自由填写）。该提交合并到 `master` 后将自动触发发布：GitHub Actions 会从 Changelog 自动提取 Release 文案、创建同版本 Tag 并发布到 PyPI。

## 提交 Issue

### Bug 报告

请包含以下信息：

- Python 版本
- 操作系统
- 完整的错误堆栈
- 复现步骤

### 功能请求

请描述：

- 你想解决的问题
- 你期望的行为
- 可能的实现方案（可选）

## 行为准则

请保持友善和尊重。我们致力于为每个人创造一个包容的环境。

---

再次感谢你的贡献！🎉
