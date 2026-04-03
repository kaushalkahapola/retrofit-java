# H-MABS Documentation Index

**Last Updated**: April 3, 2026  
**Total Documentation**: 5 comprehensive guides  
**Total Size**: ~150KB of analysis  

---

## Quick Navigation

This index provides a map to all H-MABS documentation created during the analysis phase.

---

## Documents Created

### 1. AGENT_ARCHITECTURE_ANALYSIS.md
**Purpose**: Deep dive into the agent system architecture  
**Size**: ~30KB  
**Audience**: Engineers wanting to understand the agent logic  
**Key Sections**:
- Complete description of all 7 agents (Phase 0, 1-4, Planning, SemanticAdapter)
- Detailed data flow between agents
- LLM integration points with system prompts
- Retry logic and error recovery
- Current limitations and failure modes
- Tool integration for each agent

**When to read**: First pass - understand the overall system

---

### 2. ARCHITECTURE_SUMMARY.txt
**Purpose**: Quick visual reference guide  
**Size**: ~16KB  
**Audience**: Quick lookup for busy engineers  
**Key Sections**:
- Executive summary of architecture
- Agent roles and responsibilities (one-liner)
- Data flow diagram
- Key statistics (token usage, recursion limits, etc.)
- Failure routing table
- Component checklist

**When to read**: For quick context before diving into code

---

### 3. TOOLS_AND_UTILITIES_ANALYSIS.md
**Purpose**: Complete reference for all tools and utility modules  
**Size**: ~50KB  
**Audience**: Engineers implementing new features or debugging tools  
**Key Sections**:
- Tool suite overview (HunkGeneratorToolkit, ReasoningToolkit, ValidationToolkit)
- All 18+ tools with signatures and examples
- Utility modules (MethodFingerprinter, StructuralMatcher, EnsembleRetriever, etc.)
- Data models and validation structures
- Configuration and environment setup
- Integration examples
- Performance considerations
- Best practices and lessons learned

**When to read**: Before implementing agent tools or debugging tool behavior

---

### 4. PIPELINE_EXECUTION_FLOW.md
**Purpose**: End-to-end execution guide with real examples  
**Size**: ~40KB  
**Audience**: Engineers debugging pipeline failures or extending phases  
**Key Sections**:
- Complete pipeline flow diagram
- Phase 0 (Fast-path) algorithm with cache logic
- Phase 1 (Context) deterministic blueprint extraction
- Phase 2 (Structural) 2-phase mapping with deterministic+LLM
- Phase 2.5 (Planning) anchor verification and adaptation
- Phase 3 (File Editor) direct edits and diff generation
- Phase 4 (Validation) 6-phase validation loop
- Smart retry routing with failure categorization
- State flow diagram (AgentState fields)
- Real-world CVE backport example (XXE vulnerability)
- Key design patterns and lessons

**When to read**: When debugging failed backports or extending pipeline logic

---

### 5. DOCUMENTATION_INDEX.md (this file)
**Purpose**: Navigation guide for all documentation  
**Size**: ~10KB  
**Audience**: Everyone  

---

## How to Use This Documentation

### I want to understand the system overview
1. Read: **ARCHITECTURE_SUMMARY.txt** (5 min)
2. Read: **AGENT_ARCHITECTURE_ANALYSIS.md** - sections 1-3 (20 min)

### I'm debugging a failed backport
1. Read: **PIPELINE_EXECUTION_FLOW.md** - "Retry Logic & Routing" section (10 min)
2. Check the failure category in validation results
3. Follow the routing table to understand which agent to re-run
4. Read relevant agent section in **AGENT_ARCHITECTURE_ANALYSIS.md**

### I'm implementing a new tool
1. Read: **TOOLS_AND_UTILITIES_ANALYSIS.md** - relevant toolkit section (15 min)
2. Look at integration examples at the end
3. Study similar existing tool in source code
4. Follow "Lessons and Best Practices" section

### I'm extending an agent
1. Read: **AGENT_ARCHITECTURE_ANALYSIS.md** - relevant agent section (15 min)
2. Read: **PIPELINE_EXECUTION_FLOW.md** - relevant phase section (15 min)
3. Check **TOOLS_AND_UTILITIES_ANALYSIS.md** for available tools
4. Review system prompts in the agent source code

### I need to understand LLM integration
1. Read: **AGENT_ARCHITECTURE_ANALYSIS.md** - "LLM Integration Points" table (5 min)
2. Read: **TOOLS_AND_UTILITIES_ANALYSIS.md** - "LLM Provider Factory" (5 min)
3. Check the relevant agent's system prompt in **AGENT_ARCHITECTURE_ANALYSIS.md**

### I'm optimizing token usage
1. Read: **AGENT_ARCHITECTURE_ANALYSIS.md** - "LLM Integration Points" (5 min)
2. Read: **TOOLS_AND_UTILITIES_ANALYSIS.md** - "Token Counting" section (5 min)
3. Look at specific agent prompts in **AGENT_ARCHITECTURE_ANALYSIS.md**

---

## Key Concepts Map

### Core Concepts

| Concept | Definition | Primary Doc | Key File |
|---------|-----------|------------|----------|
| Semantic Blueprint | Fix intent + critical APIs + affected imports | Architecture Summary | context_analyzer.py |
| Consistency Map | Symbol name mappings (renames) | Agent Architecture | structural_locator.py |
| Anchor Verification | 4-pass algorithm to find exact code location | Pipeline Flow | planning_agent.py |
| str_replace Plan | Atomic edit description (old_string->new_string) | Pipeline Flow | planning_agent.py |
| Adapted Hunk | Machine-generated diff from git | Pipeline Flow | file_editor.py |
| Validation Phases | 6-step "Prove Red, Make Green" loop | Pipeline Flow | validation_agent.py |

### Tools

| Tool Suite | Purpose | Doc | Key File |
|-----------|---------|-----|----------|
| HunkGeneratorToolkit | File manipulation for Agent 3 | Tools & Utilities | hunk_generator_tools.py |
| ReasoningToolkit | Repository search for Agent 2 | Tools & Utilities | reasoning_tools.py |
| ValidationToolkit | Test/compile/analyze for Agent 4 | Tools & Utilities | validation_tools.py |
| EnsembleRetriever | Multi-strategy file search | Tools & Utilities | ensemble_retriever.py |
| MethodFingerprinter | Method matching across versions | Tools & Utilities | method_fingerprinter.py |
| StructuralMatcher | Class matching by features | Tools & Utilities | structural_matcher.py |

### Failure Routing

| Failure Category | Root Cause | Route | Purpose |
|------------------|-----------|-------|---------|
| path_or_file_operation | File moved/renamed in target | Phase 2 | Re-map files |
| context_mismatch | Anchor text not found | Phase 2.5 | Re-verify anchors |
| api_mismatch | API signature changed | Phase 2.5 | Semantic adaptation |
| generation_contract_failed | Invalid generated code | Phase 2.5 | Restructure plan |
| empty_generation | No code generated | Phase 2.5 | Re-plan |
| hunk_application_failed | Patch won't apply | Phase 3 | Retry editing |

---

## Frequently Asked Questions

### Q: Where are the system prompts documented?
**A**: In **AGENT_ARCHITECTURE_ANALYSIS.md** under "LLM Integration Points" section. Each agent's system prompt is quoted in full.

### Q: How does the retry loop work?
**A**: Explained in **PIPELINE_EXECUTION_FLOW.md** under "Retry Logic & Routing" section. The routing table shows which agent to re-run based on failure category.

### Q: What's the difference between Phase 2 and Phase 2.5?
**A**: 
- **Phase 2 (Structural Locator)**: Maps files and extracts context
- **Phase 2.5 (Planning Agent)**: Verifies anchors and creates edit plans
Read both sections in **PIPELINE_EXECUTION_FLOW.md**

### Q: How do tools avoid infinite loops?
**A**: 
- Phase 2: Max 18 recursions
- Phase 2.5: Max 100 recursions
- Phase 3: Max 100 recursions
- Identical patch guard: Detects when generated patch is identical to previous attempt
See **AGENT_ARCHITECTURE_ANALYSIS.md** - "Recursion Limits" table

### Q: What's the Semantic Hunk Adapter?
**A**: Special fallback when anchor verification fails. Called from Planning Agent when confidence drops below 0.6. Detailed in **AGENT_ARCHITECTURE_ANALYSIS.md** - "SemanticHunkAdapter Details" section.

### Q: How are tokens counted?
**A**: Explained in **TOOLS_AND_UTILITIES_ANALYSIS.md** under "Token Counting" section. Uses tiktoken if available, fallback: text_length / 4.

### Q: What's the Phase 0 cache strategy?
**A**: Phase 0 results are cached to ~/.cache/agents-backend/retrieval/. Reusability checks in **PIPELINE_EXECUTION_FLOW.md** - "Phase 0" section.

### Q: How does the file editor generate diffs?
**A**: It applies str_replace edits directly, then runs `git diff` to produce mechanically correct unified diffs. Detailed in **PIPELINE_EXECUTION_FLOW.md** - "Phase 3" section.

---

## Document Cross-References

### AGENT_ARCHITECTURE_ANALYSIS.md references
- Tools details → TOOLS_AND_UTILITIES_ANALYSIS.md
- Execution flow → PIPELINE_EXECUTION_FLOW.md
- System prompts → Look in agent source files

### TOOLS_AND_UTILITIES_ANALYSIS.md references
- Agent integration → AGENT_ARCHITECTURE_ANALYSIS.md
- Usage examples → PIPELINE_EXECUTION_FLOW.md (CVE example)
- Configuration → TOOLS_AND_UTILITIES_ANALYSIS.md - "Configuration and Environment"

### PIPELINE_EXECUTION_FLOW.md references
- Tool details → TOOLS_AND_UTILITIES_ANALYSIS.md
- Agent logic → AGENT_ARCHITECTURE_ANALYSIS.md
- Failure routing → AGENT_ARCHITECTURE_ANALYSIS.md - "Retry Logic"

### ARCHITECTURE_SUMMARY.txt references
- Detailed sections → AGENT_ARCHITECTURE_ANALYSIS.md
- Tool details → TOOLS_AND_UTILITIES_ANALYSIS.md
- Flow details → PIPELINE_EXECUTION_FLOW.md

---

## Code File Reference

### Agent Implementation Files
- `/agents/phase0_optimistic.py` - Phase 0 fast-path
- `/agents/context_analyzer.py` - Phase 1 (Agent 1)
- `/agents/structural_locator.py` - Phase 2 (Agent 2)
- `/agents/planning_agent.py` - Phase 2.5 (Planning)
- `/agents/semantic_hunk_adapter.py` - Semantic recovery
- `/agents/file_editor.py` - Phase 3 (Agent 3)
- `/agents/validation_agent.py` - Phase 4 (Agent 4)

### Tool Implementation Files
- `/agents/hunk_generator_tools.py` - HunkGeneratorToolkit
- `/agents/reasoning_tools.py` - ReasoningToolkit
- `/agents/validation_tools.py` - ValidationToolkit

### Utility Module Files
- `/utils/method_fingerprinter.py` - Method matching
- `/utils/structural_matcher.py` - Class matching
- `/utils/retrieval/ensemble_retriever.py` - File retrieval
- `/utils/patch_analyzer.py` - Diff parsing
- `/utils/file_operations.py` - File mutations
- `/utils/semantic_adaptation_helper.py` - Semantic diagnosis
- `/utils/llm_provider.py` - LLM factory
- `/utils/token_counter.py` - Token counting
- `/utils/validation_models.py` - Error/result types

### Infrastructure Files
- `/graph.py` - LangGraph orchestration
- `/state.py` - AgentState schema
- `/main.py` - Entry point

---

## Quick Cheat Sheets

### Agent Roles
```
Phase 0: Try git apply --check (deterministic, no LLM)
Phase 1: Extract semantic blueprint (deterministic, no LLM)
Phase 2: Map files + symbols (deterministic + ReAct fallback)
Phase 2.5: Verify anchors + create plans (ReAct + SemanticAdapter)
Phase 3: Apply edits + generate diffs (ReAct)
Phase 4: Validate (6-phase loop)
```

### LLM Recursion Limits
```
Agent 2:  18 max (prevent tool loop infinities)
Agent 2.5: 100 max (complex anchor recovery)
Agent 3:  100 max (complex hunk generation)
Agent 4:  N/A (direct call, no ReAct)
```

### Common Failure Routes
```
"file moved" → Phase 2 (re-map)
"anchor not found" → Phase 2.5 (re-verify)
"API signature changed" → Phase 2.5 (semantic adapt)
"patch won't apply" → Phase 3 (retry editing)
```

---

## Glossary

| Term | Definition |
|------|-----------|
| **Anchor** | Text snippet used to locate insertion point in target file |
| **Consistency Map** | Dictionary mapping symbol names (methods, classes) from mainline to target |
| **Hunk** | A single contiguous code change in a patch (unified diff @@ block) |
| **Mainline** | Source repository containing the patch to backport |
| **Phase** | Major stage in the pipeline (0-4) |
| **ReAct** | Reasoning + Acting pattern for LLM with tools (think, use tools, observe, repeat) |
| **Semantic Adaptation** | Recovery strategy for API/signature mismatches using intent + context |
| **str_replace Plan** | Atomic edit: find old_string, replace with new_string |
| **Target** | Destination repository where patch is being applied |
| **Validation** | 6-phase loop verifying patch correctness (prove vulnerability exists, apply fix, verify it works) |

---

## Statistics

### Documentation
- **Total Files**: 5 (this index + 4 guides)
- **Total Size**: ~150KB
- **Total Lines**: ~4000
- **Code Examples**: 50+
- **Diagrams**: 5+
- **Tables**: 40+

### H-MABS System
- **Agents**: 7 (Phase 0, 1-4, Planning, Semantic Adapter)
- **Tools**: 18+
- **Utility Modules**: 10+
- **System Prompts**: 8+
- **Data Models**: 20+
- **Configuration Variables**: 15+

---

## Contributing to Documentation

When making changes to the codebase:

1. **Updated an agent**: Update corresponding section in **AGENT_ARCHITECTURE_ANALYSIS.md**
2. **Added a tool**: Update relevant toolkit section in **TOOLS_AND_UTILITIES_ANALYSIS.md**
3. **Changed pipeline flow**: Update **PIPELINE_EXECUTION_FLOW.md**
4. **Modified retry logic**: Update routing table in both **AGENT_ARCHITECTURE_ANALYSIS.md** and **PIPELINE_EXECUTION_FLOW.md**
5. **Changed LLM configuration**: Update **TOOLS_AND_UTILITIES_ANALYSIS.md** - "LLM Provider Factory"

---

## Support and Questions

For questions about:
- **Architecture**: Read AGENT_ARCHITECTURE_ANALYSIS.md first
- **Implementation**: Read TOOLS_AND_UTILITIES_ANALYSIS.md
- **Debugging**: Read PIPELINE_EXECUTION_FLOW.md - "Retry Logic" section
- **Configuration**: Read TOOLS_AND_UTILITIES_ANALYSIS.md - "Configuration" section
- **Quick lookup**: Use ARCHITECTURE_SUMMARY.txt

---

## Document Maintenance

Last comprehensive update: April 3, 2026
- Architecture: Fully documented (all 7 agents, complete data flow)
- Tools: Fully documented (18+ tools, all utility modules)
- Pipeline: Fully documented (all phases, retry logic, example trace)
- Configuration: Documented (environment variables, LLM providers)

---

