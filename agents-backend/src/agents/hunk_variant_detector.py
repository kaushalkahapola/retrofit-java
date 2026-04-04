"""
Hunk Variant Detector - Option 4 Implementation

Detects multiple code patterns in mainline that implement the same semantic fix.
For example:
  - builder.startObject(CONSTANT) + toXContent() + endObject()
  - ob.xContentObject(CONSTANT, value)
  Both might need to change CONSTANT, but they're different code patterns.

This detector generates variants for each hunk so that downstream phases
(Structural Locator, Planning Agent) can find whichever variant matches in target.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class HunkVariant:
    """A variant of how to apply a semantic fix"""

    variant_id: int
    pattern_type: str  # e.g., "chunked_builder", "direct_xontent"
    description: str
    old_string: str
    new_string: str
    found_in_mainline: bool
    line_in_mainline: Optional[int] = None
    confidence: float = 0.95
    search_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HunkVariants:
    """All variants for a single hunk"""

    hunk_index: int
    semantic_intent: str
    variants: List[HunkVariant] = field(default_factory=list)


class HunkVariantDetector:
    """Detects multiple code patterns implementing the same semantic fix"""

    def __init__(self, mainline_repo_path: str):
        self.mainline_repo_path = mainline_repo_path

    def detect_variants_for_hunk(
        self,
        hunk_index: int,
        file_path: str,
        raw_hunk: str,
        old_added_lines: List[str],
        old_removed_lines: List[str],
    ) -> Optional[HunkVariants]:
        """
        Detect all code pattern variants for a single hunk.

        Args:
            hunk_index: Index of the hunk
            file_path: Target file path (repo-relative)
            raw_hunk: Raw hunk text from unified diff
            old_added_lines: Lines being added (+)
            old_removed_lines: Lines being removed (-)

        Returns:
            HunkVariants object with all detected variants, or None
        """
        # Step 1: Extract semantic intent
        intent = self._extract_semantic_intent(
            old_removed_lines, old_added_lines, raw_hunk
        )
        if not intent:
            return None

        # Step 2: Read mainline file
        mainline_file_content = self._read_mainline_file(file_path)
        if not mainline_file_content:
            # Can't detect variants without mainline file
            return None

        # Step 3: Search for patterns matching the intent
        variants = []
        patterns = self._detect_code_patterns(
            mainline_file_content, intent, old_removed_lines, old_added_lines
        )

        for i, (pattern_type, old_str, new_str, line_no) in enumerate(patterns, 1):
            variant = HunkVariant(
                variant_id=i,
                pattern_type=pattern_type,
                description=self._describe_pattern(pattern_type),
                old_string=old_str,
                new_string=new_str,
                found_in_mainline=True,
                line_in_mainline=line_no,
                confidence=0.95,
            )
            variants.append(variant)

        # Also add the original variant (in case target has exact match)
        if old_removed_lines:
            original_variant = HunkVariant(
                variant_id=len(variants) + 1,
                pattern_type="original",
                description="Original mainline pattern (exact)",
                old_string="\n".join(old_removed_lines),
                new_string="\n".join(old_added_lines),
                found_in_mainline=True,
                line_in_mainline=None,
                confidence=1.0,
            )
            variants.append(original_variant)

        if not variants:
            return None

        return HunkVariants(
            hunk_index=hunk_index, semantic_intent=intent, variants=variants
        )

    def _extract_semantic_intent(
        self, removed_lines: List[str], added_lines: List[str], raw_hunk: str
    ) -> Optional[str]:
        """
        Extract what the hunk is semantically trying to do.

        Examples:
          "Replace COMPILATIONS_HISTORY with CACHE_EVICTIONS_HISTORY"
          "Add null check for cacheEvictionsHistory"
          "Rename method from foo to bar"
        """
        if not removed_lines or not added_lines:
            return None

        # Look for constant replacements
        removed_text = "\n".join(removed_lines)
        added_text = "\n".join(added_lines)

        # Pattern: CONSTANT1 → CONSTANT2
        removed_constants = set(re.findall(r"\b[A-Z_][A-Z0-9_]*\b", removed_text))
        added_constants = set(re.findall(r"\b[A-Z_][A-Z0-9_]*\b", added_text))

        const_changes = removed_constants - added_constants
        if const_changes:
            added_new = added_constants - removed_constants
            if added_new:
                from_const = ", ".join(sorted(const_changes)[:2])
                to_const = ", ".join(sorted(added_new)[:2])
                return f"Replace {from_const} with {to_const}"

        # Pattern: Method call change
        if "(" in removed_text and "(" in added_text:
            removed_methods = re.findall(r"(\w+)\s*\(", removed_text)
            added_methods = re.findall(r"(\w+)\s*\(", added_text)
            if removed_methods and added_methods:
                if removed_methods[0] != added_methods[0]:
                    return f"Change method {removed_methods[0]} to {added_methods[0]}"

        # Pattern: Add null check
        if "if (" in added_text and "null" in added_text:
            return "Add null check"

        # Generic intent
        return "Apply semantic fix"

    def _read_mainline_file(self, file_path: str) -> Optional[str]:
        """Read the mainline file to search for patterns"""
        try:
            full_path = Path(self.mainline_repo_path) / file_path
            if full_path.exists():
                return full_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.debug(f"Could not read mainline file {file_path}: {e}")
        return None

    def _detect_code_patterns(
        self,
        file_content: str,
        intent: str,
        removed_lines: List[str],
        added_lines: List[str],
    ) -> List[tuple]:
        """
        Detect different code patterns that match the semantic intent.

        Returns list of: (pattern_type, old_string, new_string, line_number)
        """
        patterns = []

        # Extract what we're looking for
        removed_text = "\n".join(removed_lines)

        # Check for keyword patterns to guide pattern detection
        if "builder.startObject" in removed_text or "builder." in removed_text:
            patterns.extend(
                self._detect_builder_patterns(
                    file_content, intent, removed_lines, added_lines
                )
            )

        if "xContentObject" in removed_text or "xContentObject" in file_content:
            patterns.extend(
                self._detect_xcontent_patterns(
                    file_content, intent, removed_lines, added_lines
                )
            )

        if ".get(" in removed_text or ".set(" in removed_text:
            patterns.extend(
                self._detect_getter_setter_patterns(
                    file_content, intent, removed_lines, added_lines
                )
            )

        return patterns

    def _detect_builder_patterns(
        self,
        file_content: str,
        intent: str,
        removed_lines: List[str],
        added_lines: List[str],
    ) -> List[tuple]:
        """Detect builder.startObject(...).xContent(...).endObject() patterns"""
        patterns = []

        # Look for: builder.startObject(CONSTANT)
        match = re.search(
            r"builder\.startObject\(([A-Z_][A-Z0-9_]*)\)",
            "\n".join(removed_lines),
        )
        if match:
            old_const = match.group(1)
            # Find replacement constant in added lines
            added_text = "\n".join(added_lines)
            new_const = re.search(
                r"builder\.startObject\(([A-Z_][A-Z0-9_]*)\)",
                added_text,
            )
            if new_const:
                new_const = new_const.group(1)
                # Search file for all occurrences of this pattern
                for line_no, line in enumerate(file_content.splitlines(), 1):
                    if f"builder.startObject({old_const})" in line:
                        old_str = line.strip()
                        new_str = old_str.replace(
                            f"builder.startObject({old_const})",
                            f"builder.startObject({new_const})",
                        )
                        patterns.append(("chunked_builder", old_str, new_str, line_no))

        return patterns

    def _detect_xcontent_patterns(
        self,
        file_content: str,
        intent: str,
        removed_lines: List[str],
        added_lines: List[str],
    ) -> List[tuple]:
        """Detect ob.xContentObject(...) or similar patterns"""
        patterns = []

        # Look for xContentObject usage
        match = re.search(
            r"(?:ob|builder)\.xContentObject\(([A-Z_][A-Z0-9_]*),\s*(\w+)\)",
            "\n".join(removed_lines),
        )
        if match:
            old_const = match.group(1)
            value_var = match.group(2)

            # Find replacement in added lines
            added_text = "\n".join(added_lines)
            new_const_match = re.search(
                r"(?:ob|builder)\.xContentObject\(([A-Z_][A-Z0-9_]*),",
                added_text,
            )
            if new_const_match:
                new_const = new_const_match.group(1)
                # Search file for this pattern
                pattern = rf"xContentObject\({re.escape(old_const)}\s*,\s*{re.escape(value_var)}\)"
                for line_no, line in enumerate(file_content.splitlines(), 1):
                    if re.search(pattern, line):
                        old_str = line.strip()
                        new_str = old_str.replace(
                            f"{old_const},",
                            f"{new_const},",
                        )
                        patterns.append(("direct_xontent", old_str, new_str, line_no))

        return patterns

    def _detect_getter_setter_patterns(
        self,
        file_content: str,
        intent: str,
        removed_lines: List[str],
        added_lines: List[str],
    ) -> List[tuple]:
        """Detect getter/setter patterns like .get(KEY) or .set(KEY, value)"""
        patterns = []

        # Look for .get(CONSTANT) or .set(CONSTANT, ...)
        removed_text = "\n".join(removed_lines)
        added_text = "\n".join(added_lines)

        match = re.search(r"\.(?:get|set)\(([A-Z_][A-Z0-9_]*)", removed_text)
        if match:
            old_const = match.group(1)
            new_const_match = re.search(
                r"\.(?:get|set)\(([A-Z_][A-Z0-9_]*)",
                added_text,
            )
            if new_const_match:
                new_const = new_const_match.group(1)
                if old_const != new_const:
                    # Search file for this usage
                    pattern = rf"\.(?:get|set)\({re.escape(old_const)}\b"
                    for line_no, line in enumerate(file_content.splitlines(), 1):
                        if re.search(pattern, line):
                            old_str = line.strip()
                            new_str = old_str.replace(
                                f"({old_const}",
                                f"({new_const}",
                            )
                            patterns.append(
                                ("getter_setter", old_str, new_str, line_no)
                            )

        return patterns

    def _describe_pattern(self, pattern_type: str) -> str:
        """Generate a human-readable description of the pattern"""
        descriptions = {
            "chunked_builder": "ChunkedToXContent API with builder.startObject()",
            "direct_xontent": "Direct toXContent API with ob.xContentObject()",
            "getter_setter": "Getter/setter with constant replacement",
            "original": "Original mainline pattern (exact match)",
        }
        return descriptions.get(pattern_type, f"Pattern type: {pattern_type}")
