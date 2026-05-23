"""Patch Agent — generates unified-diff patches for each finding.

Owner: Member 3 (Patch + Validation).

This is a stub. Real implementation should:
1. For the current finding (state["current_finding_index"]), extract the
   relevant function source plus call-graph context.
2. Send to the LLM with the prompt from section 4.3 of the outline.
3. Parse the output into a unified-diff string and store on state["patches"].
4. If the validation feedback loop returned errors from a previous attempt,
   include them in the prompt so the LLM does not repeat its mistake.
"""

from __future__ import annotations

from forge.llm import chat
from forge.state import ForgeState, log_step

PATCH_SYSTEM_PROMPT = """You are an expert C/C++ security engineer.    
You will be given a source file and a specific bug finding.
You must generate a minimal unified diff patch that fixes the bug.

Rules:
- Output ONLY a valid unified diff (--- a/file +++ b/file format)
- Make the smallest possible change to fix the bug
- Do not change unrelated code
- Do not include any explanation outside the diff
"""

def _build_prompt(finding: dict, source_files: dict, prev_errors: str = "") -> str:
    file_name = finding.get("file", "")
    source = source_files.get(file_name, "")
    prompt = f"""Finding:
{finding}

Source file ({file_name}):
```c
{source}
```
"""
    
    if prev_errors:
        prompt += f"""
Previous patch attempt failed with these errors:
{prev_errors}

Do NOT repeat the same mistake. Generate a corrected patch.
"""

    prompt += "\nGenerate a unified diff patch to fix this finding:"
    return prompt


def _extract_diff(raw: str) -> str:
    """Strip markdown code fences if the LLM wrapped the diff in them."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1])
    return raw.strip()



def patch_agent(state: ForgeState) -> ForgeState:
    idx = state.get("current_finding_index", 0)
    attempt = state.get("current_attempt", 0)
    log_step(state, "patch", f"generating patch for finding #{idx} (attempt {attempt + 1})")
    
    findings = state.get("findings") or []
    if idx >= len(findings):
        log_step(state, "patch", f"no finding at index {idx}, skipping")
        return state
    
    finding = findings[idx]
    source_files = state.get("source_files", {})

    prev_errors = ""
    if attempt > 0:
        validation_results = state.get("validation_results", [])
        if validation_results:
            last = validation_results[-1]
            prev_errors = "\n".join(filter(None, [last.get("stderr", ""), last.get("sanitizer_output", ""),]))

    prompt = _build_prompt(finding, source_files, prev_errors)

    try:
        raw = chat(prompt, system=PATCH_SYSTEM_PROMPT, max_tokens=2048)
        diff = _extract_diff(raw)

        state.setdefault("patches", []).append({
            "finding_id": finding.get("id", f"F{idx:03d}"),
            "file": finding.get("file", ""),
            "diff": diff,
            "confidence": 1.0,
            "explanation": f"patch for: {finding.get('description', '')}",
        })
        log_step(state, "patch", f"patch generated for finding #{idx}")

    except Exception as e:
        log_step(state, "patch", f"patch generation failed: {e}")
        state.setdefault("patches", []).append({
            "finding_id": f"F{idx:03d}",
            "file": "",
            "diff": "",
            "confidence": 0.0,
            "explanation": f"failed: {str(e)}"
        })                                                  
    return state
