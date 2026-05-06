import pytest
from pathlib import Path
from forge.graph import build_graph
from forge.state import initial_state

def test_file():
    # 1. Path to C file
    proc_c_path = Path("samples/easy/kalloc.c")
    
    if not proc_c_path.exists():
        pytest.skip("proc.c not found in samples/xv6/")

    # 2. Initialize state with the real file content
    state = initial_state(source_files={
        "proc.c": proc_c_path.read_text()
    })

    # 3. Run the full Forge pipeline (Recon -> Analysis)
    graph = build_graph()
    final_state = graph.invoke(state)

    # 4. View the results
    print(f"\n--- Recon Results for {proc_c_path.name} ---")
    print(f"Functions found: {len(final_state['recon_map']['functions'])}")
    
    print(f"\n--- Analysis Results ---")
    for finding in final_state["findings"]:
        print(f"[{finding['severity']}] {finding['function']} (Line {finding['lines'][0]}): {finding['description']}")

    # Assertions to ensure it actually did something
    assert len(final_state["recon_map"]["functions"]) > 0
    assert "recon_map" in final_state