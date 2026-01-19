# AI Agent Development Guide for JMComic AI

This document provides instructions and best practices for AI Agents (like Antigravity) to develop, maintain, and extend the `jmcomic-ai` project.

## 🎯 Core Philosophy

The mission of this project is to **transform the JMComic crawler into an AI-native cognitive asset**.
- **Tools over Scripts**: Don't just write scripts; build robust MCP tools that agents can use to reason and act.
- **Documentation as Code**: Documentation (like `SKILL.md`) is the "brain" of the agent. It must be kept in sync with the implementation.
- **Self-Introspection**: The project should expose its own schema and reference through MCP Resources.

## 🏗️ Architecture for Agents

- **`src/jmcomic_ai/core.py`**: The "Brain". All business logic and tool implementations reside here in `JmcomicService`.
- **`src/jmcomic_ai/mcp/server.py`**: The "Interface". Uses `FastMCP` to dynamically register methods from `JmcomicService` as MCP tools.
- **`reference/jmcomic_src/`**: The "Knowledge Base". Contains the source code of the underlying `jmcomic` library. **Always read this first** when implementing new tools.

> [!IMPORTANT]
> **CRITICAL SOURCE CODE RULE**
> Do **NOT** attempt to locate the `jmcomic` source code using `python -c "import jmcomic; print(jmcomic.__file__)"` or `pip show`.
> The installed version in site-packages is **IRRELEVANT** for development reference.
> You **MUST** strictly use the local copy in `reference/jmcomic_src/` for all code analysis and logic extraction.
> Ignoring this rule leads to incorrect path assumptions and wasted steps.

## 🛠️ Development Workflow (Recommended for Agents)

When asked to add a new feature or tool, follow these steps:

### 1. Research & Discovery
- **STOP & READ**: Go directly to `reference/jmcomic_src/`. Do not check installed packages.
- Search `reference/jmcomic_src/` to find the relevant logic in the base library.
- For example, if adding a "favorite" feature, search for `favorite` in the reference code to see how `JmcomicClient` handles it.

### 2. Implement in `JmcomicService`
- Add the method to `src/jmcomic_ai/core.py`.
- **CRITICAL**: Use descriptive docstrings and precise type hints. The MCP server uses these to generate the tool definition for other AIs.
- **Example**:
  ```python
  def my_new_tool(self, param: str) -> str:
      """
      Detailed description of what this tool does.
      Args:
          param: What this parameter represents.
      """
      # Implementation
  ```

### 3. Handle Variable Shadowing
- **Attention**: Avoid using the same name for parameters and local variables (e.g., don't use `page = client.search(page=page)`). Use `search_page` for result objects.

### 4. Update the "Agent Manual" (`SKILL.md`)
- Every new tool or parameter change **must** be reflected in `src/jmcomic_ai/skills/jmcomic/SKILL.md`.
- This file is how other agents understand your capabilities.

### 5. Verify the MCP Integration
- Run `uv run python tests/test_mcp_integration.py` (or use `python -m unittest discover tests` for all tests).
- Ensure the new tool appears in the `list_tools` output and executes correctly via the SSE transport.

### 6. Record Changes in Changelog
- **Critical**: You **MUST** document your changes in `CHANGELOG.md` after every code modification.
- Add a concise entry under the content for the current version.
- Classify your change type: `Added`, `Changed`, `Fixed`, or `Removed`.

## 📜 Coding Standards for Agents

| Feature | Requirement |
| :--- | :--- |
| **Async** | Long-running operations (downloads) must be async or backgrounded using `asyncio.to_thread`. |
| **Logging** | Use `self.logger`. Always log the start, result, and any errors of an operation. |
| **Path Handling** | Use `pathlib.Path`. Print physical log paths upon initialization. |
| **Configuration** | Support both `option.yml` updates and environment variable overrides (`${VAR}`). |

## 🧪 Testing Strategy
- **Unit Tests**: Test core logic in `tests/test_core.py`.
- **Integration Tests**: Test the full MCP stack in `tests/test_mcp_integration.py`. This is the most important test for verifying "AI-readiness".

## 🚀 Key Commands
- Start DEV server: `uv run jmai mcp`
- Run Lint: `uv run ruff check src`
- Format: `uv run ruff format src`
- Update Dependencies: `uv sync`
- Check Version: `python .github/check_version.py`

## 📌 Version Management

The version number must be kept consistent across the following three locations:

| File | Format | Purpose |
| :--- | :--- | :--- |
| `pyproject.toml` | `version = "x.y.z"` | **Source of truth** for builds and releases |
| `src/jmcomic_ai/__init__.py` | `__version__ = "x.y.z"` | Displayed by `jmai -v` CLI output |
| `src/jmcomic_ai/skills/jmcomic/SKILL.md` | `version: "x.y.z"` | AI Skills metadata |

### Automatic Validation
The publish workflow (`.github/workflows/publish.yml`) runs version consistency checks before every release. If versions mismatch, the workflow fails and blocks the release.

### Manual Validation
During local development, you can run the following command to check version sync status:
```bash
python .github/check_version.py
```

### Release Commit Convention
To ensure the automatic release notes generator (`.github/release.py`) works correctly, use the following format for release commits:

**Format**: `v{version}: {Update Point 1}; {Update Point 2}; ...`

- **Version**: Must match the current version in `pyproject.toml`.
- **Description**: Use semicolons (`;`) to separate multiple points. These will be automatically converted into a numbered list in the release notes.

**Example**:
`v0.0.5: Add file tree preview for skills management; Improve uninstallation safety; Refactor SkillManager to remove redundancy`

---

*Note: This guide is intended for AI-to-AI collaboration. If you are a human developer, please refer to [CONTRIBUTING.md](./.github/CONTRIBUTING.md).*
