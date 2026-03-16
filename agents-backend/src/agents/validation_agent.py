"""
Agent 4: The Verifier (Validation Loop)

H-MABS Phase 4 — "Prove Red, Make Green" Loop
"""
import json
import os
import re
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from state import AgentState, AdaptedHunk
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

MAX_VALIDATION_ATTEMPTS = 3

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
    model_name = os.getenv("VALIDATION_MODEL", "gemini-2.0-flash")
    provider = os.getenv("VALIDATION_PROVIDER", "google").lower()

    if provider == "azure":
        llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_CHAT_DEPLOYMENT", "apim-4o-mini"),
            openai_api_version=os.getenv("AZURE_CHAT_VERSION", "2024-02-01"),
            azure_endpoint=os.getenv("AZURE_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY", os.getenv("OPENAI_API_KEY")),
            temperature=0
        )
    elif provider == "openai":
        llm = ChatOpenAI(
            model=model_name,
            temperature=0,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_api_base=os.getenv("OPENAI_BASE_URL")
        )
    else:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
    
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
    
    if attempts >= MAX_VALIDATION_ATTEMPTS:
        print(f"  Agent 4: Max validation attempts ({MAX_VALIDATION_ATTEMPTS}) reached. Failing.")
        return {"validation_passed": False}
        
    # Ensure clean repo
    toolkit.restore_repo_state()
    
    # Trace Initialization
    unique_code_files = list(set([h.get("target_file") for h in code_hunks if h.get("target_file")]))
    unique_test_files = list(set([h.get("target_file") for h in test_hunks if h.get("target_file")]))
    
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

    # Compile-Only Mode (Streamlined)
    if compile_only:
        print("  Agent 4: Streamline compilation verification...")
        res = toolkit.apply_adapted_hunks(code_hunks, test_hunks)
        log_step("apply_adapted_hunks", {"code_count": len(code_hunks), "test_count": len(test_hunks)}, res)
        
        if not res["success"]:
            trace.append("\n**Final Status: HUNK APPLICATION FAILED**")
            toolkit.write_trace("\n".join(trace), "validation_trace.md")
            return {
                "validation_passed": False,
                "validation_attempts": attempts + 1,
                "validation_error_context": f"Hunk application failed: {res['output']}"
            }
        
        applied_files = res.get("applied_files", [])
        build_res = toolkit.compile_files(applied_files)
        log_step("compile_files", {"files": applied_files}, build_res)
        
        if not build_res.get("success"):
            trace.append("\n**Final Status: COMPILATION FAILED**")
            toolkit.write_trace("\n".join(trace), "validation_trace.md")
            return {
                "validation_passed": False,
                "validation_attempts": attempts + 1,
                "validation_error_context": build_res.get("output", "")
            }

        # Run SpotBugs after successful compile
        print("  Agent 4: Running SpotBugs validation...")
        modules = build_res.get("modules", [])
        classes_paths = toolkit.get_module_class_paths(modules)
        
        spotbugs_res = toolkit.run_spotbugs(compiled_classes_paths=classes_paths, source_path=os.path.join(state["target_repo_path"], "src", "main", "java"))
        log_step("run_spotbugs", {"paths": classes_paths}, spotbugs_res)
        
        passed = spotbugs_res.get("success", True)
        trace.append(f"\n**Final Status: {'VALIDATION PASSED' if passed else 'STATIC VALIDATION FAILED'}**")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        
        return {
            "validation_passed": passed,
            "validation_attempts": attempts + 1,
            "validation_error_context": spotbugs_res.get("output", "") if not passed else ""
        }

    # Standard "Prove Red, Make Green" Loop
    # 3.1 Phase 6: Test Synthesis (Moved to start if missing)
    if not test_hunks:
        print("  Agent 4: No test hunks found. Synthesizing...")
        synthesized = await _synthesize_target_test(state, toolkit)
        log_step("synthesize_target_test", {}, "Hunks generated" if synthesized else "Failed")
        if not synthesized:
            error_msg = "Failed to synthesize a viable test case."
            trace.append(f"\n**Final Status: TEST SYNTHESIS FAILED**")
            toolkit.write_trace("\n".join(trace), "validation_trace.md")
            return {
                "validation_passed": False,
                "validation_attempts": attempts + 1,
                "validation_error_context": error_msg
            }
        test_hunks = synthesized

    test_classes = _extract_test_classes(test_hunks)
    
    # 3.2 Phase 1: Proof of Vulnerability
    print("  Agent 4: Phase 1 — Proof of Vulnerability (Applying tests only)...")
    res1 = toolkit.apply_adapted_hunks(code_hunks=[], test_hunks=test_hunks)
    log_step("apply_adapted_hunks (tests only)", {"count": len(test_hunks)}, res1)
    if not res1["success"]:
        error_msg = f"Failed to apply test patch:\n{res1['output']}"
        print(f"    Agent 4 Error: {error_msg}")
        trace.append(f"\n**Final Status: TEST APPLICATION FAILED**")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": error_msg,
            "adapted_test_hunks": test_hunks
        }
        
    # 3.3 Phase 2: Failure Confirmation
    print("  Agent 4: Phase 2 — Failure Confirmation (Running targeted tests)...")
    res2 = toolkit.run_targeted_tests(test_classes)
    log_step("run_targeted_tests (pre-fix)", {"classes": test_classes}, res2)
    
    if res2["compile_error"]:
        error_msg = f"Test compilation error BEFORE fix applied:\n{res2['output']}"
        print(f"    Agent 4 Error: {error_msg}")
        trace.append(f"\n**Final Status: COMPILATION FAILED (PRE-FIX)**")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": error_msg,
            "adapted_test_hunks": test_hunks
        }
        
    if res2["success"]:
        error_msg = "Targeted tests passed BEFORE the fix was applied. The test is invalid and does not trigger the vulnerability."
        print(f"    Agent 4 Error: {error_msg}")
        trace.append(f"\n**Final Status: INVALID TEST (PASSED UNEXPECTEDLY)**")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": error_msg,
            "adapted_test_hunks": test_hunks
        }
        
    trace.append("**Failure Confirmed** (Tests failed as expected).\n")
    
    # 3.4 Phase 3: Patch Application
    print("  Agent 4: Phase 3 — Patch Application (Applying code fix)...")
    toolkit.restore_repo_state() # Cleanup buggy tests before full applied
    res3 = toolkit.apply_adapted_hunks(code_hunks=code_hunks, test_hunks=test_hunks)
    log_step("apply_adapted_hunks (full)", {"code_count": len(code_hunks), "test_count": len(test_hunks)}, res3)
    
    if not res3["success"]:
        error_msg = f"Failed to apply code + test patch:\n{res3['output']}"
        print(f"    Agent 4 Error: {error_msg}")
        trace.append(f"\n**Final Status: PATCH APPLICATION FAILED**")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": error_msg,
            "adapted_test_hunks": test_hunks
        }

    # 3.5 Phase 4: Targeted Verification
    print("  Agent 4: Phase 4 — Targeted Verification (Making it Green)...")
    res4 = toolkit.run_targeted_tests(test_classes)
    log_step("run_targeted_tests (post-fix)", {"classes": test_classes}, res4)
    
    if not res4["success"]:
        error_msg = f"Fix applied, but tests failed or compile aborted:\n{res4['output']}"
        print(f"    Agent 4 Error: {error_msg}")
        trace.append(f"\n**Final Status: VERIFICATION FAILED**")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": error_msg,
            "adapted_test_hunks": test_hunks
        }
        
    trace.append("**Verification Successful** (Tests passed!).\n")

    # 3.6 Phase 5: AST/Static Validation
    print("  Agent 4: Phase 5 — AST/Static Validation (Running SpotBugs)...")
    # Recompile all files to ensure all classes are available for SpotBugs
    # This is necessary because run_targeted_tests only compiles test classes and their dependencies.
    build_res_full = toolkit.compile_files(unique_code_files + unique_test_files)
    if not build_res_full.get("success"):
        error_msg = f"Full compilation failed before SpotBugs:\n{build_res_full.get('output', '')}"
        print(f"    Agent 4 Error: {error_msg}")
        trace.append(f"\n**Final Status: COMPILATION FAILED (PRE-SPOTBUGS)**")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": error_msg,
            "adapted_test_hunks": test_hunks
        }

    modules = build_res_full.get("modules", [])
    classes_paths = toolkit.get_module_class_paths(modules)
        
    spotbugs_res = toolkit.run_spotbugs(compiled_classes_paths=classes_paths, source_path=os.path.join(target_repo_path, "src", "main", "java"))
    log_step("run_spotbugs", {"paths": classes_paths}, spotbugs_res)
    
    if not spotbugs_res.get("success", True):
        error_msg = f"SpotBugs detected potential issues:\n{spotbugs_res.get('output', 'Unknown Check Failure')}"
        print(f"    Agent 4 Error: {error_msg}")
        trace.append(f"\n**Final Status: STATIC VALIDATION FAILED**")
        toolkit.write_trace("\n".join(trace), "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": error_msg,
            "adapted_test_hunks": test_hunks
        }
    
    trace.append("**Static Validation Successful** (No high-severity bugs found).\n")

    print("  Agent 4: 'Prove Red, Make Green' loop complete! Validation PASSED.")
    trace.append("\n**Final Status: VALIDATION PASSED**")
    toolkit.write_trace("\n".join(trace), "validation_trace.md")
    
    return {
        "validation_passed": True,
        "validation_attempts": attempts + 1,
        "adapted_test_hunks": test_hunks,
        "messages": [HumanMessage(content="Validation passed successfully.")]
    }
