#!/usr/bin/env python3
"""
Configuration validation and conversion tool.
Validates option.yml files and converts between formats.

Usage:
    python scripts/validate_config.py ~/.jmcomic/option.yml
    python scripts/validate_config.py --convert-to-json option.yml
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from jmcomic import JmOption, create_option_by_file
except ImportError:
    print("❌ Error: jmcomic not found. Please install: pip install jmcomic")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Validate and convert JMComic configuration")
    parser.add_argument(
        "config_file",
        type=str,
        help="Path to option.yml file to validate"
    )
    parser.add_argument(
        "--convert-to-json",
        action="store_true",
        help="Convert YAML config to JSON format"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path for conversion (default: same name with .json extension)"
    )
    return parser.parse_args()


def validate_config(config_path: Path) -> tuple[bool, JmOption | None, str]:
    """
    Validate configuration file
    
    Returns:
        (is_valid, option_object, error_message)
    """
    if not config_path.exists():
        return False, None, f"File not found: {config_path}"
    
    try:
        option = create_option_by_file(str(config_path))
        return True, option, ""
    except Exception as e:
        return False, None, str(e)


def convert_to_json(option: JmOption, output_path: Path):
    """Convert JmOption to JSON format"""
    try:
        option_dict = option.deconstruct()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(option_dict, f, indent=2, ensure_ascii=False)
        return True, ""
    except Exception as e:
        return False, str(e)


def print_config_summary(option: JmOption):
    """Print a summary of the configuration"""
    print("\n📋 Configuration Summary:")
    print(f"{'='*50}")
    
    # Client settings
    print(f"🌐 Client:")
    print(f"  - Implementation: {option.client.get('impl', 'html')}")
    if 'domain' in option.client:
        print(f"  - Domain: {option.client['domain']}")
    
    # Download settings
    print(f"\n📥 Download:")
    threading = option.download.get('threading', {})
    print(f"  - Image threads: {threading.get('image', 30)}")
    print(f"  - Photo threads: {threading.get('photo', 5)}")
    
    # Directory settings
    print(f"\n📂 Directory:")
    print(f"  - Base dir: {option.dir_rule.base_dir}")
    print(f"  - Rule: {option.dir_rule.get('rule', 'Bd / Ptitle')}")
    
    # Proxy settings
    postman_meta = option.client.get('postman', {}).get('meta_data', {})
    if 'proxies' in postman_meta:
        print(f"\n🔒 Proxy:")
        proxies = postman_meta['proxies']
        if isinstance(proxies, dict):
            for key, value in proxies.items():
                print(f"  - {key}: {value}")
        else:
            print(f"  - {proxies}")
    
    print(f"{'='*50}")


def main():
    args = parse_args()
    config_path = Path(args.config_file).resolve()
    
    print(f"🔍 Validating configuration file: {config_path}")
    
    # Validate
    is_valid, option, error_msg = validate_config(config_path)
    
    if not is_valid:
        print(f"\n❌ Validation Failed:")
        print(f"   {error_msg}")
        sys.exit(1)
    
    print(f"✅ Configuration is valid!")
    
    # Print summary
    print_config_summary(option)
    
    # Convert to JSON if requested
    if args.convert_to_json:
        output_path = Path(args.output) if args.output else config_path.with_suffix('.json')
        print(f"\n🔄 Converting to JSON: {output_path}")
        
        success, error = convert_to_json(option, output_path)
        if success:
            print(f"✅ Successfully converted to {output_path}")
        else:
            print(f"❌ Conversion failed: {error}")
            sys.exit(1)


if __name__ == "__main__":
    main()
