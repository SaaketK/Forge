"""Smoke test: the stub graph should run end-to-end without raising."""

from pathlib import Path

from forge.graph import build_graph
from forge.state import initial_state


def test_graph_runs_with_stubs():
    sample = Path(__file__).parent.parent / "samples" / "easy" / "leak.c"
    state = initial_state(source_files={"leak.c": sample.read_text()})

    graph = build_graph()
    final = graph.invoke(state)

    assert final["recon_map"] is not None
    assert final["findings"] is not None
    assert isinstance(final["agent_trace"], list) and final["agent_trace"]
