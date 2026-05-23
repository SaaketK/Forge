# Forge

**Forge** is an agentic pipeline that audits C code, generates patches, and validates them — automatically. Upload a `.c` file, and Forge runs real static analysis tools, uses an LLM to interpret the findings, writes fixes as unified diffs, and compiles and tests each fix in a sandboxed Docker environment. If a patch fails, it retries with the compiler errors fed back to the LLM.

The key idea: **the LLM interprets and generates — the actual bug-finding is done by battle-tested tools** (`cppcheck`, `clang-tidy`, gcc sanitizers). No hallucinated bugs.

---

## How it works

```
Upload .c / .h files
        │
        ▼
┌──────────────┐     ┌────────────────┐     ┌─────────────┐     ┌──────────────────┐
│  Recon Agent │────▶│ Analysis Agent │────▶│ Patch Agent │────▶│ Validation Agent │
│              │     │                │     │             │     │                  │
│ Parses code  │     │ Runs cppcheck  │     │ LLM writes  │     │ Applies diff,    │
│ into AST,    │     │ + clang-tidy,  │     │ a minimal   │     │ compiles with    │
│ extracts     │     │ then LLM dedup │     │ unified     │     │ sanitizers in    │
│ call graph   │     │ + prioritizes  │     │ diff patch  │     │ Docker sandbox   │
└──────────────┘     └────────────────┘     └─────────────┘     └────────┬─────────┘
                                                    ▲                    │
                                                    │         PASS ──────┼──▶ Report
                                                    │                    │
                                                    └────── FAIL ────────┘
                                                      (compiler errors feedback
                                                       loop, retries up to 3×)
```

### The four agents

**Recon** — Parses your C files using `tree-sitter` into an AST. Extracts function signatures, the call graph, struct definitions, globals, and entry points. Computes cyclomatic complexity. No LLM involved in the C code breakdown.

**Analysis** — Shells out to `cppcheck` (XML output) and `clang-tidy`, then sends the raw findings plus the recon map to the LLM. The LLM deduplicates, classifies each finding as CRITICAL / WARNING / INFO, and ranks by severity * reachability (bugs in functions called from `main` rank higher).

**Patch** — For each finding, sends the relevant source code and bug description to the LLM and asks for a minimal unified diff. If a previous attempt failed, the compiler errors are included so the LLM doesn't repeat the same mistake.

**Validation** — Copies the source into a Docker container (no network, non-root user), applies the patch with `patch -p1`, compiles with `gcc -fsanitize=address,undefined`, and re-runs `cppcheck` to confirm the original issue is gone. Returns PASS or FAIL with structured feedback.

## Hosted vs. local

A hosted version is available at [forge.streamlit.app](https://forge.streamlit.app) — no setup required, runs recon + analysis + patch. The validation sandbox requires Docker and is only available when running locally.

---

## Quickstart

### Prerequisites

- Python 3.11+
- Docker (for the validation sandbox)
- `cppcheck` and `clang-tidy` installed locally
- An Anthropic or OpenAI API key

### Install

```bash
git clone https://github.com/SaaketK/Forge.git
cd Forge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in your API key
```

### Build the sandbox image

```bash
docker build -t forge-sandbox:latest -f docker/Dockerfile .
```

### Run

```bash
streamlit run app.py
```

Upload one of the sample files from `samples/easy/` (e.g. `leak.c`) and click **Run Forge**.

---

## Configuration

All options are set via environment variables (copy `.env.example` to `.env`):

| Variable | Default | Description |
|---|---|---|
| `FORGE_LLM_PROVIDER` | `anthropic` | `anthropic` or `openai` |
| `FORGE_LLM_MODEL` | `claude-sonnet-4-6` | Model name for the configured provider |
| `ANTHROPIC_API_KEY` | — | Required if using Anthropic |
| `OPENAI_API_KEY` | — | Required if using OpenAI |
| `FORGE_MAX_RETRIES` | `3` | Max patch attempts per finding before escalating |
| `FORGE_DOCKER_IMAGE` | `forge-sandbox:latest` | Sandbox image name |
| `FORGE_DOCKER_TIMEOUT` | `60` | Seconds before sandbox timeout |

---

## Tech stack

| Component | Technology |
|---|---|
| Orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) state machine |
| LLM | Anthropic or OpenAI (provider-agnostic) |
| Code parsing | `tree-sitter` + `tree-sitter-c` |
| Static analysis | `cppcheck`, `clang-tidy` |
| Compilation / sanitizers | `gcc -fsanitize=address,undefined` |
| Sandbox | Docker (network-disabled, non-root) |
| Frontend UI | Streamlit |

---

## Project structure

```
forge/
  agents/         # recon, analysis, patch, validation agents
  sandbox/        # Docker container lifecycle + compile helpers
  state.py        # ForgeState schema shared across all agents
  config.py       # env-driven configuration
  graph.py        # LangGraph state machine and routing logic
  llm.py          # provider-agnostic chat() wrapper
app.py            # Streamlit UI
docker/Dockerfile # sandbox image (gcc, clang, cppcheck)
samples/easy/     # sample C files with intentional bugs
tests/            # pytest suite
```

---

## Running tests

```bash
pytest -v          # full suite (LLM + Docker tests skipped if keys/Docker not present)
ruff check .       # lint
```