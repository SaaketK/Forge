"""Patch Agent — generates unified-diff patches for each finding.

Owner: Member 3 (Patch + Validation).

This is a stub. Real implementation should:
1. For the current finding (state["current_finding_index"]), extract the
   relevant function source plus call-graph context.
2. Send to the LLM with the prompt from section 4.3 of the outline.
3. Parse the output into a unified-diff string and store on state["patches"].
4. If the validation feedback loop returned errors from a previous attempt,
   include them in the prompt so the LLM does not repeat its mistake.
"""

from __future__ import annotations

from forge.state import ForgeState, log_step


def patch_agent(state: ForgeState) -> ForgeState:
    idx = state.get("current_finding_index", 0)
    attempt = state.get("current_attempt", 0)
    log_step(state, "patch", f"stub: pretending to generate patch for finding #{idx} (attempt {attempt + 1})")

    # TODO(member3): generate a real unified diff via the LLM.
    state.setdefault("patches", []).append(
        {
            "finding_id": f"F{idx:03d}",
            "file": "stub.c",
            "diff": "",
            "confidence": 0.0,
            "explanation": "stub patch — replace me",
        }
    )
    return state
