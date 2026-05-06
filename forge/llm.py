"""LLM client wrapper.

Centralizes the choice of provider so agents do not import vendor SDKs
directly. Swap providers by setting FORGE_LLM_PROVIDER in the environment.
"""

from __future__ import annotations

from typing import Optional

from forge.config import (
    ANTHROPIC_API_KEY,
    LLM_MODEL,
    LLM_PROVIDER,
    OPENAI_API_KEY,
)


def chat(prompt: str, system: Optional[str] = None, max_tokens: int = 2048) -> str:
    """Send a single-turn prompt to the configured provider and return text.

    Lazily imports the SDK so projects can install only what they use.
    """
    if LLM_PROVIDER == "anthropic":
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        from anthropic import Anthropic

        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=LLM_MODEL,
            max_tokens=max_tokens,
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in msg.content if block.type == "text")

    if LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set")
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            max_tokens=max_tokens,
            messages=messages,
        )
        return resp.choices[0].message.content or ""

    raise ValueError(f"Unknown FORGE_LLM_PROVIDER: {LLM_PROVIDER}")
