from typing import List, Dict
import subprocess
import os
import shutil
import tempfile
import re
from utils.mcp_client import get_client

class ValidationToolkit:
    def __init__(self, target_repo_path: str):
        self.target_repo_path = target_repo_path
        self.client = get_client()

    def _detect_module(self, file_path: str) -> str:
        """
        Attempts to infer the module name from a file path.
        Strategy:
        1. OpenJDK Source Layout Regex: src/<module>/share/classes...
        2. 'module-info.java' Search: Walks up directory tree to find module definition.
        """
        # 1. OpenJDK Source Layout
        # Regex handles both absolute (.../src/...) and relative (src/...) paths
        match_src = re.search(r"(?:^|[\\/])src[\\/]([\w\.]+)[\\/](?:share|unix|windows|linux|macosx)[\\/]classes", file_path)
        if match_src:
            return match_src.group(1)
            
        # 2. Walk up to find module-info.java
        try:
            abs_path = os.path.join(self.target_repo_path, file_path)
            if not os.path.exists(abs_path):
                return None
                
            current_dir = os.path.dirname(abs_path)
            repo_root = os.path.abspath(self.target_repo_path)
            
            # Walk up until we leave the repo
            while current_dir.startswith(repo_root):
                module_info = os.path.join(current_dir, "module-info.java")
                if os.path.exists(module_info):
                    try:
                        with open(module_info, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            # Match 'module java.desktop {' or 'open module foo.bar {'
                            match_mod = re.search(r'^\s*(?:open\s+)?module\s+([\w\.]+)\s*\{', content, re.MULTILINE)
                            if match_mod:
                                return match_mod.group(1)
                    except (OSError, UnicodeDecodeError):
                        pass
                
                parent = os.path.dirname(current_dir)
                if parent == current_dir: 
                    break
                current_dir = parent
        except Exception:
            pass
            
        return None

    def compile_files(self, file_paths: List[str]) -> Dict:
        """
        Compiles the specified files using a local 'Smart Compiler' strategy.
        Attempts to infer source roots and handle module patching.
        """
        print(f"  [Smart Compiler] Compiling {len(file_paths)} files...")
        
        # 1. Setup Output Dir
        # We use a temp dir for class outputs
        output_dir = tempfile.mkdtemp(prefix="validation_classes_")
        
        # 2. Group files by Source Root (Heuristic)
        # We need to find the compatible source path for the files.
        source_roots = set()
        detected_modules = set()
        
        for file_path in file_paths:
            abs_path = os.path.join(self.target_repo_path, file_path)
            
            # Infer module from path
            mod = self._detect_module(file_path)
            if mod:
                detected_modules.add(mod)

            if not os.path.exists(abs_path):
                print(f"    Warning: File not found: {abs_path}")
                continue
                
            # Heuristic: Read file to find 'package name;'
            pkg_name = ""
            try:
                with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    match = re.search(r'^\s*package\s+([\w\.]+)\s*;', content, re.MULTILINE)
                    if match:
                        pkg_name = match.group(1)
            except (OSError, UnicodeDecodeError):
                pass
            
            # If package is 'a.b.c' and file is '.../src/foo/a/b/c/Bar.java'
            # then source root is '.../src/foo'
            parent_dir = os.path.dirname(abs_path)
            if pkg_name:
                package_path = pkg_name.replace('.', os.sep)
                if parent_dir.endswith(package_path):
                    root = parent_dir[:-len(package_path)].rstrip(os.sep)
                    source_roots.add(root)
                else:
                    # Fallback: Source structure doesn't match package. 
                    # Use repo root or parent as best effort.
                    source_roots.add(parent_dir)
            else:
                 # Default package? root is parent dir
                 source_roots.add(parent_dir)

        # 3. Construct Command
        cmd = ["javac", "-d", output_dir]
        
        # Add sourcepath if we found any likely roots
        if source_roots:
            # We add ALL potential source roots found
            valid_roots = [r for r in source_roots if os.path.exists(r)]
            if valid_roots:
                cmd += ["-sourcepath", os.pathsep.join(valid_roots)] # Use platform path separator
        
        # Add files
        # Convert relative (file_paths) to absolute for safety, or keep relative if CWD is set?
        # Let's use absolute paths.
        abs_file_paths = [os.path.join(self.target_repo_path, f) for f in file_paths]
        cmd += abs_file_paths
        
        # 4. Run & Retry Loop
        max_retries = 3
        last_error = ""
        success = False
        
        patched_modules = set()
        
        # Add initially detected modules (from path)
        # However, we only need --patch-module if we are actually overriding it.
        # If the user is compiling 'src/java.desktop/...' javac might treat it as module source key if we setup module source path right.
        # But with -searchpath, we are doing legacy mode often.
        # Let's wait for errors to drive it, OR if we know it's a module, patch it proactively?
        # Proactive patching is safer for "package exists in another module".
        
        for attempt in range(max_retries):
            # shell=True removed for security; verify java in PATH
            print(f"    Attempt {attempt+1}: {' '.join(cmd)}")
            try:
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    cwd=self.target_repo_path  # Run from repo root
                )
                
                if result.returncode == 0:
                    success = True
                    break
                else:
                    last_error = result.stderr + "\n" + result.stdout
                    
                    # 5. DIAGNOSTICS & RECOVERY
                    # Check for "package exists in another module: foo"
                    # Error format: "error: package exists in another module: java.desktop"
                    module_matches = re.finditer(r"error: package exists in another module: ([\w\.]+)", last_error)
                    new_patches = False
                    for m in module_matches:
                        mod_name = m.group(1)
                        if mod_name not in patched_modules:
                            # We need to patch this module.
                            # We assume the source root for this module is one of our source_roots.
                            # We pick the first one that looks 'main' or just the first one?
                            # For JDK: 'src/java.desktop/share/classes'
                            # If we found multiple source roots, we might need to guess which one belongs to the module.
                            # Just merging them might work?
                            # --patch-module <module>=<path>
                            patch_path_arg = os.pathsep.join(list(source_roots)) # Try ALL known roots
                            
                            # Add flag
                            # cmd is ["javac", "-d", output_dir, ...]
                            # We want ["javac", "--patch-module", "...", "-d", ...]
                            # So we insert at index 1
                            patch_arg = f"{mod_name}={patch_path_arg}"
                            if "--patch-module" not in cmd:
                                 # Insert at pos 1
                                 cmd.insert(1, "--patch-module")
                                 cmd.insert(2, patch_arg)
                            else:
                                 # If already present, this is weird (multiple modules?), just append to args?
                                 # Actually javac allows multiple --patch-module flags.
                                 cmd.insert(1, "--patch-module")
                                 cmd.insert(2, patch_arg)
                            
                            patched_modules.add(mod_name)
                            detected_modules.add(mod_name)
                            new_patches = True
                            print(f"    Detected collision with module '{mod_name}'. Retrying with --patch-module.")
                    
                    if not new_patches:
                        # No recoverable errors found
                        break
                        
            except Exception as e:
                last_error = str(e)
                break
        
        # 6. Cleanup & Return
        # We intentionally keep output_dir if success is False for debugging? 
        # Or maybe the agent should clean it up? 
        # For now, we rely on OS cleanup or the caller to handle specific cleanup if needed.
        # But per review, we SHOULD clean up.
        # However, run_spotbugs needs the output_dir. 
        # So we return the path and add a separate cleanup method or rely on the script ending.
        # Since this is a temporary agent process, temp files usually persist until reboot unless deleted.
        # We will leave as is for now BUT note that caller must cleanup if needed.
        # Actually, let's just return it. The caller (Agent) can delete it.
        
        return {
            "success": success,
            "message": last_error if not success else "Compilation Successful",
            "output_path": output_dir, 
            "source_path": os.pathsep.join(list(source_roots)) if source_roots else None,
            "patched_modules": list(detected_modules)
        }

    def run_spotbugs(self, compiled_classes_path: str, source_path: str = None) -> Dict:
        """
        Runs SpotBugs on the compiled classes.
        """
        return self.client.call_tool("spotbugs", {
            "compiled_classes_path": compiled_classes_path,
            "source_path": source_path
        })

    def run_test_with_patch(self, test_file_path: str, patch_classes_path: str, patch_source_path: str, target_module: str = "java.desktop") -> Dict:
        """
        Compiles and runs a single test file using the Universal Test Runner strategy.
        Supports:
          1. Standard Main Method
          2. JUnit 5 (JUnit Platform)
          3. TestNG
        
        Requires 'analysis-engine/target/dependency' to be populated with runners.
        """
        print(f"  [Smart Test] Running test: {test_file_path} against module: {target_module}")
        
        # 1. Compile Test
        test_output_dir = tempfile.mkdtemp(prefix="validation_test_")
        abs_test_path = os.path.join(self.target_repo_path, test_file_path)
        
        # Locate Runners (Hardcoded relative to agent, assumes standard layout)
        # Agents -> Backend -> Retrofit Root -> Analysis Engine -> ...
        # self.target_repo_path is external to this tool structure.
        # We assume 'analysis-engine' is a sibling of 'agents-backend' or similar.
        # Let's try to find it relative to CWD first.
        
        # Assuming we run from agents-backend/
        analysis_dep_dir = os.path.abspath(os.path.join("..", "analysis-engine", "target", "dependency"))
        if not os.path.exists(analysis_dep_dir): 
             # Fallback: maybe we are in root?
             analysis_dep_dir = os.path.abspath(os.path.join("analysis-engine", "target", "dependency"))
        
        print(f"    Looking for runners in: {analysis_dep_dir}")
        runner_cp = f"{analysis_dep_dir}/*" # Wildcard execution for libs
        
        # Compile Command
        # We must add runner jars to classpath if this is a JUnit/TestNG test
        cmd_compile = [
            "javac", 
            "-d", test_output_dir,
            "--patch-module", f"{target_module}={patch_classes_path}",
            "--add-reads", f"{target_module}=ALL-UNNAMED",
            "-cp", runner_cp, # Add runners to compile CP
            abs_test_path
        ]
        
        print(f"    Compiling test: {' '.join(cmd_compile)}")
        # shell=True removed
        res_compile = subprocess.run(cmd_compile, capture_output=True, text=True, cwd=self.target_repo_path)
        
        if res_compile.returncode != 0:
            shutil.rmtree(test_output_dir, ignore_errors=True) # Cleanup on failure
            return {
                "success": False,
                "stage": "compilation",
                "message": f"Test Compilation Failed:\n{res_compile.stderr}\n{res_compile.stdout}"
            }
            
        # 2. Detect Test Type
        test_type = "MAIN"
        test_content = ""
        try:
            with open(abs_test_path, 'r', encoding='utf-8', errors='ignore') as f:
                test_content = f.read()
                if "@Test" in test_content or "@org.junit.jupiter.api.Test" in test_content:
                    test_type = "JUNIT"
                elif "@org.testng.annotations.Test" in test_content:
                    test_type = "TESTNG"
        except (OSError, IOError) as e:
            print(f"Warning: Could not read test file '{abs_test_path}': {e}")
        
        print(f"    Detected Test Type: {test_type}")

        # 3. Find Test Class Name
        test_class_name = os.path.basename(test_file_path).replace(".java", "")
        match = re.search(r'^\s*package\s+([\w\.]+)\s*;', test_content, re.MULTILINE)
        if match:
            test_class_name = f"{match.group(1)}.{test_class_name}"

        # 4. Construct Run Command
        base_cmd = [
            "java",
            "--patch-module", f"{target_module}={patch_classes_path}",
            "--add-reads", f"{target_module}=ALL-UNNAMED",
            "--add-opens", f"{target_module}/javax.swing=ALL-UNNAMED",
        ]
        
        cmd_run = []
        if test_type == "JUNIT":
            # java ... -jar junit-platform-console-standalone.jar -cp <test_out> -c <TestClass>
            # Find the specific jar name
            junit_jar = None
            if os.path.exists(analysis_dep_dir):
                for f in os.listdir(analysis_dep_dir):
                    if "junit-platform-console-standalone" in f:
                        junit_jar = os.path.join(analysis_dep_dir, f)
                        break
            
            if not junit_jar:
                 shutil.rmtree(test_output_dir, ignore_errors=True)
                 return {"success": False, "stage": "execution", "message": "JUnit Runner JAR not found."}

            # Note: When using -jar, -cp is ignored! 
            # We must use -cp <junit_jar>;<test_out> and launch ConsoleLauncher manually
            full_cp = f"{junit_jar}{os.pathsep}{test_output_dir}"
            
            cmd_run = base_cmd + [
                "-cp", full_cp,
                "org.junit.platform.console.ConsoleLauncher",
                "--select-class", test_class_name,
                "--disable-banner",
                "--details=none" # Minimal output to parsing easier
            ]
            
        elif test_type == "TESTNG":
             # Similar logic for TestNG
             # Fix variable name testng_chars -> testng_jars
             testng_jars = [os.path.join(analysis_dep_dir, f) for f in os.listdir(analysis_dep_dir) if f.endswith(".jar")]
             full_cp = os.pathsep.join(testng_jars) + os.pathsep + test_output_dir
             
             cmd_run = base_cmd + [
                 "-cp", full_cp,
                 "org.testng.TestNG",
                 "-testclass", test_class_name
             ]
             
        else: # MAIN
            cmd_run = base_cmd + [
                "-cp", test_output_dir,
                test_class_name
            ]
        
        print(f"    Running test: {' '.join(cmd_run)}")
        try:
            # shell=True removed
            res_run = subprocess.run(
                cmd_run, 
                capture_output=True, 
                text=True, 
                cwd=self.target_repo_path,
                timeout=60
            )
            
            # Check success
            # JUnit Console returns 0 on success
            success = (res_run.returncode == 0)
            
            output = (res_run.stdout + "\n" + res_run.stderr).strip()
            
            return {
                "success": success,
                "stage": "execution",
                "message": output
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stage": "execution",
                "message": "Test Execution Timed Out (60s)"
            }
        finally:
            # Cleanup test output dir
            if os.path.exists(test_output_dir):
                shutil.rmtree(test_output_dir, ignore_errors=True)

    def write_trace(self, trace_content: str, filename: str = "validation_trace.md"):
        """
        Writes the validation trace to a file.
        """
        with open(filename, "w", encoding="utf-8") as f:
            f.write(trace_content)
        print(f"Trace saved to {filename}")
