#!/usr/bin/env python3
"""
Ranking tracker tool.
Track and export ranking changes over time.

Usage:
    # Get current daily ranking
    python scripts/ranking_tracker.py --period day --output daily_ranking.json
    
    # Get multiple pages
    python scripts/ranking_tracker.py --period week --max-pages 3 --output weekly_top.csv
    
    # Track all periods
    python scripts/ranking_tracker.py --all --output rankings/
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    from jmcomic_ai.core import JmcomicService
except ImportError:
    print("❌ Error: jmcomic_ai not found. Please ensure the package is installed.")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Track JMComic rankings")
    
    # Period selection
    period_group = parser.add_mutually_exclusive_group(required=True)
    period_group.add_argument("--period", type=str, choices=["day", "week", "month"], help="Ranking period")
    period_group.add_argument("--all", action="store_true", help="Track all periods (day, week, month)")
    
    # Options
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum pages to fetch (default: 1)")
    parser.add_argument("--output", type=str, required=True, help="Output file/directory (.csv, .json, or directory for --all)")
    parser.add_argument("--option", type=str, help="Path to option.yml file")
    parser.add_argument("--add-timestamp", action="store_true", help="Add timestamp to output filename")
    
    return parser.parse_args()


def fetch_ranking(service: JmcomicService, period: str, max_pages: int) -> list[dict]:
    """Fetch ranking for a specific period"""
    all_results = []
    
    for page in range(1, max_pages + 1):
        print(f"  📄 Fetching {period} ranking page {page}...")
        
        try:
            results = service.get_ranking(period=period, page=page)
            if not results:
                print(f"  ⚠️ No results on page {page}, stopping.")
                break
            
            # Add ranking position
            for i, result in enumerate(results):
                result["rank"] = (page - 1) * len(results) + i + 1
                result["period"] = period
            
            all_results.extend(results)
            print(f"  ✅ Found {len(results)} albums")
        except Exception as e:
            print(f"  ❌ Error on page {page}: {e}")
            break
    
    return all_results


def export_to_csv(results: list[dict], output_path: Path):
    """Export results to CSV format"""
    if not results:
        print(f"⚠️ No results to export to {output_path}")
        return
    
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["rank", "id", "title", "tags", "cover_url", "period"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        for result in results:
            row = result.copy()
            row["tags"] = ", ".join(result.get("tags", []))
            writer.writerow(row)
    
    print(f"✅ Exported {len(results)} albums to {output_path}")


def export_to_json(results: list[dict], output_path: Path):
    """Export results to JSON format"""
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "total_count": len(results),
        "rankings": results
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Exported {len(results)} albums to {output_path}")


def get_output_path(base_path: str, period: str, add_timestamp: bool) -> Path:
    """Generate output path with optional timestamp"""
    path = Path(base_path)
    
    if add_timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = f"{path.stem}_{timestamp}"
        path = path.parent / f"{stem}{path.suffix}"
    
    return path


def main():
    args = parse_args()
    
    print(f"📊 Ranking Tracker Tool")
    print(f"{'='*50}")
    
    # Initialize service
    service = JmcomicService(option_path=args.option)
    
    # Determine periods to track
    if args.all:
        periods = ["day", "week", "month"]
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Tracking all periods, output to: {output_dir}")
    else:
        periods = [args.period]
    
    # Fetch and export rankings
    for period in periods:
        print(f"\n🔍 Fetching {period} ranking (max {args.max_pages} pages)...")
        results = fetch_ranking(service, period, args.max_pages)
        
        if not results:
            print(f"❌ No results for {period} ranking")
            continue
        
        # Determine output path
        if args.all:
            # For --all mode, create separate files for each period
            output_path = output_dir / f"{period}_ranking.json"
        else:
            output_path = get_output_path(args.output, period, args.add_timestamp)
        
        # Export based on file extension
        if output_path.suffix.lower() == ".csv":
            export_to_csv(results, output_path)
        else:
            export_to_json(results, output_path)
    
    print(f"\n{'='*50}")
    print(f"✨ Tracking complete!")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
