# Forge

> Agentic Build & Debug Pipeline for Systems Code.

Forge is a multi-agent system that takes a C project, runs real static
analysis and compilation tools against it, uses an LLM to interpret and
prioritize findings, generates patches, and validates those patches in a
sandboxed environment — iterating until the code is clean or the system
escalates to a human.

The full design lives in
[`docs/Forge_Project_Outline.md`](docs/Forge_Project_Outline.md).

---

## Repo layout

```
forge/
  state.py        # ForgeState — the shared contract every agent codes against
  config.py       # env-driven config (LLM keys, retry caps, Docker image)
  graph.py        # LangGraph state machine wiring the four agents together
  llm.py          # provider-agnostic chat() wrapper
  agents/         # one stub per agent (Member 2 fills recon+analysis,
                  #                       Member 3 fills patch+validation)
  sandbox/        # Docker-based compile/run helper (Member 3)
app.py            # Streamlit UI (Member 1)
docker/Dockerfile # sandbox image with gcc, clang-tidy, cppcheck
samples/easy/     # week-4 smoke-test inputs (e.g. leak.c)
tests/            # pytest smoke tests
docs/             # design outline
```

## Who owns what

| Area | Member | Files to start with |
|------|--------|--------------------|
| Orchestrator + UI | 1 | `forge/graph.py`, `app.py` |
| Recon + Analysis | 2 | `forge/agents/recon.py`, `forge/agents/analysis.py` |
| Patch + Validation | 3 | `forge/agents/patch.py`, `forge/agents/validation.py`, `forge/sandbox/docker_runner.py`, `docker/Dockerfile` |

The shared contract is `ForgeState` in [`forge/state.py`](forge/state.py).
Do not change its shape without telling the team.

---

## Quickstart

### 1. Prerequisites

- Python 3.11+
- Docker (for the validation sandbox; not needed to run the stub pipeline)
- A working `cppcheck` and `clang-tidy` (only needed by Member 2 once the
  Analysis Agent is wired up)

### 2. Install

```bash
git clone <this repo>
cd Forge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # then fill in your API key
```

### 3. Run the stub pipeline end-to-end

```bash
pytest                     # confirms the graph wires up correctly
streamlit run app.py       # opens the UI in your browser
```

Upload `samples/easy/leak.c` and click **Run Forge**. With the current stubs
the agents just log "running" — once you implement them, real findings and
patches will flow through.

### 4. Build the sandbox image (when Member 3 is ready to validate)

```bash
docker build -t forge-sandbox:latest -f docker/Dockerfile .
```

---

## Development conventions

- Each agent is a function `(state: ForgeState) -> ForgeState`.
- Agents append to `state["agent_trace"]` via `forge.state.log_step` so the
  UI gets real-time updates for free.
- Routing decisions live in [`forge/graph.py`](forge/graph.py), never in the
  agents themselves.
- Lazy-import LLM SDKs and heavy deps inside agent functions so unrelated
  tests stay fast.
- Run `pytest` before pushing.

## Useful commands

```bash
pytest -v                  # smoke tests
ruff check .               # lint
streamlit run app.py       # UI
```
