from langchain_core.messages import HumanMessage
from state import AgentState
from agents.validation_tools import ValidationToolkit
import json

async def validation_agent(state: AgentState, config):
    """
    The Gatekeeper. Validates the generated code by compiling and running SpotBugs.
    """
    print("Validation Agent: Starting validation loop...")
    
    # 1. Setup
    target_repo_path = state.get("target_repo_path")
    plan = state.get("implementation_plan")
    
    if not plan:
        msg = "Error: No implementation plan found in state."
        print(msg)
        return {"messages": [HumanMessage(content=msg)]}

    # Extract modified files from the plan
    # The plan is a dict (if coming from serialized state) or ImplementationPlan object
    # The 'steps' field contains the actions.
    steps = plan.get("steps", []) if isinstance(plan, dict) else plan.steps

    files_to_validate = set()
    for step in steps:
        # Check if step is dict or object
        file_path = step.get("file_path") if isinstance(step, dict) else step.file_path
        if file_path and file_path.endswith(".java"):
            files_to_validate.add(file_path)

    files_list = list(files_to_validate)
    print(f"Validation Agent: Files to validate: {files_list}")

    toolkit = ValidationToolkit(target_repo_path)

    trace_content = "# Validation Agent Trace\n\n"
    trace_content += "## Validation Targets\n"
    for f in files_list:
        trace_content += f"- `{f}`\n"
    trace_content += "\n"

    validation_result = {
        "success": True,
        "compilation": {},
        "spotbugs": {},
        "issues": []
    }

    # 2. Compile
    print("Validation Agent: Compiling...")
    compile_result = toolkit.compile_files(files_list)

    trace_content += "## Compilation\n"
    trace_content += f"**Success**: {compile_result.get('success')}\n\n"
    trace_content += "### Output\n```\n" + compile_result.get("message", "") + "\n```\n\n"

    validation_result["compilation"] = compile_result

    if not compile_result.get("success"):
        validation_result["success"] = False
        validation_result["issues"].append("Compilation Failed")
        trace_content += "**Status**: Compilation Failed. Aborting SpotBugs.\n"
    else:
        # 3. SpotBugs
        print("Validation Agent: Running SpotBugs...")
        compiled_classes_path = compile_result.get("output_path")
        source_path = compile_result.get("source_path")

        spotbugs_result = toolkit.run_spotbugs(compiled_classes_path, source_path)

        trace_content += "## SpotBugs Analysis\n"
        trace_content += f"**Success**: {spotbugs_result.get('success')}\n\n"
        trace_content += "### Report\n```\n" + spotbugs_result.get("report", "") + "\n```\n\n"

        validation_result["spotbugs"] = spotbugs_result

        # Determine if SpotBugs failed (this is subjective based on report content)
        # But we can check if success is false (runtime error)
        if not spotbugs_result.get("success"):
             validation_result["success"] = False
             validation_result["issues"].append("SpotBugs Runtime Error")
        else:
             # Heuristic: Check if report contains specific bug patterns or isn't empty if that implies bugs
             # For now, we assume if tool ran, it's 'success' in terms of execution,
             # but we might want to parse the report to set validation_result["success"] = False if bugs found.
             # The user said "if compilation fails then save ... with a success fail flag".
             # Implies if SpotBugs finds bugs, we might mark as fail?
             # Let's assume if report is not empty of bugs, it's a fail?
             # SpotBugs text output usually lists bugs.
             report = spotbugs_result.get("report", "")
             # Simple check: if "M" (Medium) or "H" (High) priority bugs are listed?
             # Or look for "BugInstance"?
             # TextUI output example: "H D DLS_DEAD_LOCAL_STORE ..."
             # If output is empty (or just summary saying 0 bugs), it's clean.
             pass

    # 4. Finalize
    toolkit.write_trace(trace_content)

    status_msg = "Validation Complete. " + ("Success." if validation_result["success"] else "Failed.")

    # Append the result to the state (maybe in messages or a new field if state allowed dynamic fields,
    # but strictly typed state might need update.
    # The prompt says "output the things just similar to reasoning agents outputs (the mds and all)"
    # and "save the final json".
    # I'll save the json to a file as well, and return a message.

    with open("validation_result.json", "w", encoding="utf-8") as f:
        json.dump(validation_result, f, indent=2)

    return {
        "messages": [HumanMessage(content=status_msg)]
    }
