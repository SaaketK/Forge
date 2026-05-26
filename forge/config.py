from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent

MAX_RETRIES = int(os.getenv("FORGE_MAX_RETRIES", "3"))

LLM_PROVIDER = os.getenv("FORGE_LLM_PROVIDER", "anthropic") 
LLM_MODEL = os.getenv("FORGE_LLM_MODEL", "claude-sonnet-4-6")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DOCKER_IMAGE = os.getenv("FORGE_DOCKER_IMAGE", "forge-sandbox:latest")
DOCKER_TIMEOUT_SECONDS = int(os.getenv("FORGE_DOCKER_TIMEOUT", "60"))

ARTIFACTS_DIR = ROOT_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)
