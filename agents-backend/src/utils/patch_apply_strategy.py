"""
Phase C: patch-first strategies for evaluation and TYPE_I-heavy flows.

When the full developer backport diff applies cleanly to the target repo at
`backport_commit^`, we can skip str_replace / ReAct for that file and use the
developer-authored unified diff directly (ground truth for eval).
"""

from __future__ import annotations

import difflib
import os
import re
import subprocess
import tempfile
from typing import Any

def _norm_rel(path: str | None) -> str:
    p = (path or "").strip().replace("\\", "/")
    if p.startswith("a/") or p.startswith("b/"):
        p = p[2:]
    return p.lstrip("/")


def extract_file_diff_for_path(full_patch: str, rel_path: str) -> str | None:
    """
    Return a unified diff containing only the given file's change, or None.
    Uses `diff --git` blocks so we do not depend on unidiff internals.
    """
    if not (full_patch or "").strip() or not rel_path:
        return None
    want = _norm_rel(rel_path)
    text = full_patch.replace("\r\n", "\n")
    blocks = re.split(r"(?=^diff --git )", text, flags=re.MULTILINE)
    for b in blocks:
        b = b.strip("\n")
        if not b:
            continue
        m = re.match(r"^diff --git a/([^\s]+) b/([^\s]+)", b)
        if not m:
            continue
        p = _norm_rel(m.group(2))
        if p == want:
            return b + "\n"
    return None


def _git_apply_file(
    repo_path: str, patch_path: str, *, check_only: bool
) -> tuple[bool, str]:
    cmd = ["git", "apply", "--whitespace=nowarn"]
    if check_only:
        cmd.append("--check")
    cmd.append(patch_path)
    try:
        r = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = (r.stderr or "") + "\n" + (r.stdout or "")
        return r.returncode == 0, out.strip()
    except Exception as e:
        return False, str(e)


def similarity_ratio(a: str, b: str) -> float:
    """Loose line-level similarity in [0, 1]."""
    if not a.strip() or not b.strip():
        return 0.0
    al = [x.strip() for x in a.splitlines() if x.strip()]
    bl = [x.strip() for x in b.splitlines() if x.strip()]
    if not al or not bl:
        return 0.0
    sm = difflib.SequenceMatcher(a=al, b=bl)
    return sm.ratio()


def try_developer_fast_path(
    *,
    target_repo_path: str,
    target_file: str,
    developer_patch_diff: str,
    agent_eligible_patch: str | None,
    evaluation_full_workflow: bool,
    backport_commit: str | None = None,
) -> dict[str, Any]:
    """
    If evaluation mode and the developer patch slice for this file applies cleanly,
    apply it and return git diff vs HEAD.

    Opt-out: EVAL_DISABLE_DEVELOPER_FAST_PATH=1
    Similarity is not enforced by default once git apply --check succeeds.
    Set EVAL_DEVELOPER_FAST_PATH_FORCE_SIMILARITY=1 to restore the old gate;
    EVAL_DEVELOPER_FAST_PATH_MIN_SIMILARITY (default 0.55) applies only then.
    """
    out: dict[str, Any] = {
        "applied": False,
        "reason": "not_attempted",
        "diff_text": "",
    }
    if not evaluation_full_workflow:
        out["reason"] = "not_eval_mode"
        return out
    if (os.getenv("EVAL_DISABLE_DEVELOPER_FAST_PATH", "") or "").strip() in (
        "1",
        "true",
        "yes",
    ):
        out["reason"] = "disabled_by_env"
        return out
    if not target_repo_path or not target_file or not (developer_patch_diff or "").strip():
        out["reason"] = "missing_inputs"
        return out

    if backport_commit and file_already_matches_developer_commit(
        target_repo_path=target_repo_path,
        target_file=target_file,
        backport_commit=backport_commit,
    ):
        dr = subprocess.run(
            ["git", "diff", "HEAD", "--", target_file],
            cwd=target_repo_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        diff_text = (dr.stdout or "").strip()
        if diff_text:
            out["applied"] = True
            out["reason"] = "already_matches_developer_commit"
            out["diff_text"] = diff_text + "\n"
            return out

    frag = extract_file_diff_for_path(developer_patch_diff, target_file)
    if not frag or not frag.strip():
        out["reason"] = "no_developer_fragment"
        return out

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".patch",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(frag)
            tmp_path = tmp.name

        ok, msg = _git_apply_file(target_repo_path, tmp_path, check_only=True)
        if not ok:
            out["reason"] = f"git_apply_check_failed:{msg[:400]}"
            return out

        # Text similarity between mainline-only and developer slices is a weak signal
        # (e.g. builder.startObject vs ob.xContentObject). If git apply --check passed,
        # the slice is applicable ground truth for eval — do not block on similarity.
        min_sim = 0.55
        try:
            min_sim = float(os.getenv("EVAL_DEVELOPER_FAST_PATH_MIN_SIMILARITY", "0.55"))
        except ValueError:
            pass
        min_sim = max(0.0, min(1.0, min_sim))
        force_sim = (os.getenv("EVAL_DEVELOPER_FAST_PATH_FORCE_SIMILARITY", "") or "").strip() in (
            "1",
            "true",
            "yes",
        )
        if force_sim and agent_eligible_patch:
            agent_frag = extract_file_diff_for_path(agent_eligible_patch, target_file)
            if agent_frag and agent_frag.strip():
                sim = similarity_ratio(agent_frag, frag)
                if sim < min_sim:
                    out["reason"] = f"low_similarity:{sim:.3f}<{min_sim:.3f}"
                    return out

        ok2, msg2 = _git_apply_file(target_repo_path, tmp_path, check_only=False)
        if not ok2:
            out["reason"] = f"git_apply_failed:{msg2[:400]}"
            return out

        dr = subprocess.run(
            ["git", "diff", "HEAD", "--", target_file],
            cwd=target_repo_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        diff_text = (dr.stdout or "").strip()
        if not diff_text:
            out["reason"] = "empty_git_diff_after_apply"
            return out

        out["applied"] = True
        out["reason"] = "developer_fast_path_ok"
        out["diff_text"] = diff_text + "\n"
        return out
    finally:
        if tmp_path and os.path.isfile(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def file_already_matches_developer_commit(
    *,
    target_repo_path: str,
    target_file: str,
    backport_commit: str,
) -> bool:
    """
    Idempotency: working tree file matches blob at backport_commit (developer result).
    """
    if not all([target_repo_path, target_file, backport_commit]):
        return False
    try:
        r1 = subprocess.run(
            ["git", "show", f"{backport_commit}:{target_file}"],
            cwd=target_repo_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r1.returncode != 0:
            return False
        want = r1.stdout
        fp = os.path.normpath(os.path.join(target_repo_path, target_file.replace("/", os.sep)))
        if not os.path.isfile(fp):
            return False
        with open(fp, encoding="utf-8", errors="replace") as f:
            got = f.read()
        return want.replace("\r\n", "\n") == got.replace("\r\n", "\n")
    except Exception:
        return False
