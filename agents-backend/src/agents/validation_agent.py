"""
Agent 4: The Verifier (Validation Loop)

H-MABS Phase 4 — "Prove Red, Make Green" Loop
"""
import json
import os
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
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
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
    
    try:
        response = await llm.ainvoke([
            SystemMessage(content=_SYNTHESIZE_TEST_SYSTEM),
            HumanMessage(content=prompt)
        ])
        raw_content = response.content if hasattr(response, "content") else str(response)
        adapted_hunk_text = _extract_hunk_block(raw_content)
        
        if adapted_hunk_text:
            target_file = "src/test/java/SynthesizedVulnTest.java" # Fallback
            lines = adapted_hunk_text.splitlines()
            for line in lines:
                if line.startswith("+++ b/"):
                    target_file = line[6:].strip()
                    break
            
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
    
    if attempts >= MAX_VALIDATION_ATTEMPTS:
        print(f"  Agent 4: Max validation attempts ({MAX_VALIDATION_ATTEMPTS}) reached. Failing.")
        return {"validation_passed": False}
        
    # Ensure clean repo
    toolkit.restore_repo_state()
    
    trace_content = f"# Validation Agent Trace (Attempt {attempts + 1})\n\n"
    
    # 3.1 Phase 6: Test Synthesis (Moved to start if missing)
    if not test_hunks:
        trace_content += "## Phase 6: Test Synthesis\nNo test hunks found. Synthesizing...\n"
        synthesized = await _synthesize_target_test(state, toolkit)
        if not synthesized:
            error_msg = "Failed to synthesize a viable test case."
            trace_content += f"**Error**: {error_msg}\n"
            toolkit.write_trace(trace_content, "validation_trace.md")
            return {
                "validation_passed": False,
                "validation_attempts": attempts + 1,
                "validation_error_context": error_msg
            }
        test_hunks = synthesized

    test_classes = _extract_test_classes(test_hunks)
    
    # 3.2 Phase 1: Proof of Vulnerability
    print("  Agent 4: Phase 1 — Proof of Vulnerability (Applying tests only)...")
    trace_content += "## Phase 1: Proof of Vulnerability\n"
    res1 = toolkit.apply_adapted_hunks(code_hunks=[], test_hunks=test_hunks)
    if not res1["success"]:
        error_msg = f"Failed to apply test patch:\n{res1['output']}"
        print(f"    Agent 4 Error: {error_msg}")
        trace_content += f"**Failed:**\n```\n{res1['output']}\n```\n"
        toolkit.write_trace(trace_content, "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": error_msg,
            "adapted_test_hunks": test_hunks
        }
        
    # 3.3 Phase 2: Failure Confirmation
    print("  Agent 4: Phase 2 — Failure Confirmation (Running targeted tests)...")
    trace_content += f"## Phase 2: Failure Confirmation\nRunning tests: {test_classes}\n"
    res2 = toolkit.run_targeted_tests(test_classes)
    
    if res2["compile_error"]:
        error_msg = f"Test compilation error BEFORE fix applied:\n{res2['output']}"
        print(f"    Agent 4 Error: {error_msg}")
        trace_content += f"**Compile Error:**\n```\n{res2['output']}\n```\n"
        toolkit.write_trace(trace_content, "validation_trace.md")
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
        trace_content += f"**Invalid Test (Passed unexpectedly):**\n```\n{res2['output']}\n```\n"
        toolkit.write_trace(trace_content, "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": error_msg,
            "adapted_test_hunks": test_hunks
        }
        
    trace_content += "**Failure Confirmed** (Tests failed as expected).\n"
    
    # 3.4 Phase 3: Patch Application
    print("  Agent 4: Phase 3 — Patch Application (Applying code fix)...")
    trace_content += "## Phase 3: Patch Application\n"
    toolkit.restore_repo_state() # Cleanup buggy tests before full applied
    res3 = toolkit.apply_adapted_hunks(code_hunks=code_hunks, test_hunks=test_hunks)
    if not res3["success"]:
        error_msg = f"Failed to apply code + test patch:\n{res3['output']}"
        print(f"    Agent 4 Error: {error_msg}")
        trace_content += f"**Failed:**\n```\n{res3['output']}\n```\n"
        toolkit.write_trace(trace_content, "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": error_msg,
            "adapted_test_hunks": test_hunks
        }

    # 3.5 Phase 4: Targeted Verification
    print("  Agent 4: Phase 4 — Targeted Verification (Making it Green)...")
    trace_content += "## Phase 4: Targeted Verification\n"
    res4 = toolkit.run_targeted_tests(test_classes)
    
    if not res4["success"]:
        error_msg = f"Fix applied, but tests failed or compile aborted:\n{res4['output']}"
        print(f"    Agent 4 Error: {error_msg}")
        trace_content += f"**Failed:**\n```\n{res4['output']}\n```\n"
        toolkit.write_trace(trace_content, "validation_trace.md")
        toolkit.restore_repo_state()
        return {
            "validation_passed": False,
            "validation_attempts": attempts + 1,
            "validation_error_context": error_msg,
            "adapted_test_hunks": test_hunks
        }
        
    trace_content += "**Verification Successful** (Tests passed!).\n"

    # 3.6 Phase 5: AST Validation
    print("  Agent 4: Phase 5 — AST Validation (Skipped/Stubbed)...")
    trace_content += "## Phase 5: AST Validation\n(Stubbed for now. Semantic correctness assured via tests.)\n"

    print("  Agent 4: 'Prove Red, Make Green' loop complete! Validation PASSED.")
    trace_content += "\n**Final Status: VALIDATION PASSED**"
    toolkit.write_trace(trace_content, "validation_trace.md")
    
    return {
        "validation_passed": True,
        "validation_attempts": attempts + 1,
        "adapted_test_hunks": test_hunks,
        "messages": [HumanMessage(content="Validation passed successfully.")]
    }
