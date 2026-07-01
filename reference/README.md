# Reference Code

本目录包含 `jmcomic` 库的源代码副本，**仅供开发参考**。

## ⚠️ 重要说明

- 此目录中的代码**已在 .gitignore 中设置忽略，不会被提交到 Git**
- 运行时使用的是 `pyproject.toml` 中声明的 PyPI 依赖 (`jmcomic>=2.6.12`)
- 如需修改 jmcomic 的行为，请直接向上游提交 PR

## 📁 目录结构

```
reference/
└── jmcomic_src/       # jmcomic 库源码副本
    ├── __init__.py
    ├── jm_option.py
    ├── jm_client*.py
    └── ...
```

## 🔗 上游仓库

- [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python)

## 🔄 更新方式

如需更新参考代码到最新版本：

```bash
# 进入 reference 目录
cd reference

# 删除旧版本
rm -rf jmcomic_src

# 从 GitHub 克隆最新版本
git clone --depth 1 https://github.com/hect0x7/JMComic-Crawler-Python.git jmcomic_src
```

或者直接从 GitHub 克隆：

```bash
git clone --depth 1 https://github.com/hect0x7/JMComic-Crawler-Python.git /tmp/jmcomic-repo
cp -r /tmp/jmcomic-repo/src/jmcomic reference/
```
