# Changelog

本文件记录 JMComic AI 的所有重要更新。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
