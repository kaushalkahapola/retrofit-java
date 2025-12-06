import asyncio
import os
import json
import argparse
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from agents.validation_agent import validation_agent
from utils.models import ImplementationPlan

# Load environment variables (API keys, etc.)
load_dotenv()

def parse_arguments():
    parser = argparse.ArgumentParser(description="Run Validation Agent in Experiment Mode")
    parser.add_argument("--patch", help="Path to the generated patch file (.diff or .patch)")
    parser.add_argument("--repo", help="Path to the Target Repository")
    parser.add_argument("--commit", help="Backport Commit SHA (Target Repo will be checked out to this)")
    parser.add_argument("--plan", help="Path to the Implementation Plan JSON")
    return parser.parse_args()

async def main():
    args = parse_arguments()

    # --- CONFIGURATION (Match main.py style) ---
    print("--- Validation Agent Experiment Mode ---")
    
    # 1. Patch Path
    PATCH_PATH = args.patch
    if not PATCH_PATH:
        PATCH_PATH = input("Enter the absolute path to the patch file: ").strip()

    # 2. Target Repo
    TARGET_REPO_PATH = args.repo
    if not TARGET_REPO_PATH:
        TARGET_REPO_PATH = input("Enter the absolute path to the target repo: ").strip()

    # 3. Backport Commit
    BACKPORT_COMMIT = args.commit
    if not BACKPORT_COMMIT:
        BACKPORT_COMMIT = input("Enter the backport commit hash: ").strip()

    # 4. Plan Path (Optional)
    PLAN_JSON_PATH = args.plan
    if not PLAN_JSON_PATH:
        plan_input = input("Enter the absolute path to the Implementation Plan JSON (or press Enter for default 'implementation_plan.json'): ").strip()
        PLAN_JSON_PATH = plan_input if plan_input else "implementation_plan.json"
    
    # Load your implementation plan. 
    if os.path.exists(PLAN_JSON_PATH):
        with open(PLAN_JSON_PATH, "r") as f:
            plan_data = json.load(f)
            # If the json is the whole state dump, extract 'implementation_plan'
            if "implementation_plan" in plan_data:
                plan_data = plan_data["implementation_plan"]
            plan = ImplementationPlan(**plan_data)
    elif os.path.exists(os.path.join("..", PLAN_JSON_PATH)):
        # Check parent directory
        parent_plan_path = os.path.join("..", PLAN_JSON_PATH)
        print(f"Found plan in parent directory: {parent_plan_path}")
        with open(parent_plan_path, "r") as f:
            plan_data = json.load(f)
            if "implementation_plan" in plan_data:
                plan_data = plan_data["implementation_plan"]
            plan = ImplementationPlan(**plan_data)
    else:
        # Fallback
        print(f"Warning: {PLAN_JSON_PATH} not found. Using dummy plan for demonstration.")
        plan = {
            "steps": [
                {"file_path": "retrofit/src/main/java/retrofit/RestAdapter.java"},
            ]
        }

    # --- STATE SETUP ---
    state = {
        "target_repo_path": TARGET_REPO_PATH,
        "implementation_plan": plan,
        "experiment_mode": True,
        "backport_commit": BACKPORT_COMMIT,
        "patch_path": PATCH_PATH,
        "messages": [HumanMessage(content="Starting Validation Experiment")]
    }

    print("\n--- Configuration Summary ---")
    print(f"Target Repo: {TARGET_REPO_PATH}")
    print(f"Backport Commit: {BACKPORT_COMMIT}")
    print(f"Patch Path: {PATCH_PATH}")
    print(f"Plan Path: {PLAN_JSON_PATH}")
    print("-----------------------------\n")
    
    try:
        result = await validation_agent(state, config={})
        
        print("\n--- Experiment Result ---")
        for msg in result["messages"]:
            print(f"[Agent]: {msg.content}")
            
        print("\nCheck 'validation_result.json' and 'validation_trace.md' for details.")
        
    except Exception as e:
        print(f"\nError during experiment: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
