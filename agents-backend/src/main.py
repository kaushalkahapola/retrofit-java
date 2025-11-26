import asyncio
import sys
import os
from dotenv import load_dotenv
from graph import app

# Load environment variables from .env file
load_dotenv()

# Add src to path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def main():
    # sse_url = os.getenv("MCP_SERVER_URL", "http://localhost:8080/mcp/sse")
    # print(f"Connecting to Analysis Engine at {sse_url}...")


    import argparse
    parser = argparse.ArgumentParser(description="Java Backporting Agent")
    parser.add_argument("--patch", help="Absolute path to the patch file")
    parser.add_argument("--target", help="Absolute path to the target repo")
    parser.add_argument("--mainline", help="Absolute path to the mainline repo")
    parser.add_argument("--experiment", action="store_true", help="Run in experiment mode")
    parser.add_argument("--backport-commit", help="Backport commit hash (for experiment mode)")
    parser.add_argument("--original-commit", help="Original commit hash (for experiment mode)")
    
    args = parser.parse_args()

    try:
        print("Running Orchestrator Graph...")
        
        # Get patch file path
        patch_path = args.patch
        if not patch_path:
            patch_path = input("Enter the absolute path to the patch file: ").strip()
        
        # Get target repo path
        target_repo_path = args.target
        if not target_repo_path:
            target_repo_path = input("Enter the absolute path to the target repo: ").strip()
        
        # Get mainline repo path
        mainline_repo_path = args.mainline
        if not mainline_repo_path:
            mainline_repo_path = input("Enter the absolute path to the mainline repo: ").strip()
        
        # Experiment mode
        experiment_mode = args.experiment
        if not experiment_mode and not any([args.patch, args.target, args.mainline]): # Only ask if no args provided
             experiment_input = input("Is this an experiment? (y/n): ").strip().lower()
             experiment_mode = experiment_input == 'y'
        
        backport_commit = args.backport_commit if args.backport_commit else ""
        original_commit = args.original_commit if args.original_commit else "HEAD"
        
        if experiment_mode:
            if not backport_commit:
                backport_commit = input("Enter the backport commit hash: ").strip()
            if not original_commit and not args.original_commit: # Only ask if not provided via arg
                original_commit = input("Enter the original commit hash (from mainline): ").strip()
        
        inputs = {
            "messages": ["Start"],
            "patch_path": patch_path,
            "target_repo_path": target_repo_path,
            "mainline_repo_path": mainline_repo_path,
            "experiment_mode": experiment_mode,
            "backport_commit": backport_commit,
            "original_commit": original_commit
        }
        
        async for output in app.astream(inputs):
            for key, value in output.items():
                print(f"Output from {key}:")
                # Pretty print messages
                if "messages" in value:
                    for msg in value["messages"]:
                        print(f"  {msg.content}")
                print("----")
    except Exception as e:
        print(f"Error running Orchestrator: {e}")

if __name__ == "__main__":
    asyncio.run(main())
