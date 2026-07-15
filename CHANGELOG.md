# Changelog

本文件记录 JMComic AI 的所有重要更新。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2026-07-16

### Added
- 🧪 **上游兼容性回归测试**：新增原生异步下载 API 存在性与默认 Client 配置字段覆盖测试，防止依赖或 Schema 再次失配。
- 🤖 **多平台 Skills 安装**：`jmai skills install/uninstall` 新增交互式平台选择、`jmai skills -i/-u` 快捷入口和 `--platform claude|codex|gemini|all` 自动化参数，支持 Claude、Codex 与 Gemini CLI 用户级技能目录，并增加端到端安装/卸载测试。
- 🔐 **隐私开发规范**：`AGENTS.md` 新增本地路径、日志、Cookie、密钥和测试产物的仓库隐私检查要求。

### Changed
- 📦 **上游依赖基线升级**：将 `jmcomic` 支持基线提升至 `>=2.7.1,<3.0.0`，确保运行时具备原生异步 API、客户端缓存和新版批量结果类型。
- 🌐 **域名诊断对齐上游**：`doctor.py` 改用 `JmModuleConfig.get_html_domain_all` 从 JMComic 发布页发现域名，不再复制旧版域名抓取实现，并输出完整可用域名池。
- 📚 **配置自省资料同步**：Schema、`SKILL.md` 和配置示例新增 `client.async_impl` 与 `client.cache`，与 `jmcomic 2.7.1` 默认配置保持一致。

### Fixed
- 🧠 **MCP Option Schema 拒绝合法字段**：修复 `additionalProperties: false` 导致上游默认 `async_impl`、`cache` 配置被错误判定为非法的问题。

### Removed
- 🗑️ **GitHub 域名发现回退**：删除通过 GitHub 镜像获取 JMComic 域名的功能，域名诊断仅访问 JMComic 发布页。

## [0.0.10] - 2026-06-28

### Changed
- ♻️ **工具词汇统一**：`search_album` 与 `browse_albums` 现共用同一套友好 `order_by` / `time_range` 词汇（`latest/likes/views/pictures/score/comments`、`all/day/today/week/month`），并提取为模块级共享映射，消除两处重复。
- ♻️ **进度 Downloader 去重与重构**：`download_album` / `download_photo` 内嵌的两个进度 downloader 抽成共享工厂 `_build_progress_downloaders`，并将生成的动态类提取至模块级别，消除了动态创建类的反模式，降低内存开销并优化堆栈追踪。
- ♻️ **脚本收敛单一数据源**：`scripts/` 下脚本统一改为转调 `JmcomicService` 业务方法（不再绕过到 `service.option` 或重写逻辑），与 MCP 工具契约对齐。
- 📚 **SKILL.md 渐进式披露瘦身**：SKILL.md 由 464 行精简到 ~200 行，`dir_rule` 范例、`browse_albums` 细节、脚本完整用法迁移至 `references/{post_process,browse_albums,scripts}.md`，信息不丢。

### Fixed
- 🐛 **`download_photo.py` 幽灵下载**：脚本调用 async 的 `service.download_photo` 时缺少 `asyncio.run`，导致返回未 await 的协程、从不真正下载却恒报成功；现已修复。
- 🐛 **`search_album` 排序透传**：旧版把 `order_by`/`time_range` 字符串原样透传给底层 `client.search`，未映射成 magic constants（默认 `"latest"` 实际未生效）；现已正确映射。
- 📝 **README 使用说明语病**：模块 B 把「支持 Agent Skills 自动发现」「手动粘贴 System Prompt」「MCP Resource 查阅」三种独立方式混为一谈，易误导用户，现拆分澄清。

### Removed
- 🗑️ **伪字段 `category`**：`get_album_detail` 返回中恒为 `"0"` 的 `category` 字段已删除（`JmAlbumDetail` 本无此字段）。

### Added
- 🧪 **单元测试**：新增 `tests/test_core.py`，对共享 `order_by` / `time_range` 映射做无网络依赖的校验。

## [0.0.9] - 2026-03-13

### Changed
- 🧩 **Skills 后处理参数增强**：`scripts/post_process.py` 新增 `--dir-rule` 与 `--base-dir` 参数，支持以 `dir_rule` DSL 精确控制输出路径；并增加与 `--outdir` 的互斥与配对校验，避免参数冲突。
- 📚 **Skills 契约文档补充**：`SKILL.md` 新增“Script Parameters ↔ MCP Tools Mapping”映射说明，明确脚本参数与 MCP 工具契约的对齐级别与边界。

## [0.0.8] - 2026-01-28

### Documentation
- 📚 **MCP 配置指南重构**：重写 README 和 CONTRIBUTING 文档，新增 **Claude Code** 作为首选调试工具，并完善了 Antigravity、Cursor 和 Claude Desktop 的配置参考。
- 📖 **配置示例细化**：拆分 MCP 配置为 stdio (默认)、SSE (Cursor 推荐) 和 HTTP (远程) 三种流式模式，提供了更直观的 JSON 片段。

### Fix
- 🛡️ **类型安全增强**：修复了 `src/` 下所有的 MyPy 类型检查错误，增强了 `fastmcp` 上下文调用和 lambda 表达式的健壮性。
- 🐛 **导入修复**：修正了 `core.py` 中 `Context` 重复导入和 `server.py` 中 `Transport` 类型断言的问题。

### Changed
- ♻️ **脚本适配**：`ranking_tracker.py`、`search_export.py` 等技能脚本现在统一使用新的 `browse_albums` API，逻辑更收敛。
- ⚙️ **开发工作流**：新增 `.github/workflows/mypy.yml`，在 CI 中强制进行严格的静态类型检查。

## [0.0.7] - 2026-01-19

### Changed
- 🔄 **工具输出结构化**：`download_album` 与 `post_process` 现在返回结构化的字典（包含 `status`, `download_path` 等字段）而非纯文本，以提升 AI 代理的自动化处理与验证能力。
- 🛠️ **后处理逻辑重构**：彻底简化 `post_process` 传参设计，取消冗余的 `output_dir` 抽象，回归 `jmcomic` 原生参数体系，统一使用 `dir_rule` 作为路径控制入口。
- 📚 **文档与示例补全**：在 `SKILL.md` 与代码注释中新增了涵盖 Zip、PDF、LongImg 在 Album/Photo 级别全部 6 种组合的 `dir_rule` 使用范例。

### Added
- 📈 **实时进度追踪**：`download_album` 现已支持发送 MCP 进度通知，允许客户端实时显示下载进度。
- 🧪 **集成测试增强**：新增 `test_tool_download_album_with_progress` 测试用例，验证进度捕获与结构化返回值的正确性。
- 📘 **开发规范**：在 `AGENTS.md` 中强制要求每次代码修改后必须同步更新 `CHANGELOG.md`，确保变更记录不遗漏。

### Fixed
- 🛡️ **异常处理增强**：为 `download_album` 和 `download_photo` 的 MCP 进度回调添加异常保护，防止进度报告失败导致下载中止。
- 🧹 **代码重构**：
  - 将 MCP 上下文回调保护逻辑提取为局部辅助函数 `safe_ctx_call`，消除重复代码。
  - 在 `post_process` 中统一使用 `pathlib.Path` 处理路径，确保返回绝对路径。
  - 修复了 `post_process` 成功时可能导致重复返回结果的冗余代码。
  - 修正并增强了 `long_img` 后处理的路径预测准确性。
  - 优化异常日志格式，`logger.exception()` 不再重复记录异常信息。
- 📝 **文档完善**：
  - 在 `post_process` 文档中补充 `is_directory` 字段说明。
  - 在 `download_album` 和 `download_photo` 文档中补充 `error` 字段说明。
  - 确保所有工具方法的返回值文档完整准确。


---

## [0.0.5] - 2026-01-16

### Added
- 📦 **后处理增强**：集成 `ZipPlugin`、`Img2pdfPlugin` 与 `LongImgPlugin`。支持在下载完成后按需将漫画打包为 ZIP（支持加密）、导出为 PDF 或合并长图。
- 🔍 **下载路径预判**：`download_album` 现在会预先根据规则计算并返回预期的本地存储目录，极大提升了 AI 代理的上下文感知能力（Observability）。
- 🌳 新增安装 (`install`) 与卸载 (`uninstall`) 时的文件树预览功能，在执行操作前让用户清晰感知文件变更。
- 🛡️ 增强卸载安全性：明确区分父目录与技能子目录，增加风险警告提示，并将默认确认行为改为 `False` 以防误删。

### Changed
- 🛡️ **线程安全优化**：重构 `post_process` 逻辑，通过动态实例化插件彻底废弃了临时修改全局配置的做法，支持高并发处理且无副作用。
- 🎯 统一 Skills 安装规范：修复路径逻辑，确保技能始终安装在目标目录的同名子目录（如 `jmcomic/`）中。
- 🌍 国际化：将 CLI 所有交互提示与错误信息统一为英文。
- 🏗️ 重构 `SkillManager` 核心类，提取公共路径计算与文件扫描逻辑，消除冗余代码。

### Fixed
- 📝 修复 `uninstall` 命令在目标路径不存在技能时反馈不明确的问题。
- 🚑 修复 CLI 输出在某些终端下由于 `stderr` 缓冲区导致的提示信息丢失或延迟问题。
- 🐛 修复 `post_process` 在某些情况下由于 `filename_rule` 缺失导致的 `NoneType` 异常。


---

## [0.0.4] - 2026-01-16

### Added
- 🔥 新增 MCP 服务器热重载（Hot-reload）功能，通过 `jmai mcp --reload` 启动，代码改动后服务器自动重启，大幅提升开发与调试效率。
- 📊 搜索相关工具（`search_album`, `get_ranking`, `get_category_list`）的返回结构中新增 `total_count` 字段，方便 AI 掌握搜索结果全貌。

### Fixed
- 🐛 修复 `--reload` 模式下主进程与子进程重复初始化并重复打印配置提示的问题，输出更清爽。


---

## [0.0.3] - 2026-01-15

### Added
- 🔖 新增 `jmai --version` / `jmai -v` 选项，可查看当前安装版本。
- 📋 新增版本一致性检查脚本 `.github/check_version.py`，确保 `pyproject.toml`、`__init__.py`、`SKILL.md` 三处版本同步。
- 🤖 发布工作流新增版本一致性校验步骤，版本不匹配时阻断发布。

### Changed
- 📚 重写 `CONTRIBUTING.md` 安装指南，新增 `uv run` 作为最推荐的开发方式（方案 0），调整原有方案优先级。
- 📝 更新 `AGENTS.md`，补充完整的版本管理规范与手动校验命令。

### Fixed
- 🐛 修复 `jmai skills install/uninstall` 缺少路径提示的问题，现在会明确打印预设路径或用户指定路径。


---

## [0.0.2] - 2026-01-15

### Added
- 🧰 新增 Skills 脚本套件，位于 `scripts/` 目录：
  - `ranking_tracker.py`：排行榜追踪与导出。
  - `album_info.py`：本子详情查询。
  - `batch_download.py`：批量下载。
  - `download_covers.py`：封面下载。
  - `download_photo.py`：单章下载。
  - `search_export.py`：搜索结果导出。
  - `doctor.py`：环境诊断工具。
  - `validate_config.py`：配置校验工具。
- 🚀 新增 GitHub Actions 发布工作流 `.github/workflows/publish.yml`，支持基于 tag 自动发布至 PyPI。
- 📜 新增 `.github/release.py`，用于从 Git tag 解析版本与发布说明。

### Changed
- 🗂️ 重构 Skills 目录结构：
  - `resources/` → `references/`
  - `option_schema.json` → `assets/option_schema.json`
- 📖 大幅扩展 `SKILL.md`，补充脚本使用说明与工作流示例。

### Removed
- 🗑️ 移除 `scripts/usage_example.py`（已被新脚本套件取代）。



---

## [0.0.1] - 2026-01-14

### Added
- 🎉 首次发布
- 🚀 支持 MCP (Model Context Protocol) 协议，可接入 Claude Desktop 等客户端。
- 🛠️ 暴露核心工具：`search_album`, `get_ranking`, `get_album_detail`, `download_album`, `download_photo`, `download_cover`, `update_option`, `login`。
- 🧠 提供 "Skills" 系统，内置 `SKILL.md` 指导 AI 进行智能策展。
- 🖥️ 统一 CLI 工具 `jmai` / `jmcomic-ai`，支持 `mcp` 启动、`skills` 安装与 `option` 管理。
- 📄 提供 MCP Resources：配置 Schema、参考文档及技能手册。

### Fixed
- 🐛 修复 `core.py` 中 `page_num` 未定义导致的搜索/排行失效问题。
- 🐛 修复 `update_option` 中无法动态更新内存配置的问题。
- 📝 优化 `_parse_search_page` 逻辑，使用 `jmcomic` 官方 `iter_id_title_tag` 迭代器，提高稳定性。
- 🔧 修正 `README.md` 中的过时配置示例与无效文件链接。
- 📢 增强日志功能，启动时自动打印日志文件物理路径。

### Changed
- 🏗️ 重构 `_parse_album_detail` 返回字段，简化 API 响应，移除冗余的 `series_id`。
- 📦 依赖项对齐，确保 `jmcomic>=2.6.11` 以支持最新 API 特性。
