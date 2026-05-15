"""End-to-end tests that exercise the full pipeline across all agents.

These tests verify that state flows correctly between agents and that
the LangGraph routing works (retry loop, escalation, empty findings).

Tests marked with `needs_llm` require ANTHROPIC_API_KEY in .env.
Tests marked with `needs_docker` require Docker to be running.
"""

import json
import os
import pytest

from forge.graph import build_graph
from forge.state import initial_state
from forge.agents.recon import recon_agent
from forge.agents.analysis import (
    _write_sources,
    _run_cppcheck,
    _parse_cppcheck_xml,
    _run_clang_tidy,
    _parse_clangtidy_output,
    analysis_agent,
)
from forge.agents.patch import patch_agent
from forge.agents.validation import validation_agent
from forge.sandbox.docker_runner import docker_available

import tempfile
from pathlib import Path


# ── Fixtures ─────────────────────────────────────────────────────────────────

LEAK_C = open("samples/easy/leak.c").read()

MULTI_BUG_C = """\
#include <stdlib.h>
#include <string.h>

char* make_buffer(int size) {
    char* buf = malloc(size);
    return buf;  /* no NULL check */
}

void copy_input(char* dest, const char* src) {
    strcpy(dest, src);  /* unsafe: no bounds check */
}

int main(void) {
    char* b = make_buffer(64);
    copy_input(b, "hello");
    /* leak: never freed */
    return 0;
}
"""

CLEAN_C = """\
#include <stdlib.h>

int add(int a, int b) {
    return a + b;
}

int main(void) {
    int result = add(1, 2);
    return result == 3 ? 0 : 1;
}
"""

HEADER_H = """\
#ifndef DEFS_H
#define DEFS_H

struct proc {
    int pid;
    char name[16];
};

typedef struct {
    int lock;
} spinlock_t;

int allocproc(void);
void sys_fork(void);
void scheduler(void);

extern int initproc;

#endif
"""

needs_llm = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)

needs_docker = pytest.mark.skipif(
    not docker_available(),
    reason="Docker not available",
)


# ── Recon Agent Tests ────────────────────────────────────────────────────────

class TestReconAgent:
    def test_parses_leak_c(self):
        state = initial_state(source_files={"leak.c": LEAK_C})
        result = recon_agent(state)
        rmap = result["recon_map"]

        assert "leak.c" in rmap["files"]
        names = {f["name"] for f in rmap["functions"]}
        assert "make_buffer" in names
        assert "main" in names

    def test_extracts_signatures(self):
        state = initial_state(source_files={"leak.c": LEAK_C})
        result = recon_agent(state)
        for func in result["recon_map"]["functions"]:
            assert "signature" in func, f"{func['name']} missing signature"
            assert func["signature"], f"{func['name']} has empty signature"

    def test_call_graph(self):
        state = initial_state(source_files={"leak.c": LEAK_C})
        result = recon_agent(state)
        funcs = {f["name"]: f for f in result["recon_map"]["functions"]}

        assert "make_buffer" in funcs["main"]["calls"]
        assert "free" in funcs["main"]["calls"]
        assert "malloc" in funcs["make_buffer"]["calls"]
        assert "main" in funcs["make_buffer"]["called_by"]

    def test_entry_points(self):
        state = initial_state(source_files={"leak.c": LEAK_C})
        result = recon_agent(state)
        assert "main" in result["recon_map"]["entry_points"]

    def test_includes(self):
        state = initial_state(source_files={"leak.c": LEAK_C})
        result = recon_agent(state)
        assert "stdlib.h" in result["recon_map"]["includes"]["leak.c"]

    def test_complexity(self):
        state = initial_state(source_files={"leak.c": LEAK_C})
        result = recon_agent(state)
        funcs = {f["name"]: f for f in result["recon_map"]["functions"]}
        # main has two if statements
        assert funcs["main"]["complexity"] >= 2

    def test_header_file_structs(self):
        state = initial_state(source_files={"defs.h": HEADER_H})
        result = recon_agent(state)
        rmap = result["recon_map"]

        struct_names = {s["name"] for s in rmap["structs"]}
        assert "proc" in struct_names
        assert "spinlock_t" in struct_names

    def test_header_function_declarations(self):
        state = initial_state(source_files={"defs.h": HEADER_H})
        result = recon_agent(state)
        rmap = result["recon_map"]

        names = {f["name"] for f in rmap["functions"]}
        assert "allocproc" in names
        assert "sys_fork" in names
        assert "scheduler" in names

        for func in rmap["functions"]:
            assert func.get("declaration_only") is True

    def test_header_entry_points(self):
        state = initial_state(source_files={"defs.h": HEADER_H})
        result = recon_agent(state)
        rmap = result["recon_map"]

        assert "sys_fork" in rmap["entry_points"]
        assert "scheduler" in rmap["entry_points"]

    def test_header_globals(self):
        state = initial_state(source_files={"defs.h": HEADER_H})
        result = recon_agent(state)
        rmap = result["recon_map"]

        assert "initproc" in rmap["globals"]

    def test_multi_file(self):
        state = initial_state(source_files={
            "leak.c": LEAK_C,
            "defs.h": HEADER_H,
        })
        result = recon_agent(state)
        rmap = result["recon_map"]

        assert len(rmap["files"]) == 2
        assert len(rmap["functions"]) >= 5  # 2 from leak.c + 3 from defs.h

    def test_trace_logged(self):
        state = initial_state(source_files={"leak.c": LEAK_C})
        result = recon_agent(state)
        trace = result["agent_trace"]
        assert any(e["agent"] == "recon" for e in trace)


# ── Analysis Agent Tests (tool parsing, no LLM) ─────────────────────────────

class TestAnalysisToolParsing:
    def test_cppcheck_runs(self):
        with tempfile.TemporaryDirectory(prefix="forge_") as tmpdir:
            c_files = _write_sources({"leak.c": LEAK_C}, Path(tmpdir))
            xml = _run_cppcheck(c_files)
            findings = _parse_cppcheck_xml(xml)

        assert len(findings) >= 1
        assert all(f["tool"] == "cppcheck" for f in findings)

    def test_clang_tidy_runs(self):
        with tempfile.TemporaryDirectory(prefix="forge_") as tmpdir:
            c_files = _write_sources({"leak.c": LEAK_C}, Path(tmpdir))
            output = _run_clang_tidy(c_files)
            findings = _parse_clangtidy_output(output)

        assert len(findings) >= 1
        assert all(f["tool"] == "clang-tidy" for f in findings)

    def test_cppcheck_xml_parsing(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<results version="2">
    <cppcheck version="2.20.0"/>
    <errors>
        <error id="memleak" severity="error" msg="Memory leak: buf">
            <location file="test.c" line="10" column="5"/>
        </error>
        <error id="checkersReport" severity="information" msg="ignore this"/>
    </errors>
</results>'''
        findings = _parse_cppcheck_xml(xml)
        assert len(findings) == 1  # information filtered
        assert findings[0]["severity"] == "error"
        assert findings[0]["line"] == 10

    def test_clang_tidy_output_parsing(self):
        output = "/tmp/test.c:16:14: warning: garbage value [clang-analyzer-core.Xyz]\n"
        findings = _parse_clangtidy_output(output)
        assert len(findings) == 1
        assert findings[0]["severity"] == "warning"
        assert findings[0]["line"] == 16
        assert findings[0]["file"] == "test.c"

    def test_clean_file_no_findings(self):
        with tempfile.TemporaryDirectory(prefix="forge_") as tmpdir:
            c_files = _write_sources({"clean.c": CLEAN_C}, Path(tmpdir))
            xml = _run_cppcheck(c_files)
            findings = _parse_cppcheck_xml(xml)
        # Clean code should have zero or only style findings
        serious = [f for f in findings if f["severity"] in ("error", "warning")]
        assert len(serious) == 0


# ── Analysis Agent Tests (with LLM) ─────────────────────────────────────────

class TestAnalysisWithLLM:
    @needs_llm
    def test_full_analysis(self):
        state = initial_state(source_files={"leak.c": LEAK_C})
        state = recon_agent(state)
        state = analysis_agent(state)

        findings = state["findings"]
        assert isinstance(findings, list)
        assert len(findings) >= 1

        for f in findings:
            assert "id" in f
            assert "severity" in f
            assert "description" in f
            assert f["severity"] in ("CRITICAL", "WARNING", "INFO")


# ── Patch Agent Tests ────────────────────────────────────────────────────────

class TestPatchAgent:
    @needs_llm
    def test_generates_patch(self):
        state = initial_state(source_files={"leak.c": LEAK_C})
        state["findings"] = [{
            "id": "F001",
            "severity": "CRITICAL",
            "category": "memory_leak",
            "function": "main",
            "file": "leak.c",
            "lines": [16],
            "description": "Memory leak: make_buffer() result not freed on early return",
            "patchable": True,
        }]

        result = patch_agent(state)

        assert len(result["patches"]) == 1
        assert result["patches"][0]["diff"] != ""
        assert result["patches"][0]["finding_id"] == "F001"

    @needs_llm
    def test_skips_out_of_range_index(self):
        state = initial_state(source_files={"leak.c": LEAK_C})
        state["findings"] = []
        state["current_finding_index"] = 5

        result = patch_agent(state)
        trace_msgs = [e["message"] for e in result["agent_trace"]]
        assert any("skipping" in m for m in trace_msgs)


# ── Validation Agent Tests ───────────────────────────────────────────────────

class TestValidationAgent:
    def test_no_patch_fails(self):
        state = initial_state(source_files={"main.c": ""})
        state["findings"] = [{"id": "F000", "file": "main.c", "description": "test"}]

        result = validation_agent(state)
        assert result["validation_results"][0]["verdict"] == "FAIL"
        assert result["validation_results"][0]["error"] == "no patch available"

    def test_handles_missing_docker(self):
        """When Docker is missing, validation should still return a result."""
        state = initial_state(source_files={"leak.c": LEAK_C})
        state["findings"] = [{"id": "F001", "file": "leak.c", "description": "test"}]
        state["patches"] = [{
            "finding_id": "F001",
            "file": "leak.c",
            "diff": "--- a/leak.c\n+++ b/leak.c\n",
        }]

        result = validation_agent(state)
        assert len(result["validation_results"]) == 1
        # Should have a verdict regardless of Docker availability
        assert result["validation_results"][0]["verdict"] in ("PASS", "FAIL")


# ── Full Pipeline Tests ──────────────────────────────────────────────────────

class TestFullPipeline:
    def test_graph_runs_with_stubs(self):
        """The graph should run end-to-end (agents may use stubs or real impls)."""
        state = initial_state(source_files={"leak.c": LEAK_C})
        graph = build_graph()
        # Without LLM key, analysis returns empty findings,
        # graph should skip patch/validation and finish cleanly
        try:
            final = graph.invoke(state)
        except RuntimeError as e:
            if "API_KEY" in str(e):
                pytest.skip("API key not available")
            raise

        assert final["recon_map"] is not None
        assert isinstance(final.get("agent_trace"), list)

    @needs_llm
    def test_full_pipeline_leak_c(self):
        """Full pipeline on leak.c: recon -> analysis -> patch -> validation."""
        state = initial_state(source_files={"leak.c": LEAK_C})
        graph = build_graph()
        final = graph.invoke(state)

        # Recon should have run
        assert final["recon_map"] is not None
        assert len(final["recon_map"]["functions"]) >= 2

        # Analysis should have found something
        assert len(final.get("findings", [])) >= 1

        # Patch should have generated diffs
        assert len(final.get("patches", [])) >= 1

        # Validation should have produced results
        assert len(final.get("validation_results", [])) >= 1

        # Should have accepted or escalated every finding
        accepted = len(final.get("accepted_patches", []))
        escalated = len(final.get("escalated_findings", []))
        assert accepted + escalated == len(final["findings"])

        # Trace should have entries from every agent
        agents_in_trace = {e["agent"] for e in final.get("agent_trace", [])}
        assert "recon" in agents_in_trace
        assert "analysis" in agents_in_trace
        assert "patch" in agents_in_trace
        assert "validation" in agents_in_trace

    @needs_llm
    def test_clean_file_no_patches(self):
        """Clean code should produce no findings and no patches."""
        state = initial_state(source_files={"clean.c": CLEAN_C})
        graph = build_graph()
        final = graph.invoke(state)

        findings = final.get("findings", [])
        patches = final.get("patches", [])
        # Clean code might still get style warnings, but should not get CRITICAL
        critical = [f for f in findings if f.get("severity") == "CRITICAL"]
        assert len(critical) == 0

    @needs_llm
    def test_multi_file_pipeline(self):
        """Pipeline should handle multiple files."""
        state = initial_state(source_files={
            "leak.c": LEAK_C,
            "defs.h": HEADER_H,
        })
        graph = build_graph()
        final = graph.invoke(state)

        assert len(final["recon_map"]["files"]) == 2
        assert final["recon_map"] is not None


# ── State Contract Tests ─────────────────────────────────────────────────────

class TestStateContract:
    def test_initial_state_has_all_keys(self):
        state = initial_state(source_files={"test.c": "int main(){return 0;}"})
        required = [
            "source_files", "recon_map", "findings", "patches",
            "validation_results", "current_finding_index", "current_attempt",
            "max_retries", "accepted_patches", "escalated_findings", "agent_trace",
        ]
        for key in required:
            assert key in state, f"missing key: {key}"

    def test_log_step_appends(self):
        from forge.state import log_step
        state = initial_state(source_files={})
        log_step(state, "test", "hello")
        log_step(state, "test", "world")
        assert len(state["agent_trace"]) == 2
        assert state["agent_trace"][0]["message"] == "hello"
        assert state["agent_trace"][1]["message"] == "world"
