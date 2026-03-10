"""
Phase 0: Optimistic Fast-Path Patching Node

Before spinning up the expensive 4-agent LLM pipeline, Retrofit first tries
a direct `git apply --check` on the mainline patch against the target repo.
If it applies cleanly *and* builds/tests pass, we exit immediately without
burning any LLM tokens.

This logic was previously embedded inside `reasoning_agent.py`. It is now
a standalone pre-graph node so the graph can route on `fast_path_success`.
"""

import os
from langchain_core.messages import HumanMessage
from state import AgentState
from utils.patch_analyzer import PatchAnalyzer


async def phase_0_optimistic(state: AgentState, config) -> dict:
    """
    Phase 0: The Fast-Path Direct Application Node.

    Responsibilities:
      1. Load and parse the mainline patch diff.
      2. Initialise the EnsembleRetriever (and handle experiment-mode checkout).
      3. Run `git apply --check` via ReasoningToolkit.check_patch_applicability().
      4. Set `fast_path_success` = True/False in state.
         - True  -> graph routes directly to END (no LLM agents needed).
         - False -> graph routes into the full 4-agent pipeline.

    On fast-path success this node also populates `patch_analysis` and
    `implementation_plan` (a simplified direct-apply plan) so the downstream
    validation agent has something to work with if needed.
    """
    print("Phase 0 (Optimistic): Checking direct patch applicability...")

    # ------------------------------------------------------------------
    # 1. Load the patch diff
    # ------------------------------------------------------------------
    patch_path = state.get("patch_path")
    if not patch_path or not os.path.exists(patch_path):
        return {
            "messages": [HumanMessage(content="Error: Patch file not found in Phase 0")],
            "fast_path_success": False,
        }

    with open(patch_path, "r", encoding="utf-8") as f:
        diff_text = f.read()

    analyzer = PatchAnalyzer()
    changes = analyzer.analyze(diff_text)

    # ------------------------------------------------------------------
    # 2. Handle experiment mode checkout
    # ------------------------------------------------------------------
    target_repo_path = state.get("target_repo_path")
    experiment_mode = state.get("experiment_mode", False)
    backport_commit = state.get("backport_commit")

    import subprocess

    if experiment_mode and backport_commit:
        print(f"Phase 0: Experiment mode — checking out parent of {backport_commit}...")
        try:
            subprocess.run(
                ["git", "checkout", f"{backport_commit}^"],
                cwd=target_repo_path,
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            print(f"Phase 0: Checkout failed: {e.stderr}")
            return {
                "messages": [HumanMessage(content=f"Phase 0 checkout error: {e.stderr}")],
                "fast_path_success": False,
                "patch_analysis": changes,
                "patch_diff": diff_text,
            }

    # ------------------------------------------------------------------
    # 3. Attempt direct patch application check
    # ------------------------------------------------------------------
    try:
        check_result = subprocess.run(
            ["git", "apply", "--check", patch_path],
            cwd=target_repo_path,
            capture_output=True,
            text=True
        )
        is_applicable = (check_result.returncode == 0)
        output = check_result.stdout if is_applicable else (check_result.stderr or check_result.stdout)
    except Exception as e:
        is_applicable = False
        output = str(e)

    if is_applicable:
        print("Phase 0: git apply --check SUCCEEDED. Attempting actual patch application and test run.")

        # Actually apply the patch
        patch_apply_result = None
        try:
            import subprocess
            patch_apply_result = subprocess.run(
                ["git", "apply", patch_path],
                capture_output=True,
                text=True,
                cwd=target_repo_path,
            )
        except Exception as e:
            print(f"Phase 0: Exception during git apply: {e}")
            return {
                "messages": [HumanMessage(content=f"Phase 0: Exception during git apply: {e}")],
                "patch_analysis": changes,
                "patch_diff": diff_text,
                "fast_path_success": False,
            }

        if patch_apply_result is None or patch_apply_result.returncode != 0:
            print(f"Phase 0: git apply failed: {patch_apply_result.stderr if patch_apply_result else 'Unknown error'}")
            return {
                "messages": [HumanMessage(content=f"Phase 0: git apply failed: {patch_apply_result.stderr if patch_apply_result else 'Unknown error'}")],
                "patch_analysis": changes,
                "patch_diff": diff_text,
                "fast_path_success": False,
            }

        # Identify test classes from the patch
        def _extract_test_classes(changes):
            test_classes = set()
            for change in changes:
                if hasattr(change, 'file_path') and change.is_test_file and change.file_path.endswith('.java'):
                    # Extract class name from file path
                    fname = os.path.basename(change.file_path)
                    class_name = fname[:-5] if fname.endswith('.java') else fname
                    test_classes.add(class_name)
            return list(test_classes)

        test_classes = _extract_test_classes(changes)

        # Run targeted tests using ValidationToolkit
        from agents.validation_tools import ValidationToolkit
        validation_toolkit = ValidationToolkit(target_repo_path)
        test_result = validation_toolkit.run_targeted_tests(test_classes)

        if test_result.get("success") and not test_result.get("compile_error"):
            print("Phase 0: Tests passed after patch application. Fast-path success.")
            # Build a simplified implementation plan for the validation agent
            from utils.models import Step, CompatibilityAnalysis, FileMapping, ImplementationPlan

            mappings = [
                FileMapping(
                    source_file=change.file_path,
                    target_file=change.file_path,
                    confidence=1.0,
                    reasoning="Phase 0 Optimistic Patch — git apply and tests passed.",
                )
                for change in changes
            ]
            steps = [
                Step(
                    step_id=idx + 1,
                    action="apply_patch_hunk",
                    file_path=change.file_path,
                    description="Apply patch directly — clean git apply.",
                    start_line=None,
                    end_line=None,
                    target_context=None,
                )
                for idx, change in enumerate(changes)
            ]
            plan = ImplementationPlan(
                patch_intent="Direct Backport (Phase 0 Fast-Path)",
                file_mappings=mappings,
                compatibility_analysis=CompatibilityAnalysis(
                    java_version_differences="Unknown (Optimistic)",
                    missing_dependencies=[],
                    refactoring_notes="None",
                ),
                steps=steps,
            )

            return {
                "messages": [HumanMessage(content="Phase 0: Fast-path success. Skipping LLM agents.")],
                "patch_analysis": changes,
                "patch_diff": diff_text,
                "fast_path_success": True,
                "implementation_plan": plan.dict(),
            }
        else:
            print("Phase 0: Tests failed or compile error after patch application. Rolling back.")
            validation_toolkit.restore_repo_state()
            return {
                "messages": [HumanMessage(content=f"Phase 0: Tests failed or compile error after patch. Output: {test_result.get('output','')} ")],
                "patch_analysis": changes,
                "patch_diff": diff_text,
                "fast_path_success": False,
            }
    else:
        hint = output[:200]
        print(f"Phase 0: git apply --check FAILED. Escalating to full pipeline.\n  Hint: {hint}")
        return {
            "messages": [HumanMessage(content=f"Phase 0 failed. Reason: {hint}")],
            "patch_analysis": changes,
            "patch_diff": diff_text,
            "fast_path_success": False,
        }
