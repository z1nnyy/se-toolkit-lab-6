"""Regression tests for agent.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = PROJECT_ROOT / "agent.py"


def run_agent_with_mock_server(
    question: str,
    handler_type: type[BaseHTTPRequestHandler],
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the agent against a local mock LLM server."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_type)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    env = os.environ.copy()
    env["LLM_API_KEY"] = "test-key"
    env["LLM_API_BASE"] = f"http://127.0.0.1:{server.server_port}/v1"
    env["LLM_MODEL"] = "mock-model"
    if extra_env:
        env.update(extra_env)

    try:
        result = subprocess.run(
            [sys.executable, str(AGENT_PATH), question],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            env=env,
            check=False,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)

    return result


class MockSimpleAnswerHandler(BaseHTTPRequestHandler):
    """Return a final JSON answer without tool calls."""

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        payload = json.loads(body)

        assert payload["model"] == "mock-model"
        assert payload["messages"][-1]["content"] == "What is 2+2?"
        assert isinstance(payload["tools"], list)

        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {"answer": "2 + 2 = 4.", "source": "wiki/math.md#addition"}
                        ),
                    }
                }
            ]
        }

        response_bytes = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def test_agent_output_structure() -> None:
    """Validate the base JSON shape for a final answer."""
    result = run_agent_with_mock_server("What is 2+2?", MockSimpleAnswerHandler)

    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    output = json.loads(result.stdout)

    assert output["answer"] == "2 + 2 = 4."
    assert output["source"] == "wiki/math.md#addition"
    assert output["tool_calls"] == []
