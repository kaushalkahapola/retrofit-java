import os
import re
import concurrent.futures
from typing import List, Dict, Set, Optional
import pickle
from git import Repo
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tree_sitter import Language, Parser, Query, QueryCursor
import numpy as np

import tree_sitter_java

class EnsembleRetriever:
    def __init__(self, mainline_repo_path: str, target_repo_path: str):
        self.main_repo = Repo(mainline_repo_path)
        self.target_repo = Repo(target_repo_path)
        
        # Indexes
        self.symbol_index = {}   # Map: symbol -> set(files)
        self.symbol_counts = {}  # Map: symbol -> count
        self.target_files = []   # List of all files
        
        # TF-IDF
        self.vectorizer = None
        self.target_matrix = None
        
        # Tree-sitter Setup
        self.JAVA_LANGUAGE = Language(tree_sitter_java.language())
        self.parser = Parser(self.JAVA_LANGUAGE)
        self.query = Query(self.JAVA_LANGUAGE, """
            (method_declaration name: (identifier) @m_name)
            (class_declaration name: (identifier) @c_name)
            """)
        self.cursor = QueryCursor(self.query)

    def _get_content(self, repo, commit, path):
        try: return repo.git.show(f"{commit}:{path}")
        except: return ""

    def extract_symbols(self, code: str) -> Set[str]:
        """Tree-sitter: Extract Method and Class names."""
        try:
            tree = self.parser.parse(bytes(code, "utf8"))
            captures = self.cursor.captures(tree.root_node)
            
            symbols = set()
            for _, nodes in captures.items():
                for node in nodes:
                    text = code.encode('utf8')[node.start_byte:node.end_byte].decode('utf8')
                    if len(text) > 3 and text not in ["main", "toString", "equals", "hashCode"]:
                        symbols.add(text)
            
            return symbols
        except Exception as e:
            # print(f"Error extracting symbols: {e}")
            return set()

    def preprocess_tfidf(self, code: str) -> str:
        """Regex: Clean text for TF-IDF."""
        code = re.sub(r"/\*.*?\*/|//.*?$", "", code, flags=re.DOTALL | re.MULTILINE)
        tokens = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", code)
        return " ".join(tokens)

    def build_index(self, commit_sha: str = "HEAD"):
        """
        Builds the index for the target repository at the given commit.
        Checks for cached index first.
        """
        cache_file = os.path.join(self.target_repo.working_dir, f".index_cache_{commit_sha}.pkl")
        if os.path.exists(cache_file):
            print(f"Loading index from cache: {cache_file}")
            try:
                with open(cache_file, "rb") as f:
                    data = pickle.load(f)
                    self.target_files = data["target_files"]
                    self.symbol_index = data["symbol_index"]
                    self.symbol_counts = data["symbol_counts"]
                    self.vectorizer = data["vectorizer"]
                    self.target_matrix = data["target_matrix"]
                print("Index loaded from cache.")
                return
            except Exception as e:
                print(f"Error loading cache: {e}. Rebuilding index...")

        print(f"Building index for {commit_sha}...")
        
        # Optimization: If commit is HEAD, read from disk directly (much faster than git show)
        read_from_disk = commit_sha == "HEAD"
        
        if read_from_disk:
            java_files = []
            for root, _, files in os.walk(self.target_repo.working_dir):
                for file in files:
                    if file.endswith(".java"):
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, self.target_repo.working_dir).replace("\\", "/")
                        java_files.append((rel_path, full_path))
        else:
            try:
                files = self.target_repo.git.ls_tree("-r", "--name-only", commit_sha).splitlines()
                java_files = [(f, None) for f in files if f.endswith(".java")]
            except Exception as e:
                print(f"Error listing files: {e}")
                self.target_files = []
                return

        self.target_files = [f[0] for f in java_files]
        
        documents = []
        
        def process(item):
            rel_path, full_path = item
            if full_path:
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except:
                    content = ""
            else:
                content = self._get_content(self.target_repo, commit_sha, rel_path)
            
            symbols = self.extract_symbols(content)
            processed_code = self.preprocess_tfidf(content)
            return symbols, processed_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(process, java_files))
            
        for i, (symbols, processed_code) in enumerate(results):
            # Update Symbol Index
            for sym in symbols:
                if sym not in self.symbol_index:
                    self.symbol_index[sym] = set()
                    self.symbol_counts[sym] = 0
                self.symbol_index[sym].add(i)
                self.symbol_counts[sym] += 1
            
            documents.append(processed_code)
            
        # Build TF-IDF Matrix
        print("Building TF-IDF matrix...")
        self.vectorizer = TfidfVectorizer(max_features=5000)
        try:
            self.target_matrix = self.vectorizer.fit_transform(documents)
        except ValueError:
            print("Warning: Empty vocabulary; perhaps the documents contain only stop words")
            self.target_matrix = None
            
        print(f"Index built. {len(self.target_files)} Java files indexed.")
        
        # Save to cache
        try:
            with open(cache_file, "wb") as f:
                pickle.dump({
                    "target_files": self.target_files,
                    "symbol_index": self.symbol_index,
                    "symbol_counts": self.symbol_counts,
                    "vectorizer": self.vectorizer,
                    "target_matrix": self.target_matrix
                }, f)
            print(f"Index saved to {cache_file}")
        except Exception as e:
            print(f"Error saving cache: {e}")

    # --- SIGNAL 1: GIT ---
    def get_git_candidates(self, file_path, commit):
        candidates = []
        if file_path in self.target_files: candidates.append(file_path)
        try:
            # Check file history in mainline to see if it was renamed/moved
            # Note: This is a simplified version. The notebook uses mainline log to find paths.
            # Here we assume file_path is from mainline.
            log = self.main_repo.git.log('--follow', '--name-only', '--format=', commit, '--', file_path)
            for p in log.splitlines():
                if p and p.endswith('.java') and p in self.target_files:
                    candidates.append(p)
        except: pass

        return [{"file": f, "score": 1.0, "method": "GIT"} for f in set(candidates)]

    # --- SIGNAL 2: SYMBOL MATCHING ---
    def get_symbol_candidates(self, file_path, commit, top_k=5):
        content = self._get_content(self.main_repo, commit, file_path)
        if not content: return []

        query_symbols = self.extract_symbols(content)
        scores = {}

        for s in query_symbols:
            if s in self.symbol_index:
                matches = self.symbol_index[s]
                count = self.symbol_counts[s]
                weight = 1.0 / count

                for m_file in matches:
                    scores[m_file] = scores.get(m_file, 0) + weight

        results = []
        if not scores: return []
        max_score = max(scores.values())

        sorted_files = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for f, raw_score in sorted_files[:top_k]:
            norm_score = raw_score / max_score
            if norm_score > 0.1:
                results.append({"file": f, "score": norm_score, "method": "SYMBOL"})

        return results

    # --- SIGNAL 3: TF-IDF ---
    def get_tfidf_candidates(self, file_path, commit, top_k=5):
        content = self._get_content(self.main_repo, commit, file_path)
        if not content or self.vectorizer is None: return []

        query_text = self.preprocess_tfidf(content)
        query_vec = self.vectorizer.transform([query_text])
        sims = cosine_similarity(query_vec, self.target_matrix).flatten()

        top_indices = np.argsort(sims)[::-1][:top_k]
        results = []
        for idx in top_indices:
            score = float(sims[idx])
            if score > 0.0:
                results.append({
                    "file": self.target_files[idx],
                    "score": score,
                    "method": "TF-IDF"
                })
        return results

    def decide_candidate_list(self, candidates):
        if not candidates: return []

        file_map = {}
        for c in candidates:
            f = c['file']
            if f not in file_map:
                file_map[f] = {'score': 0.0, 'methods': set()}
            if c['score'] > file_map[f]['score']:
                file_map[f]['score'] = c['score']
            file_map[f]['methods'].add(c['method'])

        final_selection = []

        git_files = [f for f, data in file_map.items() if 'GIT' in data['methods']]
        for f in git_files:
            final_selection.append({
                'file': f,
                'score': 1.0,
                'methods': file_map[f]['methods']
            })

        semantic_pool = [
            {'file': f, 'score': data['score'], 'methods': data['methods']}
            for f, data in file_map.items()
            if 'GIT' not in data['methods']
        ]

        semantic_pool.sort(key=lambda x: x['score'], reverse=True)

        if semantic_pool:
            best_score = semantic_pool[0]['score']
            threshold = best_score * 0.95
            min_score = 0.25

            for c in semantic_pool:
                check_score = c['score']
                if 'SYMBOL' in c['methods']:
                    check_score *= 1.1

                if check_score >= threshold and check_score > min_score:
                    final_selection.append(c)

        if not final_selection and semantic_pool:
            fallback = semantic_pool[0]
            fallback['methods'].add("FALLBACK")
            final_selection.append(fallback)

        result_objects = []
        for item in final_selection:
            methods_list = sorted(list(item['methods']), key=lambda x: 0 if x=='GIT' else 1)
            method_str = " + ".join(methods_list)
            result_objects.append({
                'file': item['file'],
                'reason': method_str
            })

        return result_objects

    def find_file_by_blob_hash(self, file_path: str, commit: str) -> Optional[str]:
        """
        Advanced Git Strategy: "Blob Hunting"
        Finds where the CONTENT of the file (Blob SHA) exists in the Target Repo.
        1. Get Blob SHA from Mainline.
        2. Check if this SHA exists in Target HEAD.
        """
        try:
            # 1. Get Blob SHA in Mainline
            # git rev-parse <commit>:<path>
            # Note: We strip whitespace to be safe
            blob_sha = self.main_repo.git.rev_parse(f"{commit}:{file_path}").strip()
            print(f"Blob Hunting: Searching for SHA {blob_sha} ({file_path})")
            
            # 2. Check Target HEAD (Fast)
            # git ls-tree -r HEAD | grep <sha>
            # Output format: <mode> <type> <sha>\t<path>
            try:
                ls_tree_out = self.target_repo.git.ls_tree("-r", "HEAD")
                # We need to find the line containing the SHA
                # A simple substring check is fast
                if blob_sha in ls_tree_out:
                    for line in ls_tree_out.splitlines():
                        parts = line.split()
                        if len(parts) >= 4 and parts[2] == blob_sha:
                            found_path = line.split("\t", 1)[1]
                            print(f"Blob Hunting: Found EXACT match in HEAD at {found_path}")
                            return found_path
            except Exception as e:
                print(f"Blob Hunting HEAD check failed: {e}")

            # 3. Check Target History (Deep Search) - Optional but powerful
            # git log --all --find-object=<sha> --name-only --format= -n 1
            # This finds the most recent commit where this blob existed.
            try:
                # This finds the commit
                print("Blob Hunting: Checking deep history...")
                log_out = self.target_repo.git.log(
                    "--all", 
                    f"--find-object={blob_sha}", 
                    "--name-only", 
                    "--format=", 
                    "-n", "1"
                )
                if log_out:
                    old_path = log_out.strip().splitlines()[0]
                    print(f"Blob Hunting: Found match in history at {old_path}")
                    
                    # Now we need to see where 'old_path' is NOW.
                    # It might be the same, or renamed.
                    # We can recurse or just return it as a strong candidate.
                    # Let's check if it exists in target files
                    if old_path in self.target_files:
                        return old_path
                    else:
                        # Try to trace it forward from the HEAD? 
                        # Or just return it and hope the standard rename logic caught it?
                        # Actually, if we found it in history, we should probably run the Rename Tracer on THIS path in the TARGET repo.
                        # But simpler: just return it. The user might have deleted it, but if it was renamed, 'old_path' might be the old name.
                        # Let's attempt to resolve it in target if possible.
                        return old_path 

            except Exception as e:
                # --find-object might not be supported in older git versions, or other errors
                pass
                
        except Exception as e:
            print(f"Blob Hunting failed: {e}")
        
        return None

    def resolve_git_path(self, file_path: str, original_commit: str) -> Optional[List[Dict]]:
        """
        Phase 1: Deterministic resolution using Git History.
        Returns a match if:
        1. The file exists exactly in the target.
        2. The file was renamed but we can trace it to a file that exists in the target.
        3. [NEW] The file's CONTENT exists (Blob Match) even if history is broken.
        """
        # 1. Exact Match Check
        if file_path in self.target_files:
            return [{"file": file_path, "score": 1.0, "method": "GIT_EXACT", "reason": "Exact path match"}]

        # 2. Rename Tracing (Mainline)
        try:
            log_output = self.main_repo.git.log(
                '--follow', 
                '--name-only', 
                '--format=', 
                original_commit, 
                '--', 
                file_path
            )
            historic_paths = [p.strip() for p in log_output.splitlines() if p.strip()]
            for path in historic_paths:
                if path in self.target_files:
                     return [{"file": path, "score": 1.0, "method": "GIT_RENAME", "reason": f"Traced via git log from {file_path}"}]
        except Exception as e:
            print(f"Git trace failed for {file_path}: {e}")
            
        # 3. [NEW] Blob Hunting (Content Match)
        blob_path = self.find_file_by_blob_hash(file_path, original_commit)
        if blob_path:
             # Even if the path equals the original file_path (and wasn't found in step 1),
             # checking self.target_files again in step 1 should have caught it. 
             # So this likely implies a rename or move that Step 1 & 2 missed.
             if blob_path in self.target_files:
                 return [{"file": blob_path, "score": 1.0, "method": "GIT_BLOB", "reason": f"Content (Blob) match found at {blob_path}"}]
             else:
                 pass

        # 4. [NEW] Neighbor Inference (Sibling Logic)
        neighbor_path = self.find_file_by_neighbor_inference(file_path, original_commit)
        if neighbor_path:
            return [{"file": neighbor_path, "score": 0.9, "method": "GIT_NEIGHBOR", "reason": f"Inferred from sibling files: {neighbor_path}"}]

        return None

    def find_file_by_neighbor_inference(self, file_path: str, commit: str) -> Optional[str]:
        """
        Advanced Git Strategy: "Neighbor Inference"
        If looking for 'src/pkg/Missing.java', and we find that 'src/pkg/Sibling.java' 
        was renamed to 'new/path/Sibling.java', we infer 'new/path/Missing.java'.
        """
        try:
            parent_dir = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
            
            # 1. List siblings in Mainline
            # git ls-tree --name-only <commit> <parent_dir>
            siblings_out = self.main_repo.git.ls_tree("--name-only", commit, parent_dir).splitlines()
            siblings = [f for f in siblings_out if f.endswith(".java") and f != file_path]
            print(f"Neighbor Inference: Siblings of {file_path}: {siblings}")
            
            # Limit to checking first 3 siblings to save time
            for sibling in siblings[:3]:
                # Trace sibling
                try:
                    log_out = self.main_repo.git.log('--follow', '--name-only', '--format=', commit, '--', sibling)
                    historic_paths = [p.strip() for p in log_out.splitlines() if p.strip()]
                    print(f"Neighbor Inference: Trace for {sibling}: {historic_paths}")
                    
                    found_sibling_target = None
                    for path in historic_paths:
                        if path in self.target_files:
                            found_sibling_target = path
                            break
                    
                    if found_sibling_target:
                        # Sibling 'src/pkg/Sibling.java' -> 'new/path/Sibling.java'
                        # Infer 'new/path/' + 'Missing.java'
                        sibling_dir = os.path.dirname(found_sibling_target)
                        inferred_path = os.path.join(sibling_dir, file_name)
                        
                        if inferred_path in self.target_files:
                            print(f"Neighbor Inference: Found {inferred_path} via sibling {sibling}")
                            return inferred_path
                            
                except: continue
                
        except Exception as e:
            print(f"Neighbor inference failed: {e}")
            
        return None

    def find_candidates(self, file_path: str, original_commit: str) -> List[Dict]:
        """
        Orchestrates the retrieval process using Split Flow (PORTGPT Style).
        Phase 1: Git Precision (Deterministic)
        Phase 2: Ensemble Search (Probabilistic)
        """
        # --- PHASE 1: Deterministic Git Resolution ---
        git_match = self.resolve_git_path(file_path, original_commit)
        if git_match:
            print(f"Phase 1 (Git) Match Found: {git_match[0]['file']}")
            return git_match

        # --- PHASE 2: Probabilistic Ensemble Fallback ---
        print(f"Phase 1 failed for {file_path}. Falling back to Ensemble Search...")
        
        # Note: We skip 'get_git_candidates' inside here because Phase 1 covers it better.
        # We perform the expensive search now.
        sym_cands = self.get_symbol_candidates(file_path, original_commit)
        tfidf_cands = self.get_tfidf_candidates(file_path, original_commit)

        pool = sym_cands + tfidf_cands
        return self.decide_candidate_list(pool)
