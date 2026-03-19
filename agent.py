#!/usr/bin/env python3
"""Task 1 agent CLI."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ENV_FILE = Path(__file__).with_name(".env.agent.secret")
DEFAULT_TIMEOUT_SECONDS = 60.0


def load_env_file() -> None:
    """Load environment variables from .env.agent.secret when present."""
    if not ENV_FILE.exists():
        return

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def require_env(name: str) -> str:
    """Return a required environment variable or raise a clear error."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value


def parse_answer_content(content: object) -> str:
    """Extract text from OpenAI-compatible response content."""
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        answer = "".join(text_parts).strip()
        if answer:
            return answer

    raise RuntimeError("LLM response did not include text content")


def call_llm(question: str) -> str:
    """Send the user's question to the configured LLM."""
    api_key = require_env("LLM_API_KEY")
    api_base = require_env("LLM_API_BASE").rstrip("/")
    model = require_env("LLM_MODEL")

    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a concise assistant. Answer the user's question directly."
                ),
            },
            {"role": "user", "content": question},
        ],
        "temperature": 0,
    }

    timeout = httpx.Timeout(DEFAULT_TIMEOUT_SECONDS)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise RuntimeError("LLM request timed out") from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip()
        raise RuntimeError(
            f"LLM API returned {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Could not reach LLM API: {exc}") from exc

    data = response.json()
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("LLM response did not contain choices")

    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise RuntimeError("LLM response did not contain a message")

    return parse_answer_content(message.get("content"))


def main() -> int:
    load_env_file()

    if len(sys.argv) != 2:
        print('Usage: uv run agent.py "<question>"', file=sys.stderr)
        return 1

    question = sys.argv[1].strip()
    if not question:
        print("Question must not be empty", file=sys.stderr)
        return 1

    try:
        answer = call_llm(question)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    result = {"answer": answer, "tool_calls": []}
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
