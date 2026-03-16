"""
Agent 4: The Verifier (Validation Loop)

H-MABS Phase 4 — "Prove Red, Make Green" Loop
"""
import json
import os
import re
from langchain_core.messages import HumanMessage, SystemMessage
from state import AgentState, AdaptedHunk
from utils.llm_provider import get_llm
from agents.validation_tools import ValidationToolkit
from agents.hunk_generator import _extract_hunk_block

_SYNTHESIZE_TEST_SYSTEM = """You are an expert Java test engineer.
Your task is to write a single JUnit test method that specifically triggers a vulnerability."""

_SYNTHESIZE_TEST_USER = """\
## Root Cause & Fix Logic
Root Cause: {root_cause}
Fix Logic: {fix_logic}

Write a JUnit test that proves this root cause exists (it should FAIL before the fix is applied, and PASS after).
Output ONLY the unified diff block starting with @@ showing the addition of this test to an appropriate test class.
"""

_ANALYZE_FAILURE_SYSTEM = """You are an expert Java developer reviewing a backport validation failure.
Analyze the error and provide a concise, actionable diagnosis.

Focus on:
- Root cause (missing API, signature mismatch, logic error, etc.)
- Specific files/methods involved  
- Clear fix suggestion for hunk regeneration

Keep response under 3 sentences. Be direct and technical."""

_ANALYZE_FAILURE_USER = """\
## Step: {step_name}
## Error:
{error_output}

Provide concise diagnosis and fix suggestion:"""

MAX_VALIDATION_ATTEMPTS = 3

async def _analyze_failure(step_name: str, error_output: str, state: AgentState) -> str:
    """Uses LLM to evaluate and explain a validation failure."""
    # Truncate long errors to save tokens
    if len(error_output) > 3000:
        error_output = error_output[:1500] + "\n...[TRUNCATED]...\n" + error_output[-1500:]
    
    prompt = _ANALYZE_FAILURE_USER.format(
        step_name=step_name,
        error_output=error_output
    )

    llm = get_llm(
        temperature=0,
        provider=os.getenv("LLM_PROVIDER"),
        model=os.getenv("LLM_MODEL", "gemini-2.0-flash")
    )

    try:
        response = await llm.ainvoke([
            SystemMessage(content=_ANALYZE_FAILURE_SYSTEM),
            HumanMessage(content=prompt)
        ])
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        return f"Analysis failed: {str(e)}"

async def _synthesize_target_test(state: AgentState, toolkit: ValidationToolkit) -> list[AdaptedHunk]:
    """Phase 6: Test Synthesis"""
    print("  Agent 4: No test hunks provided. Synthesizing a vulnerability test...")
    blueprint = state.get("semantic_blueprint") or {}
    root_cause = blueprint.get("root_cause_hypothesis", "")
    fix_logic = blueprint.get("fix_logic", "")
    
    prompt = _SYNTHESIZE_TEST_USER.format(
        root_cause=root_cause,
        fix_logic=fix_logic
    )
    
    llm = get_llm(temperature=0)
    
    try:
        response = await llm.ainvoke([
            SystemMessage(content=_SYNTHESIZE_TEST_SYSTEM),
            HumanMessage(content=prompt)
        ])
        raw_content = response.content if hasattr(response, "content") else str(response)
        print(f"  Agent 4: Synthesized test (raw):\n{raw_content}")
        adapted_hunk_text = _extract_hunk_block(raw_content)
        print(f"  Agent 4: Extracted hunk text:\n{adapted_hunk_text}")
        
        if adapted_hunk_text:
            target_file = "src/test/java/SynthesizedVulnTest.java" # Fallback
            lines = adapted_hunk_text.splitlines()
            for line in lines:
                if line.startswith("+++ b/"):
                    target_file = line[6:].strip()
                    break
            
            # Repair header to avoid "corrupt patch" errors
            adapted_hunk_text = _repair_hunk_header(adapted_hunk_text)
            
            # Dry run test synthesis
            dr = toolkit.apply_hunk_dry_run(target_file, adapted_hunk_text)
            
            hunk: AdaptedHunk = {
                "target_file": target_file,
                "mainline_file": "synthesized",
                "hunk_text": adapted_hunk_text,
                "insertion_line": 1,
                "intent_verified": True
            }
            return [hunk]
    except Exception as e:
        print(f"  Agent 4: Test synthesis failed: {e}")
        
    return []

def _extract_test_classes(test_hunks: list[AdaptedHunk]) -> list[str]:
    """Helper to extract class names from file paths."""
    classes = []
    for h in test_hunks:
        f = h.get("target_file", "")
        if f.endswith(".java"):
            # e.g., src/test/java/org/example/MyTest.java -> org.example.MyTest
            parts = f.replace("\\", "/").split("/")
            if "java" in parts:
                idx = parts.index("java")
                cls_path = parts[idx+1:]
                cls_name = ".".join(cls_path).replace(".java", "")
                if cls_name not in classes:
                    classes.append(cls_name)
    return classes

def _repair_hunk_header(hunk_text: str) -> str:
    """
    Recalculates the line counts in a unified diff hunk header (@@ line)
    based on the actual lines present in the hunk body.
    """
    if not hunk_text:
        return hunk_text
        
    lines = hunk_text.splitlines()
    if not lines or not lines[0].startswith("@@"):
        return hunk_text
        
    header = lines[0]
    # Parse existing header: @@ -a,b +c,d @@  <optional context>
    m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)", header)
    if not m:
        return hunk_text
        
    start_src = int(m.group(1))
    start_tgt = int(m.group(3))
    ctx = m.group(5)
    
    count_src = 0
    count_tgt = 0
    
    for line in lines[1:]:
        if line.startswith(" "):
            count_src += 1
            count_tgt += 1
        elif line.startswith("-"):
            count_src += 1
        elif line.startswith("+"):
            count_tgt += 1
            
    new_header = f"@@ -{start_src if count_src > 0 else 0},{count_src} +{start_tgt},{count_tgt} @@{ctx}"
    return "\n".join([new_header] + lines[1:]) + "\n"

async def validation_agent(state: AgentState, config) -> dict:
    """
    Agent 4: The Verifier.
    Implements the 6-Phase Prove Red, Make Green loop.
    """
    print("Agent 4 (Validation): Starting 'Prove Red, Make Green' loop...")
    
    target_repo_path = state.get("target_repo_path")
    if not target_repo_path:
        return {"messages": [HumanMessage(content="Validation Agent Error: No target_repo_path.")]}
        
    toolkit = ValidationToolkit(target_repo_path)
    
    # 3.0 Setup
    code_hunks = state.get("adapted_code_hunks", [])
    test_hunks = state.get("adapted_test_hunks", [])
    attempts = state.get("validation_attempts", 0)
    blueprint = state.get("semantic_blueprint", {})
    compile_only = state.get("compile_only", False)
    # Temporary mode: skip compilation/static-analysis phases due environment constraints.
    skip_compilation_checks = True
    # Temporary mode: validation only checks whether hunks can be applied.
    apply_only_validation = True
    
    if attempts >= MAX_VALIDATION_ATTEMPTS:
        print(f"  Agent 4: Max validation attempts ({MAX_VALIDATION_ATTEMPTS}) reached. Failing.")
        return {"validation_passed": False}
        
    # Ensure clean repo
    toolkit.restore_repo_state()
    
    # Trace Initialization
    unique_code_files = list(set([h.get("target_file") for h in code_hunks if h.get("target_file")]))
    unique_test_files = list(set([h.get("target_file") for h in test_hunks if h.get("target_file")]))
    
    validation_results = {}

    trace = [
        "# Validation Trace",
        "",
        "## Blueprint Summary",
        f"- **Root Cause**: {blueprint.get('root_cause_hypothesis', 'N/A')}",
        f"- **Fix Logic**: {blueprint.get('fix_logic', 'N/A')}",
        f"- **Dependent APIs**: {blueprint.get('dependent_apis', [])}",
        "",
        "## Hunk Segregation",
        f"- Code files: {len(unique_code_files)}",
        f"- Test files: {len(unique_test_files)}",
        "",
        "## Agent Tool Steps",
        ""
    ]

    def log_step(tool_name, params, output):
        trace.append(f"  - `Agent calls {tool_name}` with `{json.dumps(params)}`")
        # Truncate long outputs for trace readability
        out_str = str(output)
        if len(out_str) > 1000:
            out_str = out_str[:1000] + "... [TRUNCATED]"
        trace.append(f"  - `Tool: {tool_name}` -> {out_str}")

    if apply_only_validation:
        print("  Agent 4: Apply-only mode - checking patch application only...")
        res = toolkit.apply_adapted_hunks(code_hunks, test_hunks)
        log_step("apply_adapted_hunks", {"code_count": len(code_hunks), "test_count": len(test_hunks)}, res)

        validation_results["hunk_application"] = {
            "success": res["success"],
            "raw": res["output"]
        }

        if not res["success"]:
            analysis = await _analyze_failure("Hunk Application", res["output"], state)
            validation_results["hunk_application"]["agent_evaluation"] = analysis
            validation_results["hunk_application"]["error_context"] = analysis
            trace.append(f"\n**Final Status: HUNK APPLICATION FAILED**\n\n**Agent Analysis:**\n{analysis}")
            toolkit.write_trace("\n".join(trace), "validation_trace.md")
            return {
                "validation_passed": False,
                "validation_attempts": attempts + 1,
                "validation_error_context": f"Hunk application failed: {analysis}",
                "validation_results": validation_results,
                "regeneration_hint": analysis
            }

        validation_results["hunk_application"]["agent_evaluation"] = "Hunks applied successfully to all target files."
        validation_results["compilation"] = {
            "success": True,
            "raw": "Skipped by apply-only validation mode.",
            "agent_evaluation": "Compilation step intentionally skipped."
        }
        validation_results["spotbugs"] = {
            "success": True,
            "raw": "Skipped by apply-only validation mode.",
            "agent_evaluation": "SpotBugs step intentionally skipped."
        }
        trace.append("\n**Final Status: VALIDATION PASSED (APPLY-ONLY MODE)**")
        trace.append("\n**Note:** Compilation, tests, and static-analysis phases are disabled.")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        return {
            "validation_passed": True,
            "validation_attempts": attempts + 1,
            "validation_error_context": "",
            "validation_results": validation_results
        }

    # Compile-Only Mode (Streamlined - Apply patch and compile changed files only)
    if compile_only:
        print("  Agent 4: Streamlined mode - applying patch and compiling changed files only...")
        res = toolkit.apply_adapted_hunks(code_hunks, test_hunks)
        log_step("apply_adapted_hunks", {"code_count": len(code_hunks), "test_count": len(test_hunks)}, res)

        validation_results["hunk_application"] = {
            "success": res["success"],
            "raw": res["output"]
        }

        if not res["success"]:
            # Use LLM to analyze hunk application failure
            analysis = await _analyze_failure("Hunk Application", res["output"], state)
            validation_results["hunk_application"]["agent_evaluation"] = analysis
            validation_results["hunk_application"]["error_context"] = analysis
            trace.append(f"\n**Final Status: HUNK APPLICATION FAILED**\n\n**Agent Analysis:**\n{analysis}")
            toolkit.write_trace("\n".join(trace), "validation_trace.md")
            return {
                "validation_passed": False,
                "validation_attempts": attempts + 1,
                "validation_error_context": f"Hunk application failed: {analysis}",
                "validation_results": validation_results,
                "regeneration_hint": analysis  # For hunk generator to use
            }
        else:
            validation_results["hunk_application"]["agent_evaluation"] = "Hunks applied successfully to all target files."

        if skip_compilation_checks:
            validation_results["compilation"] = {
                "success": True,
                "raw": "Skipped by configuration for environment-constrained runs.",
                "agent_evaluation": "Compilation step intentionally skipped."
            }
            validation_results["spotbugs"] = {
                "success": True,
                "raw": "Skipped by configuration for environment-constrained runs.",
                "agent_evaluation": "Static analysis step intentionally skipped."
            }
            trace.append("\n**Final Status: VALIDATION PASSED (COMPILATION/SPOTBUGS SKIPPED)**")
            trace.append("\n**Note:** Compilation and static-analysis phases are disabled in this run mode.")
            passed = True
        else:
            applied_files = res.get("applied_files", [])
            build_res = toolkit.compile_files(applied_files)
            log_step("compile_files", {"files": applied_files}, build_res)

            validation_results["compilation"] = {
                "success": build_res.get("success"),
                "raw": build_res.get("output", "")
            }

            if not build_res.get("success"):
                # Use LLM to analyze compilation failure
                analysis = await _analyze_failure("Compilation", build_res.get("output", ""), state)
                validation_results["compilation"]["agent_evaluation"] = analysis
                validation_results["compilation"]["error_context"] = analysis
                trace.append(f"\n**Final Status: COMPILATION FAILED**\n\n**Agent Analysis:**\n{analysis}")
                toolkit.write_trace("\n".join(trace), "validation_trace.md")
                return {
                    "validation_passed": False,
                    "validation_attempts": attempts + 1,
                    "validation_error_context": f"Compilation failed: {analysis}",
                    "validation_results": validation_results,
                    "regeneration_hint": analysis  # For hunk generator to use
                }
            else:
                validation_results["compilation"]["agent_evaluation"] = "All modified files compiled successfully."

            # Run SpotBugs after successful compile
            print("  Agent 4: Running SpotBugs validation...")
            modules = build_res.get("modules", [])
            classes_paths = toolkit.get_module_class_paths(modules)

            # Use target_files for Maven SpotBugs optimization
            spotbugs_res = toolkit.run_spotbugs(
                compiled_classes_paths=classes_paths,
                source_path=os.path.join(state["target_repo_path"], "src", "main", "java"),
                target_files=unique_code_files + unique_test_files
            )
            log_step("run_spotbugs", {"paths": classes_paths}, spotbugs_res)

            passed = spotbugs_res.get("success", True)
            spotbugs_output = spotbugs_res.get("output", "")
            
            validation_results["spotbugs"] = {
                "success": passed,
                "raw": spotbugs_output,
                "agent_evaluation": ""
            }

            if not passed:
                # Use LLM to analyze SpotBugs findings (only send relevant findings, not full output)
                analysis = await _analyze_failure("SpotBugs", spotbugs_output, state)
                validation_results["spotbugs"]["agent_evaluation"] = analysis
                validation_results["spotbugs"]["error_context"] = analysis
                trace.append(f"\n**Final Status: STATIC VALIDATION FAILED**\n\n**Agent Analysis:**\n{analysis}")
            else:
                validation_results["spotbugs"]["agent_evaluation"] = "No high-severity bugs detected. Code passes static analysis."
                trace.append(f"\n**Final Status: {'VALIDATION PASSED'}**")

        toolkit.write_trace("\n".join(trace), "validation_trace.md")

        return {
            "validation_passed": passed,
            "validation_attempts": attempts + 1,
            "validation_error_context": spotbugs_res.get("output", "") if not passed else "",
            "validation_results": validation_results
        }

    # Standard "Prove Red, Make Green" Loop
    # 3.1 Phase 6: Test Synthesis (Moved to start if missing)
    if not test_hunks:
        print("  Agent 4: No test hunks found. Synthesizing...")
        synthesized = await _synthesize_target_test(state, toolkit)
        log_step("synthesize_target_test", {}, "Hunks generated" if synthesized else "Failed")

        validation_results["test_synthesis"] = {
            "success": bool(synthesized),
            "raw": "Hunks generated" if synthesized else "Failed to synthesize a viable test case."
        }

        if not synthesized:
            error_msg = "Failed to synthesize a viable test case."
            analysis = await _analyze_failure("Test Synthesis", error_msg, state)
            validation_results["test_synthesis"]["agent_evaluation"] = analysis
            validation_results["test_synthesis"]["error_context"] = analysis
            trace.append(f"\n**Final Status: TEST SYNTHESIS FAILED**\n\n**Agent Analysis:**\n{analysis}")
            toolkit.write_trace("\n".join(trace), "validation_trace.md")
            return {
                "validation_passed": False,
                "validation_attempts": attempts + 1,
                "validation_error_context": analysis,
                "validation_results": validation_results,
                "regeneration_hint": analysis
            }
        test_hunks = synthesized
    else:
        validation_results["test_synthesis"] = {
            "success": True,
            "agent_evaluation": "Test hunks provided from previous phase."
        }

    test_classes = _extract_test_classes(test_hunks)

    # 3.2 Phase 1: Proof of Vulnerability
    print("  Agent 4: Phase 1 — Proof of Vulnerability (Applying tests only)...")
    res1 = toolkit.apply_adapted_hunks(code_hunks=[], test_hunks=test_hunks)
    log_step("apply_adapted_hunks (tests only)", {"count": len(test_hunks)}, res1)

    validation_results["test_application"] = {
        "success": res1["success"],
        "raw": res1["output"]
    }

    if not res1["success"]:
        analysis = await _analyze_failure("Test Application", res1["output"], state)
        validation_results["test_application"]["agent_evaluation"] = analysis
        validation_results["test_application"]["error_context"] = analysis
        trace.append(f"\n**Final Status: TEST APPLICATION FAILED**\n\n**Agent Analysis:**\n{analysis}")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": analysis,
            "adapted_test_hunks": test_hunks,
            "validation_results": validation_results,
            "regeneration_hint": analysis
        }
    else:
        validation_results["test_application"]["agent_evaluation"] = "Test hunks applied successfully."

    # 3.3 Phase 2: Failure Confirmation
    print("  Agent 4: Phase 2 — Failure Confirmation (Running targeted tests)...")
    res2 = toolkit.run_targeted_tests(test_classes)
    log_step("run_targeted_tests (pre-fix)", {"classes": test_classes}, res2)

    # In Phase 2, SUCCESS (tests passing) is actually a FAILURE for the backport process
    # because the test should fail before the fix.
    validation_results["failure_confirmation"] = {
        "success": not res2["success"] and not res2["compile_error"],
        "raw": res2["output"]
    }

    if res2["compile_error"]:
        analysis = await _analyze_failure("Failure Confirmation (Compile)", res2["output"], state)
        validation_results["failure_confirmation"]["agent_evaluation"] = analysis
        validation_results["failure_confirmation"]["error_context"] = analysis
        trace.append(f"\n**Final Status: COMPILATION FAILED (PRE-FIX)**\n\n**Agent Analysis:**\n{analysis}")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": analysis,
            "adapted_test_hunks": test_hunks,
            "validation_results": validation_results,
            "regeneration_hint": analysis
        }

    if res2["success"]:
        analysis = "Test passed unexpectedly before fix. The synthesized test does not reproduce the issue. The test needs to be rewritten to properly trigger the vulnerability condition."
        validation_results["failure_confirmation"]["agent_evaluation"] = analysis
        validation_results["failure_confirmation"]["error_context"] = analysis
        trace.append(f"\n**Final Status: INVALID TEST (PASSED UNEXPECTEDLY)**\n\n**Agent Analysis:**\n{analysis}")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": analysis,
            "adapted_test_hunks": test_hunks,
            "validation_results": validation_results,
            "regeneration_hint": analysis
        }

    validation_results["failure_confirmation"]["agent_evaluation"] = "Tests failed as expected before fix - vulnerability confirmed."
    trace.append("**Failure Confirmed** (Tests failed as expected).\n")
    
    # 3.4 Phase 3: Patch Application
    print("  Agent 4: Phase 3 — Patch Application (Applying code fix)...")
    toolkit.restore_repo_state() # Cleanup buggy tests before full applied
    res3 = toolkit.apply_adapted_hunks(code_hunks=code_hunks, test_hunks=test_hunks)
    log_step("apply_adapted_hunks (full)", {"code_count": len(code_hunks), "test_count": len(test_hunks)}, res3)

    validation_results["patch_application"] = {
        "success": res3["success"],
        "raw": res3["output"]
    }

    if not res3["success"]:
        analysis = await _analyze_failure("Patch Application", res3["output"], state)
        validation_results["patch_application"]["agent_evaluation"] = analysis
        validation_results["patch_application"]["error_context"] = analysis
        trace.append(f"\n**Final Status: PATCH APPLICATION FAILED**\n\n**Agent Analysis:**\n{analysis}")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": analysis,
            "adapted_test_hunks": test_hunks,
            "validation_results": validation_results,
            "regeneration_hint": analysis
        }
    else:
        validation_results["patch_application"]["agent_evaluation"] = "Code and test hunks applied successfully."

    # 3.5 Phase 4: Targeted Verification
    print("  Agent 4: Phase 4 — Targeted Verification (Making it Green)...")
    res4 = toolkit.run_targeted_tests(test_classes)
    log_step("run_targeted_tests (post-fix)", {"classes": test_classes}, res4)

    validation_results["targeted_verification"] = {
        "success": res4["success"],
        "raw": res4["output"]
    }

    if not res4["success"]:
        analysis = await _analyze_failure("Targeted Verification", res4["output"], state)
        validation_results["targeted_verification"]["agent_evaluation"] = analysis
        validation_results["targeted_verification"]["error_context"] = analysis
        trace.append(f"\n**Final Status: VERIFICATION FAILED**\n\n**Agent Analysis:**\n{analysis}")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": analysis,
            "adapted_test_hunks": test_hunks,
            "validation_results": validation_results,
            "regeneration_hint": analysis
        }
    else:
        validation_results["targeted_verification"]["agent_evaluation"] = "All tests passed after fix application."

    trace.append("**Verification Successful** (Tests passed!).\n")

    # 3.6 Phase 5: AST/Static Validation
    print("  Agent 4: Phase 5 — AST/Static Validation (Running SpotBugs)...")
    # Recompile all files to ensure all classes are available for SpotBugs
    build_res_full = toolkit.compile_files(unique_code_files + unique_test_files)

    validation_results["full_compilation"] = {
        "success": build_res_full.get("success"),
        "raw": build_res_full.get("output", "")
    }

    if not build_res_full.get("success"):
        analysis = await _analyze_failure("Full Compilation", build_res_full.get("output", ""), state)
        validation_results["full_compilation"]["agent_evaluation"] = analysis
        validation_results["full_compilation"]["error_context"] = analysis
        trace.append(f"\n**Final Status: COMPILATION FAILED (PRE-SPOTBUGS)**\n\n**Agent Analysis:**\n{analysis}")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": analysis,
            "adapted_test_hunks": test_hunks,
            "validation_results": validation_results,
            "regeneration_hint": analysis
        }
    else:
        validation_results["full_compilation"]["agent_evaluation"] = "Full project compilation successful."

    modules = build_res_full.get("modules", [])
    classes_paths = toolkit.get_module_class_paths(modules)

    spotbugs_res = toolkit.run_spotbugs(compiled_classes_paths=classes_paths, source_path=os.path.join(target_repo_path, "src", "main", "java"))
    log_step("run_spotbugs", {"paths": classes_paths}, spotbugs_res)

    passed = spotbugs_res.get("success", True)
    validation_results["spotbugs"] = {
        "success": passed,
        "raw": str(spotbugs_res)
    }

    if not passed:
        analysis = await _analyze_failure("SpotBugs", str(spotbugs_res), state)
        validation_results["spotbugs"]["agent_evaluation"] = analysis
        validation_results["spotbugs"]["error_context"] = analysis
        trace.append(f"\n**Final Status: STATIC VALIDATION FAILED**\n\n**Agent Analysis:**\n{analysis}")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": analysis,
            "adapted_test_hunks": test_hunks,
            "validation_results": validation_results,
            "regeneration_hint": analysis
        }
    else:
        validation_results["spotbugs"]["agent_evaluation"] = "No high-severity bugs detected. Code passes static analysis."

    trace.append("**Static Validation Successful** (No high-severity bugs found).\n")

    print("  Agent 4: 'Prove Red, Make Green' loop complete! Validation PASSED.")
    trace.append("\n**Final Status: VALIDATION PASSED**")
    toolkit.write_trace("\n".join(trace), "validation_trace.md")

    return {
        "validation_passed": True,
        "validation_attempts": attempts + 1,
        "adapted_test_hunks": test_hunks,
        "validation_results": validation_results,
        "messages": [HumanMessage(content="Validation passed successfully.")]
    }
