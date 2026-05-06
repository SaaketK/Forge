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

import uuid
import atexit

container_id: str | None = None

@dataclass
class CompileResult:
    success: bool
    stdout: str
    stderr: str
    returncode: int

def start_container(source: Path) -> str:
    global container_id
    if container_id is not None:
        check = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container_id],
            capture_output=True,
            text=True,
        )
        if check.returncode != 0 or check.stdout.strip() != "true":
            print(f"Container {container_id} is not running. Starting a new one.")
            container_id = None

    if container_id is None:
        container_id = str(uuid.uuid4().hex[:8])
        name = f"forge-sandbox-{container_id}"
        process = subprocess.run([
            "docker", "run",
            "--rm",
            "--detach",
            "--name", name,
            "--network=none",
            "-v", f"{source}:/work:ro",
            "-w", "/work",
            "--user", "sandbox",
            DOCKER_IMAGE,
            "sleep", "infinity"
        ],
            capture_output=True,
            text=True,
        )
    if process.returncode != 0:
        raise RuntimeError(f"Failed to start sandbox container: {process.stderr.strip()}")
    container_id = process.stdout.strip()
    atexit.register(stop_container)
    return container_id

def stop_container():
    global container_id
    if container_id is not None:
        subprocess.run(["docker", "stop", container_id], capture_output=True, text=True)
        container_id = None

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
