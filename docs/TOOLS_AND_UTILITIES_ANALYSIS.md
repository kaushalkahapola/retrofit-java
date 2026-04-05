# H-MABS Tools and Utilities Analysis

**Document Date**: April 3, 2026  
**Status**: Comprehensive Reference Guide  
**Scope**: All tool implementations, utilities, and helper functions in H-MABS

---

## Table of Contents

1. [Tool Suites Overview](#tool-suites-overview)
2. [HunkGeneratorToolkit (Agent 3)](#hunkgeneratortoolkit-agent-3)
3. [ReasoningToolkit (Agent 2)](#reasoningtoolkit-agent-2)
4. [ValidationToolkit (Agent 4)](#validationtoolkit-agent-4)
5. [Utility Modules](#utility-modules)
   - [MethodFingerprinter](#methodfingerprinter)
   - [StructuralMatcher](#structuralmatcher)
   - [EnsembleRetriever](#ensembleretriever)
   - [PatchAnalyzer](#patchanalyzer)
   - [FileOperations](#fileoperations)
6. [Semantic and Retrieval Helpers](#semantic-and-retrieval-helpers)
7. [LLM Provider Factory](#llm-provider-factory)
8. [Token Counting](#token-counting)
9. [Data Models](#data-models)
10. [Configuration and Environment](#configuration-and-environment)

---

## Tool Suites Overview

The system provides **three specialized tool suites** for the three LLM-based agents:

| Agent | Toolkit | Purpose | Tool Count | Recursion Limit |
|-------|---------|---------|-----------|-----------------|
| Agent 2 (Structural Locator) | ReasoningToolkit | ReAct for file mapping | 7 tools | 18 |
| Agent 3 (File Editor) | HunkGeneratorToolkit | Direct file manipulation | 6 tools | 100 |
| Agent 4 (Validation) | ValidationToolkit | Test execution & analysis | Multiple | N/A (direct call) |

**Design Pattern**: Each toolkit is:
- **Scoped**: Bound to specific repo paths
- **Stateful**: Maintains session state (e.g., todo lists)
- **LangChain-Compatible**: Implements `StructuredTool` protocol
- **Safe**: Validates all inputs before mutation

---

## HunkGeneratorToolkit (Agent 3)

**File**: `/agents/hunk_generator_tools.py`  
**Size**: 1,039 lines  
**Purpose**: Enable Agent 3 (File Editor) to directly manipulate files and verify changes

### Architecture

**Session State**:
```python
self._todos: list[dict[str, str]] = []  # Per-hunk todo tracking
self._todo_counter: int = 0
```

### Tool: read_file_window

**Signature**:
```python
def read_file_window(
    file_path: str,
    center_line: int,
    radius: int = 15,
) -> str
```

**Purpose**: Verify file content around insertion point before generating code  
**Returns**: Numbered lines (1-indexed) like:
```
59:  abstract class DataNodeRequestSender {
60:      private final ClusterService clusterService;
...
```

**Key Feature**: Allows Agent to detect context mismatches before committing to diffs

### Tool: grep_in_file

**Signature**:
```python
def grep_in_file(
    file_path: str,
    search_pattern: str,
    max_results: int = 50,
) -> str
```

**Purpose**: Find exact line numbers where a string/pattern appears  
**Returns**: Lines with 1-indexed line numbers and match context

**Use Case**: Locate insertion points when code has drifted slightly

### Tool: get_exact_lines

**Signature**:
```python
def get_exact_lines(
    file_path: str,
    start_line: int,
    end_line: int,
) -> str
```

**Purpose**: Fetch numbered lines from a specific range (1-indexed)  
**Returns**: Content with line numbers

### Tool: verify_context_at_line

**Signature**:
```python
def verify_context_at_line(
    file_path: str,
    line_number: int,
    expected_text: str,
    fuzzy_match: bool = False,
) -> str
```

**Purpose**: Validate that expected text exists at exact line before modification  
**Use Case**: Prevent applying wrong hunk to wrong location

### Tool: manage_todo_list

**Signature**:
```python
def manage_todo_list(
    action: str,  # "add", "get", "mark_done", "clear"
    task: str = None,
    todo_id: str = None,
) -> str
```

**Purpose**: Track pending context requests before committing to edit  
**Pattern**: Agent can say "I need more context" before final hunk output

### Tool: str_replace_in_file

**Signature**:
```python
def str_replace_in_file(
    file_path: str,
    old_string: str,
    new_string: str,
) -> str
```

**Purpose**: Direct file manipulation (atomic, pre-validated)  
**Key**: Validates old_string exists before mutation

### Tool: insert_after_line

**Signature**:
```python
def insert_after_line(
    file_path: str,
    line_number: int,
    new_content: str,
) -> str
```

**Purpose**: Insert code after a specific line  
**Returns**: Confirmation with new line count

---

## ReasoningToolkit (Agent 2)

**File**: `/agents/reasoning_tools.py`  
**Size**: 661 lines  
**Purpose**: Enable Agent 2 (Structural Locator) to search and analyze target repository

### Tool: search_candidates

**Signature**:
```python
def search_candidates(self, file_path: str) -> List[Dict]
```

**Purpose**: Find candidate target files for a given source file  
**Returns**:
```python
[
    {"file": "src/main/java/...", "score": 0.95, "reasoning": "..."},
    ...
]
```

**Implementation**: Delegates to `EnsembleRetriever.find_candidates()`

### Tool: read_file

**Signature**:
```python
def read_file(self, file_path: str) -> str
```

**Purpose**: Read entire file content (max 2000 lines)  
**Processing**: 
- Strips comments (/* */ and //)
- Removes empty lines
- Truncates if too large

**Use Case**: Analyze target file structure for consistency mapping

### Tool: list_files

**Signature**:
```python
def list_files(self, directory: str = ".") -> List[str]
```

**Purpose**: Explore directory structure  
**Returns**: List of file/directory names

### Tool: get_dependency_graph

**Signature**:
```python
def get_dependency_graph(
    file_paths: List[str],
    explore_neighbors: bool = False,
    use_mainline: bool = False,
) -> Dict
```

**Purpose**: Analyze Java import/inheritance dependencies  
**Returns**:
```python
{
    "nodes": [
        {
            "className": "...",
            "imports": [...],
            "extends": "...",
            "implements": [...],
            "outgoingCalls": [...]
        }
    ],
    "edges": [...]
}
```

**Use Case**: Understand structural changes between mainline and target

### Tool: search_by_patterns

**Signature**:
```python
def search_by_patterns(
    patterns: List[str],
    file_path: str = None,
    limit: int = 10,
) -> List[Dict]
```

**Purpose**: Find code matching multiple regex patterns  
**Use Case**: Locate method by signature pattern when exact match fails

### Tool: get_method_info

**Signature**:
```python
def get_method_info(
    file_path: str,
    method_name: str,
) -> Dict
```

**Purpose**: Extract method details (signature, start line, calls, fields)  
**Returns**:
```python
{
    "simpleName": "...",
    "signature": "...",
    "startLine": 100,
    "calls": [...],
    "returnType": "..."
}
```

### Tool: search_class_by_outline

**Signature**:
```python
def search_class_by_outline(
    class_name: str,
    outline_query: str = None,
) -> Dict
```

**Purpose**: Find class and list its methods (outline-based)  
**Returns**: Class info with all methods and signatures

---

## ValidationToolkit (Agent 4)

**File**: `/agents/validation_tools.py`  
**Size**: 2,765 lines  
**Purpose**: Execute tests, compile code, and validate patch correctness

### Tool: test_and_restore

**Signature**:
```python
def test_and_restore(self, test_classes: List[str]) -> Dict
```

**Purpose**: Run JUnit tests on target file(s) and restore repo state  
**Returns**:
```python
{
    "success": bool,
    "test_results": {
        "passed": [...],
        "failed": [...],
        "errors": [...]
    },
    "summary": {"total": 5, "passed": 4, "failed": 1}
}
```

**Key Feature**: Automatic repo state restoration (git checkout) after tests

### Tool: apply_patch_to_file

**Signature**:
```python
def apply_patch_to_file(
    file_path: str,
    patch_text: str,
    dry_run: bool = False,
) -> Dict
```

**Purpose**: Apply a single hunk patch and validate  
**Modes**:
- `dry_run=True`: Check if patch would apply without modification
- `dry_run=False`: Actually apply the patch

**Returns**:
```python
{
    "success": bool,
    "error_type": "DRY_RUN_FAILED|APPLY_FAILED|SYNTAX_ERROR|...",
    "message": "...",
    "line_offset": 0  # If fuzzy matched
}
```

### Tool: compile_maven

**Signature**:
```python
def compile_maven(
    working_dir: str,
    specific_module: str = None,
    skip_tests: bool = True,
) -> Dict
```

**Purpose**: Run Maven compilation on target repo  
**Returns**:
```python
{
    "success": bool,
    "build_time_ms": 5000,
    "diagnostics": {
        "issues": [
            {
                "file": "...",
                "line": 100,
                "error_type": "COMPILATION_ERROR|MISSING_IMPORT|...",
                "message": "..."
            }
        ]
    }
}
```

### Tool: run_spotbugs

**Signature**:
```python
def run_spotbugs(
    working_dir: str,
    config_file: str = None,
) -> Dict
```

**Purpose**: Run static analysis with SpotBugs  
**Returns**: Bug findings organized by severity (H/M/L)

**Cleanup**: Automatically filters out "missing classes" noise

### Tool: validate_hunk_context

**Signature**:
```python
def validate_hunk_context(
    file_path: str,
    hunk_start_line: int,
    context_before: str,
    context_after: str,
) -> Dict
```

**Purpose**: Verify hunk context matches actual file  
**Returns**: Exact match indicator + suggestions for adjustment

### Tool: extract_test_class_info

**Signature**:
```python
def extract_test_class_info(
    test_file_path: str,
) -> Dict
```

**Purpose**: Parse JUnit test file for test method names and assertions  
**Returns**:
```python
{
    "test_methods": ["testVulnerability", "testFix", ...],
    "assertions": [...],
    "test_dependencies": [...]
}
```

---

## Utility Modules

### MethodFingerprinter

**File**: `/utils/method_fingerprinter.py`  
**Size**: 137 lines

#### Purpose
Find method matches across versions using multi-tier scoring:

**Tier 1**: Exact Name Match → confidence: 1.0  
**Tier 2**: Signature Match → confidence: 0.9  
**Tier 3**: Name Similarity (Levenshtein) → confidence: 0.8+  
**Tier 4**: Call Graph Similarity (Jaccard) → confidence: 0.7-0.9

#### Key Methods

**_get_ast_vector(source_code)**
```python
# Parse code and return vector of AST node type counts
# Node types: if_statement, for_statement, while_statement, try_statement, etc.
# Returns: np.ndarray of shape (10,) counting each node type
```

**_compute_jaccard(set1, set2)**
```python
# Compute set similarity for call graph matching
# Returns: float between 0.0 and 1.0
```

**find_match(old_method_name, old_signature, old_code, old_calls, candidates)**
```python
# Returns:
{
    "match": candidate_dict,
    "confidence": float,
    "reason": "Exact Name Match|Signature Match|Name Similarity|Call Graph Match"
}
```

#### Limitations
- Relies on `calls` not `body` (limited by GetDependencyTool)
- AST matching requires method body (not always available)
- Threshold tuning is hardcoded (not configurable)

---

### StructuralMatcher

**File**: `/utils/structural_matcher.py`  
**Size**: 171 lines

#### Purpose
Score and match classes across versions based on structural features

#### Scoring Breakdown (Total: 1.0)

| Component | Weight | Criteria |
|-----------|--------|----------|
| Superclass Match | 0.2 | Exact or loose match |
| Interfaces | 0.1 | Common interfaces |
| Outgoing Calls | 0.4 | Call graph overlap |
| Fields | 0.1 | Field type overlap |
| Name Similarity | 0.2 | Class name similarity |

#### Key Functions

**normalize_type(type_name)**
```python
# Remove generics and package names
# "java.util.List<String>" -> "List"
```

**calculate_structure_score(mainline, target)**
```python
# Returns: float 0.0-1.0 with detailed breakdown
```

**find_best_matches(mainline_data, candidates_data)**
```python
# Returns:
{
    "matches": [best_candidate],
    "score": 0.85,
    "completeness": {
        "total_features": 10,
        "covered": ["METHOD:foo()", ...],
        "missing": ["FIELD:id"],
        "ratio": 0.9
    }
}
```

#### Multi-File Matching
If top match < 60%, attempts to combine multiple targets to achieve feature coverage

---

### EnsembleRetriever

**File**: `/utils/retrieval/ensemble_retriever.py`  
**Size**: 605+ lines

#### Purpose
Multi-strategy file retrieval combining:
1. **Symbol Index**: Tree-sitter method/class extraction
2. **TF-IDF**: Textual similarity (sklearn)
3. **Caching**: Persistent index cache (~/.cache/agents-backend/retrieval/)

#### Initialization
```python
retriever = EnsembleRetriever(
    mainline_repo_path="/path/to/mainline",
    target_repo_path="/path/to/target"
)
```

#### Key Methods

**extract_symbols(code) -> Set[str]**
```python
# Tree-sitter: Extract method/class names from Java code
# Filters: main, toString, equals, hashCode (common noise)
# Returns: {"methodName", "ClassName", ...}
```

**build_index(commit_sha="HEAD")**
```python
# Build/cache symbol index + TF-IDF matrix for target repo
# Caching key: SHA256(repo_path)[:12] + commit_sha
# Optimization: Reads from disk if commit_sha == "HEAD" (skip git show)
# Parallelization: 16 worker threads for file processing
```

**preprocess_tfidf(code) -> str**
```python
# Regex: Remove comments, extract identifier tokens (3+ chars)
# Returns: space-separated tokens for TF-IDF vectorization
```

**find_candidates(file_path, commit_sha) -> List[Dict]**
```python
# Multi-strategy search:
# 1. Symbol index (exact symbols in file)
# 2. TF-IDF cosine similarity
# 3. Path similarity heuristics
# Returns: sorted by composite score, top-10
```

#### Caching Strategy
**Cache Location**: `~/.cache/agents-backend/retrieval/index_<repo_hash>_<commit_sha>.pkl`

**Cache Contents**:
- `target_files`: List of all Java files
- `symbol_index`: Dict[symbol] -> Set[file_indices]
- `symbol_counts`: Dict[symbol] -> count
- `vectorizer`: TfidfVectorizer fitted model
- `target_matrix`: Sparse matrix of TF-IDF scores

**Security**: Hash-based isolation prevents repo path enumeration

---

### PatchAnalyzer

**File**: `/utils/patch_analyzer.py`  
**Size**: 208 lines

#### Purpose
Parse unified diff format into structured data

#### Data Model

```python
@dataclass
class FileChange:
    file_path: str
    change_type: str  # "MODIFIED", "ADDED", "DELETED", "RENAMED"
    added_lines: List[str]
    removed_lines: List[str]
    is_test_file: bool
    previous_file_path: Optional[str]  # for RENAMED
```

#### Key Methods

**parse_diff(diff_text) -> PatchSet**
```python
# Wraps unidiff library parsing
# Returns: PatchSet object with all hunks and files
```

**analyze(diff_text, with_test_changes=False) -> List[FileChange]**
```python
# Structured analysis per file:
# - change_type detection (MODIFIED/ADDED/DELETED/RENAMED)
# - Line collection (added/removed)
# - Test file filtering
# - Previous file path for renames
```

**extract_raw_hunks(diff_text, with_test_changes=False) -> Dict**
```python
# Returns: Dict[file_path] -> List[hunk_strings]
# Each hunk_string is @@ header + context + changes
# Useful for passing individual hunks to LLM without re-parsing
```

**extract_file_only_operations(diff_text) -> List**
```python
# Hunks with no line changes (pure renames, adds, deletes)
# Separate from content-changing hunks
```

#### Test File Detection
```python
# Heuristic: "test" in lower(file_path) or endswith("test.java")
```

---

### FileOperations

**File**: `/utils/file_operations.py`  
**Size**: 298 lines

#### Pattern
CLAW-inspired proven patterns:
- Pre-validation BEFORE mutation
- Exact string matching (no fuzzy)
- Comprehensive structured output
- Line number convention: internal 0-indexed, output 1-indexed

#### Key Functions

**read_file(path, offset=None, limit=None)**
```python
# Returns: (success: bool, TextFilePayload | error_dict)
# TextFilePayload:
{
    "file_path": "/absolute/path/to/file",
    "content": "...",
    "num_lines": 50,
    "start_line": 101,  # 1-indexed for display
    "total_lines": 500
}
```

**edit_file(path, old_string, new_string, replace_all=False)**
```python
# Pre-validation checks:
# 1. Read original file
# 2. Verify old_string exists (exact match)
# 3. Create updated version
# 4. Only THEN write to disk
# 
# Returns: (success: bool, EditFileOutput | error_dict)
# EditFileOutput:
{
    "file_path": "/absolute/path",
    "success": true,
    "old_content": "...",
    "new_content": "...",
    "occurrences_replaced": 1,
    "patch": [StructuredPatchHunk, ...]
}
```

**make_patch(original, updated)**
```python
# CLAW approach: Single hunk for entire file
# Avoids multi-hunk line offset issues
# Returns: List[StructuredPatchHunk] with old_start=1, new_start=1
```

---

### SemanticAdaptationHelper

**File**: `/utils/semantic_adaptation_helper.py`  
**Size**: 561 lines

#### Purpose
Diagnose why anchor text matching failed and suggest recovery strategies

#### Diagnosis Types

```python
class SemanticDiagnosis(Enum):
    METHOD_RENAMED = "method_renamed"
    METHOD_REFACTORED = "method_refactored"
    CLASS_REFACTORED = "class_refactored"
    CODE_MOVED = "code_moved"
    METHOD_SIGNATURE_CHANGED = "method_signature_changed"
    SURROUNDING_CODE_CHANGED = "surrounding_code_changed"
    UNKNOWN = "unknown"
```

#### Severity Levels

```python
class SemanticSeverity(Enum):
    CRITICAL = "critical"  # Anchor completely invalidated
    HIGH = "high"  # Severely degraded
    MEDIUM = "medium"  # Needs adjustment
    LOW = "low"  # Minor style changes
    NONE = "none"  # No change detected
```

#### Result Structure

```python
@dataclass
class SemanticAnalysisResult:
    diagnosis: SemanticDiagnosis
    severity: SemanticSeverity
    confidence: float  # 0.0-1.0
    detected_issues: List[str]
    potential_matches: List[Dict]
    suggested_retry_strategy: Optional[str]
    recovery_actions: List[str]
    evidence: Dict[str, Any]
```

---

## Semantic and Retrieval Helpers

### MCP Client

**File**: `/utils/mcp_client.py`

Provides Language Server Protocol (LSP) access to Java project structure:
- Method definition extraction
- Import resolution
- Type inference
- Inheritance hierarchy

### Method Discovery

**File**: `/utils/method_discovery.py`  
**Size**: 152 lines

#### GitMethodTracer

Traces method evolution through git history using:
- `git log -L` for line history tracing
- `git log -S` (pickaxe) for content-based searching

#### find_moved_method_by_pickaxe()

```python
# Searches git history for when a method appeared/disappeared
# Useful for tracking renamed/moved methods across versions
```

---

## LLM Provider Factory

**File**: `/utils/llm_provider.py`  
**Size**: 318 lines

### Supported Providers

| Provider | Auth Method | Model Examples |
|----------|------------|-----------------|
| OpenAI | OPENAI_API_KEY | gpt-4o-mini, gpt-4 |
| Azure OpenAI | AZURE_ENDPOINT + deployment | gpt-4, gpt-35-turbo |
| Groq | GROQ_API_KEY | mixtral-8x7b-32768 |
| Google Gemini | GOOGLE_API_KEY | gemini-2.0-flash |
| AWS Bedrock | AWS credentials | claude-3-5-sonnet, etc. |
| Custom/Cerebras | OPENAI_BASE_URL | Any OpenAI-compatible |

### Factory Function

```python
def get_llm(
    temperature: float = 0,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> BaseChatModel
```

### Default Configuration
- **Provider**: OpenAI
- **Model**: gpt-4o-mini
- **Temperature**: 0
- **Fallback**: Sequential provider attempts if first fails

### Environment Variables

```bash
# Provider selection
LLM_PROVIDER=openai|azure|groq|google|bedrock|custom

# API keys
OPENAI_API_KEY=sk-...
AZURE_ENDPOINT=https://...
GROQ_API_KEY=gsk_...
GOOGLE_API_KEY=...

# Azure-specific
AZURE_CHAT_DEPLOYMENT=gpt-4
AZURE_CHAT_VERSION=2024-02-01

# AWS Bedrock
AWS_REGION=us-east-1
AWS_PROFILE=default
```

---

## Token Counting

**File**: `/utils/token_counter.py`  
**Size**: 120 lines

### Functions

**count_text_tokens(text, model_name=None) -> int**
```python
# Uses tiktoken if available, fallback: text_length / 4
# Automatically detects model encoding
```

**count_messages_tokens(messages, model_name=None) -> int**
```python
# Process list of message tuples or objects
# Returns: total tokens across all messages
```

**extract_usage_from_response(resp) -> Dict[str, int] | None**
```python
# Extract provider-reported token usage from LLM response
# Handles: response_metadata, usage_metadata
# Returns: {"input_tokens": X, "output_tokens": Y, "total_tokens": Z}
```

**add_usage(total, input_tokens, output_tokens, source) -> None**
```python
# Accumulate token usage from multiple calls
# Tracks source for debugging
```

---

## Data Models

### FileOperationsModels

**File**: `/utils/file_operations_models.py`

```python
@dataclass
class StructuredPatchHunk:
    old_start: int  # 1-indexed line number
    old_lines: int  # Count of lines
    new_start: int
    new_lines: int
    lines: List[str]  # Patch lines with +/- prefix

@dataclass
class TextFilePayload:
    file_path: str
    content: str
    num_lines: int
    start_line: int  # 1-indexed
    total_lines: int

@dataclass
class EditFileOutput:
    file_path: str
    success: bool
    old_content: str
    new_content: str
    occurrences_replaced: int
    patch: List[StructuredPatchHunk]

@dataclass
class HunkContext:
    before: List[str]
    after: List[str]
    surrounding_context: str

@dataclass
class FileOperationResult:
    success: bool
    message: str
    file_path: str
```

### ValidationModels

**File**: `/utils/validation_models.py`

```python
class HunkValidationErrorType(Enum):
    DRY_RUN_FAILED = "dry_run_failed"
    CONTEXT_MISMATCH = "context_mismatch"
    LINE_OFFSET_ERROR = "line_offset_error"
    APPLY_FAILED = "apply_failed"
    SYNTAX_ERROR = "syntax_error"
    COMPILATION_ERROR = "compilation_error"
    MALFORMED_PATCH = "malformed_patch"
    FUZZY_MATCH_FAILED = "fuzzy_match_failed"
    UNKNOWN = "unknown"

@dataclass
class HunkValidationError:
    error_type: HunkValidationErrorType
    message: str
    error_code: Optional[str] = None
    line_number: Optional[int] = None
    context_lines: List[str] = []
    suggestions: List[str] = []
    raw_output: Optional[str] = None
    semantic_analysis: Optional[Dict] = None

@dataclass
class HunkValidationResult:
    hunk_id: str
    is_error: bool
    error: Optional[HunkValidationError] = None
    validation_output: Optional[str] = None
    applied_successfully: bool = False
    line_offset: int = 0

@dataclass
class PatchValidationResult:
    patch_id: str
    target_file: str
    hunks: List[HunkValidationResult] = []
    all_passed: bool = False

@dataclass
class PatchRetryContext:
    patch_id: str
    failed_hunks: List[HunkValidationResult]
    target_file_path: str
    target_file_content: str
    line_offset_adjustments: Dict[str, int] = {}
    assembly_error_messages: List[str] = []
    suggestions_from_phase4: List[str] = []
```

---

## Configuration and Environment

### Standard Environment Variables

```bash
# LLM Configuration
LLM_PROVIDER=openai  # or azure, groq, google, bedrock
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1  # for custom endpoints

# Azure OpenAI
AZURE_ENDPOINT=https://xxx.openai.azure.com/
AZURE_CHAT_DEPLOYMENT=gpt-4
AZURE_CHAT_VERSION=2024-02-01

# Java Configuration
JAVA_HOME=/path/to/java21
JAVA_21_HOME=/path/to/java21
MAVEN_HOME=/path/to/maven

# Retrieval Cache
RETRIEVAL_CACHE_DIR=~/.cache/agents-backend/retrieval

# Phase 0 Caching
PHASE0_CACHE_DIR=./evaluate/full_run/phase0_cache

# Logging
LOG_LEVEL=INFO
```

### .env File Example

```
# LLM Provider
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...

# Java
JAVA_21_HOME=/usr/lib/jvm/java-21-openjdk

# Debugging
VERBOSE=false
SKIP_PHASE_0=false
```

---

## Integration Examples

### Using HunkGeneratorToolkit in Agent 3

```python
from agents.hunk_generator_tools import HunkGeneratorToolkit

toolkit = HunkGeneratorToolkit(target_repo_path="/path/to/target")

# Verify content before editing
content = toolkit.read_file_window("src/Main.java", center_line=50)
print(content)

# Find exact line
matches = toolkit.grep_in_file("src/Main.java", "methodName")
print(matches)

# Apply edit
toolkit.str_replace_in_file(
    "src/Main.java",
    old_string="int x = 10;",
    new_string="int x = 20;",
)

# Generate diff
diff = subprocess.run(["git", "diff", "HEAD"], capture_output=True, text=True)
```

### Using MethodFingerprinter

```python
from utils.method_fingerprinter import MethodFingerprinter

fingerprinter = MethodFingerprinter()

result = fingerprinter.find_match(
    old_method_name="vulnerableMethod",
    old_signature="void vulnerableMethod(String input)",
    old_code="... method body ...",
    old_calls=["validateInput", "processData"],
    candidate_methods=[
        {
            "simpleName": "vulnerableMethod",
            "signature": "void vulnerableMethod(String input)",
            "calls": ["validateInput", "processData"]
        },
        ...
    ]
)

print(f"Match: {result['match']['simpleName']}, Confidence: {result['confidence']}")
```

### Using EnsembleRetriever

```python
from utils.retrieval.ensemble_retriever import EnsembleRetriever

retriever = EnsembleRetriever(
    mainline_repo_path="/path/to/mainline",
    target_repo_path="/path/to/target"
)

# Build index (cached after first run)
retriever.build_index(commit_sha="HEAD")

# Find candidates for a file
candidates = retriever.find_candidates("src/main/java/Security.java", "HEAD")
for cand in candidates[:3]:
    print(f"  {cand['file']}: score={cand['score']}")
```

### Using ValidationToolkit

```python
from agents.validation_tools import ValidationToolkit

toolkit = ValidationToolkit()

# Run tests
result = toolkit.test_and_restore(
    test_classes=["com.example.SecurityTest", "com.example.UtilsTest"]
)

if not result["success"]:
    print(f"Tests failed: {result['test_results']['failed']}")

# Compile
build_result = toolkit.compile_maven(working_dir="/path/to/target")
if build_result["success"]:
    print(f"Build successful (took {build_result['build_time_ms']}ms)")
```

---

## Lessons and Best Practices

### 1. **Tool Naming**
Use verb-noun pattern: `read_file`, `grep_in_file`, not `file_reader`

### 2. **Return Consistency**
All tools return structured data:
```python
Dict with keys: success, error, data, suggestions
```

### 3. **Error Handling**
All tools include try/except with detailed error context:
```python
if old_string not in file_content:
    return {"error": "Anchor not found", "suggestions": [...]}
```

### 4. **Line Numbering**
- **Internal**: 0-indexed (array operations)
- **Output**: 1-indexed (human display)
- Convert consistently at boundaries

### 5. **Caching Strategy**
- Hash-based isolation for security
- Pickle for serialization
- Check before expensive operations

### 6. **Pre-validation Pattern**
Always validate BEFORE mutation:
```python
# CORRECT:
validate() -> if OK, mutate()

# WRONG:
mutate() -> if error, rollback()
```

---

## Performance Considerations

| Operation | Typical Time | Notes |
|-----------|--------------|-------|
| `build_index` (first run) | 5-30s | Depends on repo size, parallelized |
| `build_index` (cached) | <1s | Pickled from ~/.cache |
| `grep_in_file` (large file) | 100-500ms | Regex performance |
| `compile_maven` | 10-60s | Maven build varies |
| `run_spotbugs` | 5-20s | Static analysis |
| LLM tool call overhead | 100-300ms | Serialization + network |

---

## Future Improvements

1. **Streaming Tools**: Support streaming responses for large file reads
2. **Caching Strategies**: LRU cache for frequently accessed files
3. **Parallel Tool Execution**: Run independent tools concurrently
4. **Tool Composition**: Chain tools into higher-level operations
5. **Custom Validators**: Plugin architecture for domain-specific validation

---

