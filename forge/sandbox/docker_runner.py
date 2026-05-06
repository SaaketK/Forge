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
        # check container if still running
        check = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container_id],
            capture_output=True,
            text=True,
        )
        if check.returncode != 0 or check.stdout.strip() != "true":
            print(f"Container {container_id} is not running. Starting a new one.")
            container_id = None

    atexit_registered = False
    if container_id is None:
        suffix = str(uuid.uuid4().hex[:8])
        name = f"forge-sandbox-{suffix}"
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
    if not atexit_registered:
        atexit_registered = True
        atexit.register(stop_container)
    return container_id

def stop_container():
    global container_id
    if container_id is not None:
        subprocess.run(["docker", "stop", container_id], capture_output=True, text=True)
        container_id = None

def compile_in_sandbox(source_dir: Path, command: str) -> CompileResult:
    
    cid = start_container(source_dir)

    process = subprocess.run([
        "docker", "exec", cid,
        "bash", "-c", command,
        ],
        capture_output=True,
        text=True,
        timeout=DOCKER_TIMEOUT_SECONDS,
    )
    response = process.returncode == 0
    return CompileResult(
        success=response,
        stdout=process.stdout,
        stderr=process.stderr,
        returncode=process.returncode,
    )

def apply_and_compile(source_dir: Path, patch: str, command: str) -> CompileResult:
    import tempfile, shutil
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        shutil.copytree(source_dir, temp_path / "src")
        (temp_path / "src" / "fix.patch").write_text(patch)
        return compile_in_sandbox(temp_path / "src", f"patch -p1 < fix.patch && {command}")