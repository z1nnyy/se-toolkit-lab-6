# Task 3 Plan: The System Agent

## Goal

Extend the Task 2 documentation agent with a third tool, `query_api`, so it can answer:

- live data questions from the running backend
- status code and auth behavior questions
- bug-diagnosis questions that require both API reproduction and source inspection

## Tool Schema

Add `query_api` to the existing tool list.

- `method` — HTTP method string
- `path` — API path such as `/items/`
- `body` — optional JSON string for request bodies

The tool returns a JSON string with:

- `status_code`
- `body`

## Authentication and Configuration

Environment variables:

- `LLM_API_KEY`
- `LLM_API_BASE`
- `LLM_MODEL`
- `LMS_API_KEY`
- `AGENT_API_BASE_URL` with default `http://localhost:42002`

Local convenience files:

- `.env.agent.secret`
- `.env.docker.secret`

`query_api` will send `Authorization: Bearer <LMS_API_KEY>` by default.
For unauthenticated checks, the tool will support `GET_NO_AUTH` as a special method value.

## System Prompt Update

The prompt will route questions like this:

- wiki questions → `list_files` / `read_file` in `wiki/`
- source-code questions → `list_files` / `read_file` in the repo
- runtime/data questions → `query_api`
- bug diagnosis → `query_api` first, then `read_file`

## Implementation Steps

1. Load both `.env.agent.secret` and `.env.docker.secret`.
2. Add `query_api` schema to the chat completion request.
3. Implement `query_api` with default auth and JSON result formatting.
4. Keep the existing agentic loop and tool recording.
5. Allow final `source` to be empty for API-only answers.

## Testing Strategy

Add two more regression tests with mocks:

1. Source-code question:
   - LLM calls `read_file("backend/app/main.py")`
   - final answer identifies `FastAPI`

2. Data/API question:
   - LLM calls `query_api({"method": "GET", "path": "/items/"})`
   - a local mock backend returns a JSON array
   - final answer reports the item count

All tests should remain local and deterministic.

## Benchmark Diagnosis

Initial benchmark run: not run yet in this planning step.

Planned iteration strategy:

1. Finish tool and test implementation locally.
2. Run targeted eval questions first with `uv run run_eval.py --index N`.
3. Fix prompt or tool behavior based on the first failing question.
4. Only after targeted fixes, run the full benchmark.
