---
todo
---

# Changelog

本文件记录 JMComic AI 的所有重要更新。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
