"""Shared state schema for the Forge pipeline.

Every agent reads from and writes to a ForgeState dictionary. This is the
contract everyone codes against — do not break it without consulting the team.
"""

from __future__ import annotations

from typing import Optional, TypedDict


class ForgeState(TypedDict, total=False):
    # ---- Inputs ----
    source_files: dict[str, str]          # filename -> file content
    user_description: Optional[str]        # what the code is supposed to do
    test_inputs: Optional[list[str]]       # optional test cases

    # ---- Recon Agent output ----
    recon_map: Optional[dict]              # structural map JSON

    # ---- Analysis Agent output ----
    findings: Optional[list[dict]]         # prioritized findings

    # ---- Patch + Validation ----
    patches: list[dict]                    # generated patches
    validation_results: list[dict]         # per-patch verdicts

    # ---- Loop tracking ----
    current_finding_index: int
    current_attempt: int
    max_retries: int                       # default 3

    # ---- Final output ----
    accepted_patches: list[dict]
    escalated_findings: list[dict]
    agent_trace: list[dict]                # full log of every step


def initial_state(
    source_files: dict[str, str],
    user_description: Optional[str] = None,
    test_inputs: Optional[list[str]] = None,
    max_retries: int = 3,
) -> ForgeState:
    """Build a fresh ForgeState with sensible defaults."""
    return ForgeState(
        source_files=source_files,
        user_description=user_description,
        test_inputs=test_inputs,
        recon_map=None,
        findings=None,
        patches=[],
        validation_results=[],
        current_finding_index=0,
        current_attempt=0,
        max_retries=max_retries,
        accepted_patches=[],
        escalated_findings=[],
        agent_trace=[],
    )


def log_step(state: ForgeState, agent: str, message: str, **extras) -> None:
    """Append an entry to the agent trace. Used by the UI for the live log."""
    from datetime import datetime, timezone

    state.setdefault("agent_trace", []).append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "message": message,
            **extras,
        }
    )
