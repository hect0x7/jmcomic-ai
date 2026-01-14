---
todo
---

# Changelog

本文件记录 JMComic AI 的所有重要更新。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2026-01-14

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
