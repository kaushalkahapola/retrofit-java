"""
TYPE_V Rulebook — Structured retry logic for complex backport failures.

This replaces the "give the LLM all tools and hope" approach with a
deterministic decision tree that runs FIRST, then hands targeted context
to the planning/editing agent.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from agents.failure_diagnosis import (
    Diagnosis,
    FailureDiagnosisEngine,
    FailureKind,
)


@dataclass
class RulebookDecision:
    """
    Output of the rulebook — tells the planning agent exactly what to do.
    """
    action: str                         # "remap_file" | "adapt_signature" | "add_side_file"
                                        # | "apply_to_parent" | "full_react" | "skip"
    
    # Override for planning agent
    override_target_file: str = ""      # if set, replace the target file in the plan
    override_target_method: str = ""    # if set, use this method name
    
    # Extra files to include in the edit plan
    additional_files: list[str] = field(default_factory=list)
    
    # Signature adaptation context
    target_signature: str = ""
    param_adaptation_notes: str = ""
    
    # Anchor override
    new_anchor_file: str = ""
    new_anchor_line: int = 0
    new_anchor_snippet: str = ""
    
    # Structured context for the planning agent prompt
    investigation_summary: str = ""
    
    # Confidence that this decision is correct
    confidence: float = 0.0
    
    def to_prompt_context(self) -> str:
        """Render this decision as a section to inject into the planning agent prompt."""
        lines = [
            "## RULEBOOK DIAGNOSIS (deterministic pre-analysis)",
            f"Action: {self.action}",
            f"Confidence: {self.confidence:.0%}",
        ]
        if self.investigation_summary:
            lines.append(f"\nInvestigation:\n{self.investigation_summary}")
        if self.override_target_file:
            lines.append(f"\nUse this target file: `{self.override_target_file}`")
        if self.override_target_method:
            lines.append(f"Use this method name: `{self.override_target_method}`")
        if self.target_signature:
            lines.append(f"Target signature (verified in file): `{self.target_signature}`")
        if self.param_adaptation_notes:
            lines.append(f"Signature adaptation notes: {self.param_adaptation_notes}")
        if self.additional_files:
            lines.append(f"Also edit these files: {self.additional_files}")
        if self.new_anchor_file:
            lines.append(f"Anchor found in: `{self.new_anchor_file}` line {self.new_anchor_line}")
        if self.new_anchor_snippet:
            snippet_str = str(self.new_anchor_snippet)
            lines.append(f"New anchor context:\n```java\n{snippet_str[:400]}\n```")

        lines.append(
            "\nYou MUST follow this diagnosis. Do NOT re-investigate what the "
            "rulebook already checked — go straight to the action above."
        )
        return "\n".join(lines)


class TypeVRulebook:
    """
    Runs the structured decision tree for TYPE_V retry scenarios.
    """

    def __init__(self, target_repo_path: str, mainline_repo_path: str = ""):
        self.repo = target_repo_path
        self.mainline = mainline_repo_path
        self.engine = FailureDiagnosisEngine(target_repo_path, mainline_repo_path)

    def apply(
        self,
        *,
        target_file: str,
        failed_plan_entry: dict[str, Any],
        build_error: str = "",
        hunk_apply_error: str = "",
        consistency_map: dict[str, str] | None = None,
        patch_diff_for_file: str = "",
    ) -> RulebookDecision:
        """
        Main entry point. Returns a RulebookDecision.
        """
        old_string = str(failed_plan_entry.get("old_string") or "")
        new_string = str(failed_plan_entry.get("new_string") or "")

        # Extract the most likely "failed symbol" from old_string
        failed_symbol = _extract_primary_symbol(old_string or new_string)

        # --- Run diagnosis ---
        diag = self.engine.diagnose(
            target_file=target_file,
            failed_old_string=old_string,
            failed_symbol=failed_symbol,
            build_error=build_error or hunk_apply_error,
            hunk_text=patch_diff_for_file,
            consistency_map=consistency_map,
        )

        # --- Route to rule ---
        return self._route(diag, target_file, old_string, new_string, build_error=build_error)


    def _route(
        self,
        diag: Diagnosis,
        target_file: str,
        old_string: str,
        new_string: str,
        build_error: str = "",
    ) -> RulebookDecision:


        if diag.kind == FailureKind.LOGIC_MOVED:
            return self._rule_logic_moved(diag, old_string, new_string)

        if diag.kind == FailureKind.SIGNATURE_CHANGED:
            return self._rule_signature_changed(diag, old_string, new_string)

        if diag.kind == FailureKind.PARENT_CLASS_CHANGE:
            return self._rule_parent_class(diag, old_string, new_string)

        if diag.kind == FailureKind.SIDE_FILE_NEEDED:
            return self._rule_side_files(diag)

        if diag.kind == FailureKind.ANCHOR_NOT_FOUND:
            return self._rule_anchor_moved(diag, old_string)

        # Unknown — escalate to full ReAct but with evidence
        # Emergency Fallback: If build error has signature mismatch, try one more time
        m_error = re.search(r"method (\w+) in class (\w+) cannot be applied", build_error)
        if m_error:
            # We already tried this in the engine and it failed, but maybe we can just 
            # tell the agent to check that class regardless.
            return RulebookDecision(
                action="full_react",
                confidence=0.4,
                investigation_summary=(
                    f"POTENTIAL SIGNATURE MISMATCH: The build error mentions method '{m_error.group(1)}' "
                    f"in class '{m_error.group(2)}'. Investigation failed to locate it precisely. "
                    f"You MUST use grep_in_repo to find 'class {m_error.group(2)}' and its methods."
                ),
            )

        return RulebookDecision(
            action="full_react",
            confidence=0.3,
            investigation_summary="\n".join([str(e) for e in diag.evidence]),
        )


    def _rule_logic_moved(
        self, diag: Diagnosis, old_string: str, new_string: str
    ) -> RulebookDecision:
        if not diag.candidate_files:
            return RulebookDecision(action="full_react", confidence=0.2)

        best_file = str(diag.candidate_files[0])
        snippet = self._get_method_snippet(diag.failed_symbol, best_file)

        return RulebookDecision(
            action="remap_file",
            override_target_file=best_file,
            override_target_method=diag.failed_symbol,
            new_anchor_file=best_file,
            new_anchor_snippet=snippet,
            confidence=diag.confidence,
            investigation_summary="\n".join([str(e) for e in diag.evidence]),
        )

    def _rule_signature_changed(
        self, diag: Diagnosis, old_string: str, new_string: str
    ) -> RulebookDecision:
        if not diag.new_signature:
            return RulebookDecision(action="full_react", confidence=0.3)

        old_params = _extract_params(old_string)
        new_params = _extract_params(diag.new_signature)

        added = [p for p in new_params if p not in old_params]
        removed = [p for p in old_params if p not in new_params]
        notes_parts = []
        if added:
            notes_parts.append(f"New params: {added}")
        if removed:
            notes_parts.append(f"Removed params: {removed}")
        if not notes_parts:
            notes_parts.append("Parameter types likely changed")

        snippet = ""
        if diag.candidate_methods:
            snippet = self._get_lines_around(
                diag.target_file,
                int(diag.candidate_methods[0].get("line") or 0),
                radius=15,
            )

        return RulebookDecision(
            action="adapt_signature",
            override_target_method=diag.failed_symbol,
            target_signature=diag.new_signature,
            param_adaptation_notes=" | ".join(notes_parts),
            new_anchor_snippet=snippet,
            confidence=diag.confidence,
            investigation_summary="\n".join([str(e) for e in diag.evidence]),
        )

    def _rule_parent_class(
        self, diag: Diagnosis, old_string: str, new_string: str
    ) -> RulebookDecision:
        snippet = ""
        if diag.parent_file:
            hit = self._find_text_line(old_string, diag.parent_file)
            if hit:
                snippet = self._get_lines_around(diag.parent_file, hit, radius=10)

        return RulebookDecision(
            action="apply_to_parent",
            override_target_file=diag.parent_file,
            new_anchor_file=diag.parent_file,
            new_anchor_snippet=snippet,
            confidence=diag.confidence,
            investigation_summary="\n".join([str(e) for e in diag.evidence]),
        )

    def _rule_side_files(self, diag: Diagnosis) -> RulebookDecision:
        return RulebookDecision(
            action="add_side_file",
            additional_files=diag.side_files,
            confidence=diag.confidence,
            investigation_summary="\n".join([str(e) for e in diag.evidence]),
        )

    def _rule_anchor_moved(
        self, diag: Diagnosis, old_string: str
    ) -> RulebookDecision:
        if not diag.candidate_files:
            return RulebookDecision(action="full_react", confidence=0.2)

        best_file = str(diag.candidate_files[0])
        line = self._find_text_line(old_string, best_file)
        snippet = self._get_lines_around(best_file, line or 1, radius=12) if line else ""

        return RulebookDecision(
            action="remap_anchor",
            override_target_file=best_file,
            new_anchor_file=best_file,
            new_anchor_line=line or 0,
            new_anchor_snippet=snippet,
            confidence=diag.confidence,
            investigation_summary="\n".join([str(e) for e in diag.evidence]),
        )

    def _get_method_snippet(self, method_name: str, rel_file: str, radius: int = 25) -> str:
        content = self._read(rel_file)
        if not content:
            return ""
        lines = content.splitlines()
        pat = re.compile(
            rf"(?:public|protected|private|static|final|synchronized|\s)+"
            rf"[\w<>\[\]?,\s]*\s+{re.escape(method_name)}\s*\(",
        )
        for i, line in enumerate(lines):
            if pat.search(line):
                start = max(0, i - 2)
                end = min(len(lines), i + radius)
                return "\n".join(f"{start+j+1}: {lines[start+j]}" for j in range(end - start))
        return ""

    def _get_lines_around(self, rel_file: str, center: int, radius: int = 15) -> str:
        content = self._read(rel_file)
        if not content:
            return ""
        lines = content.splitlines()
        start = max(0, center - 1 - radius)
        end = min(len(lines), center - 1 + radius)
        return "\n".join(f"{start+i+1}: {lines[start+i]}" for i in range(end - start))

    def _find_text_line(self, text: str, rel_file: str) -> int | None:
        content = self._read(rel_file)
        if not content:
            return None
        best = max(
            (l.strip() for l in text.splitlines() if l.strip() and len(l.strip()) > 15),
            key=len,
            default="",
        )
        if not best:
            return None
        for i, line in enumerate(content.splitlines(), start=1):
            if line.strip() == best or best in line:
                return i
        return None

    def _read(self, rel_path: str) -> str:
        try:
            with open(os.path.join(self.repo, rel_path), encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception:
            return ""


def _extract_primary_symbol(text: str) -> str:
    m = re.search(
        r"(?:public|private|protected|static|final|synchronized)+"
        r"\s+[\w<>?,\[\]]+\s+(\w+)\s*\(",
        text,
    )
    if m:
        name = m.group(1)
        if name not in {"if", "for", "while", "new", "return"}:
            return name

    tokens = re.findall(r"\b([A-Z][a-zA-Z0-9]+|[a-z][a-zA-Z0-9]+)\b", text)
    for t in tokens:
        if len(t) > 4 and t not in {"this", "null", "true", "false", "void", "class"}:
            return t
    return ""


def _extract_params(text: str) -> list[str]:
    m = re.search(r"\(([^)]*)\)", text)
    if not m:
        return []
    raw = m.group(1)
    params = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        words = part.split()
        if words:
            params.append(words[0].split("<")[0])
    return params
