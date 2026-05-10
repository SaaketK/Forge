from forge.state import initial_state
from forge.agents.patch import patch_agent

def test_patch_agent():
    state = initial_state(
        source_files={
            "main.c": """
#include <string.h>
void process(char* input) {
    char buf[64];
    strcpy(buf, input);
}
"""
        }
    )

    state["findings"] = [{
        "id": "F000",
        "file": "main.c",
        "description": "buffer overflow in process()",
        "line": 4,
    }]

    result = patch_agent(state)

    assert len(result["patches"]) == 1
    print("PATCHES:", result["patches"])
    print("TRACE:", result["agent_trace"])
    assert result["patches"][0]["diff"] != ""
    assert result["patches"][0]["finding_id"] == "F000"
