"""
Semantic Hunk Adapter - Phase 3+ Recovery Strategy

Intelligently adapts hunks when structural differences exist between mainline
and target branches (e.g., API refactoring, method signature changes).

When a hunk fails to apply after retries due to "not_found_single" anchor
failures, the adapter:
  1. Analyzes what the hunk is trying to do (HunkIntent extraction)
  2. Finds semantically equivalent locations in the target file
  3. Rewrites the hunk to match the target's API/structure (hunk recomposition)
  4. Validates the adapted hunk for sanity
  5. Returns confidence-scored adaptation results

Integration Point:
  - Called from planning_agent_node() when processing validation_retry_hunks
  - Triggered when: old_resolution_failed:not_found_single + semantic diagnosis confidence >60%
  - Uses semantic diagnosis from file_editor failures
"""

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import difflib

logger = logging.getLogger(__name__)


class HunkOperationType(Enum):
    """Type of operation the hunk performs"""

    IMPORT_ADDITION = "import_addition"
    METHOD_CALL = "method_call"
    METHOD_DEFINITION = "method_definition"
    FIELD_DECLARATION = "field_declaration"
    CLASS_MODIFICATION = "class_modification"
    CONDITIONAL_LOGIC = "conditional_logic"
    OBJECT_INITIALIZATION = "object_initialization"
    UNKNOWN = "unknown"


class AdaptationStrategy(Enum):
    """Strategy used to adapt the hunk"""

    EXACT_MATCH = "exact_match"  # No adaptation needed
    METHOD_RENAME = "method_rename"  # Method was renamed
    SIGNATURE_ADAPT = "signature_adapt"  # Method signature changed
    API_TRANSFORM = "api_transform"  # API completely refactored
    CONTEXT_ADJUST = "context_adjust"  # Surrounding code changed
    PATTERN_MATCH = "pattern_match"  # Semantic pattern matching
    NONE = "none"  # Could not adapt


@dataclass
class HunkIntent:
    """Parsed intent of what a hunk is trying to do"""

    operation_type: HunkOperationType
    target_entity: str  # Method name, class name, field name, etc.
    old_api_signature: Optional[str] = None  # Original API/method signature
    new_api_signature: Optional[str] = None  # New API/method signature
    change_rationale: str = ""  # Why the change was made
    confidence: float = 0.0  # Confidence in the extracted intent (0.0-1.0)

    # Supporting evidence
    original_old_string: str = ""  # Original old_string from hunk
    original_new_string: str = ""  # Original new_string from hunk


@dataclass
class AdaptationResult:
    """Result of attempting to adapt a hunk"""

    strategy: AdaptationStrategy
    success: bool
    confidence: float  # Overall confidence in adaptation (0.0-1.0)

    # Adapted hunk content
    adapted_old_string: Optional[str] = None
    adapted_new_string: Optional[str] = None

    # Analysis details
    intent: Optional[HunkIntent] = None
    equivalent_location_line: Optional[int] = None
    detected_changes: List[str] = field(default_factory=list)
    adaptation_steps: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)

    # Reasoning
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "strategy": self.strategy.value,
            "success": self.success,
            "confidence": self.confidence,
            "adapted_old_string": self.adapted_old_string,
            "adapted_new_string": self.adapted_new_string,
            "intent": {
                "operation_type": self.intent.operation_type.value
                if self.intent
                else None,
                "target_entity": self.intent.target_entity if self.intent else None,
                "confidence": self.intent.confidence if self.intent else None,
            }
            if self.intent
            else None,
            "equivalent_location_line": self.equivalent_location_line,
            "detected_changes": self.detected_changes,
            "adaptation_steps": self.adaptation_steps,
            "validation_errors": self.validation_errors,
            "reason": self.reason,
        }


class APISignatureMapper:
    """
    Maps API signatures between mainline and target implementations.

    Handles:
      - Method renames: startObject() -> xContentObject()
      - Signature changes: method(arg1) -> method(arg1, arg2)
      - Builder pattern changes: builder.method() -> object.method()
      - Parameter transformations: old_param -> new_param
    """

    def __init__(self):
        """Initialize mapper"""
        self.signature_transformations: Dict[str, str] = {}
        self.parameter_mappings: Dict[str, Dict[str, str]] = {}

    def extract_method_signature(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract method signature from text.

        Returns:
            Dict with: {method_name, return_type, parameters, modifiers}
        """
        # Pattern: [modifiers] return_type method_name(params) [throws]
        sig_pattern = (
            r"(?:(public|private|protected|static|final|synchronized)\s+)*"
            r"([\w<>,\[\]?]+)\s+(\w+)\s*\(([^)]*)\)(?:\s+throws\s+([\w,\s]+))?"
        )

        match = re.search(sig_pattern, text)
        if not match:
            return None

        modifiers = [m for m in match.group(1).split() if m] if match.group(1) else []
        return_type = match.group(2).strip() if match.group(2) else None
        method_name = match.group(3)
        parameters = (
            [p.strip() for p in match.group(4).split(",") if p.strip()]
            if match.group(4)
            else []
        )
        exceptions = (
            [e.strip() for e in match.group(5).split(",") if e.strip()]
            if match.group(5)
            else []
        )

        return {
            "method_name": method_name,
            "return_type": return_type,
            "parameters": parameters,
            "modifiers": modifiers,
            "exceptions": exceptions,
            "full_signature": match.group(0).strip(),
        }

    def extract_method_call(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract method call from text.

        Returns:
            Dict with: {object, method_name, arguments}
        """
        # Pattern: object.method(args) or just method(args)
        call_pattern = r"([\w.]+?)\.(\w+)\s*\(([^)]*)\)"

        match = re.search(call_pattern, text)
        if not match:
            return None

        object_name = match.group(1) if match.group(1) else None
        method_name = match.group(2)
        arguments = (
            [arg.strip() for arg in match.group(3).split(",") if arg.strip()]
            if match.group(3)
            else []
        )

        return {
            "object": object_name,
            "method_name": method_name,
            "arguments": arguments,
            "full_call": match.group(0).strip(),
        }

    def transform_method_call(
        self,
        old_call: Dict[str, Any],
        new_method_name: str,
        new_object: Optional[str] = None,
        parameter_mapping: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Transform a method call to use new API.

        Args:
            old_call: Extracted call info
            new_method_name: New method name
            new_object: New object name (if changed)
            parameter_mapping: Map old params to new params

        Returns:
            Transformed call string
        """
        object_part = new_object or old_call.get("object", "")
        method_name = new_method_name

        # Transform arguments
        old_args = old_call.get("arguments", [])
        new_args = []

        if parameter_mapping:
            for arg in old_args:
                new_arg = parameter_mapping.get(arg, arg)
                new_args.append(new_arg)
        else:
            new_args = old_args

        # Build new call
        if object_part:
            return f"{object_part}.{method_name}({', '.join(new_args)})"
        else:
            return f"{method_name}({', '.join(new_args)})"


class SemanticHunkAdapter:
    """
    Adapts hunks to work with structurally different target code.

    Core workflow:
      1. analyze_and_adapt() - Main entry point
      2. _extract_hunk_intent() - Understand what hunk is trying to do
      3. _find_equivalent_location() - Find similar code in target
      4. _recompose_hunk() - Rewrite hunk for target API
      5. _validate_adaptation() - Sanity checks
      6. _score_confidence() - Overall confidence assessment
    """

    def __init__(self):
        """Initialize adapter"""
        self.method_fingerprinter = None  # Will lazy-load if needed
        self.structural_matcher = None
        self.api_mapper = APISignatureMapper()  # API signature mapper

    def analyze_and_adapt(
        self,
        hunk_old_string: str,
        hunk_new_string: str,
        target_file_content: str,
        target_file_path: str,
        semantic_diagnosis: Optional[Dict[str, Any]] = None,
        mainline_context: Optional[str] = None,
    ) -> AdaptationResult:
        """
        Main entry point: analyze and adapt a single hunk.

        Args:
            hunk_old_string: The old_string from the failed hunk
            hunk_new_string: The new_string from the failed hunk
            target_file_content: Full content of target file
            target_file_path: Path to target file (for logging)
            semantic_diagnosis: Optional diagnosis from file_editor failure
            mainline_context: Context from mainline (surrounding lines)

        Returns:
            AdaptationResult with adapted_old_string/new_string if successful
        """
        logger.info(f"Starting hunk adaptation for {target_file_path}")

        # Step 1: Extract intent from the hunk
        intent = self._extract_hunk_intent(
            hunk_old_string=hunk_old_string,
            hunk_new_string=hunk_new_string,
            mainline_context=mainline_context,
        )

        result = AdaptationResult(
            strategy=AdaptationStrategy.NONE,
            success=False,
            confidence=0.0,
            intent=intent,
            reason="Initialization",
        )

        if intent.confidence < 0.3:
            result.reason = f"Low intent confidence: {intent.confidence}"
            logger.warning(result.reason)
            return result

        # Step 2: Try exact match first (no adaptation needed)
        if hunk_old_string in target_file_content:
            result.strategy = AdaptationStrategy.EXACT_MATCH
            result.success = True
            result.confidence = 1.0
            result.adapted_old_string = hunk_old_string
            result.adapted_new_string = hunk_new_string
            result.reason = "Exact match found - no adaptation needed"
            logger.info("Hunk found exactly in target file")
            return result

        # Step 3: Find equivalent location in target
        equivalent_location = self._find_equivalent_location(
            intent=intent,
            target_file_content=target_file_content,
            semantic_diagnosis=semantic_diagnosis,
        )

        if not equivalent_location:
            result.reason = "Could not find equivalent location in target"
            logger.warning(result.reason)
            return result

        result.equivalent_location_line = equivalent_location.get("line_number")
        result.adaptation_steps.append(
            f"Found equivalent at line {equivalent_location.get('line_number')}"
        )

        # Step 4: Recompose hunk for target API
        recomposed = self._recompose_hunk(
            intent=intent,
            original_old_string=hunk_old_string,
            original_new_string=hunk_new_string,
            equivalent_location=equivalent_location,
            target_file_content=target_file_content,
        )

        if not recomposed:
            result.reason = "Could not recompose hunk for target API"
            logger.warning(result.reason)
            return result

        result.strategy = recomposed.get("strategy", AdaptationStrategy.PATTERN_MATCH)
        result.adapted_old_string = recomposed.get("adapted_old_string")
        result.adapted_new_string = recomposed.get("adapted_new_string")
        result.adaptation_steps.extend(recomposed.get("steps", []))
        result.detected_changes.extend(recomposed.get("detected_changes", []))

        # Step 5: Validate adapted hunk
        validation_errors = self._validate_adaptation(
            adapted_old_string=result.adapted_old_string,
            adapted_new_string=result.adapted_new_string,
            target_file_content=target_file_content,
        )

        if validation_errors:
            result.validation_errors = validation_errors
            result.confidence = 0.3  # Downgrade confidence for validation errors
            result.reason = f"Validation errors: {'; '.join(validation_errors[:2])}"
            logger.warning(f"Validation failed: {result.reason}")
        else:
            result.success = True
            result.reason = "Adaptation successful"
            logger.info(result.reason)

        # Step 6: Score confidence
        result.confidence = self._score_confidence(
            intent_confidence=intent.confidence,
            equivalent_location_confidence=equivalent_location.get("confidence", 0.5),
            recomposition_confidence=recomposed.get("confidence", 0.5),
            validation_errors=len(validation_errors),
        )

        return result

    def _extract_hunk_intent(
        self,
        hunk_old_string: str,
        hunk_new_string: str,
        mainline_context: Optional[str] = None,
    ) -> HunkIntent:
        """
        Extract what the hunk is trying to do.

        Analyzes old_string and new_string to determine:
          - What entity is being modified (method, field, etc.)
          - What type of operation (method call, signature change, etc.)
          - Confidence in the extracted intent
        """
        intent = HunkIntent(
            operation_type=HunkOperationType.UNKNOWN,
            target_entity="",
            confidence=0.0,
            original_old_string=hunk_old_string,
            original_new_string=hunk_new_string,
        )

        # Analyze operation type
        if self._is_import_operation(hunk_old_string, hunk_new_string):
            intent.operation_type = HunkOperationType.IMPORT_ADDITION
            intent.confidence = 0.95
            match = re.search(
                r"import\s+(?:static\s+)?(?:\w+\.)*(\w+)", hunk_new_string
            )
            if match:
                intent.target_entity = match.group(1)

        elif self._is_method_call_operation(hunk_old_string, hunk_new_string):
            intent.operation_type = HunkOperationType.METHOD_CALL
            intent.confidence = 0.8
            self._extract_method_calls(hunk_old_string, hunk_new_string, intent)

        elif self._is_method_signature_change(hunk_old_string, hunk_new_string):
            intent.operation_type = HunkOperationType.METHOD_DEFINITION
            intent.confidence = 0.85
            self._extract_method_signatures(hunk_old_string, hunk_new_string, intent)

        elif self._is_field_operation(hunk_old_string, hunk_new_string):
            intent.operation_type = HunkOperationType.FIELD_DECLARATION
            intent.confidence = 0.8
            self._extract_field_info(hunk_old_string, hunk_new_string, intent)

        elif self._is_object_initialization(hunk_old_string, hunk_new_string):
            intent.operation_type = HunkOperationType.OBJECT_INITIALIZATION
            intent.confidence = 0.75
            self._extract_object_init_info(hunk_old_string, hunk_new_string, intent)

        else:
            # Generic change
            intent.operation_type = HunkOperationType.UNKNOWN
            intent.confidence = 0.4
            intent.change_rationale = "Generic code modification"

        return intent

    def _is_import_operation(self, old_str: str, new_str: str) -> bool:
        """Check if this hunk is adding/removing imports"""
        return (
            bool(re.search(r"import\s+", new_str))
            and old_str.strip() != new_str.strip()
        )

    def _is_method_call_operation(self, old_str: str, new_str: str) -> bool:
        """Check if this hunk is modifying method calls"""
        # Pattern: method_name(...)
        method_call_pattern = r"\w+\s*\("
        old_has_call = bool(re.search(method_call_pattern, old_str))
        new_has_call = bool(re.search(method_call_pattern, new_str))
        return old_has_call and new_has_call and old_str.strip() != new_str.strip()

    def _is_method_signature_change(self, old_str: str, new_str: str) -> bool:
        """Check if this hunk is changing method signatures"""
        # Pattern: [modifiers] return_type method_name(params)
        sig_pattern = r"(?:public|private|protected|static|final)?\s+[\w<>,\[\]?]+\s+\w+\s*\([^)]*\)\s*(?:\{|throws)?"
        old_has_sig = bool(re.search(sig_pattern, old_str))
        new_has_sig = bool(re.search(sig_pattern, new_str))
        return old_has_sig and new_has_sig

    def _is_field_operation(self, old_str: str, new_str: str) -> bool:
        """Check if this hunk is modifying fields"""
        field_pattern = r"(?:public|private|protected|static|final)?\s+[\w<>,\[\]?]+\s+\w+\s*(?:=|;)"
        old_has_field = bool(re.search(field_pattern, old_str))
        new_has_field = bool(re.search(field_pattern, new_str))
        return old_has_field and new_has_field

    def _is_object_initialization(self, old_str: str, new_str: str) -> bool:
        """Check if this hunk is changing object initialization"""
        # Pattern: new ClassName(...) or method().method() chains
        new_pattern = r"new\s+\w+\s*\("
        method_chain_pattern = r"\w+\s*\([^)]*\)\s*\."
        return bool(
            re.search(new_pattern, old_str + new_str)
            or re.search(method_chain_pattern, old_str + new_str)
        )

    def _extract_method_calls(
        self,
        old_str: str,
        new_str: str,
        intent: HunkIntent,
    ) -> None:
        """Extract method call information"""
        old_methods = re.findall(r"(\w+)\s*\(", old_str)
        new_methods = re.findall(r"(\w+)\s*\(", new_str)

        if old_methods:
            intent.old_api_signature = old_methods[0]
            intent.target_entity = old_methods[0]

        if new_methods:
            intent.new_api_signature = new_methods[0]
            if not intent.target_entity:
                intent.target_entity = new_methods[0]

        if old_methods != new_methods:
            intent.change_rationale = f"Method call changed from {old_methods[0]} to {new_methods[0] if new_methods else 'unknown'}"

    def _extract_method_signatures(
        self,
        old_str: str,
        new_str: str,
        intent: HunkIntent,
    ) -> None:
        """Extract method signature information"""
        sig_pattern = r"(?:public|private|protected|static|final)?\s+([\w<>,\[\]?]+)\s+(\w+)\s*\(([^)]*)\)"

        old_match = re.search(sig_pattern, old_str)
        new_match = re.search(sig_pattern, new_str)

        if old_match:
            intent.old_api_signature = old_match.group(0).strip()
            intent.target_entity = old_match.group(2)  # Method name

        if new_match:
            intent.new_api_signature = new_match.group(0).strip()
            if not intent.target_entity:
                intent.target_entity = new_match.group(2)

    def _extract_field_info(
        self,
        old_str: str,
        new_str: str,
        intent: HunkIntent,
    ) -> None:
        """Extract field information"""
        field_pattern = r"(?:public|private|protected|static|final)?\s+[\w<>,\[\]?]+\s+(\w+)\s*(?:=|;)"

        old_match = re.search(field_pattern, old_str)
        new_match = re.search(field_pattern, new_str)

        if old_match:
            intent.target_entity = old_match.group(1)
            intent.old_api_signature = old_str.strip()

        if new_match:
            intent.new_api_signature = new_str.strip()

    def _extract_object_init_info(
        self,
        old_str: str,
        new_str: str,
        intent: HunkIntent,
    ) -> None:
        """Extract object initialization information"""
        new_pattern = r"new\s+(\w+)\s*\("
        new_match = re.search(new_pattern, old_str)
        if new_match:
            intent.old_api_signature = new_match.group(0).strip()
            intent.target_entity = new_match.group(1)

        new_match = re.search(new_pattern, new_str)
        if new_match:
            intent.new_api_signature = new_match.group(0).strip()
            if not intent.target_entity:
                intent.target_entity = new_match.group(1)

    def _find_equivalent_location(
        self,
        intent: HunkIntent,
        target_file_content: str,
        semantic_diagnosis: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find semantically equivalent location in target file.

        Strategies:
          1. If diagnosis says METHOD_RENAMED: search for similar method with high confidence
          2. If diagnosis says METHOD_SIGNATURE_CHANGED: find method and extract new signature
          3. Search for partial string matches (key identifiers from old_string)
          4. Fuzzy matching for code patterns

        Returns:
            Dict with: {location_text, line_number, confidence, ...}
            or None if not found
        """
        # Strategy 1: Use semantic diagnosis if available
        if semantic_diagnosis:
            diagnosis_type = semantic_diagnosis.get("diagnosis")
            potential_matches = semantic_diagnosis.get("potential_matches", [])

            if potential_matches and diagnosis_type:
                best_match = potential_matches[0]
                return {
                    "location_text": best_match.get("signature", ""),
                    "line_number": best_match.get("line_number"),
                    "confidence": 0.75,
                    "match_type": best_match.get("match_type", "semantic"),
                }

        # Strategy 2: Search for key identifiers from original hunk
        key_identifiers = self._extract_key_identifiers(intent.original_old_string)

        for identifier in key_identifiers:
            lines = target_file_content.split("\n")
            for line_num, line in enumerate(lines, 1):
                if identifier in line and not line.strip().startswith("//"):
                    # Found a match
                    return {
                        "location_text": line.strip(),
                        "line_number": line_num,
                        "confidence": 0.6,
                        "match_type": "identifier_search",
                        "identifier": identifier,
                    }

        # Strategy 3: Fuzzy match on method/class names
        if intent.target_entity:
            lines = target_file_content.split("\n")
            for line_num, line in enumerate(lines, 1):
                if intent.target_entity in line:
                    return {
                        "location_text": line.strip(),
                        "line_number": line_num,
                        "confidence": 0.5,
                        "match_type": "entity_search",
                    }

        return None

    def _extract_key_identifiers(self, text: str) -> List[str]:
        """Extract key identifiers from text for searching"""
        identifiers = []

        # Extract method names
        method_matches = re.findall(r"(\w+)\s*\(", text)
        identifiers.extend(method_matches)

        # Extract class/type names (capitalized)
        type_matches = re.findall(r"\b([A-Z]\w+)\b", text)
        identifiers.extend(type_matches)

        # Extract field names (common patterns)
        field_matches = re.findall(r"\b(this\.\w+|\w+\s*=)", text)
        identifiers.extend(
            [m.replace("this.", "").replace(" =", "") for m in field_matches]
        )

        # Remove duplicates and return
        return list(dict.fromkeys(identifiers))  # Preserve order, remove dupes

    def _recompose_hunk(
        self,
        intent: HunkIntent,
        original_old_string: str,
        original_new_string: str,
        equivalent_location: Dict[str, Any],
        target_file_content: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Recompose hunk to work with target's API.

        Transforms the original old_string/new_string to match the target code
        structure while preserving the semantic change.
        """

        # Determine strategy based on operation type
        if intent.operation_type == HunkOperationType.IMPORT_ADDITION:
            return self._recompose_import_hunk(
                original_old_string, original_new_string, equivalent_location
            )

        elif intent.operation_type == HunkOperationType.METHOD_CALL:
            return self._recompose_method_call_hunk(
                intent,
                original_old_string,
                original_new_string,
                equivalent_location,
                target_file_content,
            )

        elif intent.operation_type == HunkOperationType.METHOD_DEFINITION:
            return self._recompose_method_definition_hunk(
                intent,
                original_old_string,
                original_new_string,
                equivalent_location,
                target_file_content,
            )

        elif intent.operation_type == HunkOperationType.OBJECT_INITIALIZATION:
            return self._recompose_object_init_hunk(
                intent,
                original_old_string,
                original_new_string,
                equivalent_location,
                target_file_content,
            )

        else:
            # Generic recomposition: try to adapt with context adjustment
            return self._recompose_generic_hunk(
                original_old_string, original_new_string, equivalent_location
            )

    def _recompose_import_hunk(
        self,
        original_old_string: str,
        original_new_string: str,
        equivalent_location: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Recompose import addition hunk"""
        # For imports, the location might be an existing import
        location_text = equivalent_location.get("location_text", "")

        return {
            "strategy": AdaptationStrategy.CONTEXT_ADJUST,
            "adapted_old_string": location_text,
            "adapted_new_string": location_text + "\n" + original_new_string.strip(),
            "confidence": 0.8,
            "steps": ["Found anchor import", "Appended new import"],
            "detected_changes": ["Import addition"],
        }

    def _recompose_method_call_hunk(
        self,
        intent: HunkIntent,
        original_old_string: str,
        original_new_string: str,
        equivalent_location: Dict[str, Any],
        target_file_content: str,
    ) -> Optional[Dict[str, Any]]:
        """Recompose method call hunk for API changes"""

        # Extract method call information
        old_call = self.api_mapper.extract_method_call(original_old_string)
        new_call = self.api_mapper.extract_method_call(original_new_string)

        if not old_call or not new_call:
            return None

        # Get surrounding context from equivalent location
        location_line = equivalent_location.get("line_number", 0)
        lines = target_file_content.split("\n")

        # Strategy 1: If old call exists in target, adapt it
        if old_call["full_call"] in target_file_content:
            # Found exact call, just transform it
            adapted_old = old_call["full_call"]
            adapted_new = self.api_mapper.transform_method_call(
                old_call=old_call,
                new_method_name=new_call["method_name"],
                new_object=new_call["object"],
            )

            return {
                "strategy": AdaptationStrategy.API_TRANSFORM,
                "adapted_old_string": adapted_old,
                "adapted_new_string": adapted_new,
                "confidence": 0.8,
                "steps": [
                    f"Found method call: {old_call['full_call']}",
                    f"Transformed to: {adapted_new}",
                ],
                "detected_changes": ["Method call API changed"],
            }

        # Strategy 2: Use context location to build adapted strings
        if location_line > 0 and location_line <= len(lines):
            context_line = lines[location_line - 1]

            # Try to find method call in context line
            context_call = self.api_mapper.extract_method_call(context_line)

            if context_call:
                # Adapt based on context
                adapted_old = context_line.strip()
                adapted_new = self.api_mapper.transform_method_call(
                    old_call=context_call,
                    new_method_name=new_call["method_name"],
                    new_object=new_call["object"],
                )

                return {
                    "strategy": AdaptationStrategy.API_TRANSFORM,
                    "adapted_old_string": adapted_old,
                    "adapted_new_string": adapted_new,
                    "confidence": 0.65,
                    "steps": [
                        f"Found method at line {location_line}",
                        f"Transformed {context_call['method_name']} -> {new_call['method_name']}",
                    ],
                    "detected_changes": ["Method call API changed"],
                }

        # Strategy 3: Generic transformation
        # Try to replace method names directly
        adapted_old = original_old_string
        adapted_new = original_old_string.replace(
            old_call["method_name"], new_call["method_name"]
        )

        # If object changed, replace that too
        if old_call.get("object") and new_call.get("object"):
            if old_call["object"] != new_call["object"]:
                adapted_new = adapted_new.replace(
                    old_call["object"], new_call["object"]
                )

        return {
            "strategy": AdaptationStrategy.API_TRANSFORM,
            "adapted_old_string": adapted_old,
            "adapted_new_string": adapted_new,
            "confidence": 0.55,
            "steps": [
                f"Transformed {old_call['method_name']} -> {new_call['method_name']}",
            ],
            "detected_changes": ["Method call API changed"],
        }

    def _recompose_method_definition_hunk(
        self,
        intent: HunkIntent,
        original_old_string: str,
        original_new_string: str,
        equivalent_location: Dict[str, Any],
        target_file_content: str,
    ) -> Optional[Dict[str, Any]]:
        """Recompose method definition hunk"""

        location_line = equivalent_location.get("line_number", 0)
        lines = target_file_content.split("\n")

        if location_line > 0 and location_line <= len(lines):
            target_method = lines[location_line - 1]

            return {
                "strategy": AdaptationStrategy.SIGNATURE_ADAPT,
                "adapted_old_string": target_method,
                "adapted_new_string": target_method,  # Placeholder: would need actual rewrite
                "confidence": 0.5,
                "steps": ["Found target method", "Noted structural match"],
                "detected_changes": ["Method signature change"],
            }

        return None

    def _recompose_object_init_hunk(
        self,
        intent: HunkIntent,
        original_old_string: str,
        original_new_string: str,
        equivalent_location: Dict[str, Any],
        target_file_content: str,
    ) -> Optional[Dict[str, Any]]:
        """Recompose object initialization hunk"""

        # Extract class name
        class_match = re.search(r"new\s+(\w+)", original_old_string)
        if not class_match:
            return None

        class_name = class_match.group(1)
        location_line = equivalent_location.get("line_number", 0)

        return {
            "strategy": AdaptationStrategy.API_TRANSFORM,
            "adapted_old_string": original_old_string,
            "adapted_new_string": original_new_string,
            "confidence": 0.6,
            "steps": [
                f"Found class {class_name} at line {location_line}",
                "Object initialization adapted",
            ],
            "detected_changes": ["Object initialization changed"],
        }

    def _recompose_generic_hunk(
        self,
        original_old_string: str,
        original_new_string: str,
        equivalent_location: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Generic hunk recomposition"""

        # For generic changes, use context adjustment
        location_text = equivalent_location.get("location_text", "")

        # If we have meaningful context, use it as anchor
        if location_text:
            return {
                "strategy": AdaptationStrategy.CONTEXT_ADJUST,
                "adapted_old_string": location_text,
                "adapted_new_string": location_text
                + "\n"
                + original_new_string.strip(),
                "confidence": 0.5,
                "steps": ["Found context anchor", "Adjusted for target structure"],
                "detected_changes": ["Code structure changed"],
            }

        return None

    def _validate_adaptation(
        self,
        adapted_old_string: Optional[str],
        adapted_new_string: Optional[str],
        target_file_content: str,
    ) -> List[str]:
        """
        Validate adapted hunk for sanity.

        Checks:
          1. adapted_old_string exists in target file (or key identifiers found)
          2. No syntax errors detected
          3. Logic preservation (heuristic)
          4. Context integrity

        Returns:
            List of validation errors (empty if all pass)
        """
        errors = []

        if not adapted_old_string or not adapted_new_string:
            errors.append("Missing adapted old or new string")
            return errors

        # Check 1: adapted_old_string exists in target (or at least key parts exist)
        if adapted_old_string not in target_file_content:
            # More lenient: check if key identifiers from old_string exist
            key_identifiers = self._extract_key_identifiers(adapted_old_string)
            found_identifiers = sum(
                1 for id in key_identifiers if id in target_file_content
            )

            # If less than 50% of key identifiers found, it's suspicious
            if key_identifiers and found_identifiers < len(key_identifiers) * 0.5:
                errors.append(
                    f"Adapted old_string not found in target file (only {found_identifiers}/{len(key_identifiers)} identifiers found)"
                )

        # Check 2: Syntax sanity (basic bracket matching)
        if not self._check_bracket_balance(adapted_new_string):
            errors.append("Bracket/paren imbalance in adapted new_string")

        # Check 3: Logic preservation (heuristic: if old has identifiers, new should too)
        old_identifiers = set(re.findall(r"\b\w+\b", adapted_old_string))
        new_identifiers = set(re.findall(r"\b\w+\b", adapted_new_string))

        # Some identifiers may be removed (good), but shouldn't lose critical ones
        critical_keywords = {
            "this",
            "return",
            "if",
            "for",
            "while",
            "class",
            "interface",
        }
        lost_keywords = (old_identifiers & critical_keywords) - new_identifiers

        if lost_keywords:
            errors.append(f"Lost critical keywords: {lost_keywords}")

        return errors

        # Check 1: adapted_old_string exists in target
        if adapted_old_string not in target_file_content:
            errors.append(f"Adapted old_string not found in target file")

        # Check 2: Syntax sanity (basic bracket matching)
        if not self._check_bracket_balance(adapted_new_string):
            errors.append("Bracket/paren imbalance in adapted new_string")

        # Check 3: Logic preservation (heuristic: if old has identifiers, new should too)
        old_identifiers = set(re.findall(r"\b\w+\b", adapted_old_string))
        new_identifiers = set(re.findall(r"\b\w+\b", adapted_new_string))

        # Some identifiers may be removed (good), but shouldn't lose critical ones
        critical_keywords = {
            "this",
            "return",
            "if",
            "for",
            "while",
            "class",
            "interface",
        }
        lost_keywords = (old_identifiers & critical_keywords) - new_identifiers

        if lost_keywords:
            errors.append(f"Lost critical keywords: {lost_keywords}")

        return errors

    def _check_bracket_balance(self, text: str) -> bool:
        """Check if brackets/parens are balanced"""
        stack = {"(": ")", "[": "]", "{": "}"}
        paren_stack = []

        i = 0
        while i < len(text):
            char = text[i]

            # Handle string literals
            if char in "\"'":
                quote = char
                i += 1
                while i < len(text) and text[i] != quote:
                    if text[i] == "\\":
                        i += 2
                    else:
                        i += 1
                i += 1
                continue

            if char in stack:
                paren_stack.append(char)
            elif char in stack.values():
                if not paren_stack:
                    return False
                if stack[paren_stack[-1]] != char:
                    return False
                paren_stack.pop()

            i += 1

        return len(paren_stack) == 0

    def _score_confidence(
        self,
        intent_confidence: float,
        equivalent_location_confidence: float,
        recomposition_confidence: float,
        validation_errors: int,
    ) -> float:
        """
        Calculate overall confidence score (0.0-1.0).

        Uses multiplicative scoring:
          base = intent_conf * location_conf * recomp_conf
          Then apply penalty for validation errors
        """

        # Multiplicative scoring for individual components
        base_confidence = (
            intent_confidence
            * equivalent_location_confidence
            * recomposition_confidence
        )

        # Apply penalty for validation errors
        error_penalty = 1.0 - (validation_errors * 0.1)  # 10% per error
        error_penalty = max(0.0, min(1.0, error_penalty))  # Clamp to [0, 1]

        # Final confidence
        final_confidence = base_confidence * error_penalty

        return max(0.0, min(1.0, final_confidence))  # Clamp to [0, 1]
