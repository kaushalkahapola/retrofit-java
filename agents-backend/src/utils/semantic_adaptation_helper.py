"""
Semantic Adaptation Helper for Phase 3 (File Editor) Anchor Resolution Failures

This module provides semantic analysis capabilities to diagnose why anchor text
matching failed and suggest recovery strategies. It wraps existing semantic tools
(MethodFingerprinter, StructuralMatcher) for use in the file editor pipeline.

Architecture:
- When deterministic anchor matching (4-pass algorithm) fails, we analyze the anchor
- Semantic analysis attempts to detect: renamed methods, refactored code, moved code, etc.
- Results feed into routing logic to select appropriate retry strategy
"""

import re
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SemanticDiagnosis(Enum):
    """Root cause diagnosis for anchor resolution failure"""
    
    # Structural changes
    METHOD_RENAMED = "method_renamed"  # Method exists but with different name
    METHOD_REFACTORED = "method_refactored"  # Method signature/structure changed
    CLASS_REFACTORED = "class_refactored"  # Class structure changed
    CODE_MOVED = "code_moved"  # Code moved to different file/class
    
    # Signature changes
    METHOD_SIGNATURE_CHANGED = "method_signature_changed"  # API evolution
    
    # Context changes
    SURROUNDING_CODE_CHANGED = "surrounding_code_changed"  # Context lines no longer adjacent
    
    # Unable to diagnose
    UNKNOWN = "unknown"  # Could not determine root cause


class SemanticSeverity(Enum):
    """Severity of semantic change affecting anchor viability"""
    
    CRITICAL = "critical"  # Anchor completely invalidated
    HIGH = "high"  # Anchor severely degraded
    MEDIUM = "medium"  # Anchor needs adjustment
    LOW = "low"  # Minor code style changes
    NONE = "none"  # No semantic change detected


@dataclass
class SemanticAnalysisResult:
    """Result from semantic analysis of failed anchor"""
    
    diagnosis: SemanticDiagnosis
    severity: SemanticSeverity
    confidence: float  # 0.0-1.0 confidence in diagnosis
    
    # Root cause details
    detected_issues: List[str] = field(default_factory=list)
    potential_matches: List[Dict[str, Any]] = field(default_factory=list)
    
    # Recommended recovery strategy
    suggested_retry_strategy: Optional[str] = None
    recovery_actions: List[str] = field(default_factory=list)
    
    # Supporting evidence
    evidence: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "diagnosis": self.diagnosis.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "detected_issues": self.detected_issues,
            "potential_matches": self.potential_matches,
            "suggested_retry_strategy": self.suggested_retry_strategy,
            "recovery_actions": self.recovery_actions,
            "evidence": self.evidence,
        }


class SemanticAdaptationHelper:
    """
    Helper for semantic analysis of anchor failures.
    
    Responsibilities:
    1. Extract method/class context from anchor text
    2. Search for semantically similar code in target file
    3. Diagnose reason for anchor mismatch
    4. Suggest recovery strategy
    """
    
    def __init__(self, method_fingerprinter=None, structural_matcher=None):
        """
        Initialize helper with optional semantic tools.
        
        Args:
            method_fingerprinter: MethodFingerprinter instance (optional, will be lazy-loaded)
            structural_matcher: StructuralMatcher function (optional)
        """
        self.method_fingerprinter = method_fingerprinter
        self.structural_matcher = structural_matcher
        
        # Cache for parsed methods in target file
        self._method_cache: Dict[str, List[Dict]] = {}
    
    def analyze_anchor_failure(
        self,
        anchor_text: str,
        target_file_content: str,
        target_file_path: str,
        resolution_reason: str,
        context_lines: Optional[List[str]] = None,
    ) -> SemanticAnalysisResult:
        """
        Analyze why anchor text failed to resolve in target file.
        
        Args:
            anchor_text: The anchor text that couldn't be found
            target_file_content: Full content of target file
            target_file_path: Path to target file (for context)
            resolution_reason: Why the 4-pass algorithm failed (e.g., "not_found_single")
            context_lines: Lines surrounding the anchor in mainline (for fingerprinting)
        
        Returns:
            SemanticAnalysisResult with diagnosis and recovery suggestions
        """
        
        # Step 1: Extract method/class context from anchor text
        anchor_context = self._extract_anchor_context(anchor_text, context_lines)
        
        # Step 2: Search for semantically similar code
        potential_matches = self._find_semantic_matches(
            anchor_context=anchor_context,
            target_file_content=target_file_content,
            target_file_path=target_file_path,
        )
        
        # Step 3: Diagnose the root cause
        diagnosis = self._diagnose_failure(
            anchor_text=anchor_text,
            anchor_context=anchor_context,
            potential_matches=potential_matches,
            target_file_content=target_file_content,
            resolution_reason=resolution_reason,
        )
        
        # Step 4: Suggest recovery strategy
        recovery_strategy = self._suggest_recovery_strategy(diagnosis)
        
        return SemanticAnalysisResult(
            diagnosis=diagnosis["diagnosis"],
            severity=diagnosis["severity"],
            confidence=diagnosis["confidence"],
            detected_issues=diagnosis.get("detected_issues", []),
            potential_matches=potential_matches,
            suggested_retry_strategy=recovery_strategy.get("strategy"),
            recovery_actions=recovery_strategy.get("actions", []),
            evidence=diagnosis.get("evidence", {}),
        )
    
    def _extract_anchor_context(
        self,
        anchor_text: str,
        context_lines: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Extract method/class information from anchor text.
        
        Returns:
            Dict with extracted context: method_name, class_name, signature, etc.
        """
        context = {
            "anchor_text": anchor_text,
            "method_name": None,
            "class_name": None,
            "signature": None,
            "is_method_signature": False,
            "is_field_declaration": False,
        }
        
        # Try to extract method signature
        # Pattern: [modifiers] return_type method_name(params) [throws]
        method_pattern = r'(?:public|private|protected|static|final|synchronized)?\s+[\w<>,\[\]?]+\s+(\w+)\s*\([^)]*\)'
        method_match = re.search(method_pattern, anchor_text)
        
        if method_match:
            context["method_name"] = method_match.group(1)
            context["signature"] = method_match.group(0).strip()
            context["is_method_signature"] = True
        
        # Try to extract class declaration
        class_pattern = r'(?:public|private|protected)?\s*(?:class|interface|enum)\s+(\w+)'
        class_match = re.search(class_pattern, anchor_text)
        
        if class_match:
            context["class_name"] = class_match.group(1)
        
        # Try to extract field declaration
        field_pattern = r'(?:public|private|protected|static|final)?\s+[\w<>,\[\]?]+\s+(\w+)\s*(?:=|;)'
        field_match = re.search(field_pattern, anchor_text)
        
        if field_match:
            context["is_field_declaration"] = True
        
        return context
    
    def _find_semantic_matches(
        self,
        anchor_context: Dict[str, Any],
        target_file_content: str,
        target_file_path: str,
    ) -> List[Dict[str, Any]]:
        """
        Search for semantically similar code in target file.
        
        Returns:
            List of potential matches with similarity scores
        """
        matches = []
        
        # If we extracted a method name, search for similar methods
        if anchor_context.get("method_name"):
            matches.extend(
                self._find_similar_methods(
                    method_name=anchor_context["method_name"],
                    target_file_content=target_file_content,
                )
            )
        
        # If we extracted a class name, search for similar classes
        if anchor_context.get("class_name"):
            matches.extend(
                self._find_similar_classes(
                    class_name=anchor_context["class_name"],
                    target_file_content=target_file_content,
                )
            )
        
        # Search for substring matches (fuzzy)
        matches.extend(
            self._find_fuzzy_matches(
                anchor_text=anchor_context["anchor_text"],
                target_file_content=target_file_content,
            )
        )
        
        return matches
    
    def _find_similar_methods(
        self,
        method_name: str,
        target_file_content: str,
    ) -> List[Dict[str, Any]]:
        """
        Find methods in target file that are similar to the anchor method.
        """
        matches = []
        
        # Pattern: [modifiers] return_type method_name(params)
        method_pattern = r'(?:public|private|protected|static|final|synchronized)?\s+[\w<>,\[\]?]+\s+(\w+)\s*\(([^)]*)\)'
        
        for match in re.finditer(method_pattern, target_file_content):
            found_method_name = match.group(1)
            found_params = match.group(2)
            found_signature = match.group(0)
            line_num = target_file_content[:match.start()].count('\n') + 1
            
            # Calculate similarity
            name_similarity = self._string_similarity(method_name, found_method_name)
            
            if name_similarity > 0.6:  # Threshold for name similarity
                matches.append({
                    "type": "method",
                    "name": found_method_name,
                    "signature": found_signature,
                    "params": found_params,
                    "line_number": line_num,
                    "similarity_score": name_similarity,
                    "match_type": "exact" if name_similarity == 1.0 else "similar",
                })
        
        # Sort by similarity (exact matches first, then by score)
        matches.sort(key=lambda x: (-1 if x["match_type"] == "exact" else 0, -x["similarity_score"]))
        
        return matches
    
    def _find_similar_classes(
        self,
        class_name: str,
        target_file_content: str,
    ) -> List[Dict[str, Any]]:
        """
        Find classes in target file that are similar to the anchor class.
        """
        matches = []
        
        # Pattern: [modifiers] class ClassName [extends] [implements]
        class_pattern = r'(?:public|private|protected)?\s*(?:class|interface|enum)\s+(\w+)(?:\s+(?:extends|implements)\s+([^{]+))?'
        
        for match in re.finditer(class_pattern, target_file_content):
            found_class_name = match.group(1)
            found_inheritance = match.group(2)
            line_num = target_file_content[:match.start()].count('\n') + 1
            
            # Calculate similarity
            name_similarity = self._string_similarity(class_name, found_class_name)
            
            if name_similarity > 0.6:
                matches.append({
                    "type": "class",
                    "name": found_class_name,
                    "inheritance": found_inheritance,
                    "line_number": line_num,
                    "similarity_score": name_similarity,
                    "match_type": "exact" if name_similarity == 1.0 else "similar",
                })
        
        # Sort by similarity
        matches.sort(key=lambda x: (-1 if x["match_type"] == "exact" else 0, -x["similarity_score"]))
        
        return matches
    
    def _find_fuzzy_matches(
        self,
        anchor_text: str,
        target_file_content: str,
        context_window: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Find fuzzy matches of anchor text in target file.
        Uses sliding window approach to find partial matches.
        """
        matches = []
        
        # Split anchor into tokens
        anchor_tokens = set(re.findall(r'\b\w+\b', anchor_text))
        
        # Slide a window through target file
        lines = target_file_content.split('\n')
        
        for i in range(len(lines)):
            # Create window of lines around current position
            start = max(0, i - context_window // 2)
            end = min(len(lines), i + context_window // 2)
            window_text = '\n'.join(lines[start:end])
            
            # Calculate token overlap
            window_tokens = set(re.findall(r'\b\w+\b', window_text))
            overlap = len(anchor_tokens.intersection(window_tokens))
            
            if overlap > 0:
                similarity = overlap / len(anchor_tokens) if anchor_tokens else 0.0
                
                if similarity > 0.5:  # At least 50% token overlap
                    matches.append({
                        "type": "fuzzy_match",
                        "line_number": i + 1,
                        "context": window_text[:100],  # First 100 chars
                        "token_overlap": overlap,
                        "total_tokens": len(anchor_tokens),
                        "similarity_score": similarity,
                    })
        
        return matches
    
    def _diagnose_failure(
        self,
        anchor_text: str,
        anchor_context: Dict[str, Any],
        potential_matches: List[Dict[str, Any]],
        target_file_content: str,
        resolution_reason: str,
    ) -> Dict[str, Any]:
        """
        Diagnose the root cause of anchor failure.
        
        Returns:
            Dict with diagnosis, severity, confidence, and evidence
        """
        
        detected_issues = []
        evidence = {}
        severity = SemanticSeverity.UNKNOWN
        confidence = 0.0
        diagnosis = SemanticDiagnosis.UNKNOWN
        
        # Analysis 1: Check if method/class was renamed
        if potential_matches and anchor_context.get("method_name"):
            method_matches = [m for m in potential_matches if m.get("type") == "method"]
            if method_matches and method_matches[0]["similarity_score"] > 0.7:
                diagnosis = SemanticDiagnosis.METHOD_RENAMED
                severity = SemanticSeverity.MEDIUM
                confidence = method_matches[0]["similarity_score"]
                detected_issues.append(
                    f"Method '{anchor_context['method_name']}' likely renamed to "
                    f"'{method_matches[0]['name']}' (similarity: {confidence:.2f})"
                )
                evidence["renamed_to"] = method_matches[0]["name"]
                evidence["match_line"] = method_matches[0]["line_number"]
        
        # Analysis 2: Check if code exists in file but with modified signature
        if (
            resolution_reason == "not_found_single"
            and not anchor_context.get("is_method_signature")
            and potential_matches
        ):
            # Significant token overlap but exact text not found
            fuzzy_matches = [m for m in potential_matches if m.get("type") == "fuzzy_match"]
            if fuzzy_matches and fuzzy_matches[0]["similarity_score"] > 0.7:
                diagnosis = SemanticDiagnosis.SURROUNDING_CODE_CHANGED
                severity = SemanticSeverity.MEDIUM
                confidence = fuzzy_matches[0]["similarity_score"]
                detected_issues.append(
                    f"Code structure found but exact anchor text not present "
                    f"(token overlap: {fuzzy_matches[0]['token_overlap']}/{fuzzy_matches[0]['total_tokens']})"
                )
                evidence["token_overlap"] = fuzzy_matches[0]["token_overlap"]
                evidence["match_lines"] = [m["line_number"] for m in fuzzy_matches[:3]]
        
        # Analysis 3: Method exists but signature changed
        if anchor_context.get("is_method_signature"):
            method_matches = [m for m in potential_matches if m.get("type") == "method"]
            if (
                method_matches
                and method_matches[0]["name"] == anchor_context.get("method_name")
                and method_matches[0].get("params") != ""
            ):
                # Same method name but we didn't find the signature
                diagnosis = SemanticDiagnosis.METHOD_SIGNATURE_CHANGED
                severity = SemanticSeverity.HIGH
                confidence = 0.8
                detected_issues.append(
                    f"Method signature changed: '{anchor_context['signature']}' "
                    f"-> '{method_matches[0]['signature']}'"
                )
                evidence["old_signature"] = anchor_context["signature"]
                evidence["new_signature"] = method_matches[0]["signature"]
        
        # Default: No semantic matches found
        if diagnosis == SemanticDiagnosis.UNKNOWN and not potential_matches:
            detected_issues.append("No semantically similar code found in target file")
            severity = SemanticSeverity.CRITICAL
            confidence = 0.0
        
        return {
            "diagnosis": diagnosis,
            "severity": severity,
            "confidence": confidence,
            "detected_issues": detected_issues,
            "evidence": evidence,
        }
    
    def _suggest_recovery_strategy(
        self,
        diagnosis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Suggest a recovery strategy based on diagnosis.
        
        Returns:
            Dict with suggested strategy and recovery actions
        """
        diagnosis_type = diagnosis["diagnosis"]
        
        if diagnosis_type == SemanticDiagnosis.METHOD_RENAMED:
            return {
                "strategy": "structural_locator",
                "actions": [
                    "Use structural_locator to map methods by semantic similarity",
                    "Look for methods with similar call signatures or dependencies",
                    "Use fingerprinter to match by AST structure",
                ],
            }
        
        elif diagnosis_type == SemanticDiagnosis.METHOD_SIGNATURE_CHANGED:
            return {
                "strategy": "structural_locator",
                "actions": [
                    "Use fingerprinter tier 2 (signature matching) with relaxed params",
                    "Check if method still accepts same parameter types",
                    "Look for alternative overloads of the method",
                ],
            }
        
        elif diagnosis_type == SemanticDiagnosis.SURROUNDING_CODE_CHANGED:
            return {
                "strategy": "context_adjustment",
                "actions": [
                    "Try removing/simplifying context lines",
                    "Use window-based matching to find code blocks",
                    "Match on semantic content rather than exact text",
                ],
            }
        
        elif diagnosis_type == SemanticDiagnosis.CODE_MOVED:
            return {
                "strategy": "code_search",
                "actions": [
                    "Search full codebase with grep_repo",
                    "Check if code was moved to different file",
                    "Verify if it's in a sibling class or utility",
                ],
            }
        
        else:  # UNKNOWN or no matches
            return {
                "strategy": "fallback_llm",
                "actions": [
                    "Escalate to LLM-based hunk regeneration",
                    "Provide LLM with full target file context",
                    "Request creative anchor text that works in current codebase",
                ],
            }
    
    @staticmethod
    def _string_similarity(s1: str, s2: str) -> float:
        """
        Calculate string similarity using Levenshtein-like ratio.
        Range: 0.0 (completely different) to 1.0 (identical)
        """
        if not s1 or not s2:
            return 1.0 if s1 == s2 else 0.0
        
        # Simple: use set intersection / union ratio for terms
        tokens1 = set(s1.lower().split())
        tokens2 = set(s2.lower().split())
        
        if not tokens1 and not tokens2:
            return 1.0
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))
        
        return intersection / union if union > 0 else 0.0


# Convenience function for quick analysis
def analyze_anchor_failure_quick(
    anchor_text: str,
    target_file_content: str,
    target_file_path: str = "unknown",
    resolution_reason: str = "not_found",
) -> SemanticAnalysisResult:
    """
    Quick analysis without initializing heavy tools.
    
    Use this when you just need fast semantic diagnosis without full fingerprinting.
    """
    helper = SemanticAdaptationHelper()
    return helper.analyze_anchor_failure(
        anchor_text=anchor_text,
        target_file_content=target_file_content,
        target_file_path=target_file_path,
        resolution_reason=resolution_reason,
    )
