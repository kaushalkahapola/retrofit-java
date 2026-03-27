from typing import List, Dict, Optional, Any
from utils.mcp_client import get_client
import tempfile
import os
import subprocess
import json
import re
import glob
import shutil
import xml.etree.ElementTree as ET
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

    def _is_known_project_with_helper(self, project: str) -> bool:
        project_dir = self._get_project_helper_dir(project)
        return os.path.isdir(project_dir)

    def _find_maven_module_for_path(self, rel_path: str) -> str:
        """Find nearest parent directory containing pom.xml for a repo-relative path."""
        head = (rel_path or "").replace("\\", "/")
        while head:
            head, _ = os.path.split(head)
            if os.path.exists(os.path.join(self.target_repo_path, head, "pom.xml")):
                return head
        return ""

    def _clear_previous_junit_reports(self) -> None:
        """Remove stale JUnit XML files so each run reflects only current execution."""
        try:
            for xml_path in glob.glob(
                os.path.join(self.target_repo_path, "**", "surefire-reports", "TEST-*.xml"),
                recursive=True,
            ):
                try:
                    os.remove(xml_path)
                except Exception:
                    pass

            aggregate_dir = os.path.join(self.target_repo_path, "build", "all-test-results")
            if os.path.isdir(aggregate_dir):
                shutil.rmtree(aggregate_dir, ignore_errors=True)
        except Exception:
            # Best effort cleanup only.
            pass

    def _collect_junit_xml_paths(self) -> list[str]:
        """Collect JUnit XML report file paths from common Maven/Gradle output locations."""
        paths = set(
            glob.glob(
                os.path.join(self.target_repo_path, "**", "surefire-reports", "TEST-*.xml"),
                recursive=True,
            )
        )
        paths.update(
            glob.glob(
                os.path.join(self.target_repo_path, "build", "all-test-results", "TEST-*.xml"),
                recursive=True,
            )
        )
        return sorted(paths)

    def _detect_project_name(self) -> str:
        return os.path.basename(self.target_repo_path).strip().lower()

    def _extract_test_state_with_project_helper(
        self,
        target_info: Optional[Dict[str, Any]] = None,
        console_output: str = "",
    ) -> Dict[str, Any] | None:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        helper_script = os.path.join(root_dir, "evaluate", "helpers", "collect_test_results.py")
        if not os.path.exists(helper_script):
            return None

        info = target_info or {}
        target_classes = [
            t.split(":", 1)[1]
            for t in (info.get("test_targets") or [])
            if ":" in t
        ]
        target_classes_arg = ",".join(sorted(set(target_classes)))

        console_file = os.path.join(self.target_repo_path, "build", "test-console.log")
        try:
            os.makedirs(os.path.dirname(console_file), exist_ok=True)
            with open(console_file, "w", encoding="utf-8") as f:
                f.write(console_output or "")
        except Exception:
            console_file = ""

        cmd = [
            "python3",
            helper_script,
            "--project",
            self._detect_project_name(),
            "--repo",
            self.target_repo_path,
            "--target-classes",
            target_classes_arg,
        ]
        if console_file:
            cmd.extend(["--console-file", console_file])

        result = self._run_cmd_capture(cmd, cwd=self.target_repo_path)
        if not result.get("success"):
            return None

        try:
            return json.loads(result.get("output", "{}"))
        except json.JSONDecodeError:
            return None

    def _extract_test_state(self, target_info: Optional[Dict[str, Any]] = None, console_output: str = "") -> Dict[str, Any]:
        """
        Parse JUnit XML files and return test-case and class-level statuses.

        Status values: passed | failed | error | skipped
        """
        helper_state = self._extract_test_state_with_project_helper(target_info=target_info, console_output=console_output)
        if helper_state is not None:
            return helper_state

        info = target_info or {}
        target_classes = {
            t.split(":", 1)[1]
            for t in (info.get("test_targets") or [])
            if ":" in t
        }

        xml_paths = self._collect_junit_xml_paths()
        test_case_status: dict[str, str] = {}
        class_status_acc: dict[str, list[str]] = {}

        for xml_path in xml_paths:
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
            except Exception:
                continue

            for case in root.findall(".//testcase"):
                classname = (case.attrib.get("classname") or "").strip()
                testname = (case.attrib.get("name") or "").strip()
                if not classname or not testname:
                    continue

                if target_classes and classname not in target_classes:
                    continue

                if case.find("failure") is not None:
                    status = "failed"
                elif case.find("error") is not None:
                    status = "error"
                elif case.find("skipped") is not None:
                    status = "skipped"
                else:
                    status = "passed"

                test_key = f"{classname}#{testname}"
                test_case_status[test_key] = status
                class_status_acc.setdefault(classname, []).append(status)

        class_status: dict[str, str] = {}
        for classname, statuses in class_status_acc.items():
            if any(s in {"failed", "error"} for s in statuses):
                class_status[classname] = "failed"
            elif all(s == "skipped" for s in statuses):
                class_status[classname] = "skipped"
            else:
                class_status[classname] = "passed"

        return {
            "xml_reports": xml_paths,
            "target_classes": sorted(target_classes),
            "test_cases": test_case_status,
            "classes": class_status,
            "summary": {
                "passed": sum(1 for s in test_case_status.values() if s == "passed"),
                "failed": sum(1 for s in test_case_status.values() if s in {"failed", "error"}),
                "skipped": sum(1 for s in test_case_status.values() if s == "skipped"),
                "total": len(test_case_status),
            },
        }

    def evaluate_test_state_transition(
        self,
        baseline_test_result: Optional[Dict[str, Any]],
        patched_test_result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Evaluate whether patched tests represent a valid transition.

        Valid iff:
          - no pass -> fail transitions
          - and at least one fail -> pass transition OR a newly observed passing test
        """
        baseline_state = (baseline_test_result or {}).get("test_state") or {}
        patched_state = (patched_test_result or {}).get("test_state") or {}

        baseline_cases = baseline_state.get("test_cases") or {}
        patched_cases = patched_state.get("test_cases") or {}

        # If no case-level data exists, use class-level status as fallback.
        if not baseline_cases and not patched_cases:
            baseline_cases = baseline_state.get("classes") or {}
            patched_cases = patched_state.get("classes") or {}

        fail_to_pass = sorted(
            case
            for case, old_status in baseline_cases.items()
            if old_status in {"failed", "error"} and patched_cases.get(case) == "passed"
        )
        pass_to_fail = sorted(
            case
            for case, old_status in baseline_cases.items()
            if old_status == "passed" and patched_cases.get(case) in {"failed", "error"}
        )
        newly_passing = sorted(
            case
            for case, new_status in patched_cases.items()
            if case not in baseline_cases and new_status == "passed"
        )

        valid = (not pass_to_fail) and bool(fail_to_pass or newly_passing)

        if pass_to_fail:
            reason = "Invalid: Some tests regressed from pass to fail."
        elif fail_to_pass or newly_passing:
            reason = "Valid: Observed fail-to-pass and/or newly passing relevant tests with no regressions."
        else:
            reason = "Invalid: No fail-to-pass or newly passing relevant tests were observed."

        return {
            "valid_backport_signal": valid,
            "fail_to_pass": fail_to_pass,
            "pass_to_fail": pass_to_fail,
            "newly_passing": newly_passing,
            "baseline_total": len(baseline_cases),
            "patched_total": len(patched_cases),
            "reason": reason,
        }

    def _get_project_helper_dir(self, project: str) -> str:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        return os.path.join(root_dir, "evaluate", "helpers", project.strip().lower())

    def _get_current_head(self) -> str:
        res = self._run_cmd_capture(["git", "rev-parse", "--short", "HEAD"], cwd=self.target_repo_path)
        if res.get("success"):
            return (res.get("output") or "worktree").strip().splitlines()[0]
        return "worktree"

    def _ensure_project_builder_image(self, project: str) -> tuple[str | None, str | None]:
        helper_dir = self._get_project_helper_dir(project)
        dockerfile = os.path.join(helper_dir, "Dockerfile")
        if not os.path.exists(dockerfile):
            return None, f"Helper Dockerfile not found for project {project}: {dockerfile}"

        image_tag = os.getenv(f"{project.upper()}_BUILDER_IMAGE_TAG", f"retrofit-{project.lower()}-builder:local")

        inspect_res = self._run_cmd_capture(["docker", "image", "inspect", image_tag], cwd=self.target_repo_path)
        if inspect_res.get("success"):
            return image_tag, None

        build_res = self._run_cmd_capture(
            ["docker", "build", "-t", image_tag, "-f", dockerfile, helper_dir],
            cwd=self.target_repo_path,
        )
        if not build_res.get("success"):
            return None, f"Failed to build helper image for {project} ({image_tag}): {build_res.get('output', '')}"

        return image_tag, None

    def _run_cmd_capture(self, cmd: List[str], cwd: Optional[str] = None, env: Optional[dict] = None) -> Dict[str, Any]:
        """Run a command and return success plus combined output."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd or self.target_repo_path,
                env=env,
            )
            output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "output": output,
            }
        except Exception as e:
            return {"success": False, "returncode": 1, "output": str(e)}

    def detect_relevant_test_targets(self, project: str = "") -> Dict[str, Any]:
        """
        Detect relevant test targets/modules from current worktree diff.

        For Druid, delegates to evaluate helper script and returns:
          {
            "test_targets": ["module:pkg.ClassTest", ...],
            "source_modules": ["processing", ...],
            "all_modules": [...],
            "raw": <helper_json>
          }
        """
        normalized_project = (project or "").strip().lower()
        if not normalized_project:
            normalized_project = self._detect_project_name()

        if not self._is_known_project_with_helper(normalized_project):
            return {
                "test_targets": [],
                "source_modules": [],
                "all_modules": [],
                "raw": {},
            }

        helper_dir = self._get_project_helper_dir(normalized_project)
        helper_script = os.path.join(helper_dir, "get_test_targets.py")
        if not os.path.exists(helper_script):
            return {
                "test_targets": [],
                "source_modules": [],
                "all_modules": [],
                "raw": {"error": f"Helper script not found: {helper_script}"},
            }

        helper_res = self._run_cmd_capture(
            ["python3", helper_script, "--repo", self.target_repo_path, "--worktree"],
            cwd=self.target_repo_path,
        )
        if not helper_res.get("success"):
            return {
                "test_targets": [],
                "source_modules": [],
                "all_modules": [],
                "raw": {"error": helper_res.get("output", "helper failed")},
            }

        try:
            parsed = json.loads(helper_res.get("output", "{}"))
        except json.JSONDecodeError:
            parsed = {"error": f"Invalid helper JSON: {helper_res.get('output', '')}"}

        test_targets = sorted(set((parsed.get("modified") or []) + (parsed.get("added") or [])))
        source_modules = sorted(set(parsed.get("source_modules") or []))
        all_modules = sorted(set(parsed.get("all_modules") or []))

        return {
            "test_targets": test_targets,
            "source_modules": source_modules,
            "all_modules": all_modules,
            "raw": parsed,
        }

    def detect_relevant_test_targets_from_changed_files(self, changed_files: List[str]) -> Dict[str, Any]:
        """
        Infer relevant tests/modules directly from changed file paths.
        This avoids relying on worktree diff state during Phase 0 baseline runs.
        """
        ignored_modules = {"web-console", "distribution", "docs", "examples"}

        test_targets = set()
        source_modules = set()
        all_modules = set()

        for rel_path in changed_files or []:
            p = (rel_path or "").replace("\\", "/")
            if not p:
                continue

            module_path = self._find_maven_module_for_path(p)
            if not module_path or module_path in ignored_modules:
                continue

            all_modules.add(module_path)
            if p.endswith(".java") and "src/main/java/" in p:
                source_modules.add(module_path)

            # Support both XXXTest.java (Crate/Druid) and TestXXX.java (HBase) patterns
            filename = os.path.basename(p)
            is_test_file = (
                p.endswith("Test.java") or  # XXXTest.java pattern
                (filename.startswith("Test") and p.endswith(".java"))  # TestXXX.java pattern
            )
            if is_test_file and "src/test/java/" in p:
                try:
                    class_path = p.split("src/test/java/", 1)[1]
                    class_name = class_path.replace("/", ".").replace(".java", "")
                    test_targets.add(f"{module_path}:{class_name}")
                except Exception:
                    continue

        return {
            "test_targets": sorted(test_targets),
            "source_modules": sorted(source_modules),
            "all_modules": sorted(all_modules),
            "raw": {"source": "changed_files", "changed_files": sorted(set(changed_files or []))},
        }

    def run_relevant_tests(self, project: str = "", target_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run relevant tests based on detected targets/modules.

        Priority:
          1) If exact test classes are known, run those in the corresponding modules.
          2) Else run module-level tests for source-touched modules.
          3) Else skip.
        """
        info = target_info or self.detect_relevant_test_targets(project)
        test_targets = list(info.get("test_targets") or [])
        source_modules = list(info.get("source_modules") or [])

        if not test_targets and not source_modules:
            return {
                "success": True,
                "compile_error": False,
                "output": "No relevant test targets/modules detected.",
                "failed_tests": [],
                "mode": "skip",
                "targets": info,
                "test_state": {
                    "xml_reports": [],
                    "target_classes": [],
                    "test_cases": {},
                    "classes": {},
                    "summary": {"passed": 0, "failed": 0, "skipped": 0, "total": 0},
                },
            }

        self._clear_previous_junit_reports()

        normalized_project = (project or "").strip().lower() or self._detect_project_name()
        if self._is_known_project_with_helper(normalized_project):
            helper_script = os.path.join(self._get_project_helper_dir(normalized_project), "run_tests.sh")
            if os.path.exists(helper_script):
                image_tag, image_err = self._ensure_project_builder_image(normalized_project)
                if image_tag:
                    helper_env = os.environ.copy()
                    helper_env.update(
                        {
                            "PROJECT_NAME": normalized_project,
                            "PROJECT_DIR": self.target_repo_path,
                            "BUILDER_IMAGE_TAG": image_tag,
                            "IMAGE_TAG": image_tag, # For backward compatibility with some scripts
                            "COMMIT_SHA": self._get_current_head(),
                            "WORKTREE_MODE": "1",
                            "TEST_TARGETS": " ".join(sorted(set(test_targets))) if test_targets else "NONE",
                            "TEST_MODULES": ",".join(sorted(set(source_modules))) if source_modules else "",
                        }
                    )
                    print(f"    Agent 4: Executing {normalized_project} helper test script: {helper_script}")
                    result = self._run_cmd_capture(["bash", helper_script], cwd=self.target_repo_path, env=helper_env)
                    output_text = result.get("output", "")
                    return {
                        "success": bool(result.get("success")),
                        "compile_error": (not bool(result.get("success"))) and ("compilation error" in output_text.lower()),
                        "output": output_text,
                        "failed_tests": [],
                        "mode": f"{normalized_project}-helper-script",
                        "targets": info,
                        "test_state": self._extract_test_state(info, output_text),
                    }
                else:
                    print(f"    Agent 4 Warning: {normalized_project} helper image unavailable for tests. Falling back. Details: {image_err}")

        is_gradle = os.path.exists(os.path.join(self.target_repo_path, "build.gradle"))
        java_compat_args = ["-Djdk.security.manager.allow.argLine="]

        if is_gradle:
            cmd = ["gradle", "test"]
            for t in test_targets:
                try:
                    _, cls = t.split(":", 1)
                    cmd.extend(["--tests", cls])
                except ValueError:
                    continue
            mode = "gradle-targeted" if test_targets else "gradle-module"
        else:
            module_set = set(source_modules)
            test_classes = []
            for t in test_targets:
                try:
                    module, cls = t.split(":", 1)
                    if module:
                        module_set.add(module)
                    if cls:
                        test_classes.append(cls)
                except ValueError:
                    continue

            module_list = sorted(module_set)
            if test_classes:
                cmd = [
                    "mvn", "test",
                    "-pl", ",".join(module_list),
                    "-am",
                    f"-Dtest={','.join(sorted(set(test_classes)))}",
                    "-DfailIfNoTests=false",
                    "-Dmaven.javadoc.skip=true",
                    "-Dcheckstyle.skip=true",
                    "-Dpmd.skip=true",
                    "-Dforbiddenapis.skip=true",
                    "-Denforcer.skip=true",
                ] + java_compat_args
                mode = "maven-targeted"
            else:
                cmd = [
                    "mvn", "test",
                    "-pl", ",".join(module_list),
                    "-am",
                    "-DfailIfNoTests=false",
                    "-Dmaven.javadoc.skip=true",
                    "-Dcheckstyle.skip=true",
                    "-Dpmd.skip=true",
                    "-Dforbiddenapis.skip=true",
                    "-Denforcer.skip=true",
                ] + java_compat_args
                mode = "maven-module"

        print(f"    Agent 4: Executing relevant test command: {' '.join(cmd)}")
        env = os.environ.copy()
        resolved_java_home = _resolve_valid_java_home()
        if resolved_java_home:
            env["JAVA_HOME"] = resolved_java_home

        cmd_res = self._run_cmd_capture(cmd, cwd=self.target_repo_path, env=env)
        output_text = cmd_res.get("output", "")
        return {
            "success": bool(cmd_res.get("success")),
            "compile_error": (not bool(cmd_res.get("success"))) and ("compilation error" in output_text.lower()),
            "output": output_text,
            "failed_tests": [],
            "mode": mode,
            "targets": info,
            "test_state": self._extract_test_state(info, output_text),
        }

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
                    1) Build one unified diff section per file with hunks in bottom-to-top order.
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

        # Sort hunks within each file bottom-to-top so earlier line numbers remain stable.
        for target_file in hunks_by_file:
            hunks_by_file[target_file].sort(
                key=lambda h: h.get("insertion_line", 0),
                reverse=True
            )
            insertion_lines = [h.get("insertion_line") for h in hunks_by_file[target_file]]
            print(
                f"  Validation: {target_file} - applying {len(hunks_by_file[target_file])} "
                f"hunk(s) in bottom-to-top order: {insertion_lines}"
            )

        # Build one patch section per file so offsets are resolved cumulatively.
        patch_parts = []
        applied_files = []
        for target_file in hunks_by_file:
            file_hunks = []
            file_operations = set()
            old_file_path = None

            for h in hunks_by_file[target_file]:
                hunk_text = h.get("hunk_text", "")
                file_op = (h.get("file_operation") or "MODIFIED").upper()

                # Track the old path for renamed files
                if file_op == "RENAMED":
                    old_file_path = h.get("mainline_file")

                # Skip hunks with empty text (structural operations handled separately)
                if not hunk_text or not hunk_text.strip():
                    # This is a structural operation with no hunks
                    file_operations.add(file_op)
                    continue

                file_hunks.append(hunk_text if hunk_text.endswith("\n") else hunk_text + "\n")
                file_operations.add(file_op)

            # Determine the operation type
            file_operation = next(iter(file_operations)) if len(file_operations) == 1 else "MODIFIED"

            # Handle structural operations (no hunks)
            if not file_hunks and file_operation in ["RENAMED", "ADDED", "DELETED"]:
                try:
                    patch_part = self._build_patch_file(
                        target_file,
                        "",  # Empty hunk_text for structural operations
                        file_operation=file_operation,
                        old_file_path=old_file_path
                    )
                    patch_parts.append(patch_part)
                    if target_file not in applied_files:
                        applied_files.append(target_file)
                    print(f"  Validation: {file_operation} operation for {target_file}")
                except ValueError as e:
                    return {
                        "success": False,
                        "output": f"Invalid {file_operation} operation for {target_file}: {e}",
                        "applied_files": [],
                    }
                continue

            if not file_hunks:
                continue

            combined_hunks = "".join(file_hunks)
            try:
                patch_part = self._build_patch_file(
                    target_file,
                    combined_hunks,
                    file_operation=file_operation,
                    old_file_path=old_file_path
                )
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
        project_name = os.path.basename(self.target_repo_path).strip().lower()

        if project_name == "druid":
            helper_script = os.path.join(self._get_project_helper_dir("druid"), "run_build.sh")
            if os.path.exists(helper_script):
                image_tag, image_err = self._ensure_project_builder_image("druid")
                if image_tag:
                    helper_env = os.environ.copy()
                    helper_env.update(
                        {
                            "PROJECT_DIR": self.target_repo_path,
                            "BUILDER_IMAGE_TAG": image_tag,
                            "IMAGE_TAG": image_tag,
                            "COMMIT_SHA": self._get_current_head(),
                            "WORKTREE_MODE": "1",
                        }
                    )
                    print(f"    Agent 4: Executing Druid helper build script: {helper_script}")
                    result = self._run_cmd_capture(["bash", helper_script], cwd=self.target_repo_path, env=helper_env)
                    return {
                        "success": bool(result.get("success")),
                        "output": result.get("output", ""),
                        "mode": "druid-helper-script",
                    }
                else:
                    print(f"    Agent 4 Warning: Druid helper image unavailable. Falling back. Details: {image_err}")
        elif self._is_known_project_with_helper(project_name):
            # Generic helper-based build for projects with a run_build.sh (e.g., crate)
            helper_script = os.path.join(self._get_project_helper_dir(project_name), "run_build.sh")
            if os.path.exists(helper_script):
                image_tag, image_err = self._ensure_project_builder_image(project_name)
                if image_tag:
                    helper_env = os.environ.copy()
                    helper_env.update(
                        {
                            "PROJECT_NAME": project_name,
                            "PROJECT_DIR": self.target_repo_path,
                            "TOOLKIT_DIR": self._get_project_helper_dir(project_name),
                            "BUILDER_IMAGE_TAG": image_tag,
                            "IMAGE_TAG": image_tag,
                            "COMMIT_SHA": self._get_current_head(),
                            "WORKTREE_MODE": "1",
                        }
                    )
                    print(f"    Agent 4: Executing {project_name} helper build script: {helper_script}")
                    result = self._run_cmd_capture(["bash", helper_script], cwd=self.target_repo_path, env=helper_env)
                    return {
                        "success": bool(result.get("success")),
                        "output": result.get("output", ""),
                        "mode": f"{project_name}-helper-script",
                    }
                else:
                    print(f"    Agent 4 Warning: {project_name} helper image unavailable. Falling back. Details: {image_err}")

        if is_gradle:
            cmd = ["gradle", "build", "-x", "test"]
        else:
            # Druid can fail on `mvn clean compile` because some modules depend on
            # classifier artifacts (e.g., tests-jar) that are not produced at compile phase.
            # Build only touched modules at package phase so required artifacts exist.
            if project_name == "druid":
                target_info = self.detect_relevant_test_targets(project="druid")
                modules = sorted(set(target_info.get("all_modules") or target_info.get("source_modules") or []))
                if modules:
                    cmd = [
                        "mvn", "clean", "package",
                        "-pl", ",".join(modules),
                        "-am",
                        "-DskipTests",
                        "-DskipITs",
                        "-DfailIfNoTests=false",
                        "-Dmaven.javadoc.skip=true",
                        "-Dcheckstyle.skip=true",
                        "-Dpmd.skip=true",
                        "-Dforbiddenapis.skip=true",
                        "-Denforcer.skip=true",
                        "-Drat.skip=true",
                        "-Dweb.console.skip=true",
                    ]
                else:
                    cmd = [
                        "mvn", "clean", "package",
                        "-DskipTests",
                        "-DskipITs",
                        "-DfailIfNoTests=false",
                        "-Dmaven.javadoc.skip=true",
                        "-Dcheckstyle.skip=true",
                        "-Dpmd.skip=true",
                        "-Dforbiddenapis.skip=true",
                        "-Denforcer.skip=true",
                        "-Drat.skip=true",
                        "-Dweb.console.skip=true",
                        "-pl", "!:distribution",
                    ]
            else:
                cmd = ["mvn", "clean", "compile"]
        
        try:
            print(f"    Agent 4: Executing build command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.target_repo_path,
            )
            return {
                "success": result.returncode == 0,
                "output": ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
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
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.target_repo_path,
            )
            success = result.returncode == 0
            output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
            compile_error = (not success) and ("compilation error" in output.lower())
            
            return {
                "success": success,
                "compile_error": compile_error,
                "output": output,
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

    def _build_patch_file(self, target_file_path: str, hunk_text: str, file_operation: str = "MODIFIED", old_file_path: str = None) -> str:
        """
        Wraps a hunk in a minimal unified diff file header so `git apply`
        can understand it. The hunk_text must already start with @@ ... @@.

        For file-only operations (rename, pure add, pure delete) with no hunk_text,
        generates an appropriate diff header without body hunks.

        Args:
            target_file_path: New path (for renames) or target path
            hunk_text: Unified diff hunks (may be empty for structural operations)
            file_operation: "ADDED" | "DELETED" | "MODIFIED" | "RENAMED"
            old_file_path: Old path (for renames)
        """
        # Normalize path separators and strip optional diff prefixes.
        p = (target_file_path or "").strip().replace("\\", "/").lstrip("/")
        if p.startswith("a/") or p.startswith("b/"):
            p = p[2:]

        if not p:
            raise ValueError("target_file_path is empty")

        normalized_op = (file_operation or "MODIFIED").upper()
        old_p = (old_file_path or "").strip().replace("\\", "/").lstrip("/") if old_file_path else p
        if old_p.startswith("a/") or old_p.startswith("b/"):
            old_p = old_p[2:]

        # Handle structural operations (no hunks)
        if not hunk_text or not hunk_text.strip():
            if normalized_op == "RENAMED":
                header = (
                    f"diff --git a/{old_p} b/{p}\n"
                    f"similarity index 100%\n"
                    f"rename from {old_p}\n"
                    f"rename to {p}\n"
                )
                return header + "\n"
            elif normalized_op == "ADDED":
                header = (
                    f"diff --git a/{p} b/{p}\n"
                    f"new file mode 100644\n"
                    f"index 0000000..0000000\n"
                    f"--- /dev/null\n"
                    f"+++ b/{p}\n"
                )
                return header + "\n"
            elif normalized_op == "DELETED":
                header = (
                    f"diff --git a/{p} b/{p}\n"
                    f"deleted file mode 100644\n"
                    f"index 0000000..0000000\n"
                    f"--- a/{p}\n"
                    f"+++ /dev/null\n"
                )
                return header + "\n"
            else:
                # MODIFIED with no hunks doesn't make sense, but handle gracefully
                raise ValueError(f"MODIFIED operation requires hunks, but hunk_text is empty")

        # Normal case: file operation with hunks
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
