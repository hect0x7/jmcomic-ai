"""
Version consistency checker for JMComic AI.

This script verifies that the version number is consistent across:
- pyproject.toml (source of truth)
- src/jmcomic_ai/__init__.py
- src/jmcomic_ai/skills/jmcomic/SKILL.md

Run this script before releasing to ensure version synchronization.
"""

import re
import sys
from pathlib import Path

# 定义根目录
ROOT_DIR = Path(__file__).parent.parent


def get_version_from_pyproject() -> str:
    """从 pyproject.toml 提取版本号（作为基准版本）。"""
    path = ROOT_DIR / "pyproject.toml"
    content = path.read_text(encoding="utf-8")
    match = re.search(r'version = "(.*?)"', content)
    if match:
        return match.group(1)
    raise ValueError(f"Could not find version in {path}")


def get_version_from_init() -> str:
    """从 __init__.py 提取版本号。"""
    path = ROOT_DIR / "src" / "jmcomic_ai" / "__init__.py"
    content = path.read_text(encoding="utf-8")
    match = re.search(r'__version__ = "(.*?)"', content)
    if match:
        return match.group(1)
    raise ValueError(f"Could not find version in {path}")


def get_version_from_skill() -> str:
    """从 SKILL.md 提取版本号。"""
    path = ROOT_DIR / "src" / "jmcomic_ai" / "skills" / "jmcomic" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    match = re.search(r'version: "(.*?)"', content)
    if match:
        return match.group(1)
    raise ValueError(f"Could not find version in {path}")


def check_versions() -> bool:
    """检查所有位置的版本号是否一致。"""
    errors = []

    try:
        base_version = get_version_from_pyproject()
        print(f"[*] Base version from pyproject.toml: {base_version}")
    except Exception as e:
        print(f"[!] Error reading pyproject.toml: {e}")
        return False

    # Check __init__.py
    try:
        init_version = get_version_from_init()
        if init_version != base_version:
            errors.append(
                f"src/jmcomic_ai/__init__.py: expected '{base_version}', found '{init_version}'"
            )
        else:
            print("[+] src/jmcomic_ai/__init__.py matches")
    except Exception as e:
        errors.append(f"Error reading __init__.py: {e}")

    # Check SKILL.md
    try:
        skill_version = get_version_from_skill()
        if skill_version != base_version:
            errors.append(
                f"SKILL.md: expected '{base_version}', found '{skill_version}'"
            )
        else:
            print("[+] SKILL.md matches")
    except Exception as e:
        errors.append(f"Error reading SKILL.md: {e}")

    if errors:
        print("\n[!] Version consistency check FAILED:")
        for error in errors:
            print(f"    - {error}")
        return False

    print("\n[OK] All versions are consistent!")
    return True


if __name__ == "__main__":
    if not check_versions():
        sys.exit(1)
    sys.exit(0)
