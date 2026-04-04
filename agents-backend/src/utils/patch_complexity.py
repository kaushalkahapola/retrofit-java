from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Any

from utils.patch_analyzer import PatchAnalyzer


def _git_apply_check_passes(diff_text: str, target_repo_path: str) -> tuple[bool, str]:
    if not diff_text or not target_repo_path:
        return False, "missing_diff_or_repo"

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False) as tmp:
            tmp.write(diff_text)
            tmp_path = tmp.name

        result = subprocess.run(
            ["git", "apply", "--check", tmp_path],
            cwd=target_repo_path,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0, (result.stderr or result.stdout or "").strip()
    except Exception as e:
        return False, str(e)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _anchor_match_ratio(diff_text: str, target_repo_path: str, file_path: str) -> float:
    analyzer = PatchAnalyzer()
    hunks_by_file = analyzer.extract_raw_hunks(diff_text, with_test_changes=True)
    hunks = hunks_by_file.get(file_path, [])
    if not hunks:
        return 1.0

    full_path = os.path.join(target_repo_path, file_path)
    if not os.path.isfile(full_path):
        return 0.0

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return 0.0

    needles: list[str] = []
    for hunk in hunks:
        for i, line in enumerate((hunk or "").splitlines()):
            if i == 0 and line.startswith("@@"):
                continue
            if line.startswith("-") and not line.startswith("---"):
                s = line[1:].strip()
                if s:
                    needles.append(s)
            elif line.startswith(" "):
                s = line[1:].strip()
                if s:
                    needles.append(s)

    if not needles:
        return 1.0

    matched = sum(1 for n in needles if n in content)
    return matched / max(1, len(needles))


def classify_patch_complexity(
    *,
    patch_diff: str,
    target_repo_path: str,
    with_test_changes: bool = False,
) -> dict[str, Any]:
    """
    Deterministic complexity classifier used for graph routing.

    Returns a dict with:
      - complexity: TRIVIAL | STRUCTURAL | REWRITE
      - reason: short deterministic reason
      - details: metrics used in classification
    """
    analyzer = PatchAnalyzer()
    changes = analyzer.analyze(patch_diff, with_test_changes=with_test_changes)

    if not changes:
        return {
            "complexity": "TRIVIAL",
            "reason": "no_changes",
            "details": {"file_count": 0},
        }

    apply_ok, apply_msg = _git_apply_check_passes(patch_diff, target_repo_path)
    if apply_ok:
        return {
            "complexity": "TRIVIAL",
            "reason": "git_apply_check_passes",
            "details": {
                "file_count": len(changes),
                "git_apply_check": True,
            },
        }

    code_changes = []
    for c in changes:
        p = (c.file_path or "").lower()
        if not p.endswith(".java"):
            continue
        if not with_test_changes and c.is_test_file:
            continue
        code_changes.append(c)

    if not code_changes:
        return {
            "complexity": "TRIVIAL",
            "reason": "non_java_or_test_only_changes",
            "details": {
                "file_count": len(changes),
                "git_apply_check": False,
                "git_apply_error": apply_msg[:300],
            },
        }

    files_exist = True
    structural_ops = False
    ratios: list[float] = []

    for c in code_changes:
        if c.change_type in {"ADDED", "DELETED", "RENAMED"}:
            structural_ops = True
        full_path = os.path.join(target_repo_path, c.file_path)
        if not os.path.isfile(full_path):
            files_exist = False
        ratios.append(_anchor_match_ratio(patch_diff, target_repo_path, c.file_path))

    avg_ratio = sum(ratios) / max(1, len(ratios))

    if files_exist and not structural_ops and avg_ratio >= 0.45:
        return {
            "complexity": "STRUCTURAL",
            "reason": "files_present_with_anchor_overlap",
            "details": {
                "file_count": len(code_changes),
                "files_exist": files_exist,
                "structural_ops": structural_ops,
                "avg_anchor_ratio": round(avg_ratio, 4),
                "git_apply_check": False,
                "git_apply_error": apply_msg[:300],
            },
        }

    return {
        "complexity": "REWRITE",
        "reason": "low_anchor_overlap_or_structural_ops",
        "details": {
            "file_count": len(code_changes),
            "files_exist": files_exist,
            "structural_ops": structural_ops,
            "avg_anchor_ratio": round(avg_ratio, 4),
            "git_apply_check": False,
            "git_apply_error": apply_msg[:300],
        },
    }
