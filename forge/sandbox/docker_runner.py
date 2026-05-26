from __future__ import annotations
import shutil
import tempfile

import subprocess
from dataclasses import dataclass
from pathlib import Path

from forge.config import DOCKER_IMAGE, DOCKER_TIMEOUT_SECONDS

import uuid
import atexit

container_id: str | None = None


def docker_available() -> bool:
    # check install
    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

@dataclass
class CompileResult:
    success: bool
    stdout: str
    stderr: str
    returncode: int
    sanitizer_output: str = ""

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
            "--platform", "linux/amd64",
            "--name", name,
            "--network=none",
            "-v", f"{source}:/work:ro",
            "-w", "/work",
            "--user", "forge",
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
    
@dataclass
class PatchResult:
    success: bool
    patched_dir: Path | None
    error: str = ""

def apply_patch(source_dir: Path, patch_dict: dict) -> PatchResult:
    tmp_dir = Path(tempfile.mkdtemp(prefix="forge_patch_"))
    try:
        shutil.copytree(source_dir, tmp_dir, dirs_exist_ok=True)

        patch_content = patch_dict.get("diff", "")
        if not patch_content:
            return PatchResult(success=False, patched_dir=None,
                               error="patch_dict has no diff content")

        patch_file = tmp_dir / "forge.patch"
        patch_file.write_text(patch_content)

        proc = subprocess.run(
            ["patch", "-p1", "-i", str(patch_file)],
            cwd=str(tmp_dir),
            capture_output=True,
            text=True,
        )
        patch_file.unlink()

        if proc.returncode != 0:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return PatchResult(success=False, patched_dir=None, error=proc.stderr)

        return PatchResult(success=True, patched_dir=tmp_dir)

    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return PatchResult(success=False, patched_dir=None, error=str(e))

def compile_and_test(
    source_dir: Path,
    source_file: str,
    extra_flags: str = "",
) -> CompileResult:
    command = (
        f"gcc -Wall -Werror "
        f"-fsanitize=address,undefined "
        f"{extra_flags} "
        f"-o /tmp/forge_bin {source_file} && "
        f"ASAN_OPTIONS=halt_on_error=0 /tmp/forge_bin"
    )

    result = compile_in_sandbox(source_dir, command)

    sanitizer_lines = [
        line for line in result.stderr.splitlines()
        if any(marker in line for marker in [
            "ERROR: AddressSanitizer",
            "ERROR: LeakSanitizer",
            "runtime error:",
            "SUMMARY:",
        ])
    ]

    sanitizer_output = "\n".join(sanitizer_lines)

    return CompileResult(
        success=result.success and not sanitizer_output,
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
        sanitizer_output=sanitizer_output,
    )