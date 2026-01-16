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

### 分支策略

- `master`: 稳定分支，用于发布
- `dev`: 开发分支，日常开发在此进行
- `feature/*`: 特性分支
- `fix/*`: 修复分支

### 提交代码

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交你的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

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
    - 使用 `tail -f` 观察项目根目录下的 `jmcomic_ai.log` 日志。
    - **热重载调试**：使用 `jmai mcp --reload` 启动服务。在该模式下，你对 `src/` 目录下代码的任何修改都会触发服务器自动重启，无需反复手动开关服务。
3. **本地 AI 智能体/编辑器调试**：在你的客户端（如 Cursor, Antigravity, Windsurf, VS Code, Claude Desktop 等）中添加本地开发配置。
   以 Claude Desktop 为例，在 `claude_desktop_config.json` 中配置：
   ```json
   "mcpServers": {
     "jmcomic-ai-dev": {
       "command": "uv",
       "args": ["--directory", "D:/你的路径/jmcomic-ai", "run", "jmai", "mcp"]
     }
   }
   ```
   如果是 Cursor 或其他支持 MCP 的编辑器，通常在设置界面添加类似的 `command` 和 `args` 即可。

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
