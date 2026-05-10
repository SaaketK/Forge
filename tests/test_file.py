import pytest
from pathlib import Path
from forge.graph import build_graph
from forge.state import initial_state
from forge.agents.patch import patch_agent
from forge.agents.validation import validation_agent

def test_file():
    # 1. Path to C file
    proc_c_path = Path("samples/easy/kalloc.c")
    
    if not proc_c_path.exists():
        pytest.skip("kalloc.c not found in samples/easy/")

    # 2. Initialize state with the real file content
    state = initial_state(source_files={
        "proc.c": proc_c_path.read_text()
    })

    # 3. Run Recon + Analysis via graph
    graph = build_graph()
    state = graph.invoke(state)

    # 4. View Recon + Analysis results
    print(f"\n--- Recon Results for {proc_c_path.name} ---")
    print(f"Functions found: {len(state['recon_map']['functions'])}")

    print(f"\n--- Analysis Results ---")
    for finding in state["findings"]:
        print(f"[{finding['severity']}] {finding['function']} (Line {finding['lines'][0]}): {finding['description']}")

    assert "recon_map" in state
    assert len(state["recon_map"]["functions"]) > 0
    assert "findings" in state
    assert len(state["findings"]) > 0

    # 5. Patch
    print(f"\n--- Patch Agent ---")
    state = patch_agent(state)
    print(f"Patches generated: {len(state['patches'])}")
    print(f"Diff:\n{state['patches'][0]['diff']}")

    assert len(state["patches"]) > 0
    assert state["patches"][0]["diff"] != ""

    # 6. Validation
    print(f"\n--- Validation Agent ---")
    state = validation_agent(state)
    verdict = state["validation_results"][0]["verdict"]
    print(f"Verdict: {verdict}")
    print(f"Compile success: {state['validation_results'][0]['compile_success']}")
    print(f"Sanitizer clean: {state['validation_results'][0]['sanitizer_clean']}")
    print(f"Cppcheck output: {state['validation_results'][0]['cppcheck_output']}")

    assert len(state["validation_results"]) > 0
    assert verdict in ["PASS", "FAIL"]