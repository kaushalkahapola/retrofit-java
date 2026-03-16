#!/usr/bin/env python3
"""
Debug script to analyze hunk corruption in the druid_5b093294 case.

Inspects the generated hunk and shows:
1. What the hunk_text actually contains
2. What git apply sees when applying it
3. Line-by-line validation of hunk header vs content
"""

import json
import subprocess
import tempfile
import os
from pathlib import Path

# Load the generated hunk
hunk_json_path = "/media/kaushal/FDrive/retrofit-java/agents-backend/evaluate/pipeline/results/druid/druid_5b093294/phase3_hunk_generator_hunk_generator.json"

with open(hunk_json_path, "r") as f:
    hunk_data = json.load(f)

hunk = hunk_data["adapted_code_hunks"][0]
hunk_text = hunk["hunk_text"]

print("=" * 80)
print("HUNK CORRUPTION DEBUG")
print("=" * 80)

print("\n1. Raw Hunk Text (with escaped chars visible):")
print("-" * 80)
print(repr(hunk_text[:500]))  # Show repr to see actual \n chars
print("\n... [truncated] ...\n")
print(repr(hunk_text[-300:]))

print("\n2. Hunk Text Line by Line:")
print("-" * 80)
lines = hunk_text.split("\n")
for i, line in enumerate(lines, 1):
    # Show line content with length
    prefix = f"L{i:3d}: "
    visible = repr(line)[:70]
    print(f"{prefix}{visible:70s} len={len(line)}")

print(f"\nTotal lines: {len(lines)}")

print("\n3. Hunk Header Analysis:")
print("-" * 80)
header = lines[0]
print(f"Header: {repr(header)}")

# Parse header
import re
match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)", header)
if match:
    old_start = int(match.group(1))
    old_count = int(match.group(2) or 1)
    new_start = int(match.group(3))
    new_count = int(match.group(4) or 1)
    
    print(f"  Old: starts at line {old_start}, expects {old_count} lines")
    print(f"  New: starts at line {new_start}, expects {new_count} lines")
    
    # Count actual diff lines
    removed_lines = 0
    added_lines = 0
    context_lines = 0
    
    for line in lines[1:]:
        if line.startswith("-"):
            removed_lines += 1
        elif line.startswith("+"):
            added_lines += 1
        elif line.startswith(" "):
            context_lines += 1
        # Skip empty hunk trailing newline
    
    expected_old = context_lines + removed_lines
    expected_new = context_lines + added_lines
    
    print(f"\n  Actual counts:")
    print(f"    Context lines: {context_lines}")
    print(f"    Removed lines: {removed_lines}")
    print(f"    Added lines: {added_lines}")
    print(f"    Total old should be: {expected_old} (header says {old_count})")
    print(f"    Total new should be: {expected_new} (header says {new_count})")
    
    if expected_old != old_count:
        print(f"    ❌ MISMATCH: Expected {old_count} lines, got {expected_old}")
    if expected_new != new_count:
        print(f"    ❌ MISMATCH: Expected {new_count} lines, got {expected_new}")

print("\n4. Build Full Patch and Test git apply:")
print("-" * 80)

# Build a complete patch file
target_file = hunk["target_file"]
p = target_file.replace("\\", "/").lstrip("/")

patch_content = (
    f"diff --git a/{p} b/{p}\n"
    f"index 0000000..0000000 100644\n"
    f"--- a/{p}\n"
    f"+++ b/{p}\n"
    f"{hunk_text}"
)

# Try to apply dry-run
tmp_path = None
try:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False, encoding="utf-8") as tmp:
        tmp.write(patch_content)
        tmp_path = tmp.name
    
    print(f"Patch written to: {tmp_path}")
    print(f"Patch size: {len(patch_content)} bytes")
    
    # Run git apply --check
    repo_path = "/media/kaushal/FDrive/retrofit-java/temp_repo_storage/druid"
    result = subprocess.run(
        ["git", "apply", "--check", tmp_path],
        capture_output=True,
        text=True,
        cwd=repo_path,
    )
    
    print(f"\ngit apply --check exit code: {result.returncode}")
    if result.returncode != 0:
        print(f"STDERR:\n{result.stderr}")
        print(f"STDOUT:\n{result.stdout}")
    else:
        print("✅ Patch applied successfully!")
        
finally:
    if tmp_path and os.path.exists(tmp_path):
        os.unlink(tmp_path)

print("\n5. First 30 lines of built patch:")
print("-" * 80)
patch_lines = patch_content.split("\n")
for i, line in enumerate(patch_lines[:30], 1):
    print(f"L{i:3d}: {repr(line)}")
