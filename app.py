"""Streamlit entry point for Forge.

Run with:
    streamlit run app.py

Owner: Member 1 (Orchestrator / UI). This is the skeleton — fill in the
results panel, diff viewer, and download buttons as the agents come online.
"""

from __future__ import annotations

import json

import streamlit as st

from forge.graph import build_graph
from forge.state import initial_state

st.set_page_config(page_title="Forge", page_icon="🔥", layout="wide")
st.title("FORGE — Agentic C Code Auditor")

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
    max_retries = st.number_input("Max retries per finding", min_value=1, max_value=10, value=3)
    run = st.button("Run Forge", type="primary", disabled=not uploaded)

if run:
    source_files = {f.name: f.read().decode("utf-8", errors="replace") for f in uploaded}
    state = initial_state(
        source_files=source_files,
        user_description=description or None,
        max_retries=int(max_retries),
    )

    graph = build_graph()

    trace_box = st.container()
    with st.status("Running Forge pipeline...", expanded=True) as status:
        # Stream node-by-node so the trace updates in real time.
        for event in graph.stream(state):
            for node, node_state in event.items():
                trace_box.write(f"**{node}** completed")
                state = node_state  # latest cumulative state
        status.update(label="Forge run complete", state="complete")

    st.subheader("Results")
    col1, col2, col3 = st.columns(3)
    col1.metric("Findings", len(state.get("findings") or []))
    col2.metric("Accepted patches", len(state.get("accepted_patches") or []))
    col3.metric("Escalated", len(state.get("escalated_findings") or []))

    with st.expander("Agent trace"):
        for entry in state.get("agent_trace", []):
            st.write(entry)

    st.download_button(
        "Download full report (JSON)",
        data=json.dumps(state, indent=2, default=str),
        file_name="forge_report.json",
        mime="application/json",
    )
else:
    st.info("Upload one or more `.c` / `.h` files in the sidebar, then click **Run Forge**.")
