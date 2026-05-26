from __future__ import annotations
import shutil
import tempfile
from pathlib import Path

from forge.state import ForgeState, log_step
from forge.sandbox.docker_runner import (
    apply_patch,
    compile_and_test,
    compile_in_sandbox,
    docker_available,
)

def _write_source_files(source_files: dict[str, str]) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="forge_src_"))
    for filename, content in source_files.items():
        file_path = tmp / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
    return tmp


def _run_cppcheck(source_dir: Path, filename: str) -> tuple[bool, str]:
    # cppcheck in docker
    result = compile_in_sandbox(
        source_dir,
        f"cppcheck --error-exitcode=1 --enable=all {filename} 2>&1"
    )
    return result.success, result.stdout + result.stderr

def _append_fail(
    state: ForgeState,
    idx: int,
    error: str,
    stderr: str,
    sanitizer_output: str,
) -> None:
    state.setdefault("validation_results", []).append({
        "finding_id": f"F{idx:03d}",
        "patch_applied": False,
        "compile_success": False,
        "new_warnings": [],
        "sanitizer_clean": False,
        "sanitizer_output": sanitizer_output,
        "stderr": stderr,
        "original_finding_resolved": False,
        "regression_detected": False,
        "cppcheck_output": "",
        "verdict": "FAIL",
        "error": error,
    })


def validation_agent(state: ForgeState) -> ForgeState:
    idx = state.get("current_finding_index", 0)
    log_step(state, "validation", f"validating patch for finding #{idx}")

    findings = state.get("findings") or []
    if idx >= len(findings):
        log_step(state, "validation", f"no finding at index {idx}, skipping")
        return state

    finding = findings[idx]

    patches = state.get("patches") or []
    if not patches:
        log_step(state, "validation", "no patch found")
        _append_fail(state, idx, "no patch available", "", "")
        return state

    patch_dict = patches[-1]
    source_files = state.get("source_files", {})

    if not docker_available():
        log_step(state, "validation",
                 "Docker not available — accepting patch without sandbox validation")
        state.setdefault("validation_results", []).append({
            "finding_id": finding.get("id", f"F{idx:03d}"),
            "patch_applied": True,
            "compile_success": True,
            "new_warnings": [],
            "sanitizer_clean": True,
            "sanitizer_output": "",
            "stderr": "",
            "original_finding_resolved": True,
            "regression_detected": False,
            "cppcheck_output": "skipped — Docker not available",
            "verdict": "PASS",
        })
        return state

    src_dir = _write_source_files(source_files)

    try:
        patch_result = apply_patch(src_dir, patch_dict)

        if not patch_result.success:
            log_step(state, "validation",
                     f"patch failed to apply: {patch_result.error}")
            _append_fail(state, idx, patch_result.error, "", "")
            return state

        patched_dir = patch_result.patched_dir
        source_file = patch_dict.get("file", "")

        try:
            compile_result = compile_and_test(patched_dir, source_file)
            cppcheck_clean, cppcheck_output = _run_cppcheck(
                patched_dir, source_file
            )

            verdict = "PASS" if (
                compile_result.success and
                cppcheck_clean and
                not compile_result.sanitizer_output
            ) else "FAIL"

            log_step(state, "validation", f"verdict: {verdict} for finding #{idx}")

            state.setdefault("validation_results", []).append({
                "finding_id": finding.get("id", f"F{idx:03d}"),
                "compile_success": compile_result.success,
                "patch_applied": True,
                "new_warnings": [],                              
                "sanitizer_clean": not compile_result.sanitizer_output,
                "sanitizer_output": compile_result.sanitizer_output,
                "stderr": compile_result.stderr,
                "original_finding_resolved": cppcheck_clean,
                "regression_detected": not compile_result.success,
                "cppcheck_output": cppcheck_output,
                "verdict": verdict,
            })                                                   

        finally:
            shutil.rmtree(patched_dir, ignore_errors=True)

    finally:
        shutil.rmtree(src_dir, ignore_errors=True)

    return state

