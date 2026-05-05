# Forge — Agentic Build & Debug Pipeline for Systems Code

## Full Project Outline

---

## 1. Project Summary

**Forge** is a multi-agent AI system that takes a C project (such as an xv6 kernel module), runs real static analysis and compilation tools against it, uses an LLM to interpret and prioritize findings, generates patches, and validates those patches in a sandboxed environment — iterating until the code is clean or the system escalates to a human.

The key distinction: **the LLM orchestrates real tools rather than pretending to be one.** The AI interprets, synthesizes, and generates — the actual bug-finding is done by battle-tested analyzers like `cppcheck`, `clang-tidy`, and compiler sanitizers.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit UI                          │
│  Upload .c files → view agent trace → download patches  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Supervisor / Orchestrator                   │
│         (LangGraph state machine + routing)              │
└──┬──────────┬──────────┬──────────┬─────────────────────┘
   │          │          │          │
   ▼          ▼          ▼          ▼
┌──────┐ ┌────────┐ ┌────────┐ ┌──────────┐
│Recon │→│Analysis│→│ Patch  │→│Validation│
│Agent │ │ Agent  │ │ Agent  │ │  Agent   │
└──────┘ └────────┘ └────────┘ └────┬─────┘
                                    │
                         ┌──────────┴──────────┐
                         │  Pass?              │
                         │  YES → Report       │
                         │  NO  → Loop back    │
                         │        to Patch     │
                         │  MAX_RETRIES hit?   │
                         │  → Escalate to user │
                         └─────────────────────┘
```

---

## 3. Team Roles

| Role | Member | Responsibility | Key Tech |
|------|--------|---------------|----------|
| **Orchestrator / UI** | Member 1 | LangGraph state machine, Supervisor routing logic, Streamlit dashboard, state schema design | LangGraph, Streamlit, Python |
| **Tool Agents** | Member 2 | Recon Agent + Analysis Agent: tool integration (cppcheck, clang-tidy, gcc sanitizers, tree-sitter), prompt engineering for interpretation and prioritization | tree-sitter, cppcheck, clang-tidy, LLM prompts |
| **Patch + Validation** | Member 3 | Patch generation agent, Docker sandbox for compilation and testing, feedback loop logic, retry/escalation policy | Docker, gcc, Python subprocess, LLM prompts |

### Parallel Work Strategy

- All three members can work simultaneously from Week 1.
- Member 1 builds the skeleton state machine with stub agents; Members 2 and 3 implement the real agents against that interface.
- Shared contract: each agent is a Python function that takes and returns a `ForgeState` dictionary. Define this schema on Day 1.

---

## 4. Detailed Agent Specifications

### 4.1 Recon Agent

**Purpose:** Parse the uploaded C project and build a structural map so downstream agents have context.

**Inputs:** Raw `.c` and `.h` files uploaded by the user.

**Process:**
1. Use `tree-sitter` (with the C grammar) to parse each file into an AST.
2. Extract: function names, signatures, call relationships, `#include` dependencies, global variables, struct definitions.
3. Build a dependency graph (which function calls which).
4. Identify entry points (e.g., `main()`, syscall handlers in xv6 like `sys_fork`).
5. Estimate complexity: lines per function, cyclomatic complexity (count branch points in the AST).

**Output:** A structured JSON object:
```json
{
  "files": ["proc.c", "proc.h"],
  "functions": [
    {
      "name": "allocproc",
      "file": "proc.c",
      "line_start": 45,
      "line_end": 92,
      "calls": ["kalloc", "memset", "acquire", "release"],
      "called_by": ["fork", "userinit"],
      "complexity": 8,
      "allocations": ["kalloc (line 58)"]
    }
  ],
  "entry_points": ["main", "userinit"],
  "includes": {"proc.c": ["proc.h", "defs.h", "types.h"]},
  "globals": ["ptable", "initproc"]
}
```

**Tech:**
- `tree-sitter` Python bindings + `tree-sitter-c` grammar
- No LLM needed for this agent — it's purely deterministic parsing

**Fallback:** If tree-sitter fails on non-standard syntax (e.g., xv6 macros), fall back to regex-based extraction for function signatures and a warning in the output.

---

### 4.2 Analysis Agent

**Purpose:** Run real static analysis tools, collect their structured output, then use the LLM to interpret, deduplicate, and prioritize findings.

**Inputs:** The original source files + the Recon Agent's structural map.

**Process:**

**Step A — Tool Execution (no LLM):**
Run the following tools and capture their output:

| Tool | What It Finds | Command |
|------|--------------|---------|
| `cppcheck` | Memory leaks, null dereference, buffer overflows, uninitialized vars | `cppcheck --enable=all --xml --output-file=report.xml <files>` |
| `clang-tidy` | Style issues, modernization, bug-prone patterns, cert-c violations | `clang-tidy <files> -checks='*' -- <compile_flags>` |
| `gcc -fsanitize` | Compile with sanitizers and run test input if available | `gcc -fsanitize=address,undefined -g -o test <files>` |

**Step B — LLM Interpretation:**
Feed the raw tool outputs + the Recon dependency graph to the LLM with this prompt structure:

```
You are a C systems expert. Below are static analysis results for a codebase.
Also provided is the function dependency graph.

Your job:
1. Deduplicate findings that refer to the same root cause.
2. Classify each unique finding: [CRITICAL / WARNING / INFO]
3. Prioritize by: severity × reachability (is this function called from an entry point?)
4. For each finding, identify the specific function and line range.
5. Suggest which findings are likely patchable vs. which need human judgment.

Output as JSON.
```

**Output:** Prioritized findings list:
```json
{
  "findings": [
    {
      "id": "F001",
      "severity": "CRITICAL",
      "category": "memory_leak",
      "tool_source": "cppcheck",
      "function": "allocproc",
      "file": "proc.c",
      "lines": [58, 72],
      "description": "kalloc() on line 58 has no corresponding kfree() on the error path at line 72",
      "reachable_from": ["fork", "userinit"],
      "patchable": true
    }
  ],
  "summary": "3 critical, 5 warnings, 12 informational. 2 findings are duplicates across tools."
}
```

---

### 4.3 Patch Agent

**Purpose:** Generate concrete code patches for each patchable finding.

**Inputs:** The prioritized findings list + the original source files + the Recon structural map.

**Process:**
1. For each finding marked `patchable: true`, extract the relevant function's source code.
2. Send to the LLM with this prompt structure:

```
You are patching a C systems codebase. Here is a bug report:

[Finding JSON]

Here is the function source code:

[Extracted function code with line numbers]

Here is the function's call graph context:

[Relevant portion of dependency graph]

Generate a minimal, correct patch. Rules:
- Change as few lines as possible.
- Do not alter function signatures.
- Do not introduce new dependencies.
- Preserve the coding style of the original.
- Output as a unified diff.
```

3. Parse the LLM output into a structured patch object.
4. If the LLM cannot generate a confident patch, mark the finding as `needs_human_review`.

**Output:** List of patches in unified diff format, linked to finding IDs:
```json
{
  "patches": [
    {
      "finding_id": "F001",
      "file": "proc.c",
      "diff": "--- a/proc.c\n+++ b/proc.c\n@@ -70,6 +70,7 @@\n   if(p->pagetable == 0){\n+    kfree((char*)p->kstack);\n     release(&p->lock);\n     return 0;\n   }",
      "confidence": 0.9,
      "explanation": "Added kfree for the kstack allocation before returning on the error path."
    }
  ],
  "deferred": ["F003 — requires understanding of lock ordering, needs human review"]
}
```

---

### 4.4 Validation Agent

**Purpose:** Apply each patch, compile the result, run tests if available, and determine if the patch is safe.

**Inputs:** Original source files + generated patches.

**Process:**

**Step A — Sandbox Setup:**
- Spin up a Docker container with `gcc`, `make`, and sanitizers pre-installed.
- Copy the original source files into the container.
- The container has no network access (security isolation).

**Step B — Per-Patch Validation:**
For each patch:
1. Apply the diff to a fresh copy of the source.
2. Compile: `gcc -Wall -Werror -fsanitize=address,undefined -o test <files>`
3. If the project has a Makefile, use `make` instead.
4. If test inputs are available, run the compiled binary and capture output.
5. Run `cppcheck` again on just the patched function to verify the original finding is gone.
6. Collect: compile success/fail, warnings, sanitizer output, test pass/fail.

**Step C — Verdict:**
```json
{
  "finding_id": "F001",
  "patch_applied": true,
  "compile_success": true,
  "new_warnings": [],
  "sanitizer_clean": true,
  "original_finding_resolved": true,
  "regression_detected": false,
  "verdict": "PASS"
}
```

**On failure:** Package the compiler errors, sanitizer output, and the failed patch, then send back to the Patch Agent for retry.

---

### 4.5 Feedback Loop (Iterative Refinement)

This is the core "agentic" behavior the rubric cares about.

**Loop Logic (managed by the Supervisor in LangGraph):**

```
MAX_RETRIES = 3

for each finding:
    attempt = 0
    while attempt < MAX_RETRIES:
        patch = PatchAgent.generate(finding, previous_errors)
        result = ValidationAgent.validate(patch)
        
        if result.verdict == "PASS":
            accept patch
            break
        else:
            attempt += 1
            previous_errors.append(result)  # feed errors back
    
    if attempt == MAX_RETRIES:
        escalate to human review with full attempt history
```

**What gets fed back on failure:**
- The exact compiler error message
- The sanitizer output (if it compiled but crashed)
- The previous patch attempt (so the LLM doesn't repeat itself)
- A counter: "This is attempt 2 of 3. Previous attempts failed because: ..."

**Logging:** Every iteration is logged with timestamps, inputs, outputs, and token counts. This log becomes the basis for the "agent trace" view in the UI and the results section of the report.

---

## 5. State Schema (LangGraph)

All agents read from and write to a shared state dictionary. This is the contract everyone codes against.

```python
from typing import TypedDict, List, Optional

class ForgeState(TypedDict):
    # Inputs
    source_files: dict[str, str]          # filename → content
    user_description: Optional[str]        # what the code should do
    test_inputs: Optional[list[str]]       # optional test cases
    
    # Recon output
    recon_map: Optional[dict]              # structural map JSON
    
    # Analysis output
    findings: Optional[list[dict]]         # prioritized findings
    
    # Patch + Validation
    patches: list[dict]                    # generated patches
    validation_results: list[dict]         # per-patch verdicts
    
    # Loop tracking
    current_finding_index: int
    current_attempt: int
    max_retries: int                       # default 3
    
    # Final output
    accepted_patches: list[dict]
    escalated_findings: list[dict]
    agent_trace: list[dict]                # full log of every step
```

---

## 6. Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Orchestration | LangGraph | State machine with conditional edges — perfect for the retry loop |
| LLM | OpenAI GPT-4o or Claude via API | Prompt-based interpretation and code generation |
| Parsing | tree-sitter + tree-sitter-c | Fast, accurate AST parsing for C |
| Static Analysis | cppcheck, clang-tidy | Industry-standard, structured output |
| Compilation | gcc with sanitizers | Real compilation validation |
| Sandboxing | Docker (no network) | Isolation for running untrusted compiled code |
| UI | Streamlit | Fast to build, supports real-time updates with `st.status` |
| Language | Python 3.11+ | Everything integrates cleanly |

---

## 7. UI Design (Streamlit)

### Layout

```
┌────────────────────────────────────────────────┐
│  FORGE — Agentic C Code Auditor                │
├────────────────────────────────────────────────┤
│                                                │
│  [Upload .c / .h files]  [Optional: Makefile]  │
│  [Optional: describe what this code does]      │
│  [Optional: upload test inputs]                │
│                                                │
│  [ Run Forge ]                                 │
│                                                │
├────────────────────────────────────────────────┤
│  Agent Trace (real-time)                       │
│  ┌──────────────────────────────────────────┐  │
│  │ ✅ Recon Agent: parsed 4 files,          │  │
│  │    found 12 functions, 3 entry points    │  │
│  │ ✅ Analysis Agent: ran cppcheck +        │  │
│  │    clang-tidy, found 8 issues            │  │
│  │ ⏳ Patch Agent: working on F001...       │  │
│  │ ❌ Validation: F001 patch failed         │  │
│  │    (compile error: implicit declaration) │  │
│  │ ⏳ Patch Agent: retry 2/3 for F001...    │  │
│  │ ✅ Validation: F001 patch PASSED         │  │
│  └──────────────────────────────────────────┘  │
│                                                │
├────────────────────────────────────────────────┤
│  Results                                       │
│  ┌──────────────────────────────────────────┐  │
│  │ Findings: 8 total                        │  │
│  │ Patched successfully: 5                  │  │
│  │ Escalated to human: 2                    │  │
│  │ Informational (no patch needed): 1       │  │
│  │                                          │  │
│  │ [View Diffs] [Download Patched Files]    │  │
│  │ [Download Full Report JSON]              │  │
│  └──────────────────────────────────────────┘  │
└────────────────────────────────────────────────┘
```

### Key Streamlit Features to Use
- `st.file_uploader` for multi-file upload
- `st.status` for the real-time agent trace (shows spinner while running)
- `st.expander` for viewing individual diffs per finding
- `st.code` with `language="diff"` for patch display
- `st.download_button` for patched files and the JSON report

---

## 8. Development Timeline (8-Week Plan)

### Week 1: Foundation
- **All:** Agree on `ForgeState` schema. Set up shared GitHub repo.
- **Member 1:** Scaffold LangGraph state machine with stub agents (each agent just prints "running" and returns dummy state). Get basic Streamlit upload working.
- **Member 2:** Get tree-sitter-c parsing working on a sample `.c` file. Install and test `cppcheck` and `clang-tidy` locally.
- **Member 3:** Create the Docker image (`Dockerfile` with gcc, make, sanitizers). Write a Python wrapper that copies files in, compiles, and captures output.

### Week 2: Individual Agents
- **Member 1:** Implement Supervisor routing logic (Recon → Analysis → Patch → Validation → Loop or Done).
- **Member 2:** Complete Recon Agent (tree-sitter parsing → JSON output). Start Analysis Agent tool runners.
- **Member 3:** Complete Validation Agent (apply diff, compile in Docker, capture results). Define the feedback payload format.

### Week 3: LLM Integration
- **Member 2:** Add LLM interpretation step to Analysis Agent (deduplicate + prioritize).
- **Member 3:** Build the Patch Agent with LLM code generation.
- **Member 1:** Wire real agents into LangGraph. Implement the retry loop conditional edges.

### Week 4: End-to-End
- **All:** First full pipeline run on a simple test case (a `.c` file with a known memory leak).
- Debug integration issues. Ensure state flows correctly between all agents.

### Week 5: Iteration Polish
- Improve prompts based on Week 4 results (this is where most of the quality comes from).
- Add the escalation path for unfixable findings.
- Handle edge cases: files that don't compile at all, files with no findings, huge files.

### Week 6: UI + Logging
- **Member 1:** Build out the Streamlit dashboard with real-time trace, diff viewer, and download buttons.
- **Members 2 & 3:** Add comprehensive logging to every agent. Build the JSON report generator.

### Week 7: Evaluation
- Run Forge against real codebases: your own xv6 labs, MIT 6.1810 lab code, or open-source C projects.
- Collect metrics: findings found, patches generated, patches that passed validation, average retries needed.
- Identify failure modes and document them.

### Week 8: Report + Demo
- Write the project report (problem, design, workflow, results, what we'd do differently).
- Record or prepare a live demo.
- Clean up code, add README, ensure reproducibility.

---

## 9. Test Cases (Start With These)

### Easy (Week 4)
```c
// leak.c — obvious memory leak
#include <stdlib.h>
char* make_buffer() {
    char* buf = malloc(256);
    if (!buf) return NULL;
    // forgot to handle the error path in the caller
    return buf;
}
int main() {
    char* b = make_buffer();
    if (b[0] == 'x') return 1;  // leak: no free(b)
    free(b);
    return 0;
}
```

### Medium (Week 5)
- An xv6 `proc.c` function with a missing `release()` on an error path
- A `.c` file with `strcpy` that should be `strncpy`

### Hard (Week 7)
- A multi-file xv6 module (proc.c + vm.c + kalloc.c) with interacting bugs
- A file where cppcheck finds a false positive and the LLM needs to filter it out

---

## 10. Metrics for the Report

Track and present these in your final report:

| Metric | What It Shows |
|--------|--------------|
| Total findings per tool | How much each analyzer contributes |
| LLM deduplication rate | How many raw findings collapsed into unique issues |
| Patch generation success rate | % of findings that got a valid patch on first attempt |
| Average retries per finding | How much iteration was needed |
| Validation pass rate | % of patches that compiled and passed tests |
| Escalation rate | % of findings the system couldn't handle |
| End-to-end time | Wall clock from upload to final report |
| Token usage per run | Cost awareness |

These metrics let you write sentences like: *"Forge identified 12 unique issues across proc.c and vm.c, successfully patching 9 of them with an average of 1.4 retries per finding."*

---

## 11. Stretch Goals (If You Have Time)

1. **Differential mode:** User uploads before and after versions; Forge audits only the diff.
2. **Learning from retries:** After a successful retry, log what the first attempt got wrong and feed that as few-shot context to future Patch Agent calls.
3. **Custom rules:** Let the user define project-specific rules (e.g., "every `acquire()` must have a matching `release()` in the same function") that the Analysis Agent checks via AST pattern matching.
4. **xv6 integration:** Pre-load the xv6 Makefile and header structure so users can upload just one modified file and Forge handles the build context.
5. **Comparative report:** Show a side-by-side of "cppcheck alone," "LLM alone," and "Forge combined" to demonstrate the value of the hybrid approach.

---

## 12. What Makes This Resume-Worthy

**For systems roles:** You built Docker sandboxing, integrated real compiler toolchains, and worked with AST parsing — not just prompt engineering.

**For AI/ML roles:** You designed a multi-agent system with meaningful state management, tool use, and iterative refinement — the exact pattern used in production AI systems.

**For SWE roles:** Clean architecture, parallel team development with a shared contract, real CI-like validation pipeline.

**For your MIT application specifically:** This demonstrates you can combine systems knowledge (compilers, sanitizers, kernel code) with AI orchestration — exactly the kind of cross-cutting work CSAIL values.

---

## 13. Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| LLM generates patches that compile but introduce new bugs | Re-run cppcheck on patched code; compare sanitizer output before/after |
| tree-sitter chokes on macro-heavy code (xv6) | Fallback to regex parsing; preprocess with `gcc -E` to expand macros |
| Docker adds too much latency per validation | Pre-build the image; keep the container warm between validations rather than creating/destroying each time |
| LLM costs spiral during development | Use GPT-4o-mini or Claude Haiku for iteration during development; switch to the full model for final evaluation runs |
| Scope creep | The MVP is: one file in, findings + patches out. Multi-file support is Week 7, not Week 1 |
