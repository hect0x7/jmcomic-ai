#!/usr/bin/env python3
"""
Search and export tool for JMComic.
Search albums and export results to CSV or JSON format.

Usage:
    # Search by keyword
    python scripts/search_export.py --keyword "搜索词" --output results.csv
    
    # Get daily ranking
    python scripts/search_export.py --ranking day --output ranking.json
    
    # Browse category
    python scripts/search_export.py --category doujin --output doujin.csv
"""

import argparse
import csv
import json
import sys
from pathlib import Path

try:
    from jmcomic_ai.core import JmcomicService
except ImportError:
    print("❌ Error: jmcomic_ai not found. Please ensure the package is installed.")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Search and export JMComic albums")
    
    # Search mode selection (mutually exclusive)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--keyword", type=str, help="Search by keyword")
    mode.add_argument("--ranking", type=str, choices=["day", "week", "month"], help="Get ranking")
    mode.add_argument("--category", type=str, help="Browse by category (e.g., doujin, hanman, single)")
    
    # Common options
    parser.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum pages to fetch (default: 1)")
    parser.add_argument("--output", type=str, required=True, help="Output file path (.csv or .json)")
    parser.add_argument("--option", type=str, help="Path to option.yml file")
    
    # Search-specific options
    parser.add_argument("--order-by", type=str, default="latest", help="Sort order for search (default: latest)")
    parser.add_argument("--sort-by", type=str, default="mr", help="Sort order for category (default: mr)")
    
    return parser.parse_args()


def fetch_results(service: JmcomicService, args) -> list[dict]:
    """Fetch search results based on mode"""
    all_results = []
    
    for page in range(args.page, args.page + args.max_pages):
        print(f"📄 Fetching page {page}...")
        
        if args.keyword:
            results = service.search_album(args.keyword, page=page, order_by=args.order_by)
        elif args.ranking:
            results = service.get_ranking(period=args.ranking, page=page)
        elif args.category:
            results = service.get_category_list(category=args.category, page=page, sort_by=args.sort_by)
        else:
            results = []
        
        if not results:
            print(f"⚠️ No results on page {page}, stopping.")
            break
        
        all_results.extend(results)
        print(f"✅ Found {len(results)} albums on page {page}")
    
    return all_results


def export_to_csv(results: list[dict], output_path: Path):
    """Export results to CSV format"""
    if not results:
        print("⚠️ No results to export")
        return
    
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        # Use first result to determine fields
        fieldnames = ["id", "title", "tags", "cover_url"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        for result in results:
            # Convert tags list to string
            row = result.copy()
            row["tags"] = ", ".join(result.get("tags", []))
            writer.writerow(row)
    
    print(f"✅ Exported {len(results)} albums to {output_path}")


def export_to_json(results: list[dict], output_path: Path):
    """Export results to JSON format"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Exported {len(results)} albums to {output_path}")


def main():
    args = parse_args()
    output_path = Path(args.output)
    
    # Determine export format
    if output_path.suffix.lower() not in [".csv", ".json"]:
        print("❌ Error: Output file must be .csv or .json")
        sys.exit(1)
    
    print(f"🔍 JMComic Search Export Tool")
    print(f"{'='*50}")
    
    # Initialize service
    service = JmcomicService(option_path=args.option)
    
    # Fetch results
    results = fetch_results(service, args)
    
    if not results:
        print("❌ No results found")
        sys.exit(1)
    
    print(f"\n📊 Total albums found: {len(results)}")
    
    # Export
    if output_path.suffix.lower() == ".csv":
        export_to_csv(results, output_path)
    else:
        export_to_json(results, output_path)
    
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
