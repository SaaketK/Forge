"""Validation Agent — applies a patch in a Docker sandbox, compiles, and
verifies the original finding is gone without introducing regressions.

Owner: Member 3 (Patch + Validation).

This is a stub. Real implementation should:
1. Spin up (or reuse) the forge-sandbox Docker container.
2. Apply the latest patch on top of the original source.
3. Compile with `gcc -Wall -Werror -fsanitize=address,undefined` (or `make`).
4. Re-run cppcheck on the patched function to confirm the original finding is
   resolved.
5. Return a verdict (PASS / FAIL) plus structured feedback for the loop.

See forge/sandbox/docker_runner.py for the sandbox helper.
"""

from __future__ import annotations

from forge.state import ForgeState, log_step


def validation_agent(state: ForgeState) -> ForgeState:
    idx = state.get("current_finding_index", 0)
    log_step(state, "validation", f"stub: pretending to validate patch for finding #{idx}")

    # TODO(member3): apply diff, compile in Docker, capture results.
    state.setdefault("validation_results", []).append(
        {
            "finding_id": f"F{idx:03d}",
            "patch_applied": True,
            "compile_success": True,
            "new_warnings": [],
            "sanitizer_clean": True,
            "original_finding_resolved": True,
            "regression_detected": False,
            "verdict": "PASS",
        }
    )
    return state
