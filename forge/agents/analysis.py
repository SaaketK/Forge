"""Analysis Agent — runs cppcheck/clang-tidy/sanitizers, then asks the LLM to
deduplicate and prioritize.

Owner: Member 2 (Tool Agents).

This is a stub. Real implementation should:
1. Shell out to cppcheck (XML output) and clang-tidy.
2. Optionally compile with -fsanitize=address,undefined.
3. Pass the raw tool output + recon_map to the LLM with the prompt from
   section 4.2 of Forge_Project_Outline.md.
4. Return a deduplicated, severity-ranked list of findings.
"""

from __future__ import annotations

from forge.state import ForgeState, log_step


def analysis_agent(state: ForgeState) -> ForgeState:
    log_step(state, "analysis", "stub: pretending to run cppcheck + clang-tidy")

    # TODO(member2): run real tools, capture XML output, send to LLM.
    state["findings"] = []
    return state
