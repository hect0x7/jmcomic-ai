# Security Policy

## 报告安全漏洞

感谢您帮助保持 JMComic AI 的安全！

如果您发现了安全漏洞，请**不要**在公开的 Issue 中报告。相反，请通过以下方式私密报告：

### 报告方式

1. **GitHub Security Advisories** (推荐)
   - 前往 [Security Advisories](https://github.com/hect0x7/jmcomic-ai/security/advisories)
   - 点击 "Report a vulnerability"

### 报告内容

请在报告中包含以下信息：

- 漏洞类型 (例如: RCE, XSS, 信息泄露等)
- 受影响的版本
- 详细的复现步骤
- 潜在影响评估
- 如果有的话，建议的修复方案

### 响应时间

- 我们会在 **48 小时** 内确认收到您的报告
- 我们会在 **7 天** 内提供初步评估
- 我们会与您保持沟通，直到问题解决

### 致谢

我们感谢所有负责任地报告安全问题的研究者。在漏洞修复后，我们会在 CHANGELOG 和 Release Notes 中致谢（除非您希望保持匿名）。

## 支持的版本

| 版本 | 支持状态 |
|------|---------|
| 0.1.x | ✅ 支持 |

## 安全最佳实践

使用 JMComic AI 时，请注意：

1. **配置文件安全**：`option.yml` 可能包含敏感信息，请勿将其提交到公开仓库
2. **网络安全**：使用 SSE 模式时，确保在安全的网络环境中运行
3. **依赖更新**：定期运行 `uv sync` 确保依赖是最新的
