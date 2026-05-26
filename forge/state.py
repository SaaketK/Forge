"""shared state schema"""

from __future__ import annotations

from typing import Optional, TypedDict


class ForgeState(TypedDict, total=False):
    source_files: dict[str, str] # filename and content
    user_description: Optional[str] # what the code is supposed to do
    test_inputs: Optional[list[str]] # test cases

    recon_map: Optional[dict] # structural map JSON

    # analysis output
    findings: Optional[list[dict]] # prio findings

    # Patch and validation
    patches: list[dict] # generated patches
    validation_results: list[dict] # verdicts of patches

    current_finding_index: int
    current_attempt: int
    max_retries: int               

    accepted_patches: list[dict]
    escalated_findings: list[dict]
    agent_trace: list[dict] # log of steps


def initial_state(
    source_files: dict[str, str],
    user_description: Optional[str] = None,
    test_inputs: Optional[list[str]] = None,
    max_retries: int = 3,
) -> ForgeState:
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
    from datetime import datetime, timezone

    state.setdefault("agent_trace", []).append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "message": message,
            **extras,
        }
    )
