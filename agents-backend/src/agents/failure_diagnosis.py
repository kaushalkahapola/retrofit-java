"""
FailureDiagnosis — Deterministic pre-analysis before TYPE_V retry.

Runs structured checks against the target repo to produce a typed diagnosis
that guides the planning agent's retry. No LLM calls, no token burn.
The diagnosis is consumed by the rulebook router.
"""
from __future__ import annotations
import os
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FailureKind(str, Enum):
    ANCHOR_NOT_FOUND       = "anchor_not_found"
    SYMBOL_MISSING         = "symbol_missing"
    SIGNATURE_CHANGED      = "signature_changed"
    LOGIC_MOVED            = "logic_moved"
    SIDE_FILE_NEEDED       = "side_file_needed"
    PARENT_CLASS_CHANGE    = "parent_class_change"
    UNKNOWN                = "unknown"


@dataclass
class MethodMatch:
    name: str
    file: str
    line: int
    signature: str


@dataclass
class Diagnosis:
    kind: FailureKind
    confidence: float           # 0.0-1.0
    target_file: str
    failed_symbol: str = ""

    # For ANCHOR_NOT_FOUND / LOGIC_MOVED
    candidate_files: list[str] = field(default_factory=list)
    candidate_methods: list[MethodMatch] = field(default_factory=list)

    # For SIGNATURE_CHANGED
    old_signature: str = ""
    new_signature: str = ""
    param_diff: list[str] = field(default_factory=list)

    # For SIDE_FILE_NEEDED
    side_files: list[str] = field(default_factory=list)

    # For PARENT_CLASS_CHANGE
    parent_class: str = ""
    parent_file: str = ""

    # Suggested strategy for planner
    suggested_strategy: str = ""
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "confidence": self.confidence,
            "target_file": self.target_file,
            "failed_symbol": self.failed_symbol,
            "candidate_files": self.candidate_files,
            "candidate_methods": [
                {"name": m.name, "file": m.file, "line": m.line, "signature": m.signature}
                for m in self.candidate_methods
            ],
            "old_signature": self.old_signature,
            "new_signature": self.new_signature,
            "param_diff": self.param_diff,
            "side_files": self.side_files,
            "parent_class": self.parent_class,
            "parent_file": self.parent_file,
            "suggested_strategy": self.suggested_strategy,
            "evidence": self.evidence,
        }


class FailureDiagnosisEngine:
    """
    Deterministic diagnosis of why a TYPE_V edit failed.
    
    Designed to run BEFORE a planning retry so the planner gets structured
    context rather than free-form error logs.
    """

    def __init__(self, target_repo_path: str, mainline_repo_path: str = ""):
        self.repo = target_repo_path
        self.mainline = mainline_repo_path

    # ------------------------------------------------------------------ #
    # Public entry point                                                    #
    # ------------------------------------------------------------------ #

    def diagnose(
        self,
        *,
        target_file: str,
        failed_old_string: str,
        failed_symbol: str,
        build_error: str,
        hunk_text: str = "",
        consistency_map: dict[str, str] | None = None,
    ) -> Diagnosis:
        """
        Run all diagnostic checks and return a typed Diagnosis.
        
        Checks run in priority order — first confident match wins.
        """
        # 1. Symbol completely absent from target file but grep finds it elsewhere
        if failed_symbol:
            moved = self._check_symbol_moved(failed_symbol, target_file)
            if moved:
                return moved

        # 2. Symbol present but signature changed (compile error: cannot find symbol / 
        #    wrong arg count)
        if failed_symbol and _is_api_error(build_error):
            sig_diag = self._check_signature_changed(failed_symbol, target_file, build_error)
            if sig_diag:
                return sig_diag

        # 3. Anchor text not in file → could be in parent class
        if failed_old_string and not self._text_in_file(failed_old_string, target_file):
            parent_diag = self._check_parent_class(failed_old_string, target_file)
            if parent_diag:
                return parent_diag

        # 4. Build error mentions files NOT in our hunk set → side file needed
        if build_error:
            side_diag = self._check_side_files_needed(build_error, target_file)
            if side_diag:
                return side_diag

        # 5. Generic anchor-not-found with candidate search
        if failed_old_string and not self._text_in_file(failed_old_string, target_file):
            anchor_diag = self._check_anchor_location(failed_old_string, failed_symbol)
            if anchor_diag:
                return anchor_diag

        evidence_str = f"No deterministic diagnosis found. Build error: {build_error}"
        return Diagnosis(
            kind=FailureKind.UNKNOWN,
            confidence=0.0,
            target_file=target_file,
            failed_symbol=failed_symbol,
            suggested_strategy="escalate_to_full_react",
            evidence=[str(evidence_str[:300])],
        )

    # ------------------------------------------------------------------ #
    # Check 1: symbol moved to another file                                #
    # ------------------------------------------------------------------ #

    def _check_symbol_moved(self, symbol: str, current_file: str) -> Diagnosis | None:
        # First, check if symbol is in the current file. If so, it hasn't "moved".
        if self._text_in_file(symbol, current_file):
            return None

        hits = self._grep(symbol, "*.java", context=0)
        if not hits:
            return None

        other_files = [
            h for h in hits
            if str(h.get("file") or "") != current_file
            and not str(h.get("file") or "").lower().endswith("test.java")
            and "test" not in str(h.get("file") or "").lower()
        ]
        if not other_files:
            return None

        # Count hits per file and rank
        by_file: dict[str, list] = {}
        for h in other_files:
            f = str(h.get("file") or "")
            by_file.setdefault(f, []).append(h)

        ranked = sorted(by_file.items(), key=lambda x: len(x[1]), reverse=True)
        best_file, best_hits = ranked[0]

        # Is it a declaration (class/method def) or just a reference?
        decl_hits = [
            h for h in best_hits
            if re.search(
                rf"\b(class|interface|enum)\s+{re.escape(symbol)}\b"
                rf"|\b(void|[A-Z][a-zA-Z0-9<>]*)\s+{re.escape(symbol)}\s*\(",
                str(h.get("content") or ""),
            )
        ]
        confidence = 0.85 if decl_hits else 0.55

        candidates = [str(f) for f, _ in ranked[:5]]
        return Diagnosis(
            kind=FailureKind.LOGIC_MOVED,
            confidence=confidence,
            target_file=current_file,
            failed_symbol=symbol,
            candidate_files=candidates,
            suggested_strategy="remap_to_candidate_file",
            evidence=[
                f"Symbol '{symbol}' not declared in {current_file} "
                f"but found in: {candidates}"
            ],
        )


    # ------------------------------------------------------------------ #
    # Check 2: signature changed                                           #
    # ------------------------------------------------------------------ #

    def _check_signature_changed(self, symbol: str, target_file: str, build_error: str = "") -> Diagnosis | None:
        # 1. Try to find class/method hints in build error
        # [ERROR] ...: error: method estimateSizeForColumns in class Stats cannot be applied...
        target_f = target_file
        sym = symbol
        
        m_error = re.search(r"method (\w+) in class (\w+) cannot be applied", build_error)
        evidence = []
        if m_error:
            sym = m_error.group(1)
            class_name = m_error.group(2)
            evidence.append(f"Detected javac signature mismatch: method '{sym}' in class '{class_name}'")
            # Find the file for this class
            hits = self._grep(f"class {class_name}", "*.java", context=0)
            if hits:
                target_f = str(hits[0].get("file") or "")
                evidence.append(f"Mapped class '{class_name}' to file '{target_f}'")
            else:
                # Fallback: grep for method declaration globally if class search failed
                evidence.append(f"Could not find 'class {class_name}', searching globally for method '{sym}' declaration")
                hits = self._grep(rf"\b{re.escape(sym)}\s*\(", "*.java", context=0, is_regex=True)
                if hits:
                    # Filter for declarations (contains public/private/protected/etc)
                    decls = [h for h in hits if re.search(r"(public|protected|private|static|void|[A-Z])", str(h.get("content") or ""))]
                    if decls:
                        target_f = str(decls[0].get("file") or "")
                        evidence.append(f"Global search found declaration in '{target_f}'")

        # Find all method declarations matching the symbol name in target file
        content = self._read_file(target_f)
        if not content:
            if target_f != target_file:
                evidence.append(f"File '{target_f}' unreadable, falling back to '{target_file}'")
                target_f = target_file
                content = self._read_file(target_f)
            if not content:
                return None

        # Broader pattern for Java method signatures (generics, annotations, throws)
        pattern = re.compile(
            rf"(?:@\w+\s+)?(?:public|protected|private|static|final|synchronized|native|abstract|\s)*"
            rf"[<\w\s,>?\[\]]*\s+{re.escape(sym)}\s*\(([^)]*)\)"
            rf"(?:\s*throws\s+[\w\s,.]+)?\s*\{{?",
            re.MULTILINE,
        )
        matches = list(pattern.finditer(content))
        if not matches:
            evidence.append(f"No declaration for '{sym}' found in '{target_f}' using enhanced regex")
            return None

        # Return the first match with metadata
        first_match = matches[0]
        line_no = int(content[: first_match.start()].count("\n") + 1)
        sig_text = str(first_match.group(0)).strip().rstrip("{").strip()
        params_list = _extract_params(sig_text)
        
        evidence.append(f"Found signature: '{sig_text}' at line {line_no}")
        return Diagnosis(
            kind=FailureKind.SIGNATURE_CHANGED,
            confidence=0.95,
            target_file=target_f,
            failed_symbol=sym,
            new_signature=sig_text,
            param_diff=params_list,
            suggested_strategy="adapt_call_to_target_signature",
            evidence=evidence,
        )



    # ------------------------------------------------------------------ #
    # Check 3: method defined in parent class                              #
    # ------------------------------------------------------------------ #

    def _check_parent_class(self, anchor_text: str, target_file: str) -> Diagnosis | None:
        content = self._read_file(target_file)
        if not content:
            return None

        # Find superclass declaration
        m = re.search(r"class\s+\w+\s+extends\s+(\w+)", content)
        if not m:
            return None

        parent_name = m.group(1)

        # Grep for parent class file
        hits = self._grep(f"class {parent_name}", "*.java", context=0)
        if not hits:
            return None

        parent_files = [
            h["file"] for h in hits
            if not h["file"].lower().endswith("test.java")
        ]
        if not parent_files:
            return None

        parent_file = parent_files[0]

        # Check if anchor text is in parent
        if self._text_in_file(anchor_text, parent_file):
            return Diagnosis(
                kind=FailureKind.PARENT_CLASS_CHANGE,
                confidence=0.90,
                target_file=target_file,
                parent_class=parent_name,
                parent_file=parent_file,
                suggested_strategy="apply_edit_to_parent_class",
                evidence=[
                    f"Anchor text found in parent class {parent_name} ({parent_file})",
                    f"Target file {target_file} extends {parent_name}",
                ],
            )
        return None

    # ------------------------------------------------------------------ #
    # Check 4: build error references a side file we didn't touch         #
    # ------------------------------------------------------------------ #

    def _check_side_files_needed(
        self, build_error: str, current_file: str
    ) -> Diagnosis | None:
        # Extract .java file paths from compiler output
        java_refs = re.findall(
            r"([a-zA-Z0-9_/.-]+\.java):\d+",
            build_error,
        )
        side_files = list({
            f for f in java_refs
            if f != current_file
            and not f.lower().endswith("test.java")
            and os.path.exists(os.path.join(self.repo, f))
        })

        if not side_files:
            return None

        return Diagnosis(
            kind=FailureKind.SIDE_FILE_NEEDED,
            confidence=0.70,
            target_file=current_file,
            side_files=side_files[:5],
            suggested_strategy="include_side_files_in_edit_plan",
            evidence=[
                f"Compiler errors reference files outside current edit scope: {side_files[:3]}"
            ],
        )

    # ------------------------------------------------------------------ #
    # Check 5: generic anchor search across repo                           #
    # ------------------------------------------------------------------ #

    def _check_anchor_location(
        self, anchor_text: str, symbol: str
    ) -> Diagnosis | None:
        # Use the most unique line from anchor_text as search term
        best_line = self._pick_strongest_anchor_line(anchor_text)
        if not best_line:
            return None

        hits = self._grep(best_line, "*.java", context=0, max_results=10)
        if not hits:
            return None

        candidates = list({str(h.get("file") or "") for h in hits})
        return Diagnosis(
            kind=FailureKind.ANCHOR_NOT_FOUND,
            confidence=0.65,
            target_file="(unknown)",
            failed_symbol=symbol,
            candidate_files=candidates[:5],
            suggested_strategy="remap_anchor_to_found_location",
            evidence=[
                f"Anchor line '{best_line[:80]}' found in: {candidates[:5]}"
            ],
        )

    # ------------------------------------------------------------------ #
    # Helpers                                                               #
    # ------------------------------------------------------------------ #

    def _grep(
        self,
        pattern: str,
        glob: str = "*.java",
        context: int = 0,
        max_results: int = 30,
        is_regex: bool = False,
    ) -> list[dict]:
        cmd = ["git", "grep", "-n", "--full-name"]
        if not is_regex:
            cmd.append("-F")
        if context:
            cmd.extend([f"-C{context}"])
        cmd.extend([pattern, "HEAD", "--", glob])
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.repo, timeout=15
            )
            hits: list[dict[str, Any]] = []
            for line in result.stdout.splitlines()[:max_results]:
                parts = line.split(":", 3)
                if len(parts) >= 4:
                    hits.append({
                        "file": str(parts[1]),
                        "line": int(parts[2]) if parts[2].isdigit() else 0,
                        "content": str(parts[3]),
                    })
            return hits
        except Exception:
            return []


    def _read_file(self, rel_path: str) -> str:
        try:
            full = os.path.join(self.repo, rel_path)
            with open(full, encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception:
            return ""

    def _text_in_file(self, text: str, rel_path: str) -> bool:
        content = self._read_file(rel_path)
        if not content:
            return False
        # Try exact, then trimmed-line match
        if text in content:
            return True
        first_line = next(
            (l.strip() for l in text.splitlines() if l.strip()), ""
        )
        return bool(first_line and first_line in content)

    def _pick_strongest_anchor_line(self, text: str) -> str:
        """Return the longest, most unique-looking line from anchor text."""
        candidates = []
        for line in text.splitlines():
            s = line.strip()
            if (
                len(s) > 20
                and not s.startswith("//")
                and not s.startswith("*")
                and s not in {"{", "}", "};", "();"}
            ):
                candidates.append(s)
        if not candidates:
            return ""
        return max(candidates, key=len)


def _is_api_error(build_error: str) -> bool:
    lower = (build_error or "").lower()
    return (
        "cannot find symbol" in lower
        or "cannot be applied" in lower
        or "no suitable method" in lower
        or "method" in lower and "argument" in lower
    )


def _extract_params(text: str) -> list[str]:
    """Extract parameter type names from a method signature fragment."""
    m = re.search(r"\(([^)]*)\)", text)
    if not m:
        return []
    raw = m.group(1)
    params = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        # "TypeName varName" → take TypeName
        words = part.split()
        if words:
            params.append(words[0].split("<")[0])  # strip generics
    return params

