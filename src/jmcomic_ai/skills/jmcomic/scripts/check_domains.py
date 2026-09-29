#!/usr/bin/env python3
"""
JMComic Domain Health Checker.
Tests connectivity, latency, redirect chains, and Cloudflare challenges across HTML and API domains.

Usage:
    python scripts/check_domains.py
    python scripts/check_domains.py --type html --best
    python scripts/check_domains.py --proxy http://127.0.0.1:7890 --json
"""

import argparse
import json
import socket
import sys
import time
from urllib.parse import urlsplit

# Ensure UTF-8 output on Windows.  ``sys.stdout`` may be absent when the
# script is embedded or launched with detached standard streams.
_reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
if callable(_reconfigure_stdout):
    _reconfigure_stdout(encoding="utf-8", errors="replace")

try:
    from ._script_utils import exit_for_import_error
except ImportError:
    from _script_utils import exit_for_import_error  # type: ignore[no-redef]

try:
    from jmcomic import JmModuleConfig, JmOption, disable_jm_log

    from jmcomic_ai.core import JmcomicService
except ImportError as exc:
    exit_for_import_error(exc, "jmcomic", "Please install: pip install jmcomic jmcomic_ai")

# Built-in fallback domain sets
FALLBACK_HTML_DOMAINS = [
    "18comic.vip",
    "18comic.ink",
    "18comic.org",
    "jmcomic-zzz.one",
    "jmcomic-zzz.org",
    "comic18j-jjeg.cc",
    "comic18j-hbd.online",
    "comic18j-jjeg.club",
]

FALLBACK_API_DOMAINS = [
    "www.cdnhjk.net",
    "www.cdngwc.club",
    "www.cdngwc.net",
    "www.cdngwc.cc",
]

COMMON_LOCAL_PROXY_PORTS = [7890, 7897, 10808, 10809, 1080, 8080]


def is_telegram_link(value: str) -> bool:
    """Return whether a discovered value points to Telegram."""
    parsed = urlsplit(value if "://" in value else f"//{value}")
    return parsed.hostname == "t.me"


def detect_local_proxy() -> str | None:
    """Detect if a common local proxy port is active."""
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


def fetch_candidate_domains(domain_type: str) -> dict[str, list[str]]:
    """Gather HTML and/or API domains using dynamic discovery and fallbacks."""
    result: dict[str, list[str]] = {}

    if domain_type in ("all", "html"):
        html_domains = set(FALLBACK_HTML_DOMAINS)
        try:
            discovered = JmModuleConfig.get_html_domain_all()
            for d in discovered:
                clean = d.strip()
                if clean and not is_telegram_link(clean):
                    # JMComic publishes path-prefixed domains as well as bare
                    # hosts (for example ``jm-88.cc/ZNPJam``).  The path is
                    # part of the endpoint and must survive discovery.
                    html_domains.add(clean.rstrip("/"))
        except Exception:
            pass
        result["html"] = sorted(html_domains)

    if domain_type in ("all", "api"):
        api_domains = set(FALLBACK_API_DOMAINS)
        try:
            if hasattr(JmModuleConfig, "DOMAIN_API_LIST") and JmModuleConfig.DOMAIN_API_LIST:
                api_domains.update(JmModuleConfig.DOMAIN_API_LIST)
            if hasattr(JmModuleConfig, "DOMAIN_API_UPDATED_LIST") and JmModuleConfig.DOMAIN_API_UPDATED_LIST:
                api_domains.update(JmModuleConfig.DOMAIN_API_UPDATED_LIST)
        except Exception:
            pass
        result["api"] = sorted(api_domains)

    return result


def test_single_domain(
    domain: str,
    domain_type: str,
    option: JmOption,
    timeout: int = 5,
) -> dict:
    """
    Test connectivity, latency, status code, and verdict for a single domain.
    """
    disable_jm_log()
    url_path = "/setting" if domain_type == "api" else "/"

    start_time = time.perf_counter()
    latency_ms = None
    status_code = None
    location = None
    has_cf_challenge = False
    verdict = "error"
    error_detail = None

    try:
        client = option.new_jm_client(impl=domain_type, domain_list=[domain])
        resp = client.get(url_path, allow_redirects=False, timeout=timeout)
        elapsed = time.perf_counter() - start_time
        latency_ms = round(elapsed * 1000, 1)
        status_code = resp.status_code

        if status_code == 200:
            text = resp.text or ""
            # Check Cloudflare challenge signatures
            if "Just a moment..." in text or "challenge-platform" in text or "cf-browser-verification" in text:
                has_cf_challenge = True
                verdict = "blocked"
                error_detail = "Cloudflare Challenge"
            elif domain_type == "api" and not _is_valid_api_setting_response(resp):
                verdict = "http_error"
                error_detail = "HTTP 200 without a valid API response"
            else:
                verdict = "available"
        elif status_code in (301, 302, 307, 308):
            location = resp.headers.get("Location") or resp.headers.get("location") or ""
            target_host = urlsplit(location if "://" in location else f"//{location}").hostname

            # If it's an internal redirect (same domain, e.g. / -> /albums/meiman), the domain is ACTIVE!
            domain_host = urlsplit(domain if "://" in domain else f"//{domain}").hostname
            if not target_host or target_host.lower() == (domain_host or domain).lower():
                # Test /login endpoint to confirm it's a real active service
                try:
                    login_resp = client.get("/login", allow_redirects=False, timeout=timeout)
                    if login_resp.status_code == 200:
                        verdict = "available"
                        error_detail = "Active (Internal routing)"
                    else:
                        verdict = "redirect"
                        error_detail = f"In-domain redirect to {location}"
                except Exception:
                    verdict = "available"
                    error_detail = f"In-domain redirect to {location}"
            else:
                verdict = "redirect"
                error_detail = f"Redirects to {location}"
        elif status_code == 403:
            verdict = "blocked"
            error_detail = "HTTP 403 (Forbidden / WAF)"
        else:
            verdict = "http_error"
            error_detail = f"HTTP {status_code}"

    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        latency_ms = round(elapsed * 1000, 1)
        exc_str = str(exc)
        if "Connection was reset" in exc_str or "curl: (35)" in exc_str:
            verdict = "reset"
            error_detail = "TCP Reset (GFW / Connection Reset)"
        elif "certificate" in exc_str.lower() or "curl: (60)" in exc_str:
            verdict = "ssl_error"
            error_detail = "SSL Certificate Error"
        elif "timed out" in exc_str.lower() or "curl: (28)" in exc_str:
            verdict = "timeout"
            error_detail = "Connection Timed Out"
        else:
            verdict = "error"
            error_detail = exc_str[:80]

    return {
        "domain": domain,
        "type": domain_type,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "verdict": verdict,
        "location": location,
        "has_cf_challenge": has_cf_challenge,
        "error_detail": error_detail,
    }


def _is_valid_api_setting_response(resp: object) -> bool:
    """Return whether a 200 response has the JMComic API envelope.

    A CDN/WAF can return an HTML page with HTTP 200.  Checking the normal
    ``code``/``data`` envelope keeps those pages from being recommended as API
    domains while remaining compatible with the current jmcomic response
    format.
    """
    # Future jmcomic versions may return a wrapped API response object here.
    model_data = getattr(resp, "model_data", None)
    res_data = getattr(resp, "res_data", None)
    if isinstance(model_data, (dict, list)) or isinstance(res_data, (dict, list)):
        return True

    json_method = getattr(resp, "json", None)
    if not callable(json_method):
        return False
    try:
        payload = json_method()
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    return str(payload.get("code", "")) == "200" and "data" in payload


def parse_args():
    parser = argparse.ArgumentParser(description="Check health and connectivity of JMComic domains")
    parser.add_argument(
        "--type",
        choices=["all", "html", "api"],
        default="all",
        help="Type of domains to check (default: all)",
    )
    parser.add_argument(
        "--proxy",
        help="Proxy URL (e.g., http://127.0.0.1:7890) or 'none' to bypass proxy",
    )
    proxy_group = parser.add_mutually_exclusive_group()
    proxy_group.add_argument(
        "--auto-proxy",
        dest="auto_proxy",
        action="store_true",
        help="Automatically detect and try a local proxy (default: enabled)",
    )
    proxy_group.add_argument(
        "--no-auto-proxy",
        dest="auto_proxy",
        action="store_false",
        help="Disable local proxy auto-detection",
    )
    parser.set_defaults(auto_proxy=True)
    parser.add_argument(
        "--best",
        action="store_true",
        help="Output only the best available domain(s)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Request timeout in seconds (default: 5)",
    )
    parser.add_argument(
        "--option",
        help="Path to option.yml file",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Setup base option
    try:
        service = JmcomicService(option_path=args.option)
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"Error: failed to initialize JmcomicService: {exc}", file=sys.stderr)
        sys.exit(1)
    option = service.option

    # Configure proxy
    detected_proxy = None
    if args.proxy:
        if args.proxy.lower() == "none":
            option.client.postman.meta_data["proxies"] = {}
        else:
            option.client.postman.meta_data["proxies"] = {
                "http": args.proxy,
                "https": args.proxy,
            }
    else:
        # Check if option already has proxy; if not and auto-proxy is on, check local
        current_proxies = option.client.postman.meta_data.get("proxies")
        if not current_proxies and args.auto_proxy:
            detected_proxy = detect_local_proxy()
            if detected_proxy:
                option.client.postman.meta_data["proxies"] = {
                    "http": detected_proxy,
                    "https": detected_proxy,
                }

    domain_map = fetch_candidate_domains(args.type)
    results: list[dict] = []

    for dtype, domains in domain_map.items():
        for d in domains:
            res = test_single_domain(d, dtype, option, timeout=args.timeout)
            results.append(res)

    # Sort results: available first (sorted by latency), then redirect, then blocked/error
    verdict_rank = {
        "available": 1,
        "redirect": 2,
        "blocked": 3,
        "http_error": 4,
        "reset": 5,
        "ssl_error": 6,
        "timeout": 7,
        "error": 8,
    }

    results.sort(key=lambda r: (verdict_rank.get(r["verdict"], 99), r["latency_ms"] or 9999))

    best_html = next((r["domain"] for r in results if r["type"] == "html" and r["verdict"] == "available"), None)
    best_api = next((r["domain"] for r in results if r["type"] == "api" and r["verdict"] == "available"), None)

    configured_proxy = option.client.postman.meta_data.get("proxies")
    if args.proxy:
        active_proxy_str = args.proxy
    elif detected_proxy:
        active_proxy_str = detected_proxy
    elif isinstance(configured_proxy, dict):
        active_proxy_str = configured_proxy.get("https") or configured_proxy.get("http") or "Direct (No proxy)"
    elif configured_proxy:
        active_proxy_str = str(configured_proxy)
    else:
        active_proxy_str = "Direct (No proxy)"

    if args.best:
        if args.json:
            print(json.dumps({"best_html": best_html, "best_api": best_api}, indent=2, ensure_ascii=False))
        else:
            if best_html:
                print(f"Best HTML Domain: {best_html}")
            if best_api:
                print(f"Best API Domain: {best_api}")
        sys.exit(0 if (best_html or best_api) else 1)

    if args.json:
        payload = {
            "proxy": active_proxy_str,
            "best_html": best_html,
            "best_api": best_api,
            "domains": results,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        sys.exit(0 if (best_html or best_api) else 1)

    # Pretty CLI Print
    print("=" * 80)
    print(f"🌐 JMComic Domain Health Diagnostic  [Proxy: {active_proxy_str}]")
    print("=" * 80)
    print(f"{'TYPE':<6} {'DOMAIN':<24} {'STATUS':<8} {'LATENCY':<10} {'VERDICT':<14} {'DETAILS'}")
    print("-" * 80)

    for r in results:
        status_disp = str(r["status_code"]) if r["status_code"] is not None else "-"
        latency_disp = f"{r['latency_ms']} ms" if r["latency_ms"] is not None else "-"
        verdict = r["verdict"]

        if verdict == "available":
            tag = "🟢 Available"
        elif verdict == "redirect":
            tag = "🟡 Redirect"
        elif verdict == "blocked":
            tag = "🔴 Blocked"
        elif verdict == "reset":
            tag = "⚪ Reset"
        elif verdict == "ssl_error":
            tag = "⚪ SSL Expired"
        elif verdict == "timeout":
            tag = "⚪ Timeout"
        else:
            tag = "❌ Error"

        detail_disp = r["error_detail"] or "-"
        if len(detail_disp) > 30:
            detail_disp = detail_disp[:27] + "..."

        print(f"{r['type'].upper():<6} {r['domain']:<24} {status_disp:<8} {latency_disp:<10} {tag:<14} {detail_disp}")

    print("=" * 80)
    print("💡 Recommendations:")
    if best_html:
        print(f"  - Recommended HTML domain: {best_html}")
    else:
        print("  - No direct HTML domain available (check proxy configuration or enable VPN)")
    if best_api:
        print(f"  - Recommended API domain:  {best_api}")
    else:
        print("  - No direct API domain available")
    print("=" * 80)

    sys.exit(0 if (best_html or best_api) else 1)


if __name__ == "__main__":
    main()
