"""Streamlit entry point for Forge.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import json
import os

import streamlit as st

# Streamlit Community Cloud stores secrets in st.secrets, not os.environ.
# Bridge them in before forge/config.py loads so ANTHROPIC_API_KEY etc. are visible.
try:
    for _k, _v in st.secrets.items():
        if _k not in os.environ:
            os.environ[_k] = str(_v)
except Exception:
    pass  # running locally — .env handles secrets

from forge.graph import build_graph
from forge.state import initial_state

st.set_page_config(page_title="Forge", layout="wide")
st.title("FORGE — Agentic C Code Auditor")

# ── Sidebar: inputs ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Inputs")
    uploaded = st.file_uploader(
        "Upload .c / .h files",
        type=["c", "h"],
        accept_multiple_files=True,
    )
    description = st.text_area(
        "What does this code do? (optional)",
        placeholder="e.g. xv6 process allocator",
    )
    max_retries = st.number_input(
        "Max retries per finding", min_value=1, max_value=10, value=3
    )
    run = st.button("Run Forge", type="primary", disabled=not uploaded)

# ── Main area ────────────────────────────────────────────────────────────────
if run:
    source_files = {
        f.name: f.read().decode("utf-8", errors="replace") for f in uploaded
    }
    state = initial_state(
        source_files=source_files,
        user_description=description or None,
        max_retries=int(max_retries),
    )

    graph = build_graph()

    # ── Agent trace (real-time) ──────────────────────────────────────────────
    with st.status("Running Forge pipeline...", expanded=True) as status:
        for event in graph.stream(state):
            for node, node_state in event.items():
                state = node_state
                # Show the latest trace entries for this node
                trace = state.get("agent_trace", [])
                for entry in trace:
                    if entry.get("agent") == node or (
                        node in ("advance", "bump_attempt")
                        and entry.get("agent") == "supervisor"
                    ):
                        st.write(f"**{entry['agent']}**: {entry['message']}")
        status.update(label="Forge run complete", state="complete")

    st.divider()

    # ── Results summary ──────────────────────────────────────────────────────
    st.subheader("Results")

    findings = state.get("findings") or []
    accepted = state.get("accepted_patches") or []
    escalated = state.get("escalated_findings") or []

    col1, col2, col3 = st.columns(3)
    col1.metric("Findings", len(findings))
    col2.metric("Patched", len(accepted), delta=f"{len(accepted)}/{len(findings)}" if findings else None)
    col3.metric("Escalated", len(escalated), delta=None if not escalated else "needs human review",
                delta_color="inverse" if escalated else "off")

    st.divider()

    # ── Per-finding breakdown ────────────────────────────────────────────────
    if findings:
        st.subheader("Findings")
        for i, finding in enumerate(findings):
            severity = finding.get("severity", "INFO")
            patched = any(
                p.get("finding_id") == finding.get("id") for p in accepted
            )
            patch_badge = "Patched" if patched else ""
            escalated_badge = "Escalated" if finding in escalated else ""
            status_badge = patch_badge or escalated_badge or "Pending"

            with st.expander(
                f"[{severity}] **{finding.get('id', f'F{i:03d}')}** — "
                f"{finding.get('category', 'unknown')} in `{finding.get('function', '?')}()` "
                f"({finding.get('file', '?')}:{','.join(str(l) for l in finding.get('lines', []))}) "
                f"[{status_badge}]"
            ):
                st.markdown(f"**Severity:** {severity}")
                st.markdown(f"**Description:** {finding.get('description', 'N/A')}")
                st.markdown(f"**Tool:** {finding.get('tool_source', 'N/A')}")
                st.markdown(f"**Reachable from:** {', '.join(finding.get('reachable_from', []))}")
                st.markdown(f"**Patchable:** {'Yes' if finding.get('patchable') else 'No'}")

                # Show the diff if this finding was patched
                matching_patches = [
                    p for p in state.get("patches", [])
                    if p.get("finding_id") == finding.get("id")
                ]
                if matching_patches:
                    st.markdown("---")
                    st.markdown("**Generated Patch:**")
                    st.code(matching_patches[-1].get("diff", ""), language="diff")
                    st.caption(matching_patches[-1].get("explanation", ""))

                # Show validation results for this finding
                matching_results = [
                    r for r in state.get("validation_results", [])
                    if r.get("finding_id") == finding.get("id")
                ]
                if matching_results:
                    last_result = matching_results[-1]
                    st.markdown("---")
                    st.markdown("**Validation:**")
                    vcol1, vcol2, vcol3 = st.columns(3)
                    vcol1.metric("Compile", "OK" if last_result.get("compile_success") else "FAIL")
                    vcol2.metric("Sanitizer", "OK" if last_result.get("sanitizer_clean") else "FAIL")
                    vcol3.metric("Verdict", last_result.get("verdict", "?"))
                    if last_result.get("stderr"):
                        with st.popover("Compiler output"):
                            st.code(last_result["stderr"], language="text")

    st.divider()

    # ── Agent trace (full) ───────────────────────────────────────────────────
    with st.expander("Full agent trace"):
        for entry in state.get("agent_trace", []):
            ts_str = entry.get("timestamp", "")[:19]
            st.text(f"[{ts_str}] {entry.get('agent', '?'):12s} | {entry.get('message', '')}")

    # ── Downloads ────────────────────────────────────────────────────────────
    st.subheader("Downloads")
    dcol1, dcol2 = st.columns(2)

    with dcol1:
        st.download_button(
            "Download full report (JSON)",
            data=json.dumps(state, indent=2, default=str),
            file_name="forge_report.json",
            mime="application/json",
        )

    # Build patched files for download
    patched_files = dict(state.get("source_files", {}))
    for patch in accepted:
        # Show which files were patched
        fname = patch.get("file", "")
        if fname:
            patched_files[f"{fname}.patched"] = patched_files.get(fname, "") + f"\n/* Forge patch applied: {patch.get('finding_id', '')} */\n"

    with dcol2:
        st.download_button(
            "Download patched source",
            data=json.dumps(patched_files, indent=2),
            file_name="forge_patched_source.json",
            mime="application/json",
        )

else:
    # ── Landing page ─────────────────────────────────────────────────────────
    st.info("Upload one or more `.c` / `.h` files in the sidebar, then click **Run Forge**.")

    st.markdown("""
    ### How Forge works

    1. **Recon Agent** — parses your C code into an AST, extracts functions, call graph, structs
    2. **Analysis Agent** — runs `cppcheck` + `clang-tidy`, then uses an LLM to deduplicate and prioritize findings
    3. **Patch Agent** — generates minimal unified diffs to fix each bug
    4. **Validation Agent** — applies patches in a Docker sandbox, compiles with sanitizers, verifies the fix

    The system iterates: if a patch fails validation, it retries with the error context (up to 3 attempts).
    After max retries, the finding is escalated to human review.
    """)
