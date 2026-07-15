#!/usr/bin/env python3
"""
Diagnostic tool for the JMComic Skill.
Checks environment, dependencies, and network connectivity.

Usage:
    python scripts/doctor.py
"""

import sys
from pathlib import Path


def check_python_version():
    print(f"🐍 Python version: {sys.version.split()[0]}")


def check_dependencies():
    print("📦 Checking dependencies...")
    try:
        import jmcomic

        print(f"✅ jmcomic version: {jmcomic.__version__}")
    except ImportError:
        print("❌ Error: jmcomic library not found.")

    try:
        from jmcomic_ai.core import JmcomicService  # noqa: F401

        print("✅ jmcomic_ai core is accessible.")
    except ImportError:
        print("❌ Error: jmcomic_ai core not found.")


def check_network():
    """
    检查网络连接性，测试当前IP可以访问哪些禁漫域名
    使用 jmcomic 2.7.1+ 提供的官方域名发现 API
    """
    print("🌐 Checking network connectivity (Dynamic Domain Discovery)...")
    try:
        from jmcomic import JmModuleConfig, JmOption, disable_jm_log, multi_thread_launcher
    except ImportError:
        print("❌ Error: Missing jmcomic dependencies.")
        return

    # 禁用 jmcomic 的冗余日志输出
    disable_jm_log()

    option = JmOption.default()

    # 1. 获取所有域名
    print("📡 Fetching latest domain list from the JMComic publish page...")
    try:
        domain_set = set(JmModuleConfig.get_html_domain_all())
    except Exception:
        domain_set = set()

    if not domain_set:
        print("❌ Failed to discover domains from the JMComic publish page. You might need to configure a proxy.")
        return

    print(f"🔍 Discovered {len(domain_set)} domains. Testing business connectivity...")

    # 2. 测试每个域名
    domain_status_dict = {}

    def test_domain(domain: str):
        """测试单个域名的可用性"""
        client = option.new_jm_client(impl="html", domain_list=[domain])
        status = "ok"

        try:
            # 测试一个已知的通用相册ID
            client.get_album_detail("123456")
        except Exception as e:
            status = str(e.args)

        domain_status_dict[domain] = status

    multi_thread_launcher(
        iter_objs=domain_set,
        apply_each_obj_func=test_domain,
    )

    # 3. 输出测试结果
    print("\n" + "=" * 50)
    print("Domain Test Results:")
    print("=" * 50)

    ok_domains = []
    for domain, status in sorted(domain_status_dict.items()):
        if status == "ok":
            print(f"✅ {domain}: {status}")
            ok_domains.append(domain)
        else:
            # 截断过长的错误信息
            error_msg = status[:60] + "..." if len(status) > 60 else status
            print(f"❌ {domain}: {error_msg}")

    # 4. 输出总结
    print("=" * 50)
    if ok_domains:
        print(f"✨ Network summary: {len(ok_domains)}/{len(domain_set)} domains are working.")
        print("💡 Recommended HTML domain pool for config:")
        for domain in sorted(ok_domains):
            print(f"   - {domain}")
    else:
        print("❌ All discovered domains failed. You likely need to configure a proxy.")


def check_config():
    print("⚙️ Checking configuration...")
    config_path = Path.home() / ".jmcomic" / "option.yml"
    if config_path.exists():
        print(f"✅ Config found at: {config_path}")
    else:
        print("ℹ️ Config not found at default location (~/.jmcomic/option.yml). Using built-in defaults.")


def main():
    print("🏥 JMComic Skill Doctor - Diagnostic Report\n" + "=" * 45)
    check_python_version()
    print("-" * 20)
    check_dependencies()
    print("-" * 20)
    check_config()
    print("-" * 20)
    check_network()
    print("=" * 45 + "\n✨ Diagnostic complete.")


if __name__ == "__main__":
    main()
