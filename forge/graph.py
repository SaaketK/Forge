"""LangGraph state machine that wires the four agents together.

Owner: Member 1 (Orchestrator / UI).

Flow:
    recon -> analysis -> [loop over findings: patch -> validation] -> done

The loop logic is implemented with a conditional edge after `validation`:
- verdict PASS or no more findings -> advance / finish
- verdict FAIL and attempts < max_retries -> back to patch
- verdict FAIL and attempts == max_retries -> escalate, advance to next finding

All routing decisions read from ForgeState. Agents themselves never decide
where to go next.
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from forge.agents import analysis_agent, patch_agent, recon_agent, validation_agent
from forge.state import ForgeState, log_step


def _route_after_validation(state: ForgeState) -> Literal["patch", "advance", "done"]:
    findings = state.get("findings") or []
    idx = state.get("current_finding_index", 0)

    if not findings or idx >= len(findings):
        return "done"

    last_result = (state.get("validation_results") or [])[-1] if state.get("validation_results") else None
    verdict = last_result.get("verdict") if last_result else "FAIL"

    if verdict == "PASS":
        return "advance"

    attempt = state.get("current_attempt", 0)
    if attempt + 1 >= state.get("max_retries", 3):
        return "advance"  # escalate handled by `_advance`

    return "patch"


def _advance(state: ForgeState) -> ForgeState:
    """Move to the next finding, or finalize accepted/escalated lists."""
    findings = state.get("findings") or []
    idx = state.get("current_finding_index", 0)
    last_result = (state.get("validation_results") or [])[-1] if state.get("validation_results") else None

    if last_result and last_result.get("verdict") == "PASS":
        state.setdefault("accepted_patches", []).append(state["patches"][-1])
    elif idx < len(findings):
        state.setdefault("escalated_findings", []).append(findings[idx])

    state["current_finding_index"] = idx + 1
    state["current_attempt"] = 0
    log_step(state, "supervisor", f"advancing to finding #{state['current_finding_index']}")
    return state


def _bump_attempt(state: ForgeState) -> ForgeState:
    state["current_attempt"] = state.get("current_attempt", 0) + 1
    return state


def build_graph():
    """Compile the LangGraph state machine. Call once at startup."""
    g = StateGraph(ForgeState)

    g.add_node("recon", recon_agent)
    g.add_node("analysis", analysis_agent)
    g.add_node("patch", patch_agent)
    g.add_node("validation", validation_agent)
    g.add_node("advance", _advance)
    g.add_node("bump_attempt", _bump_attempt)

    g.set_entry_point("recon")
    g.add_edge("recon", "analysis")
    g.add_edge("analysis", "patch")
    g.add_edge("patch", "validation")

    g.add_conditional_edges(
        "validation",
        _route_after_validation,
        {
            "patch": "bump_attempt",
            "advance": "advance",
            "done": END,
        },
    )
    g.add_edge("bump_attempt", "patch")

    # After advancing, decide whether to keep looping or finish.
    g.add_conditional_edges(
        "advance",
        lambda s: "patch" if s["current_finding_index"] < len(s.get("findings") or []) else "done",
        {"patch": "patch", "done": END},
    )

    return g.compile()
