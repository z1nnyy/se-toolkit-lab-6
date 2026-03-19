# Agent Documentation

## Overview

This project agent started in Task 1 as a simple CLI that sent one question to an OpenAI-compatible LLM API and printed a JSON answer. In Task 2 it became a documentation agent with repository tools. In Task 3 it becomes a system agent: it can still inspect the repository, but it can also query the running backend API to answer live questions about data, auth behavior, status codes, and runtime failures. The final result is still a single CLI program, `agent.py`, but now it supports a small tool-based reasoning loop instead of a single request-response exchange.

The agent always prints one JSON object to stdout. Its output contains `answer`, `source`, and `tool_calls`. The `source` field is used when a file or wiki section supports the answer. For API-only questions, `source` may be empty. All progress and error information stays on stderr so stdout remains valid JSON for the autochecker.

## Architecture

The agent loads configuration from environment variables. For local development it reads `.env.agent.secret` for LLM settings and `.env.docker.secret` for backend API settings. Environment variables injected by the shell or autochecker take priority, which matters because the grader uses different credentials and may provide a different backend URL.

The main loop works like this:

1. Build the message history with a system prompt and the user question.
2. Send the question plus tool schemas to the LLM.
3. If the LLM asks for tools, execute them locally and append the tool results as `tool` role messages.
4. Repeat until the model returns a final JSON answer or the tool limit is reached.
5. Print the final JSON result.

## Tools

### `list_files`

Lists repository files and directories from a relative path. It helps the model discover where relevant information lives before opening a file directly.

### `read_file`

Reads a UTF-8 text file from the repository. This tool is used for wiki questions, source-code inspection, Docker and deployment questions, and bug diagnosis after reproducing an issue.

### `query_api`

Calls the deployed backend API and returns a JSON string with `status_code` and `body`. By default it authenticates with `LMS_API_KEY` using the `Authorization: Bearer` header. The base URL comes from `AGENT_API_BASE_URL`, which defaults to `http://localhost:42002`. This keeps the agent compatible with both local development and the autochecker environment. For unauthenticated checks, the agent supports a special `GET_NO_AUTH` method convention so the LLM can intentionally test the API without sending the backend key.

## Safety and Path Handling

Repository tools only accept relative paths. Absolute paths are rejected, path traversal is blocked after resolution, and invalid requests return error strings instead of crashing the program. This is important both for correctness and for keeping the tool outputs predictable for the LLM.

## Prompt Strategy

The system prompt tells the model how to route questions:

- wiki/documentation questions: prefer `wiki/` with `list_files` and `read_file`
- source-code questions: inspect code directly with repository tools
- live data and status-code questions: use `query_api`
- bug diagnosis: reproduce with `query_api`, then inspect the source with `read_file`

This routing is important for the benchmark because the evaluator checks not only the answer text but also whether the correct tools were used.

## Testing and Benchmarking

The regression tests do not call the real LLM or the real backend. Instead, they use tiny local mock HTTP servers that emulate both the OpenAI-compatible chat API and, for Task 3, the backend API. That keeps the tests deterministic and avoids burning OpenRouter credits during development.

Local regression tests currently cover:

- base JSON output
- `read_file`
- `list_files`
- source-code lookup for framework detection
- `query_api` for live data questions

Run them with:

```bash
uv run pytest tests/test_agent_task1.py tests/test_agent_task2.py tests/test_agent_task3.py -v
```

Benchmark status: local regression tests pass. Full `run_eval.py` benchmarking should be run against a working backend with careful, targeted iterations first, for example `uv run run_eval.py --index N`, before the full run. Final eval score is not recorded in this document yet.
