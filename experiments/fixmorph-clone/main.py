#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import argparse
from pathlib import Path
from detector import BackportDetector


def main():
    parser = argparse.ArgumentParser(
        description='Detect Java code segments in target_before that need backporting'
    )
    parser.add_argument('mainline_before', type=str, 
                       help='Path to mainline_before.java')
    parser.add_argument('mainline_after', type=str,
                       help='Path to mainline_after.java')
    parser.add_argument('target_before', type=str,
                       help='Path to target_before.java')
    parser.add_argument('-o', '--output', type=str, default='backport_segments.json',
                       help='Output JSON file (default: backport_segments.json)')
    parser.add_argument('-s', '--similarity', type=float, default=0.4,
                       help='Similarity threshold (default: 0.4)')
    
    args = parser.parse_args()
    
    # Validate input files
    for file_path in [args.mainline_before, args.mainline_after, args.target_before]:
        if not Path(file_path).exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            sys.exit(1)
    
    print("=" * 60)
    print("Java Backport Detector")
    print("=" * 60)
    print(f"Mainline Before: {args.mainline_before}")
    print(f"Mainline After:  {args.mainline_after}")
    print(f"Target Before:   {args.target_before}")
    print(f"Similarity Threshold: {args.similarity}")
    print("=" * 60)
    
    # Initialize detector
    detector = BackportDetector(
        mainline_before=args.mainline_before,
        mainline_after=args.mainline_after,
        target_before=args.target_before,
        similarity_threshold=args.similarity
    )
    
    # Run detection
    print("\n[1/4] Parsing ASTs...")
    detector.parse_files()
    
    print("\n[2/4] Detecting changes in mainline...")
    changes = detector.detect_mainline_changes()
    
    # Filter to only show modifications (not adds/deletes)
    modified_changes = [c for c in changes if c['operation'] == 'modify']
    
    print(f"\nFound {len(changes)} total changes ({len(modified_changes)} modifications):")
    for change in changes:
        op_symbol = "~" if change['operation'] == 'modify' else ("+" if change['operation'] == 'add' else "-")
        print(f"  {op_symbol} {change['type']}: {change['name']} ({change['operation']})")
    
    print("\n[3/4] Finding corresponding segments in target...")
    print("(Only matching modified segments - additions/deletions skipped)")
    results = detector.find_target_segments(changes)
    
    print("\n[4/4] Generating output...")
    
    # Format results
    output = {
        "summary": {
            "mainline_before": args.mainline_before,
            "mainline_after": args.mainline_after,
            "target_before": args.target_before,
            "total_changes_in_mainline": len(changes),
            "modifications_only": len([c for c in changes if c['operation'] == 'modify']),
            "target_segments_to_backport": len(results),
            "similarity_threshold": args.similarity
        },
        "segments": results
    }
    
    # Write to JSON
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Results written to: {args.output}")
    print(f"✓ Total segments to backport: {len(results)}")
    
    # Print summary
    segment_types = {}
    for result in results:
        seg_type = result['segment_type']
        segment_types[seg_type] = segment_types.get(seg_type, 0) + 1
    
    if segment_types:
        print("\nBreakdown by type:")
        for seg_type, count in segment_types.items():
            print(f"  - {seg_type}: {count}")
    
    print("=" * 60)


if __name__ == "__main__":
    main()