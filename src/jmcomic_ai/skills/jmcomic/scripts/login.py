#!/usr/bin/env python3
"""
JMComic Authentication and Login CLI tool.
Supports testing API and HTML authentication, displaying user profile statistics,
and persisting session cookies (AVS) directly into option.yml.

Usage:
    python scripts/login.py -u my_username -p my_password
    python scripts/login.py -u my_username -p my_password --impl api --save
    python scripts/login.py -u my_username -p my_password --impl html --domain 18comic.ink --save
    python scripts/login.py -u my_username -p my_password --json
"""

import argparse
import getpass
import json
import os
import sys

# Ensure UTF-8 output on Windows.  ``sys.stdout`` can be ``None`` when the
# script is embedded or launched with detached standard streams.
_reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
if callable(_reconfigure_stdout):
    _reconfigure_stdout(encoding="utf-8", errors="replace")

try:
    from ._script_utils import exit_for_import_error
except ImportError:
    from _script_utils import exit_for_import_error  # type: ignore[no-redef]

try:
    from jmcomic import disable_jm_log

    from jmcomic_ai.core import JmcomicService
except ImportError as exc:
    exit_for_import_error(exc, "jmcomic", "Please install: pip install jmcomic jmcomic_ai")

# Safe default HTML domain known to work without Cloudflare 403 or redirects
DEFAULT_RECOMMENDED_HTML_DOMAIN = "18comic.ink"
COMMON_LOCAL_PROXY_PORTS = [7890, 7897, 10808, 10809, 1080, 8080]


def detect_local_proxy() -> str | None:
    """Detect if a common local proxy port is active."""
    import socket

    for port in COMMON_LOCAL_PROXY_PORTS:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.15)
            result = s.connect_ex(("127.0.0.1", port))
            s.close()
            if result == 0:
                return f"http://127.0.0.1:{port}"
        except Exception:
            pass
    return None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Authenticate with JMComic and optionally save credentials to option.yml"
    )
    parser.add_argument(
        "--username",
        "-u",
        default=os.getenv("JM_USERNAME", ""),
        help="Account username (or set JM_USERNAME environment variable)",
    )
    parser.add_argument(
        "--password",
        "-p",
        default=os.getenv("JM_PASSWORD", ""),
        help="Account password (or set JM_PASSWORD environment variable)",
    )
    parser.add_argument(
        "--impl",
        choices=["both", "api", "html"],
        default="both",
        help="Target client implementation to verify (default: both)",
    )
    parser.add_argument(
        "--domain",
        help="Custom domain to test (e.g. 18comic.ink or www.cdngwc.club)",
    )
    parser.add_argument(
        "--proxy",
        help="Custom proxy URL (e.g. http://127.0.0.1:7890) or 'none'",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save valid AVS cookie and working domain to option.yml upon successful login",
    )
    parser.add_argument(
        "--option",
        help="Path to option.yml file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON results",
    )
    return parser.parse_args()


def perform_api_login(service: JmcomicService, username: str, password: str, domain: str | None = None) -> dict:
    """Verify login against JMComic Mobile API."""
    client = None
    client_domain = domain
    try:
        option = service.option
        domain_list = [domain] if domain else None
        client = option.new_jm_client(impl="api", domain_list=domain_list)
        client_domain = getattr(client, "current_domain", None) or (
            client.domain_list[0] if client.domain_list else None
        )
        resp = client.login(username, password)
        res_data = getattr(resp, "res_data", {})
        cookies = dict(client.get_meta_data("cookies") or {})
        avs_cookie = cookies.get("AVS") or (res_data.get("s") if isinstance(res_data, dict) else None)

        return {
            "status": "success",
            "uid": str(res_data.get("uid", "")) if res_data else None,
            "username": res_data.get("username", username) if res_data else username,
            "email": res_data.get("email") if res_data else None,
            "gender": res_data.get("gender") if res_data else None,
            "coin": res_data.get("coin") if res_data else None,
            "level": res_data.get("level") if res_data else None,
            "level_name": res_data.get("level_name") if res_data else None,
            "exp": res_data.get("exp") if res_data else None,
            "album_favorites": res_data.get("album_favorites") if res_data else None,
            "album_favorites_max": res_data.get("album_favorites_max") if res_data else None,
            "message": res_data.get("message") if res_data else None,
            "avs_cookie": avs_cookie,
            "client_domain": client_domain,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "client_domain": client_domain,
        }


def perform_html_login(service: JmcomicService, username: str, password: str, domain: str | None = None) -> dict:
    """Verify login against JMComic Web HTML interface."""
    # If domain not specified, use DEFAULT_RECOMMENDED_HTML_DOMAIN to bypass known 301 bounces
    target_domains = [domain] if domain else [DEFAULT_RECOMMENDED_HTML_DOMAIN]
    try:
        option = service.option
        client = option.new_jm_client(impl="html", domain_list=target_domains)
        resp = client.login(username, password)
        cookies = dict(client.get_meta_data("cookies") or {})
        avs_cookie = cookies.get("AVS")

        return {
            "status": "success",
            "status_code": resp.status_code,
            "avs_cookie": avs_cookie,
            "client_domain": target_domains[0],
        }
    except Exception as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "client_domain": target_domains[0],
        }


def save_credentials_to_option(
    service: JmcomicService, avs_cookie: str, target_impl: str, working_domain: str | None
) -> tuple[bool, str]:
    """Persist AVS cookie and optionally domain/impl into option.yml."""
    try:
        updates: dict = {
            "client": {
                "postman": {
                    "meta_data": {
                        "cookies": {
                            "AVS": avs_cookie,
                        }
                    }
                }
            }
        }

        if target_impl in ("api", "html"):
            updates["client"]["impl"] = target_impl

        if working_domain and target_impl in ("api", "html"):
            updates["client"]["domain"] = [working_domain]

        msg = service.update_option(updates)
        if msg.lower().startswith("option update failed"):
            return False, msg
        return True, msg
    except Exception as exc:
        return False, str(exc)


def main():
    args = parse_args()

    username = args.username
    password = args.password

    # Prompt interactively if not supplied
    if not username:
        if sys.stdin.isatty():
            username = input("JMComic Username: ").strip()
        if not username:
            print("Error: Username is required. Provide --username or set JM_USERNAME.", file=sys.stderr)
            sys.exit(1)

    if not password:
        if sys.stdin.isatty():
            password = getpass.getpass("JMComic Password: ").strip()
        if not password:
            print("Error: Password is required. Provide --password or set JM_PASSWORD.", file=sys.stderr)
            sys.exit(1)

    disable_jm_log()

    try:
        service = JmcomicService(option_path=args.option)
    except Exception as exc:
        print(f"Error: failed to initialize JmcomicService: {exc}", file=sys.stderr)
        sys.exit(1)

    # Configure proxy
    if args.proxy:
        if args.proxy.lower() == "none":
            service.option.client.postman.meta_data["proxies"] = {}
        else:
            service.option.client.postman.meta_data["proxies"] = {
                "http": args.proxy,
                "https": args.proxy,
            }
    else:
        # Check if option already has proxy; if not, auto-detect local proxy
        current_proxies = service.option.client.postman.meta_data.get("proxies")
        if not current_proxies:
            detected_proxy = detect_local_proxy()
            if detected_proxy:
                service.option.client.postman.meta_data["proxies"] = {
                    "http": detected_proxy,
                    "https": detected_proxy,
                }

    results: dict = {
        "username": username,
        "impl": args.impl,
        "results": {},
        "saved_to_option": False,
        "option_path": str(service.option_path),
    }

    all_success = True
    best_avs_cookie = None
    working_domain = None

    # 1. API Login
    if args.impl in ("both", "api"):
        api_res = perform_api_login(service, username, password, args.domain)
        results["results"]["api"] = api_res
        if api_res["status"] == "success":
            best_avs_cookie = api_res.get("avs_cookie") or best_avs_cookie
            working_domain = api_res.get("client_domain") or working_domain
        else:
            all_success = False

    # 2. HTML Login
    if args.impl in ("both", "html"):
        html_res = perform_html_login(service, username, password, args.domain)
        results["results"]["html"] = html_res
        if html_res["status"] == "success":
            # Keep the API cookie when both implementations return one so the
            # cookie and selected implementation/domain remain consistent.
            best_avs_cookie = best_avs_cookie or html_res.get("avs_cookie")
            if args.impl == "html" or not working_domain:
                working_domain = html_res.get("client_domain")
        else:
            all_success = False

    results["status"] = (
        "success"
        if all_success
        else "partial"
        if any(r.get("status") == "success" for r in results["results"].values())
        else "failed"
    )

    # 3. Save to option.yml if requested
    if args.save:
        if best_avs_cookie:
            # Prefer the API result when both implementations succeeded, matching
            # the default client implementation and keeping its domain/cookie pair
            # together.  Fall back to HTML when API did not return an AVS cookie.
            save_impl = args.impl if args.impl in ("api", "html") else "api"
            if args.impl == "both" and not results["results"].get("api", {}).get("avs_cookie"):
                save_impl = "html"
            if save_impl == "html":
                working_domain = results["results"].get("html", {}).get("client_domain") or working_domain
            saved, save_msg = save_credentials_to_option(service, best_avs_cookie, save_impl, working_domain)
            results["saved_to_option"] = saved
            results["save_message"] = save_msg
        else:
            results["save_message"] = "no valid session cookie obtained"

        if not results["saved_to_option"]:
            results["status"] = "failed"

    # Output
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        sys.exit(0 if results["status"] == "success" else 1)

    # CLI Formatted Output
    print("=" * 60)
    print(f"🔐 JMComic Authentication Result  [User: {username}]")
    print("=" * 60)

    if "api" in results["results"]:
        api = results["results"]["api"]
        if api["status"] == "success":
            print("📱 API Client:       ✅ SUCCESS")
            print(f"   - UID:             {api.get('uid') or '-'}")
            print(f"   - Email:           {api.get('email') or '-'}")
            print(f"   - Level:           Lv.{api.get('level')} ({api.get('level_name')}) [EXP: {api.get('exp')}]")
            print(f"   - Coins:           {api.get('coin')}")
            print(f"   - Favorites:       {api.get('album_favorites')} / {api.get('album_favorites_max')}")
            if api.get("message"):
                # Clean html tags from welcome message
                clean_msg = api["message"].replace("<br>", " | ").replace("<br/>", " | ")
                print(f"   - Reward/Msg:      {clean_msg}")
        else:
            print("📱 API Client:       ❌ FAILED")
            print(f"   - Error:           {api.get('error')}")

    if "html" in results["results"]:
        html = results["results"]["html"]
        if html["status"] == "success":
            print(f"🌐 HTML Client:      ✅ SUCCESS (Domain: {html.get('client_domain')})")
            if html.get("avs_cookie"):
                masked_cookie = html["avs_cookie"][:6] + "..." + html["avs_cookie"][-4:]
                print(f"   - AVS Cookie:      {masked_cookie}")
        else:
            print(f"🌐 HTML Client:      ❌ FAILED (Domain: {html.get('client_domain')})")
            print(f"   - Error:           {html.get('error')}")

    print("=" * 60)
    if results.get("saved_to_option"):
        print(f"💾 Option Update:    ✅ Saved valid AVS cookie to {results['option_path']}")
    elif args.save and not best_avs_cookie:
        print("💾 Option Update:    ⚠️ Skipped (no valid session cookie obtained)")

    sys.exit(0 if results["status"] == "success" else 1)


if __name__ == "__main__":
    main()
