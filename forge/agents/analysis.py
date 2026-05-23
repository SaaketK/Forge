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

import json
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from forge.llm import chat
from forge.state import ForgeState, log_step

def _write_sources(source_files: dict[str, str], dest: Path) -> list[Path]:
    c_files = []
    for name, content in source_files.items():
        p = dest / name
        p.write_text(content)
        if name.endswith(".c"):
            c_files.append(p)
    return c_files

def _run_cppcheck(c_files: list[Path]) -> str:
    if not c_files:
        return ""
    result = subprocess.run(
        ["cppcheck", "--enable=all", "--xml"] + [str(f) for f in c_files],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stderr # cpp writes XML to stderr 

def _parse_cppcheck_xml(xml: str) -> list[dict]:
    if not xml.strip():
        return []
    found = []
    root = ET.fromstring(xml)
    for error in root.iter("error"):
        severity = error.get("severity", "")
        if severity == "information":
            continue
        location = error.find("location")
        found.append({
            "tool": "cppcheck",
            "severity": severity,
            "id": error.get("id", ""),
            "message": error.get("msg", ""),
            "verbose": error.get("verbose", ""),
            "file": Path(location.get("file", "")).name if location is not None else "",
            "line": int(location.get("line", "0")) if location is not None else 0,
        })
    return found

def _find_clang_tidy() -> str:
    if shutil.which("clang-tidy"):
        return "clang-tidy"
    brew_path = "/opt/homebrew/opt/llvm/bin/clang-tidy"
    if Path(brew_path).exists():
        return brew_path
    raise FileNotFoundError("clang-tidy not found")

def _get_sysroot() -> str:
    try:
       result = subprocess.run(
            ["xcrun", "--show-sdk-path"],
            capture_output=True,
            text=True,
            timeout=10,
        )
       return result.stdout.strip()
    except FileNotFoundError:
       return ""

def _run_clang_tidy(c_files: list[Path]) -> str:
    if not c_files:
        return ""
    sysroot = _get_sysroot()
    cmd = [
        _find_clang_tidy(),
        *[str(f) for f in c_files],
        "-checks=clang-analyzer-*,bugprone-*,cert-*",
        "--",
    ]
    if sysroot:
        cmd.append(f"-isysroot{sysroot}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return result.stdout

_CLANG_TIDY_REGEX = re.compile(r"^(.+?):(\d+):(\d+): (warning|error): (.+?) \[(.+?)\]$", re.MULTILINE)

def _parse_clangtidy_output(output: str) -> list[dict]:
    found = []
    for match in _CLANG_TIDY_REGEX.finditer(output):
        found.append({
            "tool": "clang-tidy",
            "id": match.group(6),
            "severity": match.group(4),
            "message": match.group(5),
            "file": Path(match.group(1)).name,
            "line": int(match.group(2)),
        })
    return found

_ANALYSIS_PROMPT = """You are a C systems expert. You will receive:
1) Raw static analysis findings from cppcheck and clang-tidy.
2) A structural map of the codebase (functions, call graph, entry points).

Your job:
1) Deduplicate findings that refer to the same root cause.
2) Classify each unique finding: CRITICAL / WARNING / INFO.
3) Prioritize by: severity * reachability (is the function called from an entry point?).
4) For each finding, identify the specific function and line range.
5) Decide which findings are patchable by an AI vs which ones need human judgment.

Respond with ONLY a JSON object (no markdown, no explanation):
{
  "findings": [
    {
      "id": "F001",
      "severity": "CRITICAL",
      "category": "memory_leak",
      "tool_source": "cppcheck",
      "function": "function_name",
      "file": "filename.c",
      "lines": [42],
      "description": "Human-readable explanation of the bug",
      "reachable_from": ["main"],
      "patchable": true
    }
  ],
  "summary": "X critical, Y warnings, Z informational. N duplicates removed."
}"""

def _llm_interpret(raw: list[dict], recon_map: dict) -> list[dict]:
   prompt = f"""Raw static analysis findings: 
{json.dumps(raw, indent=2)}

Codebase Structural Map:
{json.dumps(recon_map, indent=2)}"""
   response = chat(prompt, system=_ANALYSIS_PROMPT, max_tokens = 4096)
   cleaned = response.strip()
   if cleaned.startswith("```"):
      cleaned = cleaned.split("\n", 1)[1]
      cleaned = cleaned.rsplit("```", 1)[0]
   try:
      parsed = json.loads(cleaned)
   except json.JSONDecodeError as exc:
      raise RuntimeError(f"LLM returned non-JSON response: {exc}\n---\n{cleaned}") from exc
   return parsed.get("findings", [])

def analysis_agent(state: ForgeState) -> ForgeState:
   source_files = state.get("source_files", {})
   recon_map = state.get("recon_map", {})

   with tempfile.TemporaryDirectory(prefix="forge_") as tmpdir:
      c_files = _write_sources(source_files, Path(tmpdir))
      log_step(state, "analysis", "running cpp-check")
      cppcheck_xml = _run_cppcheck(c_files)
      cppcheck_findings = _parse_cppcheck_xml(cppcheck_xml)

      log_step(state, "analysis", "running clang-tidy")
      clang_output = _run_clang_tidy(c_files)
      clang_findings = _parse_clangtidy_output(clang_output)

   raw_findings = cppcheck_findings + clang_findings
   log_step(state, "analysis",
            f"tools returned {len(raw_findings)} raw findings "
            f"({len(cppcheck_findings)} cppcheck, {len(clang_findings)} clang-tidy)")
   
   if not raw_findings:
      state["findings"] = []  
      log_step(state, "analysis", "nothing found, no patches made")
      return state
   
   log_step(state, "analysis", "sending to LLM for interpretation")
   findings = _llm_interpret(raw_findings, recon_map)
   state["findings"] = findings
   log_step(state, "analysis",
            f"LLM returned {len(findings)} deduplicated findings")
   return state

