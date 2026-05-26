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
    Reads env vars at call time so Streamlit Cloud secrets are always visible.
    """
    import os
    provider = os.getenv("FORGE_LLM_PROVIDER", LLM_PROVIDER)
    model = os.getenv("FORGE_LLM_MODEL", LLM_MODEL)

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY") or ANTHROPIC_API_KEY
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in msg.content if block.type == "text")

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY") or OPENAI_API_KEY
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
        return resp.choices[0].message.content or ""

    raise ValueError(f"Unknown FORGE_LLM_PROVIDER: {provider}")
