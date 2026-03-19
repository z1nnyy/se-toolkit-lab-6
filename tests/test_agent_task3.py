"""Regression tests for Task 3 system-agent behavior."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tests.test_agent_task1 import run_agent_with_mock_server


class MockFrameworkHandler(BaseHTTPRequestHandler):
    """Simulate a source-code lookup for the backend framework."""

    request_count = 0

    def do_POST(self) -> None:  # noqa: N802
        type(self).request_count += 1

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        payload = json.loads(body)
        messages = payload["messages"]

        if type(self).request_count == 1:
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call-read-main",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": json.dumps(
                                            {"path": "backend/app/main.py"}
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        else:
            assert messages[-1]["role"] == "tool"
            assert "FastAPI" in messages[-1]["content"]
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "answer": "The backend uses FastAPI.",
                                    "source": "backend/app/main.py#L1",
                                }
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


class MockDataQuestionHandler(BaseHTTPRequestHandler):
    """Simulate a live data question that requires query_api."""

    request_count = 0

    def do_POST(self) -> None:  # noqa: N802
        type(self).request_count += 1

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        payload = json.loads(body)
        messages = payload["messages"]

        if type(self).request_count == 1:
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call-query-items",
                                    "type": "function",
                                    "function": {
                                        "name": "query_api",
                                        "arguments": json.dumps(
                                            {"method": "GET", "path": "/items/"}
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        else:
            assert messages[-1]["role"] == "tool"
            assert '"status_code": 200' in messages[-1]["content"]
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "answer": "There are 3 items in the database.",
                                    "source": "",
                                }
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


class MockBackendHandler(BaseHTTPRequestHandler):
    """Return a fixed items list for query_api tests."""

    def do_GET(self) -> None:  # noqa: N802
        assert self.path == "/items/"
        assert self.headers.get("Authorization") == "Bearer backend-test-key"

        response_bytes = json.dumps(
            [
                {"id": 1, "title": "Item 1"},
                {"id": 2, "title": "Item 2"},
                {"id": 3, "title": "Item 3"},
            ]
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def test_agent_reads_source_code_for_framework_question() -> None:
    """Ensure read_file still handles source-code questions in Task 3."""
    MockFrameworkHandler.request_count = 0
    result = run_agent_with_mock_server(
        "What framework does the backend use?",
        MockFrameworkHandler,
    )

    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    output = json.loads(result.stdout)

    assert "FastAPI" in output["answer"]
    assert output["tool_calls"][0]["tool"] == "read_file"
    assert output["tool_calls"][0]["args"] == {"path": "backend/app/main.py"}


def test_agent_uses_query_api_for_data_question() -> None:
    """Ensure query_api is used for live data questions."""
    MockDataQuestionHandler.request_count = 0

    backend_server = ThreadingHTTPServer(("127.0.0.1", 0), MockBackendHandler)
    backend_thread = threading.Thread(target=backend_server.serve_forever, daemon=True)
    backend_thread.start()

    try:
        result = run_agent_with_mock_server(
            "How many items are in the database?",
            MockDataQuestionHandler,
            extra_env={
                "LMS_API_KEY": "backend-test-key",
                "AGENT_API_BASE_URL": f"http://127.0.0.1:{backend_server.server_port}",
            },
        )
    finally:
        backend_server.shutdown()
        backend_server.server_close()
        backend_thread.join(timeout=1)

    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    output = json.loads(result.stdout)

    assert "3" in output["answer"]
    assert output["tool_calls"][0]["tool"] == "query_api"
    assert output["tool_calls"][0]["args"] == {"method": "GET", "path": "/items/"}
