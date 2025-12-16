from langchain_core.messages import HumanMessage
from state import AgentState
from agents.validation_tools import ValidationToolkit
import json

async def validation_agent(state: AgentState, config):
    """
    The Gatekeeper. Validates the generated code by compiling and running SpotBugs.
    Uses a 'Reasoning Trace' format with intelligent failure analysis.
    """
    print("Validation Agent: Starting validation loop...")
    
    # 1. Setup
    target_repo_path = state.get("target_repo_path")
    plan = state.get("implementation_plan")
    experiment_mode = state.get("experiment_mode", False)
    backport_commit = state.get("backport_commit")
    patch_path = state.get("patch_path")

    if not plan:
        msg = "Error: No implementation plan found in state."
        print(msg)
        return {"messages": [HumanMessage(content=msg)]}
    
    # Trace Helpers
    trace_content = "# Validation Agent Trace\n\n"
    
    def write_thought(text):
        nonlocal trace_content
        trace_content += f"## Agent Thought\n{text}\n\n"
    
    def write_tool_output(tool_name, output):
        nonlocal trace_content
        trace_content += f"## Tool Output ({tool_name})\n"
        if isinstance(output, (dict, list)):
            trace_content += f"```json\n{json.dumps(output, indent=2, default=str)}\n```\n\n"
        else:
            trace_content += f"```\n{output}\n```\n\n"

    # Identify plan files
    steps = plan.get("steps", []) if isinstance(plan, dict) else plan.steps
    plan_files = set()
    for step in steps:
        file_path = step.get("file_path") if isinstance(step, dict) else step.file_path
        if file_path:
            plan_files.add(file_path)

    # --- EXPERIMENT MODE OPERATIONS ---
    repo = None
    if experiment_mode:
        write_thought(f"Running in EXPERIMENT MODE.\nTarget: Backporting {backport_commit} to {state['target_repo_path']}.\nStrategy: Force Clean -> Checkout -> Patch -> Compile -> Verify.")
        
        if not backport_commit or not patch_path:
             return {"messages": [HumanMessage(content="Error: Missing commit/patch for experiment mode.")]}
        
        try:
            from git import Repo
            repo = Repo(target_repo_path)
            
            # 1. Checkout
            write_thought("Preparing repository. I will force clean local changes and checkout the target commit.")
            try:
                 repo.git.reset("--hard")
                 repo.git.clean("-fd")
            except Exception as e:
                 print(f"Warning during clean: {e}")
            
            repo.git.checkout(backport_commit, force=True)
            # 2. Reset
            repo.git.reset("--hard", "HEAD^")
            
            write_tool_output("git_checkout", f"Checked out {backport_commit} and reset to HEAD^")

            # 3. Apply Patch
            write_thought(f"Applying patch `{patch_path}`. I will attempt multiple strategies (Direct, Whitespace, Newline Fix).")
            
            apply_success = False
            apply_log = []
            
            # Application Logic (Simplified for brevity but retaining robustness)
            # Application Logic (Simplified for brevity but retaining robustness)
            try:
                repo.git.apply(patch_path)
                apply_success = True
                apply_log.append("Direct Apply: Success")
            except Exception:
                apply_log.append("Direct Apply: Failed")
                try:
                    repo.git.apply(patch_path, ignore_space_change=True, ignore_whitespace=True)
                    apply_success = True
                    apply_log.append("Whitespace Ignore: Success")
                except Exception:
                    apply_log.append("Whitespace Ignore: Failed")
                    # Newline Fix Strategy
                    try:
                        with open(patch_path, 'rb') as f:
                            raw = f.read()
                        content = raw.decode('utf-8', errors='ignore').replace('\r\n', '\n')
                        if not content.endswith('\n'): content += '\n'
                        
                        import tempfile, os
                        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".patch", encoding='utf-8', newline='\n') as tf:
                            tf.write(content)
                            tf_path = tf.name
                        
                        try:
                            repo.git.apply(tf_path, ignore_space_change=True, ignore_whitespace=True)
                            apply_success = True
                            apply_log.append("Newline Fix: Success")
                        finally:
                            if os.path.exists(tf_path): os.remove(tf_path)
                    except Exception:
                        apply_log.append("Newline Fix: Failed")
            
            write_tool_output("git_apply", "\n".join(apply_log))
            
            if not apply_success:
                 write_thought("Patch application failed completely. Aborting.")
                 toolkit = ValidationToolkit(target_repo_path)
                 toolkit.write_trace(trace_content)
                 return {"messages": [HumanMessage(content="Patch Application Failed")]}

            # 4. Verify Files
            write_thought("Patch applied. Verifying changed files against the plan.")
            from utils.patch_analyzer import PatchAnalyzer
            with open(patch_path, "r", encoding="utf-8") as f:
                patch_files = set(c.file_path for c in PatchAnalyzer().analyze(f.read()))
            
            write_tool_output("patch_verification", {
                "plan_files": list(plan_files),
                "patch_files": list(patch_files),
                "match": list(plan_files) == list(patch_files)
            })

        except Exception as e:
            trace_content += f"\nCRITICAL ERROR: {e}\n"
            return {"messages": [HumanMessage(content=f"Error: {e}")]}

    # --- VALIDATION ---
    files_to_validate = list(patch_files) if (experiment_mode and 'patch_files' in locals()) else list(plan_files)
    files_to_validate = [f for f in files_to_validate if f.endswith(".java")]
    
    toolkit = ValidationToolkit(target_repo_path)
    
    validation_result = {"success": True, "issues": []}

    # 1. Compile
    write_thought(f"Compiling {len(files_to_validate)} files using Smart Compiler (javac).")
    compile_result = toolkit.compile_files(files_to_validate)
    write_tool_output("smart_compile", compile_result)
    
    validation_result["compilation"] = compile_result
    
    if not compile_result["success"]:
        validation_result["success"] = False
        validation_result["issues"].append("Compilation Failed")
        
        # FAILURE ANALYSIS
        write_thought("Compilation failed. Using LLM to analyze the error log and suggest fixes.")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
            fail_prompt = f"""
You are a Java Compiler Expert.
ERROR LOG:
{compile_result.get('message', '')}

TASK:
1. Explain root cause.
2. Suggest specific fixes.

OUTPUT: Markdown.
"""
            analysis = llm.invoke(fail_prompt).content
            write_thought(f"**Failure Analysis**:\n{analysis}")
            validation_result["analysis"] = {"failure_analysis": analysis}
        except Exception as e:
            write_thought(f"Analysis failed: {e}")

    else:
        # 2. SpotBugs
        write_thought("Compilation passed. Running SpotBugs.")
        spotbugs_result = toolkit.run_spotbugs(compile_result["output_path"], source_path=compile_result.get("source_path"))
        write_tool_output("spotbugs", spotbugs_result)
        validation_result["spotbugs"] = spotbugs_result
        
        if not spotbugs_result.get("success"):
            validation_result["issues"].append("SpotBugs Runtime Error")
        
        # 3. Test Execution (Smart Test)
        test_results = []
        # Identify test files from the plan/patch list
        # We look for files in 'test/' dir or ending in 'Test.java'
        candidate_tests = [f for f in files_to_validate if "test/" in f.replace("\\", "/") or f.endswith("Test.java")]
        
        if candidate_tests:
            write_thought(f"Detected {len(candidate_tests)} test files. Running Smart Test Execution.")
            
            # Determine Module (Priority: Compilation Result > First Patch File > Fallback)
            target_module = "java.desktop" # Fallback
            detected_modules = compile_result.get("patched_modules", [])
            if detected_modules:
                target_module = detected_modules[0]
                if len(detected_modules) > 1:
                     write_thought(f"Multiple modules detected ({detected_modules}). Using primary: {target_module}")
            
            for test_file in candidate_tests:
                # We need the compiled path of the patch, and its source path
                patch_out = compile_result["output_path"]
                patch_src = compile_result.get("source_path", "")
                
                t_res = toolkit.run_test_with_patch(test_file, patch_out, patch_src, target_module=target_module)
                t_res["file"] = test_file
                test_results.append(t_res)
                
                write_tool_output(f"smart_test_execution__{os.path.basename(test_file)}", t_res)
                
                if not t_res["success"]:
                    validation_result["success"] = False
                    validation_result["issues"].append(f"Test Failed: {os.path.basename(test_file)}")
        else:
            write_thought("No test files detected in patch. Skipping Test Execution.")

        validation_result["tests"] = test_results

        # 4. Intelligent Analysis
        write_thought("Performing Intelligent Validation (Consistency & Quality Check).")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
            
            with open(patch_path, "r", encoding="utf-8", errors="replace") as f:
                p_content = f.read()
                
            # Summarize test results for LLM
            test_summary = "No tests run."
            if test_results:
                passed = sum(1 for t in test_results if t['success'])
                total = len(test_results)
                test_summary = f"Passed: {passed}/{total}\n"
                for t in test_results:
                    test_summary += f"- {t['file']}: {'PASS' if t['success'] else 'FAIL'}\n"
                    if not t['success']:
                        test_summary += f"  Error: {t['message'][:500]}...\n"

            prompt = f"""
You are a Senior Java Reviewer.
CONTEXT:
Plan: {json.dumps(plan, indent=2, default=str)}
Patch: ```diff\n{p_content[:5000]}\n```
SpotBugs: ```\n{spotbugs_result.get('report', '')[:4000]}\n```
Test Execution:
```
{test_summary}
```

TASK:
Determine acceptability. Return JSON:
{{
  "acceptable": boolean,
  "reason": "string",
  "consistency_score": 0.0-1.0,
  "changes_needed": "string",
  "regenerate": boolean
}}
"""
            resp = llm.invoke(prompt).content.strip()
            if resp.startswith("```"): resp = resp.split("```")[1].strip()
            if resp.startswith("json"): resp = resp[4:].strip()
            
            analysis_json = json.loads(resp)
            write_tool_output("intelligent_validation", analysis_json)
            validation_result["analysis"] = analysis_json
            
            if not analysis_json.get("acceptable"):
                validation_result["success"] = False
                validation_result["issues"].append("LLM Rejected Patch")
                
        except Exception as e:
             write_thought(f"Intelligent Analysis Error: {e}")

    # Finalize
    toolkit.write_trace(trace_content)
    with open("validation_result.json", "w", encoding="utf-8") as f:
        json.dump(validation_result, f, indent=2)

    # Cleanup Compilation Artifacts
    if "compilation" in validation_result and validation_result["compilation"].get("output_path"):
        import shutil
        out_path = validation_result["compilation"]["output_path"]
        if os.path.exists(out_path):
             shutil.rmtree(out_path, ignore_errors=True)

    return {"messages": [HumanMessage(content="Validation Complete.")]}
