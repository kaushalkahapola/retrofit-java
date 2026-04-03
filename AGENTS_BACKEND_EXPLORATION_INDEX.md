# Agents-Backend Exploration - Documentation Index

**Exploration Date**: April 3, 2026  
**Focus**: Semantic adaptation for "anchor text not found" failures in Phase 3

---

## Quick Navigation

### For Quick Understanding (Start Here)
1. **SEMANTIC_ADAPTATION_QUICK_REFERENCE.md** (269 lines)
   - Problem statement with visual flowcharts
   - Root causes addressed by semantic tools
   - Usage examples for each tool
   - Implementation strategy with code snippets
   - Integration checklist
   - **Read this first for implementation clarity**

### For Deep Technical Understanding
2. **AGENTS_BACKEND_EXPLORATION.md** (670 lines)
   - Complete Phase 3 architecture breakdown
   - Current failure detection mechanisms (4 levels)
   - Error information available at failure point
   - File context APIs (4 categories)
   - Structural Locator (Phase 2) capabilities
   - Consistency Map (symbol renames)
   - Retry mechanisms (3 types)
   - 5 gaps in current implementation
   - 5 injection points for semantic adaptation
   - Table of critical files
   - **Read this for architectural understanding**

---

## What Each Document Covers

### SEMANTIC_ADAPTATION_QUICK_REFERENCE.md
**Audience**: Developers implementing the feature
**Best For**: Implementation roadmap

| Section | Content |
|---------|---------|
| Problem | What "anchor not found" is and why it happens |
| Root Causes | 5 semantic issues not handled by current code |
| Tools | 4 semantic tools with usage examples |
| Implementation | Step-by-step code flow with pseudocode |
| Routing | How to route based on semantic diagnosis |
| Checklist | 8-item integration checklist |
| Impact | Before/after comparison |

**Code Examples Included**:
- MethodFingerprinter usage
- StructuralMatcher usage
- HunkGeneratorToolkit usage
- grep_repo/git_pickaxe usage
- Failure recovery pseudocode
- Router modifications pseudocode

---

### AGENTS_BACKEND_EXPLORATION.md
**Audience**: Architects and explorers
**Best For**: Understanding current system

| Section | Content |
|---------|---------|
| Executive Summary | 3-sentence overview |
| Phase 3 Architecture | Node structure, entry points, contracts |
| Failure Detection | 3 failure paths with code locations |
| Error Information | Structured error models + available context |
| File Context APIs | 4 categories of APIs with descriptions |
| Structural Locator | Phase 2 mapping pipeline + LLM tools |
| Consistency Map | Symbol rename tracking + application |
| Retry Mechanisms | 3 retry strategies |
| What's Missing | 4 gaps + what to leverage |
| Injection Points | 5 specific locations with descriptions |
| Proposed Flow | High-level semantic adaptation flow |
| Utilities | Organized by use case |
| Key Findings | 5 summary statements |
| File Table | All critical files with line ranges |

**File References**:
- All absolute paths to critical files
- Line number ranges for key functions
- Structured organization by purpose

---

## Files Created This Session

```
/media/kaushal/FDrive/retrofit-java/
├── AGENTS_BACKEND_EXPLORATION.md               [670 lines]
│   └── Comprehensive technical analysis
├── SEMANTIC_ADAPTATION_QUICK_REFERENCE.md      [269 lines]
│   └── Implementation-focused guide
└── AGENTS_BACKEND_EXPLORATION_INDEX.md         [This file]
    └── Navigation guide
```

---

## Key Absolute Paths in Codebase

### Phase 3 (Current - File Editor)
```
/media/kaushal/FDrive/retrofit-java/agents-backend/src/agents/file_editor.py
  - _apply_edit_deterministically() [Lines 192-384]  ← Anchor resolution
  - _retry_with_file_check() [Lines 409-492]        ← Semantic injection point
```

### Phase 2 (Mapping)
```
/media/kaushal/FDrive/retrofit-java/agents-backend/src/agents/structural_locator.py
  - _deterministic_map_hunks_for_file() [471-527]   ← Where confidence is computed
  - _realign_mapping_to_target() [311-397]
```

### Semantic Tools
```
/media/kaushal/FDrive/retrofit-java/agents-backend/src/utils/method_fingerprinter.py
  - 4-tier method matching algorithm

/media/kaushal/FDrive/retrofit-java/agents-backend/src/utils/structural_matcher.py
  - Class-level structure comparison

/media/kaushal/FDrive/retrofit-java/agents-backend/src/agents/hunk_generator_tools.py
  - File reading & verification APIs

/media/kaushal/FDrive/retrofit-java/agents-backend/src/agents/reasoning_tools.py
  - grep_repo, git_pickaxe, git_log_follow
```

### Pipeline & Error Models
```
/media/kaushal/FDrive/retrofit-java/agents-backend/src/graph.py
  - route_validation() [Lines 68-163]               ← Router logic

/media/kaushal/FDrive/retrofit-java/agents-backend/src/utils/validation_models.py
  - HunkValidationError [Lines 48-60]               ← Error structure
  - HunkValidationResult [Lines 64-94]
```

---

## Core Concepts

### Phase 3 Failure Modes
1. **Anchor not found** → No exact match in target file
2. **Context mismatch** → Surrounding lines don't match
3. **Line offset error** → Line numbers out of range
4. **Syntax error** → Malformed diff

### What Semantic Adaptation Solves
1. **Renamed methods** → MethodFingerprinter detects via structure
2. **Refactored code** → StructuralMatcher scores similarity
3. **Code moved** → grep_repo finds in other files
4. **History changes** → git_pickaxe traces renames

### Key State Fields
- `anchor_confidence`: HIGH/MEDIUM/LOW (Phase 2)
- `anchor_reason`: Why confidence is that level
- `semantic_analysis`: Fingerprint/grep/history results
- `semantic_diagnosis`: Code moved/renamed/equivalent/unknown

---

## Implementation Roadmap

### Phase 1: Setup (1-2 days)
- [ ] Create semantic_adaptation_helper.py
- [ ] Wrap MethodFingerprinter for Phase 3 use
- [ ] Test basic fingerprinting on sample methods

### Phase 2: Integrate (2-3 days)
- [ ] Modify file_editor.py anchor failure handling
- [ ] Add semantic analysis before giving up
- [ ] Record results in validation error

### Phase 3: Route (1-2 days)
- [ ] Enhance validation_models.py with semantic_analysis field
- [ ] Modify graph.py router for semantic diagnosis
- [ ] Add routing: code_moved → structural_locator

### Phase 4: Propagate (1 day)
- [ ] Ensure Phase 2 computes anchor_confidence
- [ ] Pass confidence to Phase 3 via state
- [ ] Use confidence to decide strategy

### Phase 5: Test & Validate (2-3 days)
- [ ] Create test cases with refactored code
- [ ] Validate fingerprinter accuracy
- [ ] Test routing decisions
- [ ] Measure improvement in retry reduction

---

## Key Insights

### Architecture Strengths
- Excellent deterministic anchor matching (4-pass)
- Clean separation of concerns (Phase 2 maps, Phase 3 applies)
- Structured error models with suggestions
- Extensible retry loop with routing

### Current Weaknesses
- No semantic understanding at failure point
- Retry without structural analysis
- Phase 2 confidence not used in Phase 3
- Limited error context for diagnosis

### Opportunities
- 4 semantic tools already exist but unused in Phase 3
- Method fingerprinter has proven 4-tier algorithm
- File APIs can verify before committing
- Full-repo search can detect code movement

---

## Success Metrics

### Before Implementation
- "Anchor not found" → blind retry (3+ attempts)
- No semantic insight into divergence
- Same retry strategy for all failures

### After Implementation
- "Anchor not found" → semantic analysis (<100ms)
- Detect specific causes (renamed/refactored/moved)
- Route to correct agent (remap vs. retry)
- Reduce redundant retry attempts

---

## Questions Answered by This Exploration

1. **What happens when anchor text not found?**
   - See: AGENTS_BACKEND_EXPLORATION.md / Anchor Resolution Failures

2. **What error information is captured?**
   - See: AGENTS_BACKEND_EXPLORATION.md / Error Information Captured at Failure Point

3. **What semantic tools exist?**
   - See: SEMANTIC_ADAPTATION_QUICK_REFERENCE.md / Semantic Tools Available

4. **Where can we inject semantic analysis?**
   - See: AGENTS_BACKEND_EXPLORATION.md / Injection Points for Semantic Adaptation

5. **How do we implement this?**
   - See: SEMANTIC_ADAPTATION_QUICK_REFERENCE.md / Implementation Strategy

6. **What files do we need to modify?**
   - See: SEMANTIC_ADAPTATION_QUICK_REFERENCE.md / Key Files to Modify

7. **What's the current retry loop?**
   - See: AGENTS_BACKEND_EXPLORATION.md / Retry Mechanisms

8. **How does Phase 2 mapping work?**
   - See: AGENTS_BACKEND_EXPLORATION.md / Structural Locator (Phase 2)

---

## Document Statistics

| Document | Lines | Size | Focus |
|----------|-------|------|-------|
| AGENTS_BACKEND_EXPLORATION.md | 670 | 24KB | Architecture & Analysis |
| SEMANTIC_ADAPTATION_QUICK_REFERENCE.md | 269 | 8.8KB | Implementation Guide |
| Total | 939 | 33KB | Complete Picture |

---

## Usage Recommendations

### For Quick Start (30 minutes)
1. Read: SEMANTIC_ADAPTATION_QUICK_REFERENCE.md (full)
2. Skim: AGENTS_BACKEND_EXPLORATION.md / "5 Injection Points"
3. Reference: Key absolute paths above

### For Implementation (2-3 hours)
1. Read: SEMANTIC_ADAPTATION_QUICK_REFERENCE.md / Implementation Strategy
2. Read: AGENTS_BACKEND_EXPLORATION.md / Failure Detection paths
3. Code locations: Use absolute paths from both documents
4. Integration checklist: Follow step-by-step

### For Architecture Review (1-2 hours)
1. Read: AGENTS_BACKEND_EXPLORATION.md / Executive Summary
2. Read: AGENTS_BACKEND_EXPLORATION.md / Phase 3 Architecture
3. Reference: File table for critical locations
4. Understand: Current retry mechanisms

---

## Last Updated
April 3, 2026 at 21:26 UTC

---

**Navigation**: 
- [← Back to AGENTS_BACKEND_EXPLORATION.md](AGENTS_BACKEND_EXPLORATION.md)
- [← Back to SEMANTIC_ADAPTATION_QUICK_REFERENCE.md](SEMANTIC_ADAPTATION_QUICK_REFERENCE.md)

