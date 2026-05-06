"""Thin wrapper around the Docker sandbox.

Owner: Member 3 (Patch + Validation).

Stub. Real implementation should keep a single warm container per Forge run
(see Risks table in the outline) and expose a `compile_and_test()` function
that returns structured (stdout, stderr, returncode, sanitizer_output).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from forge.config import DOCKER_IMAGE, DOCKER_TIMEOUT_SECONDS


@dataclass
class CompileResult:
    success: bool
    stdout: str
    stderr: str
    returncode: int


def compile_in_sandbox(source_dir: Path, command: str) -> CompileResult:
    """Run `command` inside the sandbox container against the given source dir.

    TODO: replace this stub with a real implementation that:
    - Mounts source_dir read-only into the container.
    - Disables network (--network=none).
    - Runs as a non-root user inside the container.
    - Reuses a long-lived container instead of starting a fresh one each call.
    """
    cmd = [
        "docker", "run", "--rm",
        "--network=none",
        "-v", f"{source_dir}:/work:ro",
        "-w", "/work",
        DOCKER_IMAGE,
        "bash", "-c", command,
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=DOCKER_TIMEOUT_SECONDS,
    )
    return CompileResult(
        success=proc.returncode == 0,
        stdout=proc.stdout,
        stderr=proc.stderr,
        returncode=proc.returncode,
    )
