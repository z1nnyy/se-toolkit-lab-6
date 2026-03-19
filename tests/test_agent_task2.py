"""Regression tests for Task 2 tool calling."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from tests.test_agent_task1 import run_agent_with_mock_server


class MockReadFileHandler(BaseHTTPRequestHandler):
    """Simulate one read_file tool call followed by a final answer."""

    request_count = 0

    def do_POST(self) -> None:  # noqa: N802
        type(self).request_count += 1

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        payload = json.loads(body)
        messages = payload["messages"]

        if type(self).request_count == 1:
            assert messages[-1]["role"] == "user"
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call-read-file",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": json.dumps(
                                            {"path": "wiki/git-workflow.md"}
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
            assert "Git workflow" in messages[-1]["content"]
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "answer": (
                                        "Edit the conflicting file, choose the changes "
                                        "to keep, then stage and commit."
                                    ),
                                    "source": (
                                        "wiki/git-workflow.md#resolving-merge-conflicts"
                                    ),
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


class MockListFilesHandler(BaseHTTPRequestHandler):
    """Simulate one list_files tool call followed by a final answer."""

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
                                    "id": "call-list-files",
                                    "type": "function",
                                    "function": {
                                        "name": "list_files",
                                        "arguments": json.dumps({"path": "wiki"}),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        else:
            assert messages[-1]["role"] == "tool"
            assert "wiki/api.md" in messages[-1]["content"]
            response = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "answer": "The wiki contains documentation files.",
                                    "source": "wiki/coding-agents.md#coding-agents",
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


def test_agent_uses_read_file_tool() -> None:
    """Ensure documentation questions can trigger read_file."""
    MockReadFileHandler.request_count = 0
    result = run_agent_with_mock_server(
        "How do you resolve a merge conflict?",
        MockReadFileHandler,
    )

    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    output = json.loads(result.stdout)

    assert output["source"] == "wiki/git-workflow.md#resolving-merge-conflicts"
    assert output["tool_calls"][0]["tool"] == "read_file"
    assert output["tool_calls"][0]["args"] == {"path": "wiki/git-workflow.md"}


def test_agent_uses_list_files_tool() -> None:
    """Ensure directory discovery questions can trigger list_files."""
    MockListFilesHandler.request_count = 0
    result = run_agent_with_mock_server(
        "What files are in the wiki?",
        MockListFilesHandler,
    )

    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    output = json.loads(result.stdout)

    assert output["tool_calls"][0]["tool"] == "list_files"
    assert output["tool_calls"][0]["args"] == {"path": "wiki"}
