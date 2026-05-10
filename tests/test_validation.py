from forge.state import initial_state
from forge.agents.validation import validation_agent

def test_validation_agent_no_patch():
    """Should FAIL cleanly when there is no patch."""
    state = initial_state(source_files={"main.c": ""})
    state["findings"] = [{"id": "F000", "file": "main.c", "description": "test"}]

    result = validation_agent(state)

    assert result["validation_results"][0]["verdict"] == "FAIL"
    assert result["validation_results"][0]["error"] == "no patch available"


def test_validation_agent_with_patch():
    """Should compile and validate a real patch."""
    state = initial_state(
        source_files={
            "main.c": """
#include <string.h>
void process(char* input) {
    char buf[64];
    strcpy(buf, input);
}
int main() { return 0; }
"""
        }
    )

    state["findings"] = [{"id": "F000", "file": "main.c", "description": "buffer overflow"}]
    state["patches"] = [{
        "finding_id": "F000",
        "file": "main.c",
        "diff": """--- a/main.c
+++ b/main.c
@@ -3,6 +3,6 @@
 void process(char* input) {
     char buf[64];
-    strcpy(buf, input);
+    strncpy(buf, input, sizeof(buf) - 1);
 }
""",
    }]

    result = validation_agent(state)

    assert len(result["validation_results"]) == 1
    assert result["validation_results"][0]["patch_applied"] == True
    assert result["validation_results"][0]["verdict"] in ["PASS", "FAIL"]
    assert "cppcheck_output" in result["validation_results"][0]