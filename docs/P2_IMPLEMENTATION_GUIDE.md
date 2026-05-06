# P2 Implementation Guide — Tool Agents (Recon + Analysis)

You own two files: `forge/agents/recon.py` and `forge/agents/analysis.py`.
Both are stubs right now. This guide tells you exactly what to build, in what
order, and how to test each piece.

---

## Setup checklist

```bash
cd /Users/saaketk/VSCProjects/Forge
git checkout P2-Tool-Agents
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in ANTHROPIC_API_KEY
pytest                          # should pass with stubs
```

Tools you need (already installed on your machine):
- `cppcheck` → v2.20.0 at `/opt/homebrew/bin/cppcheck`
- `clang-tidy` → at `/opt/homebrew/opt/llvm/bin/clang-tidy`
  (needs flag: `-- -isysroot $(xcrun --show-sdk-path)`)
- `tree-sitter` + `tree-sitter-c` → installed in venv

---

## Part 1: Recon Agent (`forge/agents/recon.py`)

### What it does

Takes `state["source_files"]` (a dict of `{filename: content}`) and produces
`state["recon_map"]` — a JSON object describing the code structure. This is
purely deterministic; **no LLM needed**.

### Target output shape

```json
{
  "files": ["leak.c"],
  "functions": [
    {
      "name": "make_buffer",
      "file": "leak.c",
      "line_start": 7,
      "line_end": 11,
      "signature": "char * make_buffer(void)",
      "calls": ["malloc"],
      "called_by": ["main"],
      "complexity": 2
    },
    {
      "name": "main",
      "file": "leak.c",
      "line_start": 13,
      "line_end": 19,
      "signature": "int main(void)",
      "calls": ["make_buffer", "free"],
      "called_by": [],
      "complexity": 3
    }
  ],
  "entry_points": ["main"],
  "includes": {"leak.c": ["stdlib.h"]},
  "globals": []
}
```

### Step-by-step

#### Step 1 — Parse files into ASTs

```python
import tree_sitter_c as tsc
import tree_sitter as ts

C_LANGUAGE = ts.Language(tsc.language())

def _parse(source_bytes: bytes) -> ts.Tree:
    parser = ts.Parser(C_LANGUAGE)
    return parser.parse(source_bytes)
```

#### Step 2 — Extract function definitions

Walk the AST's top-level children. A function lives under a
`function_definition` node. The structure looks like:

```
function_definition
  ├── primitive_type           → return type ("int", "char", etc.)
  ├── function_declarator      → name + params (simple case: int main)
  │   ├── identifier           → function name
  │   └── parameter_list
  ├── pointer_declarator       → name + params (pointer return: char* foo)
  │   ├── *
  │   └── function_declarator
  │       ├── identifier       → function name
  │       └── parameter_list
  └── compound_statement       → body { ... }
```

**Key gotcha:** When the return type is a pointer (`char*`), the function name
is nested one level deeper under `pointer_declarator → function_declarator →
identifier`. You need to handle both cases.

```python
def _find_function_name(node):
    """Dig into function_definition to find the function name identifier."""
    for child in node.children:
        if child.type == "function_declarator":
            for c in child.children:
                if c.type == "identifier":
                    return c.text.decode()
        if child.type == "pointer_declarator":
            return _find_function_name(child)  # recurse into it
    return None
```

To get the full signature, grab the text from the start of the
`function_definition` node up to (but not including) the `compound_statement`:

```python
def _get_signature(func_node, source_bytes):
    body = None
    for child in func_node.children:
        if child.type == "compound_statement":
            body = child
            break
    if body:
        return source_bytes[func_node.start_byte:body.start_byte].decode().strip()
    return source_bytes[func_node.start_byte:func_node.end_byte].decode().strip()
```

#### Step 3 — Extract function calls (who calls whom)

Inside each function's `compound_statement`, recursively walk the subtree and
collect every `call_expression` node. The first child of a `call_expression`
is typically an `identifier` — that's the callee name.

```python
def _collect_calls(node):
    calls = set()
    if node.type == "call_expression":
        callee = node.children[0]
        if callee.type == "identifier":
            calls.add(callee.text.decode())
    for child in node.children:
        calls |= _collect_calls(child)
    return calls
```

After you've collected calls for every function, build the reverse map
(`called_by`) by iterating all functions and checking whose `calls` list
contains each function name.

#### Step 4 — Extract `#include` dependencies

Top-level `preproc_include` nodes contain a child of type `string_literal`
(for `"header.h"`) or `system_lib_string` (for `<stdlib.h>`). Collect them
per file.

```python
if node.type == "preproc_include":
    for child in node.children:
        if child.type in ("string_literal", "system_lib_string"):
            header = child.text.decode().strip('"<>')
```

#### Step 5 — Identify entry points

Scan the function list for known entry points:
- `main`
- xv6 syscall handlers: anything starting with `sys_`
- xv6 init functions: `userinit`, `scheduler`

```python
ENTRY_PREFIXES = ("main", "sys_")
ENTRY_NAMES = {"userinit", "scheduler", "forkret"}

def _is_entry_point(name):
    return name in ENTRY_NAMES or any(name.startswith(p) for p in ENTRY_PREFIXES)
```

#### Step 6 — Estimate complexity

Count branch points inside each function body (`if_statement`,
`while_statement`, `for_statement`, `case_statement`, `conditional_expression`
i.e. ternary, `&&`, `||`). Cyclomatic complexity = 1 + count.

```python
BRANCH_TYPES = {
    "if_statement", "while_statement", "for_statement",
    "do_statement", "case_statement", "conditional_expression",
}

def _count_branches(node):
    count = 1 if node.type in BRANCH_TYPES else 0
    # also count && and || as branch points
    if node.type in ("&&", "||"):
        count += 1
    for child in node.children:
        count += _count_branches(child)
    return count
```

#### Step 7 — Extract globals

Top-level `declaration` nodes that are NOT inside a function are global
variables. Grab the declarator identifier.

#### Step 8 — Wire it into the agent function

```python
def recon_agent(state: ForgeState) -> ForgeState:
    source_files = state.get("source_files", {})
    log_step(state, "recon", f"parsing {len(source_files)} file(s)")

    all_functions = []
    all_includes = {}
    all_globals = []

    for filename, content in source_files.items():
        tree = _parse(content.encode())
        # ... extract functions, includes, globals per file
        # ... append to the lists above

    # build called_by reverse map
    func_names = {f["name"] for f in all_functions}
    for func in all_functions:
        func["called_by"] = [
            other["name"]
            for other in all_functions
            if func["name"] in other["calls"] and other["name"] != func["name"]
        ]

    entry_points = [f["name"] for f in all_functions if _is_entry_point(f["name"])]

    state["recon_map"] = {
        "files": list(source_files.keys()),
        "functions": all_functions,
        "entry_points": entry_points,
        "includes": all_includes,
        "globals": all_globals,
    }

    log_step(state, "recon",
             f"found {len(all_functions)} functions, "
             f"{len(entry_points)} entry points")
    return state
```

### How to test

```bash
# Quick manual test:
python3 -c "
from forge.state import initial_state
from forge.agents.recon import recon_agent
import json

state = initial_state(source_files={'leak.c': open('samples/easy/leak.c').read()})
result = recon_agent(state)
print(json.dumps(result['recon_map'], indent=2))
"

# Then add a real test in tests/test_recon.py:
# - assert make_buffer and main are found
# - assert main calls make_buffer and free
# - assert make_buffer calls malloc
# - assert entry_points == ["main"]
# - assert includes == {"leak.c": ["stdlib.h"]}
```

### Fallback for macro-heavy code

If tree-sitter fails (returns a node with type `ERROR`), fall back to regex:

```python
import re
FUNC_RE = re.compile(
    r"^[\w\s\*]+?\b(\w+)\s*\([^)]*\)\s*\{",
    re.MULTILINE,
)
```

Log a warning in the trace when you hit the fallback path so the team knows.

---

## Part 2: Analysis Agent (`forge/agents/analysis.py`)

### What it does

1. Writes source files to a temp directory on disk (tools need real files).
2. Runs `cppcheck` and `clang-tidy` as subprocesses.
3. Parses their output into a raw findings list.
4. Sends raw findings + `recon_map` to the LLM for deduplication and
   prioritization.
5. Writes the final `state["findings"]` list.

### Target output shape (per finding)

```json
{
  "id": "F001",
  "severity": "CRITICAL",
  "category": "memory_leak",
  "tool_source": "cppcheck",
  "function": "main",
  "file": "leak.c",
  "lines": [16],
  "description": "Memory allocated by make_buffer() is not freed when b[0] == 'x' (early return on line 16)",
  "reachable_from": ["main"],
  "patchable": true
}
```

### Step-by-step

#### Step 1 — Write source files to a temp directory

Tools need real files on disk. Use `tempfile.TemporaryDirectory()`:

```python
import tempfile
from pathlib import Path

def _write_sources_to_disk(source_files: dict[str, str]) -> Path:
    tmpdir = tempfile.mkdtemp(prefix="forge_")
    for name, content in source_files.items():
        (Path(tmpdir) / name).write_text(content)
    return Path(tmpdir)
```

Keep the tmpdir around until the agent is done; clean up at the end. Or use
a context manager:

```python
with tempfile.TemporaryDirectory(prefix="forge_") as tmpdir:
    ...
```

#### Step 2 — Run cppcheck

```python
import subprocess

def _run_cppcheck(source_dir: Path) -> str:
    c_files = list(source_dir.glob("*.c"))
    if not c_files:
        return ""
    result = subprocess.run(
        ["cppcheck", "--enable=all", "--xml"] + [str(f) for f in c_files],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stderr  # cppcheck writes XML to stderr
```

#### Step 3 — Parse cppcheck XML

```python
import xml.etree.ElementTree as ET

def _parse_cppcheck_xml(xml_str: str) -> list[dict]:
    findings = []
    root = ET.fromstring(xml_str)
    for error in root.iter("error"):
        severity = error.get("severity", "")
        if severity in ("information",):
            continue  # skip noise like "missingIncludeSystem"
        location = error.find("location")
        findings.append({
            "tool": "cppcheck",
            "id": error.get("id", ""),
            "severity": severity,
            "message": error.get("msg", ""),
            "verbose": error.get("verbose", ""),
            "file": Path(location.get("file", "")).name if location is not None else "",
            "line": int(location.get("line", 0)) if location is not None else 0,
        })
    return findings
```

#### Step 4 — Run clang-tidy

clang-tidy is at `/opt/homebrew/opt/llvm/bin/clang-tidy` on your Mac. In the
Docker sandbox it'll be at just `clang-tidy`. Handle both:

```python
import shutil

def _find_clang_tidy() -> str:
    if shutil.which("clang-tidy"):
        return "clang-tidy"
    brew_path = "/opt/homebrew/opt/llvm/bin/clang-tidy"
    if Path(brew_path).exists():
        return brew_path
    raise FileNotFoundError("clang-tidy not found")

def _run_clang_tidy(source_dir: Path) -> str:
    c_files = list(source_dir.glob("*.c"))
    if not c_files:
        return ""
    # get sysroot for macOS
    sysroot = subprocess.run(
        ["xcrun", "--show-sdk-path"],
        capture_output=True, text=True
    ).stdout.strip()
    cmd = [
        _find_clang_tidy(),
        *[str(f) for f in c_files],
        "-checks=clang-analyzer-*,bugprone-*,cert-*",
        "--",
    ]
    if sysroot:
        cmd.append(f"-isysroot{sysroot}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return result.stdout
```

#### Step 5 — Parse clang-tidy output

clang-tidy outputs plain text like:
```
/path/to/file.c:16:14: warning: The left operand ... [clang-analyzer-core.Xyz]
```

Parse with regex:

```python
import re

CLANG_TIDY_RE = re.compile(
    r"^(.+?):(\d+):(\d+): (warning|error): (.+?) \[(.+?)\]$",
    re.MULTILINE,
)

def _parse_clang_tidy(output: str) -> list[dict]:
    findings = []
    for m in CLANG_TIDY_RE.finditer(output):
        findings.append({
            "tool": "clang-tidy",
            "id": m.group(6),        # check name
            "severity": m.group(4),
            "message": m.group(5),
            "file": Path(m.group(1)).name,
            "line": int(m.group(2)),
        })
    return findings
```

#### Step 6 — Send to LLM for dedup + prioritization

Combine raw findings from both tools plus the `recon_map` and ask the LLM to
deduplicate, classify, and prioritize.

```python
import json
from forge.llm import chat

ANALYSIS_SYSTEM_PROMPT = """You are a C systems expert. You will receive:
1. Raw static analysis findings from cppcheck and clang-tidy.
2. A structural map of the codebase (functions, call graph, entry points).

Your job:
1. Deduplicate findings that refer to the same root cause.
2. Classify each unique finding: CRITICAL / WARNING / INFO.
3. Prioritize by: severity × reachability (is the function called from an entry point?).
4. For each finding, identify the specific function and line range.
5. Decide which findings are patchable by an AI vs. need human judgment.

Respond with ONLY a JSON object (no markdown, no explanation):
{
  "findings": [
    {
      "id": "F001",
      "severity": "CRITICAL",
      "category": "memory_leak",
      "tool_source": "cppcheck",
      "function": "function_name",
      "file": "filename.c",
      "lines": [42],
      "description": "Human-readable explanation of the bug",
      "reachable_from": ["main"],
      "patchable": true
    }
  ],
  "summary": "X critical, Y warnings, Z informational. N duplicates removed."
}"""

def _llm_interpret(raw_findings: list[dict], recon_map: dict) -> list[dict]:
    prompt = f"""Raw static analysis findings:
{json.dumps(raw_findings, indent=2)}

Codebase structural map:
{json.dumps(recon_map, indent=2)}"""

    response = chat(prompt, system=ANALYSIS_SYSTEM_PROMPT, max_tokens=4096)

    # Strip markdown code fences if the LLM wraps the response
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]  # remove opening ```json
        cleaned = cleaned.rsplit("```", 1)[0]  # remove closing ```

    parsed = json.loads(cleaned)
    return parsed.get("findings", [])
```

#### Step 7 — Wire it all together

```python
def analysis_agent(state: ForgeState) -> ForgeState:
    source_files = state.get("source_files", {})
    recon_map = state.get("recon_map", {})

    with tempfile.TemporaryDirectory(prefix="forge_") as tmpdir:
        src_dir = _write_sources_to_disk(source_files, Path(tmpdir))

        # Run tools
        log_step(state, "analysis", "running cppcheck")
        cppcheck_xml = _run_cppcheck(src_dir)
        cppcheck_findings = _parse_cppcheck_xml(cppcheck_xml) if cppcheck_xml else []

        log_step(state, "analysis", "running clang-tidy")
        clang_output = _run_clang_tidy(src_dir)
        clang_findings = _parse_clang_tidy(clang_output)

    raw_findings = cppcheck_findings + clang_findings
    log_step(state, "analysis",
             f"tools returned {len(raw_findings)} raw findings "
             f"({len(cppcheck_findings)} cppcheck, {len(clang_findings)} clang-tidy)")

    if not raw_findings:
        state["findings"] = []
        log_step(state, "analysis", "no findings — nothing to patch")
        return state

    # LLM dedup + prioritize
    log_step(state, "analysis", "sending to LLM for interpretation")
    findings = _llm_interpret(raw_findings, recon_map)
    state["findings"] = findings
    log_step(state, "analysis",
             f"LLM returned {len(findings)} deduplicated findings")
    return state
```

### How to test

```bash
# 1) Test tools only (no LLM, no API key needed):
python3 -c "
from forge.agents.analysis import _run_cppcheck, _parse_cppcheck_xml
from forge.agents.analysis import _run_clang_tidy, _parse_clang_tidy
from pathlib import Path
import json

xml = _run_cppcheck(Path('samples/easy'))
print('=== cppcheck findings ===')
print(json.dumps(_parse_cppcheck_xml(xml), indent=2))

out = _run_clang_tidy(Path('samples/easy'))
print('=== clang-tidy findings ===')
print(json.dumps(_parse_clang_tidy(out), indent=2))
"

# 2) Full agent test (needs ANTHROPIC_API_KEY in .env):
python3 -c "
from forge.state import initial_state
from forge.agents.recon import recon_agent
from forge.agents.analysis import analysis_agent
import json

state = initial_state(source_files={'leak.c': open('samples/easy/leak.c').read()})
state = recon_agent(state)
state = analysis_agent(state)
print(json.dumps(state['findings'], indent=2))
"

# 3) Full pipeline:
pytest
streamlit run app.py
```

### Suggested tests to add in `tests/test_analysis.py`

- `test_cppcheck_parse`: feed known XML string, assert correct findings list.
- `test_clang_tidy_parse`: feed known text output, assert correct parsing.
- `test_analysis_no_findings`: empty `.c` file → `findings` is `[]`.
- `test_analysis_with_leak`: `leak.c` → at least one CRITICAL finding.

---

## Implementation order

| Step | What | Test with | LLM needed? |
|------|------|-----------|-------------|
| 1 | Recon: tree-sitter parsing + function extraction | `leak.c` | No |
| 2 | Recon: call graph + `called_by` | `leak.c` | No |
| 3 | Recon: includes, globals, entry points, complexity | `leak.c` | No |
| 4 | Analysis: run cppcheck + parse XML | `leak.c` | No |
| 5 | Analysis: run clang-tidy + parse text | `leak.c` | No |
| 6 | Analysis: LLM interpretation prompt | `leak.c` | Yes |
| 7 | End-to-end: `pytest` + `streamlit run app.py` | `leak.c` | Yes |
| 8 | Test with harder inputs (multi-file, xv6) | `samples/medium/` | Yes |

Steps 1–5 don't need an API key. You can get most of the work done before
touching the LLM.

---

## Common pitfalls

1. **Pointer return types hide the function name.** `char* make_buffer(void)`
   nests the identifier under `pointer_declarator → function_declarator →
   identifier`. Always recurse through `pointer_declarator`.

2. **cppcheck writes XML to stderr**, not stdout. Capture `result.stderr`.

3. **clang-tidy on macOS needs `-isysroot`.** Without it you get
   `'stdlib.h' file not found`. Use `xcrun --show-sdk-path`.

4. **clang-tidy path on macOS.** It's at `/opt/homebrew/opt/llvm/bin/clang-tidy`,
   not on PATH by default.

5. **LLM may wrap JSON in markdown fences.** Always strip ` ```json ` and
   ` ``` ` before parsing.

6. **`tempfile` cleanup.** If you use `mkdtemp` instead of
   `TemporaryDirectory`, you must clean up manually. Prefer the context
   manager.

7. **Don't forget `log_step`.** The Streamlit UI reads `agent_trace` to show
   real-time progress. Log at each major step (starting tool, tool done,
   sending to LLM, done).
