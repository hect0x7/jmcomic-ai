"""Download the latest APK published by hect0x7/JMComic-APK."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

LATEST_RELEASE_API = "https://api.github.com/repos/hect0x7/JMComic-APK/releases/latest"
USER_AGENT = "jmcomic-ai"


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )


def fetch_latest_apk(timeout: float = 30) -> dict[str, Any]:
    """Return metadata for the APK asset in the latest GitHub release."""
    with urllib.request.urlopen(_request(LATEST_RELEASE_API), timeout=timeout) as response:
        release = json.load(response)

    assets = release.get("assets") or []
    apk_assets = [asset for asset in assets if str(asset.get("name", "")).lower().endswith(".apk")]
    if not apk_assets:
        raise RuntimeError("The latest JMComic-APK release does not contain an APK asset")
    if len(apk_assets) > 1:
        raise RuntimeError("The latest JMComic-APK release contains multiple APK assets")

    asset = apk_assets[0]
    name = str(asset["name"])
    download_url = str(asset["browser_download_url"])
    parsed_url = urlsplit(download_url)
    if Path(name).name != name or "\\" in name:
        raise RuntimeError("The latest JMComic-APK release contains an unsafe asset name")
    if parsed_url.scheme != "https" or parsed_url.hostname != "github.com":
        raise RuntimeError("The latest JMComic-APK release contains an unexpected download URL")

    return {
        "version": str(release.get("tag_name") or release.get("name") or "unknown"),
        "release_url": str(release.get("html_url") or ""),
        "name": name,
        "size": int(asset.get("size") or 0),
        "digest": str(asset.get("digest") or ""),
        "download_url": download_url,
    }


def download_apk(asset: dict[str, Any], output_dir: Path, force: bool = False, timeout: float = 60) -> Path:
    """Download one APK asset atomically and return its absolute path."""
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / str(asset["name"])
    expected_size = int(asset.get("size") or 0)
    digest = str(asset.get("digest") or "")
    expected_sha256 = digest.removeprefix("sha256:") if digest.startswith("sha256:") else ""

    if target.exists() and not force:
        size_matches = expected_size == 0 or target.stat().st_size == expected_size
        digest_matches = not expected_sha256 or _sha256(target) == expected_sha256
        if size_matches and digest_matches:
            return target
        raise FileExistsError(f"Existing file has an unexpected size or digest: {target}. Use --force to replace it")

    temp_path: Path | None = None
    try:
        with urllib.request.urlopen(_request(str(asset["download_url"])), timeout=timeout) as response:
            with tempfile.NamedTemporaryFile(
                dir=output_dir, prefix=f".{target.name}.", suffix=".part", delete=False
            ) as tmp:
                temp_path = Path(tmp.name)
                while chunk := response.read(1024 * 1024):
                    tmp.write(chunk)

        actual_size = temp_path.stat().st_size
        if expected_size and actual_size != expected_size:
            raise RuntimeError(f"APK size mismatch: expected {expected_size} bytes, downloaded {actual_size} bytes")
        if expected_sha256:
            actual_sha256 = _sha256(temp_path)
            if actual_sha256 != expected_sha256:
                raise RuntimeError(f"APK SHA-256 mismatch: expected {expected_sha256}, downloaded {actual_sha256}")
        os.replace(temp_path, target)
        return target
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def _sha256(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            checksum.update(chunk)
    return checksum.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download the latest APK from hect0x7/JMComic-APK")
    parser.add_argument("output_dir", nargs="?", default=".", help="Download directory (default: current directory)")
    parser.add_argument("--force", action="store_true", help="Replace an existing APK with the same filename")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON result")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        asset = fetch_latest_apk()
        apk_path = download_apk(asset, Path(args.output_dir), force=args.force)
    except Exception as error:
        if args.json:
            print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False))
        else:
            print(f"Failed to download JMComic APK: {error}")
        raise SystemExit(1) from error

    result = {
        "status": "success",
        "version": asset["version"],
        "release_url": asset["release_url"],
        "download_url": asset["download_url"],
        "digest": asset["digest"],
        "apk_path": str(apk_path),
        "size": apk_path.stat().st_size,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"Downloaded JMComic APK {result['version']}")
        print(f"Source: {result['release_url']}")
        print(f"Path: {result['apk_path']}")


if __name__ == "__main__":
    main()
