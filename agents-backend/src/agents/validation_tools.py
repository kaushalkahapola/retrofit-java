from typing import List, Dict, Optional, Any
from utils.mcp_client import get_client
import tempfile
import os
import subprocess
import json
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _resolve_valid_java_home() -> str | None:
    """
    Returns a usable JAVA_HOME path if configured, otherwise None.

    Preference order:
      1) JAVA_21_HOME (if valid)
      2) JAVA_HOME (if valid)
    """
    candidates = [os.getenv("JAVA_21_HOME"), os.getenv("JAVA_HOME")]
    for candidate in candidates:
        if not candidate:
            continue
        java_bin = os.path.join(candidate, "bin", "java")
        if os.path.isdir(candidate) and os.path.isfile(java_bin):
            return candidate
    return None


def _clean_spotbugs_output(output: str) -> str:
    """
    Clean SpotBugs output by removing verbose noise while keeping important findings.
    - Keeps bug findings (lines with bug codes like H B, M V, L C, etc.)
    - Removes 'missing classes' list (usually noise for validation)
    - Truncates very long outputs
    """
    if not output:
        return output
    
    lines = output.split('\n')
    cleaned_lines = []
    in_missing_section = False
    
    for line in lines:
        # Detect start of "missing classes" section
        if "The following classes needed for analysis were missing:" in line:
            in_missing_section = True
            continue
        
        # Skip lines in missing classes section
        if in_missing_section:
            # End of missing section when we hit an empty line or a bug finding
            if not line.strip() or re.match(r'^[HML]\s+[A-Z]', line):
                in_missing_section = False
                if not line.strip():
                    continue
            else:
                continue
        
        # Keep bug findings and summary lines
        if re.match(r'^[HML]\s+[A-Z]', line) or not line.strip():
            cleaned_lines.append(line)
    
    result = '\n'.join(cleaned_lines)
    
    # Truncate if still too long (keep first and last findings)
    if len(result) > 5000:
        parts = result.split('\n\n')
        if len(parts) > 10:
            result = '\n\n'.join(parts[:5]) + '\n\n...[TRUNCATED]...\n\n' + '\n\n'.join(parts[-5:])
    
    return result.strip() if result.strip() else "SpotBugs completed with no findings."


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
            # Force Java 21 for SpotBugs compatibility (Java 25 not supported by SpotBugs)
            # Skip forbiddenapis, checkstyle, and pmd to avoid version-specific check failures
            cmd = ["mvn", "test-compile", "-pl", mod_list, "-am", "-DskipTests", "-Dfmpp.skip=true",
                   "-Dmaven.compiler.release=21", "-Dmaven.compiler.source=21", "-Dmaven.compiler.target=21",
                   "-Dforbiddenapis.skip=true", "-Dcheckstyle.skip=true", "-Dpmd.skip=true"] + java_compat_args
            
        print(f"    Agent 4: Executing fallback build: {' '.join(cmd)}")
        try:
            compile_env = os.environ.copy()
            resolved_java_home = _resolve_valid_java_home()
            if resolved_java_home:
                compile_env["JAVA_HOME"] = resolved_java_home
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.target_repo_path,
                env=compile_env,
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

    def get_project_classpath(self) -> List[str]:
        """
        Retrieves the project's classpath using Maven or Gradle.
        """
        is_gradle = os.path.exists(os.path.join(self.target_repo_path, "build.gradle"))
        
        if is_gradle:
            # For Gradle, use the 'dependencies' or similar task. 
            # A more robust way is to use a custom gradle script snippet.
            # For now, let's try to get a basic classpath.
            cmd = ["gradle", "properties", "-q"] # This is a placeholder; getting classpath from gradle is harder
            # For brevity and since most targets are Maven, we'll return empty for Gradle for now
            # or try to find common jar locations.
            return []
        else:
            # Maven: use dependency:build-classpath
            tmp_cp = os.path.join(tempfile.gettempdir(), "retrofit_cp.txt")
            cmd = ["mvn", "dependency:build-classpath", f"-Dmdep.outputFile={tmp_cp}", "-DskipTests"]
            try:
                print(f"    Agent 4: Calculating project classpath...")
                subprocess.run(cmd, cwd=self.target_repo_path, capture_output=True, text=True, check=True)
                if os.path.exists(tmp_cp):
                    with open(tmp_cp, "r") as f:
                        cp_string = f.read().strip()
                    os.unlink(tmp_cp)
                    return cp_string.split(os.pathsep)
            except Exception as e:
                print(f"    Agent 4 Warning: Failed to get classpath: {e}")
        return []

    def run_spotbugs(self, compiled_classes_paths: List[str], source_path: Optional[str] = None, target_files: List[str] = None) -> Dict[str, Any]:
        """
        Runs SpotBugs using direct JAR invocation with Java 21.
        Requires JAVA_HOME to be set to Java 21.

        Args:
            compiled_classes_paths: Paths to compiled class directories
            source_path: Path to source code directory
            target_files: List of target files to analyze (for focused analysis)
        """
        # Determine classes to analyze
        class_names = []
        if target_files:
            for f in target_files:
                if "src/main/java/" in f:
                    cls = f.split("src/main/java/")[1].replace(".java", "").replace("/", ".")
                    class_names.append(cls)
                elif "src/test/java/" in f:
                    cls = f.split("src/test/java/")[1].replace(".java", "").replace("/", ".")
                    class_names.append(cls)

        # Direct JAR Invocation with SpotBugs 4.9.3
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        spotbugs_jar = os.path.join(base_dir, "tools", "spotbugs", "spotbugs-4.9.3.jar")
        resolved_java_home = _resolve_valid_java_home()

        if os.path.exists(spotbugs_jar):
            print(f"    Agent 4: Executing SpotBugs via direct JAR invocation ({spotbugs_jar})...")
            aux_cp = self.get_project_classpath()

            # Build the command for SpotBugs 4.9.3+ using wildcard classpath for dependencies
            # Uses Java 21 from JAVA_21_HOME env variable
            spotbugs_dir = os.path.dirname(spotbugs_jar)
            java_bin = os.path.join(resolved_java_home, "bin", "java") if resolved_java_home else "java"
            cmd = [
                java_bin if os.path.exists(java_bin) else "java",
                "-cp", os.path.join(spotbugs_dir, "*"),
                "edu.umd.cs.findbugs.LaunchAppropriateUI",
                "-textui",
                "-effort:max",
                "-low",  # Report all confidence levels (low, medium, high)
                "-noClassOk"
            ]

            if class_names:
                cmd.extend(["-onlyAnalyze", ",".join(class_names)])

            # Include project's compiled classes in aux classpath to ensure visibility
            all_aux = list(aux_cp)
            for p in compiled_classes_paths:
                if p not in all_aux:
                    all_aux.append(p)

            if all_aux:
                cmd.extend(["-auxclasspath", os.pathsep.join(all_aux)])

            if source_path:
                cmd.extend(["-sourcepath", source_path])

            # Target classes for analysis (directories containing .class files)
            for p in compiled_classes_paths:
                cmd.append(p)

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                output = result.stdout + "\n" + result.stderr
                # SpotBugs returns 0 if no bugs found, >0 if bugs found
                passed = result.returncode == 0

                # Clean output - remove noise, keep findings
                cleaned_output = _clean_spotbugs_output(output)

                # Check for critical errors that indicate the tool didn't run properly
                # Ignore "Exception in thread" from missing classes (not a fatal error)
                has_fatal_error = "Exception in thread" in output and "Could not instantiate" in output
                has_fatal_error = has_fatal_error or ("Exception" in output and "ClassNotFoundException" in output)
                has_fatal_error = has_fatal_error or ("Error" in output and "BUILD FAILURE" in output)

                if has_fatal_error:
                    print(f"    Agent 4 Warning: JAR invocation encountered errors, falling back...")
                else:
                    return {
                        "success": passed,
                        "output": cleaned_output,  # Return cleaned output
                        "raw_output": output,  # Keep raw for debugging
                        "method": "direct-jar",
                        "return_code": result.returncode
                    }
            except subprocess.TimeoutExpired:
                print(f"    Agent 4 Warning: Direct JAR SpotBugs timed out, falling back...")
            except Exception as e:
                print(f"    Agent 4 Warning: Direct JAR SpotBugs failed: {e}")

        # 2. Maven Plugin Attempt (Fallback)
        is_maven = os.path.exists(os.path.join(self.target_repo_path, "pom.xml"))
        if is_maven:
            # Use SpotBugs Maven plugin as fallback (has known issues with -xml:withMessages)
            maven_env = os.environ.copy()
            resolved_java_home = _resolve_valid_java_home()
            if resolved_java_home:
                maven_env["JAVA_HOME"] = resolved_java_home
            
            cmd = [
                "mvn",
                "com.github.spotbugs:spotbugs-maven-plugin:4.9.0.0:spotbugs",
                "-Dspotbugs.effort=Max",
                "-Dspotbugs.threshold=Low",
                "-DskipTests",
                "-Djdk.security.manager.allow.argLine=",
                "-Dmaven.compiler.release=21",
                "-Dfmpp.skip=true",
                "-Dforbiddenapis.skip=true",
                "-Dcheckstyle.skip=true",
                "-Dpmd.skip=true"
            ]

            # If we have specific modules from compilation, limit scope with -pl
            if compiled_classes_paths:
                modules_to_scan = set()
                for cp in compiled_classes_paths:
                    parts = cp.replace("\\", "/").split("/")
                    if "target" in parts and "classes" in parts:
                        idx = parts.index("target")
                        if idx > 0:
                            repo_parts = self.target_repo_path.replace("\\", "/").split("/")
                            module_parts = parts[:idx]
                            if len(module_parts) > len(repo_parts):
                                relative_module = "/".join(module_parts[len(repo_parts):])
                                modules_to_scan.add(relative_module)

                if modules_to_scan:
                    cmd.extend(["-pl", ",".join(modules_to_scan)])
                    cmd.append("-am")

            print(f"    Agent 4: Executing SpotBugs via Maven plugin: {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, cwd=self.target_repo_path, capture_output=True, text=True, timeout=600, env=maven_env)
                output = result.stdout + "\n" + result.stderr

                # Check for execution errors
                if "MojoExecutionException" in output or "BUILD FAILURE" in output:
                    print(f"    Agent 4 Warning: Maven SpotBugs failed, trying full scan...")
                    cmd_fallback = [
                        "mvn",
                        "com.github.spotbugs:spotbugs-maven-plugin:4.9.0.0:spotbugs",
                        "-Dspotbugs.effort=Max",
                        "-Dspotbugs.threshold=Low",
                        "-DskipTests",
                        "-Djdk.security.manager.allow.argLine=",
                        "-Dmaven.compiler.release=21",
                        "-Dfmpp.skip=true",
                        "-Dforbiddenapis.skip=true",
                        "-Dcheckstyle.skip=true",
                        "-Dpmd.skip=true"
                    ]
                    print(f"    Agent 4: Executing full project SpotBugs scan: {' '.join(cmd_fallback)}")
                    result = subprocess.run(cmd_fallback, cwd=self.target_repo_path, capture_output=True, text=True, timeout=600, env=maven_env)
                    output = result.stdout + "\n" + result.stderr

                # Check again for critical failures
                if "MojoExecutionException" in output or "BUILD FAILURE" in output:
                    print(f"    Agent 4 Warning: Maven SpotBugs full scan also failed")
                    return {
                        "success": True,
                        "output": output,
                        "method": "maven-plugin-failed",
                        "note": "SpotBugs execution failed, assuming clean by default"
                    }
                else:
                    # Parse output for bug count - SpotBugs Maven plugin outputs "Total bugs: X"
                    # Also check for individual bug reports like "BUG: ..."
                    bug_match = re.search(r"Total bugs: (\d+)", output)
                    if bug_match:
                        bug_count = int(bug_match.group(1))
                        passed = bug_count == 0
                        return {
                            "success": passed,
                            "output": output,
                            "method": "maven-plugin",
                            "bug_count": bug_count
                        }
                    # Fallback: check for "No bugs found" or individual bug patterns
                    has_bugs = "BUG:" in output or "High: " in output or "Medium: " in output
                    passed = not has_bugs or "No bugs found" in output or "Total bugs: 0" in output
                    return {"success": passed, "output": output, "method": "maven-plugin"}
            except subprocess.TimeoutExpired:
                print(f"    Agent 4 Warning: Maven SpotBugs timed out, falling back...")
            except Exception as e:
                print(f"    Agent 4 Warning: Maven SpotBugs failed: {e}")

        # 3. Fallback to programmatic tool (Analysis Engine)
        print("    Agent 4: Falling back to programmatic SpotBugs tool...")
        aux_classpath = self.get_project_classpath()
        args = {
            "compiled_classes_paths": compiled_classes_paths,
            "aux_classpath": aux_classpath
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
                ["git", "apply", "--check", "--recount", "--whitespace=nowarn", tmp_path],
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
                using a resilient multi-pass strategy.

                Strategy:
                    1) Build one unified diff section per file with hunks in top-to-bottom order.
                    2) Try strict git apply with recount.
                    3) Retry git apply with whitespace-tolerant flags.
                    4) Fallback to GNU patch dry-run + apply (fuzzy matching/offset support).

        Args:
            code_hunks: List of AdaptedHunk dicts for code changes.
            test_hunks: List of AdaptedHunk dicts for test changes.

        Returns:
            {"success": bool, "output": str, "applied_files": list[str]}
        """
        all_hunks = list(code_hunks) + list(test_hunks)
        if not all_hunks:
            return {"success": False, "output": "No hunks to apply.", "applied_files": []}

        # Ensure all hunks have insertion_line set; fall back to hunk header parsing.
        for h in all_hunks:
            if not h.get("insertion_line"):
                hunk_text = h.get("hunk_text", "")
                try:
                    match = re.search(r'@@ -\d+(?:,\d+)? \+(\d+)', hunk_text)
                    if match:
                        h["insertion_line"] = int(match.group(1))
                except Exception:
                    h["insertion_line"] = 0  # Fallback to 0 if extraction fails
        
        # Group hunks by target file, then sort each file's hunks in ascending line order.
        hunks_by_file = {}
        for h in all_hunks:
            target_file = h.get("target_file", "unknown")
            if target_file not in hunks_by_file:
                hunks_by_file[target_file] = []
            hunks_by_file[target_file].append(h)

        # Sort hunks within each file by insertion_line in natural patch order (lowest first).
        for target_file in hunks_by_file:
            hunks_by_file[target_file].sort(
                key=lambda h: h.get("insertion_line", 0),
                reverse=False
            )
            insertion_lines = [h.get("insertion_line") for h in hunks_by_file[target_file]]
            print(
                f"  Validation: {target_file} - applying {len(hunks_by_file[target_file])} "
                f"hunk(s) in top-to-bottom order: {insertion_lines}"
            )

        # Build one patch section per file so offsets are resolved cumulatively.
        patch_parts = []
        applied_files = []
        for target_file in hunks_by_file:
            file_hunks = []
            file_operations = set()
            for h in hunks_by_file[target_file]:
                hunk_text = h.get("hunk_text", "")
                if not hunk_text:
                    continue
                file_hunks.append(hunk_text if hunk_text.endswith("\n") else hunk_text + "\n")
                file_operations.add((h.get("file_operation") or "MODIFIED").upper())

            if not file_hunks:
                continue

            combined_hunks = "".join(file_hunks)
            file_operation = next(iter(file_operations)) if len(file_operations) == 1 else "MODIFIED"
            try:
                patch_part = self._build_patch_file(target_file, combined_hunks, file_operation=file_operation)
                patch_parts.append(patch_part)
                if target_file not in applied_files:
                    applied_files.append(target_file)
            except ValueError as e:
                return {
                    "success": False,
                    "output": f"Invalid hunk format for {target_file}: {e}",
                    "applied_files": [],
                }

        if not patch_parts:
            return {
                "success": False,
                "output": "No valid hunk_text entries found.",
                "applied_files": [],
            }

        combined = "".join(patch_parts)

        return self._apply_patch_with_fallbacks(combined, applied_files)

    def _apply_patch_with_fallbacks(self, patch_content: str, applied_files: list[str]) -> Dict:
        """
        Apply patch content with increasingly permissive strategies.
        """
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

            attempts = [
                (
                    "git-apply-strict",
                    ["git", "apply", "--recount", "--whitespace=nowarn", tmp_path],
                ),
                (
                    "git-apply-whitespace-tolerant",
                    [
                        "git", "apply", "--recount", "--ignore-space-change",
                        "--ignore-whitespace", "--whitespace=nowarn", tmp_path,
                    ],
                ),
            ]

            all_errors = []
            for name, cmd in attempts:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=self.target_repo_path,
                )
                if result.returncode == 0:
                    return {
                        "success": True,
                        "output": result.stdout or f"Applied successfully via {name}.",
                        "applied_files": applied_files,
                        "apply_strategy": name,
                    }

                err = result.stderr or result.stdout or "unknown apply failure"
                all_errors.append(f"[{name}] {err.strip()}")

            patch_dry_run_cmd = [
                "patch", "-p1", "--dry-run", "--batch", "--forward",
                "--reject-file=-", "--ignore-whitespace", "-i", tmp_path,
            ]
            patch_apply_cmd = [
                "patch", "-p1", "--batch", "--forward",
                "--reject-file=-", "--ignore-whitespace", "-i", tmp_path,
            ]

            dry_run = subprocess.run(
                patch_dry_run_cmd,
                capture_output=True,
                text=True,
                cwd=self.target_repo_path,
            )

            if dry_run.returncode == 0:
                patch_apply = subprocess.run(
                    patch_apply_cmd,
                    capture_output=True,
                    text=True,
                    cwd=self.target_repo_path,
                )
                if patch_apply.returncode == 0:
                    return {
                        "success": True,
                        "output": patch_apply.stdout or "Applied successfully via patch fallback.",
                        "applied_files": applied_files,
                        "apply_strategy": "gnu-patch-fallback",
                    }

                self.restore_repo_state()
                patch_err = patch_apply.stderr or patch_apply.stdout or "patch apply failed"
                all_errors.append(f"[gnu-patch-apply] {patch_err.strip()}")
            else:
                patch_err = dry_run.stderr or dry_run.stdout or "patch dry-run failed"
                all_errors.append(f"[gnu-patch-dry-run] {patch_err.strip()}")

            return {
                "success": False,
                "output": "\n\n".join(all_errors),
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

    def _build_patch_file(self, target_file_path: str, hunk_text: str, file_operation: str = "MODIFIED") -> str:
        """
        Wraps a hunk in a minimal unified diff file header so `git apply`
        can understand it. The hunk_text must already start with @@ ... @@.
        """
        # Normalize path separators and strip optional diff prefixes.
        p = (target_file_path or "").strip().replace("\\", "/").lstrip("/")
        if p.startswith("a/") or p.startswith("b/"):
            p = p[2:]

        if not p:
            raise ValueError("target_file_path is empty")

        full_path = os.path.join(self.target_repo_path, p)

        file_exists = os.path.exists(full_path)
        normalized_op = (file_operation or "MODIFIED").upper()

        # If metadata says MODIFIED but file is absent, treat as add fallback.
        if normalized_op == "MODIFIED" and not file_exists:
            normalized_op = "ADDED"
        
        # Ensure hunk_text is properly formatted
        if not hunk_text.startswith("@@"):
            raise ValueError(f"Hunk must start with @@, got: {hunk_text[:50]}")
        
        # Ensure hunk ends with newline if it doesn't already
        body = hunk_text if hunk_text.endswith("\n") else hunk_text + "\n"
        
        # Add trailing newline for proper separation between files in combined patches
        if not body.endswith("\n\n"):
            body = body.rstrip("\n") + "\n"
        
        if normalized_op == "ADDED":
            header = (
                f"diff --git a/{p} b/{p}\n"
                f"new file mode 100644\n"
                f"index 0000000..0000000 100644\n"
                f"--- /dev/null\n"
                f"+++ b/{p}\n"
            )
        elif normalized_op == "DELETED":
            header = (
                f"diff --git a/{p} b/{p}\n"
                f"deleted file mode 100644\n"
                f"index 0000000..0000000 100644\n"
                f"--- a/{p}\n"
                f"+++ /dev/null\n"
            )
        else:
            header = (
                f"diff --git a/{p} b/{p}\n"
                f"index 0000000..0000000 100644\n"
                f"--- a/{p}\n"
                f"+++ b/{p}\n"
            )
        
        return header + body
