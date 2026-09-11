import argparse
import importlib.util
import shutil
import subprocess
import sys

try:
    from ._script_utils import exit_for_import_error
except ImportError:
    from _script_utils import exit_for_import_error  # type: ignore[no-redef]

try:
    from jmcomic_ai.core import JmcomicService
except ImportError as exc:
    exit_for_import_error(exc, "jmcomic_ai", "Please ensure the package is installed.")


# Optional third-party dependency required by each processing type.
# zip uses the stdlib zipfile module, so no external dependency is needed.
TYPE_DEPENDENCIES = {
    "img2pdf": "img2pdf",
    "long_img": "PIL",
}


def ensure_dependencies(process_type: str, auto_install: bool = True) -> None:
    """Check the optional dependency of `process_type`; install or explain when missing."""
    lib = TYPE_DEPENDENCIES.get(process_type)
    if not lib or importlib.util.find_spec(lib) is not None:
        return

    lib_name = "pillow" if lib == "PIL" else lib
    if auto_install and shutil.which(sys.executable):
        print(f"📦 Missing dependency '{lib}', attempting to install ({lib_name})...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", lib_name])
            print(f"✅ Installed {lib_name}")
            return
        except subprocess.CalledProcessError as exc:
            print(f"⚠️ Auto-install failed (exit {exc.returncode}).", file=sys.stderr)

    sys.exit(
        f"❌ Processing type '{process_type}' requires the '{lib}' package.\n"
        f"   Install it with: pip install {lib_name}\n"
        f"   Or re-run with dependency auto-install enabled."
    )


def main():
    parser = argparse.ArgumentParser(description="Post-process downloaded JMComic albums (Zip, PDF, LongImg)")
    parser.add_argument("--id", required=True, help="Album ID to process")
    parser.add_argument("--type", required=True, choices=["zip", "img2pdf", "long_img"], help="Processing type")
    parser.add_argument("--option", help="Path to option.yml")
    parser.add_argument("--delete", action="store_true", help="Delete original files after processing")
    parser.add_argument("--password", help="Password for encryption (Zip/PDF)")
    parser.add_argument("--outdir", help="Output directory")
    parser.add_argument("--no-install-deps", action="store_true",
                        help="Disable auto-install of missing optional dependencies (e.g. img2pdf)")
    parser.add_argument("--dir-rule", help="Output DSL rule, e.g. 'Bd/{Atitle}/{Pindex}.zip'")
    parser.add_argument("--base-dir", help="Base directory used with --dir-rule")
    parser.add_argument("--level", choices=["album", "photo"], default="photo", help="Processing level (default: photo)")

    args = parser.parse_args()

    if args.outdir and (args.dir_rule or args.base_dir):
        parser.error("--outdir cannot be used with --dir-rule/--base-dir")

    if args.dir_rule and not args.base_dir:
        parser.error("--base-dir is required when using --dir-rule")

    if args.base_dir and not args.dir_rule:
        parser.error("--dir-rule is required when using --base-dir")

    if args.password and args.type == "long_img":
        parser.error("--password is only supported for zip or img2pdf")

    # 参数校验全部通过后再装依赖，避免无效命令也去改环境
    ensure_dependencies(args.type, auto_install=not getattr(args, "no_install_deps", False))

    service = JmcomicService(args.option)

    params = {"level": args.level}
    if args.delete:
        params["delete_original_file"] = True
    if args.password:
        params["encrypt"] = {"password": args.password}

    if args.dir_rule and args.base_dir:
        params["dir_rule"] = {"rule": args.dir_rule, "base_dir": args.base_dir}
    elif args.outdir:
        # The plugin writes the processed file AT the path produced by the rule.
        # A bare "Bd" rule resolves to --outdir itself (a directory), which makes
        # the writer fail with PermissionError. Always append a filename with the
        # proper extension so the output lands INSIDE the given directory.
        ext = {"zip": "zip", "img2pdf": "pdf", "long_img": "png"}[args.type]
        filename = "{Atitle}" if args.level == "album" else "{Aid}_{Pindex}"
        params["dir_rule"] = {"rule": f"Bd/{filename}.{ext}", "base_dir": args.outdir}

    result = service.post_process(args.id, args.type, params)
    print(result)

    if result.get("status") != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
