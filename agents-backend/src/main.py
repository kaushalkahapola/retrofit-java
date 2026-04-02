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
    parser.add_argument("--mainline-commit", help="Original commit hash from mainline")
    parser.add_argument("--mainline-repo", help="Absolute path to the mainline repo")
    parser.add_argument(
        "--target-repo",
        help="Absolute path to the target repo (if different from mainline)",
    )
    parser.add_argument(
        "--experiment", action="store_true", help="Run in experiment mode"
    )
    parser.add_argument(
        "--backport-commit", help="Backport commit hash (for experiment mode)"
    )

    args = parser.parse_args()

    try:
        print("Running Orchestrator Graph...")

        # Get mainline commit
        mainline_commit = args.mainline_commit
        if not mainline_commit:
            mainline_commit = input("Enter the mainline commit hash: ").strip()

        # Get mainline repo path
        mainline_repo_path = args.mainline_repo
        if not mainline_repo_path:
            mainline_repo_path = input(
                "Enter the absolute path to the mainline repo: "
            ).strip()

        # Get target repo path
        target_repo_path = args.target_repo
        if not target_repo_path:
            target_repo_path = input(
                "Enter the absolute path to the target repo (press Enter to use mainline repo): "
            ).strip()
        if not target_repo_path:
            target_repo_path = mainline_repo_path

        # Experiment mode
        experiment_mode = args.experiment
        if not experiment_mode and not any(
            [args.mainline_commit, args.mainline_repo, args.target_repo]
        ):  # Only ask if no args provided
            experiment_input = input("Is this an experiment? (y/n): ").strip().lower()
            experiment_mode = experiment_input == "y"

        backport_commit = args.backport_commit if args.backport_commit else ""

        if experiment_mode:
            if not backport_commit:
                backport_commit = input("Enter the backport commit hash: ").strip()

        import subprocess

        patch_filename = "mainline_diff.patch"
        patch_path = os.path.abspath(patch_filename)
        print(f"Generating patch from {mainline_commit} in {mainline_repo_path}...")

        try:
            patch_result = subprocess.run(
                ["git", "format-patch", "-1", mainline_commit, "--stdout"],
                cwd=mainline_repo_path,
                capture_output=True,
                check=True,
                text=True,
            )
            with open(patch_path, "w", encoding="utf-8") as f:
                f.write(patch_result.stdout)
            print(f"Saved generated patch to {patch_path}")
        except subprocess.CalledProcessError as e:
            print(f"Error generating patch: {e.stderr}")
            return

        inputs = {
            "messages": ["Start"],
            "patch_path": patch_path,
            "target_repo_path": target_repo_path,
            "mainline_repo_path": mainline_repo_path,
            "experiment_mode": experiment_mode,
            "backport_commit": backport_commit,
            "original_commit": mainline_commit,
            "with_test_changes": False,  # Set to False by default to ignore test file changes
        }

        # Log and token tracking initialization
        log_file_path = os.path.join(os.path.dirname(patch_path), "log.txt")
        tokens_file_path = os.path.join(os.path.dirname(patch_path), "tokens.txt")

        with open(log_file_path, "w", encoding="utf-8") as log_f:
            log_f.write(f"Starting backport for {mainline_commit}\n")
            log_f.write(f"Mainline repo: {mainline_repo_path}\n")
            log_f.write(f"Target repo: {target_repo_path}\n")
            log_f.write("-" * 40 + "\n")

        total_tokens = {"input": 0, "output": 0}

        try:
            async for output in app.astream(inputs):
                for key, value in output.items():
                    print(f"Output from {key}:")
                    with open(log_file_path, "a", encoding="utf-8") as log_f:
                        log_f.write(f"Output from {key}:\n")

                    # Pretty print messages
                    if "messages" in value:
                        for msg in value["messages"]:
                            content = msg.content
                            print(f"  {content}")
                            with open(log_file_path, "a", encoding="utf-8") as log_f:
                                log_f.write(f"  {content}\n")

                            # Simple token estimation if metadata not available
                            # Or check if metadata exists (langchain specific)
                            if hasattr(msg, "response_metadata"):
                                usage = msg.response_metadata.get("token_usage", {})
                                if usage:
                                    total_tokens["input"] += usage.get(
                                        "prompt_tokens", 0
                                    )
                                    total_tokens["output"] += usage.get(
                                        "completion_tokens", 0
                                    )

                    print("----")
                    with open(log_file_path, "a", encoding="utf-8") as log_f:
                        log_f.write("----\n")
        except Exception as e:
            print(f"Interrupted: {e}")
            with open(log_file_path, "a", encoding="utf-8") as log_f:
                log_f.write(f"INTERRUPTED: {e}\n")
        finally:
            # Write final token counts
            with open(tokens_file_path, "w", encoding="utf-8") as token_f:
                token_f.write(f"Input tokens: {total_tokens['input']}\n")
                token_f.write(f"Output tokens: {total_tokens['output']}\n")
                token_f.write(
                    f"Total tokens: {total_tokens['input'] + total_tokens['output']}\n"
                )
            print(f"Logs saved to {log_file_path}")
            print(f"Token counts saved to {tokens_file_path}")

    except Exception as e:
        print(f"Error running Orchestrator: {e}")


if __name__ == "__main__":
    asyncio.run(main())
