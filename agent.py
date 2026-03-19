#!/usr/bin/env python3
"""Documentation agent CLI."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

ENV_FILE = Path(__file__).with_name(".env.agent.secret")
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_TOOL_CALLS = 10
MAX_FILE_CHARS = 20000

SYSTEM_PROMPT = """
You are a documentation agent for this repository.

Use repository tools to answer questions from project documentation instead of guessing.
For documentation questions, start by exploring the wiki with list_files("wiki"), then read the
most relevant file with read_file(...).

When you are ready to answer, respond with JSON only:
{"answer":"...","source":"wiki/file.md#section-anchor"}

Rules:
- Prefer wiki sources when answering documentation questions.
- Include a concrete source reference in the source field.
- Do not invent files or anchors.
- If a tool returns an error, adjust and try again.
""".strip()

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file from the repository using a relative path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative file path from the repository root.",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List files and directories at a repository path using a relative path."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from the repository root.",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
]


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


def parse_text_content(content: object) -> str:
    """Extract text from OpenAI-compatible message content."""
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        return "".join(text_parts).strip()

    return ""


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from a model response."""
    text = text.strip()
    if not text:
        raise RuntimeError("LLM response did not include answer text")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or start >= end:
            raise RuntimeError("Final LLM response was not valid JSON") from None
        parsed = json.loads(text[start : end + 1])

    if not isinstance(parsed, dict):
        raise RuntimeError("Final LLM response JSON must be an object")
    return parsed


def normalize_relative_path(path_value: str) -> Path:
    """Resolve a repository-relative path and prevent traversal."""
    raw_path = path_value.strip()
    if not raw_path:
        raise RuntimeError("Path must not be empty")

    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise RuntimeError("Absolute paths are not allowed")

    resolved = (PROJECT_ROOT / candidate).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise RuntimeError("Path escapes the repository root") from exc

    return resolved


def read_file(path_value: str) -> str:
    """Read a repository file."""
    try:
        resolved = normalize_relative_path(path_value)
    except RuntimeError as exc:
        return f"Error: {exc}"

    if not resolved.exists():
        return "Error: File does not exist"
    if not resolved.is_file():
        return "Error: Path is not a file"

    try:
        text = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "Error: File is not valid UTF-8 text"

    if len(text) > MAX_FILE_CHARS:
        return text[:MAX_FILE_CHARS] + "\n\n[truncated]"
    return text


def list_files(path_value: str) -> str:
    """List directory entries at a repository path."""
    try:
        resolved = normalize_relative_path(path_value)
    except RuntimeError as exc:
        return f"Error: {exc}"

    if not resolved.exists():
        return "Error: Directory does not exist"
    if not resolved.is_dir():
        return "Error: Path is not a directory"

    entries: list[str] = []
    for entry in sorted(resolved.iterdir(), key=lambda item: item.name):
        relative_entry = entry.relative_to(PROJECT_ROOT).as_posix()
        if entry.is_dir():
            entries.append(f"{relative_entry}/")
        else:
            entries.append(relative_entry)
    return "\n".join(entries)


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute a supported tool and return its text result."""
    path_value = arguments.get("path")
    if not isinstance(path_value, str):
        return "Error: 'path' must be a string"

    if name == "read_file":
        return read_file(path_value)
    if name == "list_files":
        return list_files(path_value)
    return f"Error: Unknown tool '{name}'"


def send_chat_completion(
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Send a chat completion request."""
    api_key = require_env("LLM_API_KEY")
    api_base = require_env("LLM_API_BASE").rstrip("/")
    model = require_env("LLM_MODEL")

    timeout = httpx.Timeout(DEFAULT_TIMEOUT_SECONDS)
    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 0,
    }

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

    return message


def run_agent(question: str) -> dict[str, Any]:
    """Run the documentation agent loop."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    recorded_tool_calls: list[dict[str, Any]] = []
    total_tool_calls = 0

    while True:
        message = send_chat_completion(messages)
        tool_calls = message.get("tool_calls") or []

        if isinstance(tool_calls, list) and tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": message.get("content") or "",
                    "tool_calls": tool_calls,
                }
            )

            for tool_call in tool_calls:
                if total_tool_calls >= MAX_TOOL_CALLS:
                    break

                function = tool_call.get("function")
                if not isinstance(function, dict):
                    continue

                name = function.get("name")
                arguments_raw = function.get("arguments", "{}")

                if not isinstance(name, str):
                    continue

                try:
                    arguments = json.loads(arguments_raw)
                except json.JSONDecodeError:
                    arguments = {}

                if not isinstance(arguments, dict):
                    arguments = {}

                result = execute_tool(name, arguments)
                recorded_tool_calls.append(
                    {"tool": name, "args": arguments, "result": result}
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", ""),
                        "content": result,
                    }
                )
                total_tool_calls += 1

            if total_tool_calls >= MAX_TOOL_CALLS:
                return {
                    "answer": "Stopped after reaching the maximum number of tool calls.",
                    "source": "",
                    "tool_calls": recorded_tool_calls,
                }

            continue

        content = parse_text_content(message.get("content"))
        final_payload = extract_json_object(content)
        answer = final_payload.get("answer", "")
        source = final_payload.get("source", "")

        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError("Final LLM response did not include a valid answer")
        if not isinstance(source, str):
            raise RuntimeError("Final LLM response did not include a valid source")

        return {
            "answer": answer.strip(),
            "source": source.strip(),
            "tool_calls": recorded_tool_calls,
        }


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
        result = run_agent(question)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
