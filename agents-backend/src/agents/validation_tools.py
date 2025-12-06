from typing import List, Dict, Optional
import subprocess
import os
import shutil
import tempfile
import re
import json
from utils.mcp_client import get_client

class ValidationToolkit:
    def __init__(self, target_repo_path: str):
        self.target_repo_path = target_repo_path
        self.client = get_client()

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
        
        for file_path in file_paths:
            abs_path = os.path.join(self.target_repo_path, file_path)
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
            except: pass
            
            # If package is 'a.b.c' and file is '.../src/foo/a/b/c/Bar.java'
            # then source root is '.../src/foo'
            parent_dir = os.path.dirname(abs_path)
            if pkg_name:
                package_path = pkg_name.replace('.', os.sep)
                if parent_dir.endswith(package_path):
                    root = parent_dir[:-len(package_path)].rstrip(os.sep)
                    source_roots.add(root)
                else:
                    # Fallback: just use parent dir? Or just repo root?
                    # If directory structure doesn't match package, sourcepath is tricky.
                    pass
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
        
        for attempt in range(max_retries):
            print(f"    Attempt {attempt+1}: {' '.join(cmd)}")
            try:
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    cwd=self.target_repo_path,  # Run from repo root
                    shell=True                  # Required for Windows PATH resolution
                )
                
                if result.returncode == 0:
                    success = True
                    break
                else:
                    last_error = result.stderr + "\n" + result.stdout
                    
                    # 5. DIAGOSTICS & RECOVERY
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
                            new_patches = True
                            print(f"    Detected collision with module '{mod_name}'. Retrying with --patch-module.")
                    
                    if not new_patches:
                        # No recoverable errors found
                        break
                        
            except Exception as e:
                last_error = str(e)
                break
        
        # 6. Cleanup & Return
        # (We keep output_dir if success? Or just return path?)
        return {
            "success": success,
            "message": last_error if not success else "Compilation Successful",
            "output_path": output_dir, # Caller manages this?
            "source_path": os.pathsep.join(list(source_roots)) if source_roots else None
        }

    def run_spotbugs(self, compiled_classes_path: str, source_path: str = None) -> Dict:
        """
        Runs SpotBugs on the compiled classes.
        """
        return self.client.call_tool("spotbugs", {
            "compiled_classes_path": compiled_classes_path,
            "source_path": source_path
        })

    def run_test_with_patch(self, test_file_path: str, patch_classes_path: str, patch_source_path: str) -> Dict:
        """
        Compiles and runs a single test file against the patched classes.
        Uses --patch-module to override the platform module with the patch.
        """
        print(f"  [Smart Test] Running test: {test_file_path}")
        
        # 1. Compile Test
        test_output_dir = tempfile.mkdtemp(prefix="validation_test_")
        abs_test_path = os.path.join(self.target_repo_path, test_file_path)
        
        # Determine module to patch (heuristic: same as patch compilation?)
        # For now, we assume 'java.desktop' is the target if not specified.
        # But a safer bet is to reuse the patch logic or just try.
        # Ideally, we inspect the patch_classes_path to see what we compiled.
        target_module = "java.desktop" 
        
        # Compile Command
        # javac -d test_out --patch-module java.desktop=patch_out test_file ...
        cmd_compile = [
            "javac", 
            "-d", test_output_dir,
            "--patch-module", f"{target_module}={patch_classes_path}",
            "--add-reads", f"{target_module}=ALL-UNNAMED",
            abs_test_path
        ]
        
        # Add sourcepath if needed for test dependencies?
        # Tests might depend on other test library classes. 
        # For simple jtreg tests, they are often self-contained or use library tags.
        # We will try a simple compile first.
        
        print(f"    Compiling test: {' '.join(cmd_compile)}")
        res_compile = subprocess.run(cmd_compile, capture_output=True, text=True, cwd=self.target_repo_path, shell=True)
        
        if res_compile.returncode != 0:
            return {
                "success": False,
                "stage": "compilation",
                "message": f"Test Compilation Failed:\n{res_compile.stderr}\n{res_compile.stdout}"
            }
            
        # 2. Run Test
        # java --patch-module ... -cp test_out TestClass
        
        # Find Test Class Name
        # Heuristic: filename without extension?
        test_class_name = os.path.basename(test_file_path).replace(".java", "")
        # If package declared, we need full name.
        try:
            with open(abs_test_path, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'^\s*package\s+([\w\.]+)\s*;', content, re.MULTILINE)
                if match:
                    test_class_name = f"{match.group(1)}.{test_class_name}"
        except: pass

        cmd_run = [
            "java",
            "--patch-module", f"{target_module}={patch_classes_path}",
            "--add-reads", f"{target_module}=ALL-UNNAMED",
            "--add-opens", f"{target_module}/javax.swing=ALL-UNNAMED", # Open internals if needed
            "-cp", test_output_dir,
            test_class_name
        ]
        
        print(f"    Running test: {' '.join(cmd_run)}")
        try:
            res_run = subprocess.run(
                cmd_run, 
                capture_output=True, 
                text=True, 
                cwd=self.target_repo_path,
                timeout=30, # Timeout to prevent infinite loops
                shell=True
            )
            
            success = (res_run.returncode == 0)
            return {
                "success": success,
                "stage": "execution",
                "message": (res_run.stdout + "\n" + res_run.stderr).strip()
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stage": "execution",
                "message": "Test Execution Timed Out (30s)"
            }

    def write_trace(self, trace_content: str, filename: str = "validation_trace.md"):
        """
        Writes the validation trace to a file.
        """
        with open(filename, "w", encoding="utf-8") as f:
            f.write(trace_content)
        print(f"Trace saved to {filename}")
