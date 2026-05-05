"""Central configuration. Read environment variables here, not in agents."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent

# Pipeline limits
MAX_RETRIES = int(os.getenv("FORGE_MAX_RETRIES", "3"))

# LLM configuration. Pick the provider you want by setting FORGE_LLM_PROVIDER.
LLM_PROVIDER = os.getenv("FORGE_LLM_PROVIDER", "anthropic")  # "anthropic" | "openai"
LLM_MODEL = os.getenv("FORGE_LLM_MODEL", "claude-sonnet-4-6")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Docker sandbox
DOCKER_IMAGE = os.getenv("FORGE_DOCKER_IMAGE", "forge-sandbox:latest")
DOCKER_TIMEOUT_SECONDS = int(os.getenv("FORGE_DOCKER_TIMEOUT", "60"))

# Where to write artifacts (logs, intermediate JSON, generated diffs)
ARTIFACTS_DIR = ROOT_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)
