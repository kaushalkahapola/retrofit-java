# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**retrofit-java** is an AI-powered Java patch backporting tool. Given a security patch applied to a mainline Java repo, the system automatically adapts and applies it to an older target repository. It combines deterministic Java AST analysis with a multi-agent LLM pipeline.

## Repository Structure

```
agents-backend/     # Python/LangGraph multi-agent orchestration pipeline
analysis-engine/    # Java/Spring Boot service exposing AST tools via MCP
vscode-extension/   # TypeScript VS Code extension (UI layer, currently skeleton)
docs/               # Architecture and implementation documentation
datasets/           # Test datasets
evaluate/           # End-to-end and per-phase evaluation scripts (inside agents-backend)
temp_repo_storage/  # Cached test repositories (elasticsearch, druid, crate, opencode)
```

## Key Commands

### agents-backend (Python)

```bash
cd agents-backend

# Install dependencies
pip install -r requirements.txt

# Run the pipeline
python src/main.py \
  --mainline-commit <hash> \
  --mainline-repo /path/to/mainline \
  --target-repo /path/to/target

# Run all tests
pytest tests/

# Run a specific test file
pytest tests/test_hunk_generator.py -v

# Run a single test by name
pytest -k "test_extract_hunk_block"

# Run evaluation
python evaluate/full_run/evaluate_full_workflow.py
```

### analysis-engine (Java)

```bash
cd analysis-engine

# Build
mvn clean package -DskipTests

# Run (required before agents-backend)
mvn spring-boot:run
# OR
java -jar target/analysis-engine-0.0.1-SNAPSHOT.jar
```

### vscode-extension (TypeScript)

```bash
cd vscode-extension
npm install
npm run watch       # Dev mode
npm run package     # Production build
npm run lint
npm run check-types
```

### Docker Compose

```bash
docker-compose up --build   # Start all services
docker-compose down
```

## Agent Pipeline Architecture

The pipeline is orchestrated via LangGraph (`agents-backend/src/graph.py`). The state flows through agents defined in `src/agents/`. Agent state schema is in `src/state.py`.

**Execution flow:**

```
Phase 0 (Optimistic): Try direct git apply
    └─ Success → done
    └─ Failure ↓

Agent 1 (Context Analyzer): Reads mainline patch → SemanticBlueprint
    ↓
Agent 2 (Structural Locator): Maps mainline symbols to target repo → ConsistencyMap + MappedTargetContext
    ↓
Planning Agent: Converts context into concrete edit instructions → HunkGenerationPlan
    ↓
Agent 3 (File Editor): Applies str_replace edits using exact string matching (CLAW approach)
    ↓
Agent 4 (Validation Agent): Compiles + runs tests → ValidationResult
    └─ Pass → done
    └─ Fail → Reasoning Architect → back to Planning Agent (up to 3 retries)
```

## Key Source Files

| File | Role |
|------|------|
| `agents-backend/src/graph.py` | LangGraph graph definition, routing logic |
| `agents-backend/src/state.py` | `AgentState` and all intermediate artifact types |
| `agents-backend/src/main.py` | CLI entry point |
| `agents-backend/src/agents/context_analyzer.py` | Phase 1 agent |
| `agents-backend/src/agents/structural_locator.py` | Phase 2 agent |
| `agents-backend/src/agents/file_editor.py` | Phase 3 agent (str_replace edits) |
| `agents-backend/src/agents/validation_agent.py` | Phase 4 agent |
| `agents-backend/src/agents/planning_agent.py` | Edit instruction planner |
| `agents-backend/src/agents/reasoning_architect.py` | Failure recovery planner |
| `agents-backend/src/utils/patch_analyzer.py` | Parses git diffs into structured `FileChange`/hunk objects |
| `agents-backend/src/utils/validation_tools.py` | Compilation, test execution, patch application |
| `agents-backend/src/utils/llm_provider.py` | LLM abstraction (OpenAI, Azure, Groq, Google, Cerebras) |

## Configuration

Copy `agents-backend/.env.example` to `agents-backend/.env` and set:
- `LLM_PROVIDER` — one of: `openai`, `azure`, `groq`, `google`, `cerebras`
- `LLM_MODEL` — e.g. `gpt-4o-mini`
- Corresponding API key (`OPENAI_API_KEY`, etc.)
- `MCP_SERVER_URL` — default: `http://localhost:8080/mcp/sse` (analysis-engine)

The analysis-engine must be running before the agents-backend pipeline can execute.

## Known Architecture Notes

- **File operations (rename/delete with no hunks)**: `patch_analyzer.py` detects renames correctly but `extract_raw_hunks()` skips files without hunks. This means rename-only operations are silently dropped from the adapted patch. See `MEMORY.md` for the tracked fix approach.
- **File Editor uses CLAW-style exact string matching**: edits are applied via `str_replace` (exact old→new replacement), not hunk offsets. Diffs are generated via `git diff HEAD` after applying edits.
- **Validation retry loop**: up to `MAX_VALIDATION_ATTEMPTS=3` in the validation agent. On failure, Reasoning Architect diagnoses and Planning Agent re-plans.
- **Phase 0 fast path**: attempts `git apply` directly before invoking any LLM agents; succeeds for trivial patches.
- **Pytest config**: set in `agents-backend/pyproject.toml`, `asyncio_mode = "auto"`.
