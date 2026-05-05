"""Recon Agent — parses C source into a structural map.

Owner: Member 2 (Tool Agents).

This is a stub. Real implementation should use tree-sitter-c to extract:
- function names, signatures, line ranges
- call relationships (who calls whom)
- #include dependencies
- entry points
- complexity per function

See section 4.1 of Forge_Project_Outline.md.
"""

from __future__ import annotations

from forge.state import ForgeState, log_step


def recon_agent(state: ForgeState) -> ForgeState:
    log_step(state, "recon", "stub: pretending to parse source files")

    # TODO(member2): replace with real tree-sitter parsing.
    state["recon_map"] = {
        "files": list(state.get("source_files", {}).keys()),
        "functions": [],
        "entry_points": [],
        "includes": {},
        "globals": [],
        "_stub": True,
    }
    return state
