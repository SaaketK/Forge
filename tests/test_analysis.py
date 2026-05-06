# Tests for the Analysis Agent

import json
from pathlib import Path
from forge.agents.analysis import (
    _write_sources,
    _run_cppcheck,
    _parse_cppcheck_xml,
    _run_clang_tidy,
    _parse_clangtidy_output,
)
from forge.state import initial_state
from forge.agents.recon import recon_agent
import tempfile


def test_cppcheck_runs():
    # cppcheck finds the style issue in leak.c
    source = {"leak.c": open("samples/easy/leak.c").read()}
    with tempfile.TemporaryDirectory(prefix="forge_") as tmpdir:
        c_files = _write_sources(source, Path(tmpdir))
        xml = _run_cppcheck(c_files)
        findings = _parse_cppcheck_xml(xml)

    print("cppcheck:", json.dumps(findings, indent=2))
    assert len(findings) >= 1
    assert any(f["tool"] == "cppcheck" for f in findings)
    print("cppcheck PASSED")


def test_clang_tidy_runs():
    # clang-tidy finds the garbage value read in leak.c
    source = {"leak.c": open("samples/easy/leak.c").read()}
    with tempfile.TemporaryDirectory(prefix="forge_") as tmpdir:
        c_files = _write_sources(source, Path(tmpdir))
        output = _run_clang_tidy(c_files)
        findings = _parse_clangtidy_output(output)

    print("clang-tidy:", json.dumps(findings, indent=2))
    assert len(findings) >= 1
    assert any(f["tool"] == "clang-tidy" for f in findings)
    print("clang-tidy PASSED")


def test_cppcheck_parse_known_xml():
    # Parse a known XML string without running cppcheck.
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
    print("parsed:", json.dumps(findings, indent=2))
    assert len(findings) == 1  # information filtered out
    assert findings[0]["severity"] == "error"
    assert findings[0]["line"] == 10
    print("cppcheck parse PASSED")


def test_clang_tidy_parse_known_output():
    # Parse known clang-tidy text without running it.
    output = """/tmp/test.c:16:14: warning: The left operand of '==' is a garbage value [clang-analyzer-core.UndefinedBinaryOperatorResult]
/tmp/test.c:22:5: error: use of undeclared identifier 'x' [clang-diagnostic-error]"""
    findings = _parse_clangtidy_output(output)
    print("parsed:", json.dumps(findings, indent=2))
    assert len(findings) == 2
    assert findings[0]["severity"] == "warning"
    assert findings[0]["line"] == 16
    assert findings[1]["severity"] == "error"
    assert findings[1]["file"] == "test.c"
    print("clang-tidy parse PASSED")


def test_empty_file():
    # No findings for an empty file
    source = {"empty.c": "int main(void) { return 0; }"}
    with tempfile.TemporaryDirectory(prefix="forge_") as tmpdir:
        c_files = _write_sources(source, Path(tmpdir))
        xml = _run_cppcheck(c_files)
        findings = _parse_cppcheck_xml(xml)
    assert findings == []
    print("empty file PASSED")


if __name__ == "__main__":
    test_cppcheck_runs()
    test_clang_tidy_runs()
    test_cppcheck_parse_known_xml()
    test_clang_tidy_parse_known_output()
    test_empty_file()
    print("\nAll analysis tests passed!")