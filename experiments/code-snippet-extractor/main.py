import sys
import os
from src.differ import MainlineDiffer
from src.locator import TargetLocator

def main():
    # Paths (Hardcoded for this snippet)
    base_dir = "inputs"
    main_before = os.path.join(base_dir, "mainline_before.java")
    main_after = os.path.join(base_dir, "mainline_after.java")
    target_before = os.path.join(base_dir, "target_before.java")

    print("--- Phase 1: Analyzing Mainline Changes ---")
    differ = MainlineDiffer(main_before, main_after)
    changes = differ.identify_changed_context()

    if not changes:
        print("No significant modifications detected in mainline anchors.")
        return

    print(f"Detected {len(changes)} modification anchor(s).")
    # Debug: Print which anchors we are actually looking for
    for c in changes:
        print(f"  - Anchor: {c['signature']}")

    print("\n--- Phase 2: Locating in Target ---")
    locator = TargetLocator(target_before)
    
    # Deduplication Set: Track which Target Method Names we have already extracted
    extracted_targets = set()

    for change in changes:
        print(f"\nProcessing Context: {change['signature']}")
        snippet_info = locator.find_and_extract(change)
        
        if snippet_info:
            target_method_name = snippet_info['method_name']
            
            # DEDUPLICATION CHECK
            if target_method_name in extracted_targets:
                print(f"  [!] Skipping duplicate extraction: {target_method_name} already processed.")
                continue
                
            extracted_targets.add(target_method_name)
            
            print("\n--- EXTRACTED SNIPPET FOR ML MODEL ---")
            print(snippet_info['code'])
            print("--------------------------------------")
        else:
            print("Could not locate relevant context in target file.")

if __name__ == "__main__":
    main()