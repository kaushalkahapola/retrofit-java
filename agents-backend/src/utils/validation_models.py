"""
Structured error and result types for H-MABS pipeline.
Inspired by CLAW architecture patterns for better error propagation and recovery.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime


class HunkValidationErrorType(Enum):
    """Classification of hunk validation errors"""

    DRY_RUN_FAILED = "dry_run_failed"
    CONTEXT_MISMATCH = "context_mismatch"
    LINE_OFFSET_ERROR = "line_offset_error"
    APPLY_FAILED = "apply_failed"
    SYNTAX_ERROR = "syntax_error"
    COMPILATION_ERROR = "compilation_error"
    MALFORMED_PATCH = "malformed_patch"
    FUZZY_MATCH_FAILED = "fuzzy_match_failed"
    UNKNOWN = "unknown"


class HookEventType(Enum):
    """Hook execution points in validation pipeline"""

    PRE_HUNK_VALIDATION = "pre_hunk_validation"
    POST_HUNK_VALIDATION = "post_hunk_validation"
    PRE_PATCH_ASSEMBLY = "pre_patch_assembly"
    POST_PATCH_ASSEMBLY = "post_patch_assembly"


@dataclass
class HookResult:
    """Result from running a validation hook"""

    allowed: bool
    messages: List[str] = field(default_factory=list)
    error_code: Optional[str] = None

    def is_denied(self) -> bool:
        return not self.allowed


@dataclass
class HunkValidationError:
    """Detailed error information from hunk validation"""

    error_type: HunkValidationErrorType
    message: str
    error_code: Optional[str] = None
    line_number: Optional[int] = None  # Line where error occurred in patch
    context_lines: List[str] = field(
        default_factory=list
    )  # Surrounding code for debugging
    suggestions: List[str] = field(default_factory=list)  # How to fix the error
    raw_output: Optional[str] = None  # Full tool output for inspection
    timestamp: datetime = field(default_factory=datetime.now)
    semantic_analysis: Optional[Dict[str, Any]] = None  # Semantic diagnosis of root cause (e.g., method_renamed, signature_changed)


@dataclass
class HunkValidationResult:
    """Complete validation result for a single hunk"""

    hunk_id: str
    is_error: bool
    error: Optional[HunkValidationError] = None
    validation_output: Optional[str] = None  # Tool output (dry-run, apply, etc)
    applied_successfully: bool = False
    line_offset: int = 0  # Offset adjustment needed after applying this hunk
    hook_results: List[HookResult] = field(default_factory=list)

    def get_error_message(self) -> Optional[str]:
        """Get human-readable error message"""
        if not self.error:
            return None
        return f"{self.error.error_type.value}: {self.error.message}"

    def add_hook_result(self, hook_result: HookResult):
        """Add a hook result"""
        self.hook_results.append(hook_result)

    def get_all_feedback(self) -> str:
        """Compile all feedback (error + hooks) for agent"""
        parts = []
        if self.error:
            parts.append(self.get_error_message())
            if self.error.suggestions:
                parts.append("Suggestions: " + "; ".join(self.error.suggestions))
        for hook in self.hook_results:
            parts.extend(hook.messages)
        return "\n".join(parts) if parts else "Validation passed"


@dataclass
class PatchValidationResult:
    """Complete validation result for entire patch"""

    patch_id: str
    target_file: str
    hunks: List[HunkValidationResult] = field(default_factory=list)
    all_passed: bool = False
    first_failed_hunk_index: Optional[int] = None
    assembly_errors: List[str] = field(default_factory=list)
    hook_results: List[HookResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def add_hunk_result(self, result: HunkValidationResult):
        """Add a hunk validation result"""
        self.hunks.append(result)
        if result.is_error and self.first_failed_hunk_index is None:
            self.first_failed_hunk_index = len(self.hunks) - 1

    def get_failed_hunks(self) -> List[HunkValidationResult]:
        """Get all failed hunks"""
        return [h for h in self.hunks if h.is_error]

    def get_failed_hunk_ids(self) -> List[str]:
        """Get IDs of failed hunks"""
        return [h.hunk_id for h in self.get_failed_hunks()]

    def update_all_passed_status(self):
        """Update the all_passed flag based on hunk results"""
        self.all_passed = (
            len(self.get_failed_hunks()) == 0 and len(self.assembly_errors) == 0
        )


@dataclass
class PatchRetryContext:
    """Context for retrying failed hunks in Phase 3"""

    patch_id: str
    failed_hunks: List[HunkValidationResult]
    target_file_path: str
    target_file_content: str
    line_offset_adjustments: Dict[str, int] = field(default_factory=dict)
    assembly_error_messages: List[str] = field(default_factory=list)
    suggestions_from_phase4: List[str] = field(default_factory=list)

    def get_context_summary(self) -> str:
        """Create a summary of retry context for Phase 3 agent"""
        parts = [
            f"Patch ID: {self.patch_id}",
            f"Failed hunks: {len(self.failed_hunks)}",
            f"Target file: {self.target_file_path}",
            f"File size: {len(self.target_file_content)} bytes",
        ]

        if self.failed_hunks:
            parts.append("\nFailed Hunk Details:")
            for hunk in self.failed_hunks:
                parts.append(f"  - Hunk ID: {hunk.hunk_id}")
                if hunk.error:
                    parts.append(f"    Error: {hunk.get_error_message()}")
                    if hunk.error.suggestions:
                        for sugg in hunk.error.suggestions:
                            parts.append(f"      Suggestion: {sugg}")

        if self.line_offset_adjustments:
            parts.append("\nLine Offset Adjustments:")
            for hunk_id, offset in self.line_offset_adjustments.items():
                parts.append(f"  - Hunk {hunk_id}: {offset:+d} lines")

        if self.assembly_error_messages:
            parts.append("\nAssembly Errors:")
            parts.extend(f"  - {msg}" for msg in self.assembly_error_messages)

        if self.suggestions_from_phase4:
            parts.append("\nSuggestions from Validation Agent:")
            parts.extend(f"  - {sugg}" for sugg in self.suggestions_from_phase4)

        return "\n".join(parts)


@dataclass
class ValidationObserverEvent:
    """Event emitted by validation process for observability"""

    event_type: str  # "hunk_validation_started", "hunk_validation_failed", etc
    timestamp: datetime = field(default_factory=datetime.now)
    patch_id: Optional[str] = None
    hunk_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


class ValidationObserver:
    """Observer pattern for validation events (inspired by CLAW hooks)"""

    def on_hunk_validation_started(self, patch_id: str, hunk_id: str):
        """Called when validation of a hunk starts"""
        pass

    def on_hunk_validation_error(self, result: HunkValidationResult):
        """Called when a hunk validation fails"""
        pass

    def on_hunk_validation_success(self, result: HunkValidationResult):
        """Called when a hunk validation succeeds"""
        pass

    def on_patch_validation_complete(self, result: PatchValidationResult):
        """Called when entire patch validation completes"""
        pass

    def on_validation_retry_needed(self, context: PatchRetryContext):
        """Called when validation indicates retry is needed"""
        pass


# Type aliases for common patterns
HunkDict = Dict[str, Any]  # Generic hunk dictionary
PatchDict = Dict[str, Any]  # Generic patch dictionary
