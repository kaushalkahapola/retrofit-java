from typing import List, Dict, Optional, Any
from utils.mcp_client import get_client
import tempfile
import os
import subprocess
import json


class ValidationToolkit:
    def test_and_restore(self, test_classes: List[str]) -> Dict:
        """
        Runs targeted tests and restores repo state if tests fail or compile error.
        Returns test result dict.
        """
        result = self.run_targeted_tests(test_classes)
        if not result.get("success") or result.get("compile_error"):
            self.restore_repo_state()
            return result
    def __init__(self, target_repo_path: str):
        self.target_repo_path = target_repo_path
        self.client = get_client()

    # ------------------------------------------------------------------
    # Existing Methods
    # ------------------------------------------------------------------

    def compile_files(self, file_paths: List[str]) -> Dict:
        """
        Compiles the specified files using the Analysis Engine's compile tool.
        If it fails, falls back to module-level Maven/Gradle compilation.
        """
        res = self.client.call_tool("compile", {
            "target_repo_path": self.target_repo_path,
            "file_paths": file_paths
        })
        
        # Check if successful (handle both success and status=success)
        is_success = res.get("success") or res.get("status") == "success"
        if is_success:
            return {"success": True, "output": res.get("output", "Targeted compilation successful.")}
        
        # If targeted compile fails, try module-level compile
        print(f"    Agent 4: Targeted compile failed, falling back to module-level build...")
        
        # Deduce module by finding closest build file for each file
        modules = set()
        is_gradle = os.path.exists(os.path.join(self.target_repo_path, "build.gradle"))
        
        for fp in file_paths:
            # Find the directory containing the closest build file
            current_dir = os.path.dirname(fp)
            build_file = "build.gradle" if is_gradle else "pom.xml"
            
            found_module = None
            while current_dir and current_dir != "":
                if os.path.exists(os.path.join(self.target_repo_path, current_dir, build_file)):
                    found_module = current_dir
                    break
                parent = os.path.dirname(current_dir)
                if parent == current_dir: # Root
                    break
                current_dir = parent
            
            if found_module:
                modules.add(found_module)
        
        java_compat_args = ["-Djdk.security.manager.allow.argLine="]
        
        if not modules:
            # Fallback to root build
            return self.run_build_script()
            
        is_gradle = os.path.exists(os.path.join(self.target_repo_path, "build.gradle"))
        java_compat_args = ["-Djdk.security.manager.allow.argLine="]
        
        if is_gradle:
            # Gradle: pass all tasks together
            gradle_tasks = []
            for mod in modules:
                gradle_mod = ":" + mod.replace(os.sep, ":")
                gradle_tasks.append(f"{gradle_mod}:classes")
            cmd = ["gradle"] + gradle_tasks
        else:
            # Maven: pass all modules with -pl
            mod_list = ",".join(modules)
            # Use test-compile to ensure both main and test sources are compiled
            # Skip FMPP and other slow plugins that aren't needed for basic compilation check
            # Force Java 21 compatibility so SpotBugs can read the classes (Java 25 is currently unsupported)
            # Skip forbiddenapis, checkstyle, and pmd to avoid version-specific check failures
            cmd = ["mvn", "test-compile", "-pl", mod_list, "-am", "-DskipTests", "-Dfmpp.skip=true", 
                   "-Dmaven.compiler.release=21", "-Dforbiddenapis.skip=true", "-Dcheckstyle.skip=true", "-Dpmd.skip=true"] + java_compat_args
            
        print(f"    Agent 4: Executing fallback build: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.target_repo_path,
            )
            if result.returncode == 0:
                return {"success": True, "output": "Module-level compilation successful.", "modules": list(modules)}
            else:
                return {
                    "success": False, 
                    "output": result.stderr or result.stdout
                }
        except Exception as e:
            return {"success": False, "output": str(e)}

    def get_module_class_paths(self, modules: List[str]) -> List[str]:
        """
        Returns a list of class paths for the given modules.
        """
        class_paths = []
        for mod in modules:
            # Check Maven
            cp = os.path.join(self.target_repo_path, mod, "target", "classes")
            if os.path.exists(cp):
                class_paths.append(cp)
            # Check Gradle
            cp = os.path.join(self.target_repo_path, mod, "build", "classes", "java", "main")
            if os.path.exists(cp):
                class_paths.append(cp)
        
        # Also check root just in case
        root_maven = os.path.join(self.target_repo_path, "target", "classes")
        if os.path.exists(root_maven) and root_maven not in class_paths:
            class_paths.append(root_maven)
        root_gradle = os.path.join(self.target_repo_path, "build", "classes", "java", "main")
        if os.path.exists(root_gradle) and root_gradle not in class_paths:
            class_paths.append(root_gradle)
            
        return class_paths

    def run_spotbugs(self, compiled_classes_paths: List[str], source_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Runs SpotBugs using the Analysis Engine.
        """
        args = {
            "compiled_classes_paths": compiled_classes_paths
        }
        if source_path:
            args["source_path"] = source_path
            
        return self.client.call_tool("spotbugs", args)

    def write_trace(self, trace_content: str, filename: str = "validation_trace.md"):
        """
        Writes the validation trace to a file.
        """
        with open(filename, "w", encoding="utf-8") as f:
            f.write(trace_content)
        print(f"Trace saved to {filename}")

    # ------------------------------------------------------------------
    # Phase 3 New Methods: Hunk Application
    # ------------------------------------------------------------------

    def apply_hunk_dry_run(self, target_file_path: str, hunk_text: str) -> Dict:
        """
        Validates that a generated unified-diff hunk can apply cleanly to the
        target file without actually modifying it.

        Writes the hunk_text to a temporary .patch file, runs
        `git apply --check <patch>` in the target repo, then cleans up.

        Args:
            target_file_path: Relative path of the target file within the repo
                              (used to prefix the hunk header if needed).
            hunk_text:        A unified diff hunk string  — MUST start with @@.

        Returns:
            {"success": bool, "output": str}
        """
        # Build a minimal patch file that git can understand
        patch_content = self._build_patch_file(target_file_path, hunk_text)

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".patch",
                delete=False,
                encoding="utf-8",
            ) as tmp:
                tmp.write(patch_content)
                tmp_path = tmp.name

            result = subprocess.run(
                ["git", "apply", "--check", tmp_path],
                capture_output=True,
                text=True,
                cwd=self.target_repo_path,
            )
            if result.returncode == 0:
                return {"success": True, "output": result.stdout or "Clean apply."}
            else:
                return {"success": False, "output": result.stderr or result.stdout}

        except Exception as e:
            return {"success": False, "output": f"Exception during dry-run: {e}"}
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def apply_adapted_hunks(self, code_hunks: list, test_hunks: list) -> Dict:
        """
        Applies the full set of adapted code and test hunks to the target repo
        by writing them into a combined patch file and running `git apply`.

        Args:
            code_hunks: List of AdaptedHunk dicts for code changes.
            test_hunks: List of AdaptedHunk dicts for test changes.

        Returns:
            {"success": bool, "output": str, "applied_files": list[str]}
        """
        all_hunks = list(code_hunks) + list(test_hunks)
        if not all_hunks:
            return {"success": False, "output": "No hunks to apply.", "applied_files": []}

        # Build one combined patch file, one section per target file
        patch_parts = []
        applied_files = []
        for h in all_hunks:
            target_file = h.get("target_file", "unknown")
            hunk_text = h.get("hunk_text", "")
            if not hunk_text or not target_file:
                continue
            patch_parts.append(self._build_patch_file(target_file, hunk_text))
            if target_file not in applied_files:
                applied_files.append(target_file)

        combined = "\n".join(patch_parts)

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".patch",
                delete=False,
                encoding="utf-8",
            ) as tmp:
                tmp.write(combined)
                tmp_path = tmp.name

            result = subprocess.run(
                ["git", "apply", tmp_path],
                capture_output=True,
                text=True,
                cwd=self.target_repo_path,
            )
            if result.returncode == 0:
                return {
                    "success": True,
                    "output": result.stdout or "Applied successfully.",
                    "applied_files": applied_files,
                }
            else:
                return {
                    "success": False,
                    "output": result.stderr or result.stdout,
                    "applied_files": [],
                }
        except Exception as e:
            return {"success": False, "output": f"Exception during apply: {e}", "applied_files": []}
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # ------------------------------------------------------------------
    # Phase 4 New Methods: Testing and Repo Management
    # ------------------------------------------------------------------

    def run_build_script(self) -> Dict:
        """
        Runs the build script for the target repo.
        Detects if it's Maven (pom.xml) or Gradle (build.gradle).
        """
        is_gradle = os.path.exists(os.path.join(self.target_repo_path, "build.gradle"))
        # Fix for Java 18+ / Java 25 security manager issues
        java_compat_args = ["-Djdk.security.manager.allow.argLine="]
        
        cmd = ["gradle", "build", "-x", "test"] if is_gradle else ["mvn", "clean", "compile"] + java_compat_args
        
        try:
            print(f"    Agent 4: Executing build command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=False, # Stream to stdout/stderr
                text=True,
                cwd=self.target_repo_path,
            )
            return {
                "success": result.returncode == 0,
                "output": "Build log streamed to console."
            }
        except Exception as e:
            return {"success": False, "output": f"Exception building repo: {e}"}

    def run_targeted_tests(self, test_classes: List[str]) -> Dict:
        """
        Runs specific unit tests in the target repository.
        Detects Maven vs Gradle automatically.

        Args:
            test_classes: List of test class names to run.

        Returns:
            {"success": bool, "compile_error": bool, "output": str, "failed_tests": list[str]}
        """
        if not test_classes:
            return {"success": True, "compile_error": False, "output": "No tests to run.", "failed_tests": []}

        is_gradle = os.path.exists(os.path.join(self.target_repo_path, "build.gradle"))
        
        # Fix for Java 18+ / Java 25 security manager issues
        java_compat_args = ["-Djdk.security.manager.allow.argLine="]

        if is_gradle:
            cmd = ["gradle", "test"]
            for cls in test_classes:
                cmd.extend(["--tests", cls])
        else:
            test_args = ",".join(test_classes)
            cmd = ["mvn", "test", f"-Dtest={test_args}"] + java_compat_args

        try:
            print(f"    Agent 4: Executing test command: {' '.join(cmd)}")
            # Use Popen to stream output if possible, or just run and let it print
            result = subprocess.run(
                cmd,
                capture_output=False, # Let it print to console
                text=True,
                cwd=self.target_repo_path,
            )
            success = result.returncode == 0
            
            # Since we didn't capture, we can't easily check for "COMPILATION ERROR" in output here
            # but usually the return code is enough for Maven/Gradle.
            # If we need to parse it, we'd need to capture AND print.
            
            return {
                "success": success,
                "compile_error": not success and result.returncode != 0, # Rough heuristic
                "output": "Test log streamed to console.",
                "failed_tests": []
            }
        except Exception as e:
            return {
                "success": False,
                "compile_error": False,
                "output": f"Exception running tests: {e}",
                "failed_tests": []
            }

    def restore_repo_state(self) -> bool:
        """
        Restores the target repository to a clean state, reverting any uncommitted patches.
        """
        try:
            subprocess.run(["git", "reset", "--hard"], cwd=self.target_repo_path, capture_output=True, check=True)
            subprocess.run(["git", "clean", "-fd"], cwd=self.target_repo_path, capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"ValidationToolkit: Error restoring repo state: {e}")
            return False

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _build_patch_file(self, target_file_path: str, hunk_text: str) -> str:
        """
        Wraps a hunk in a minimal unified diff file header so `git apply`
        can understand it. The hunk_text must already start with @@ ... @@.
        """
        # Normalize path separators
        p = target_file_path.replace("\\", "/").lstrip("/")
        full_path = os.path.join(self.target_repo_path, p)
        
        is_new = not os.path.exists(full_path)
        
        if is_new:
            header = (
                f"diff --git a/{p} b/{p}\n"
                f"new file mode 100644\n"
                f"--- /dev/null\n"
                f"+++ b/{p}\n"
            )
        else:
            header = (
                f"diff --git a/{p} b/{p}\n"
                f"--- a/{p}\n"
                f"+++ b/{p}\n"
            )
        # Ensure hunk_text ends with newline
        body = hunk_text if hunk_text.endswith("\n") else hunk_text + "\n"
        return header + body
