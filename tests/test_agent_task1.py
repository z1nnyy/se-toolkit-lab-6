"""Regression tests for agent.py (Task 1)."""

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


class MockLLMHandler(BaseHTTPRequestHandler):
    """Return a fixed OpenAI-compatible chat completion response."""

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        payload = json.loads(body)

        assert payload["model"] == "mock-model"
        assert payload["messages"][-1]["content"] == "What is 2+2?"

        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "2 + 2 = 4.",
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
        """Silence noisy test server logs."""
        return


def test_agent_output_structure() -> None:
    """Run the agent as a subprocess and validate the output JSON."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockLLMHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    env = os.environ.copy()
    env["LLM_API_KEY"] = "test-key"
    env["LLM_API_BASE"] = f"http://127.0.0.1:{server.server_port}/v1"
    env["LLM_MODEL"] = "mock-model"

    try:
        result = subprocess.run(
            [sys.executable, str(AGENT_PATH), "What is 2+2?"],
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

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    output = json.loads(result.stdout)

    assert output["answer"] == "2 + 2 = 4."
    assert "tool_calls" in output
    assert output["tool_calls"] == []
