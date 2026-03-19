# Agent Documentation

## Overview

This agent is a small CLI tool that sends one user question to an OpenAI-compatible LLM API and prints a single JSON object to stdout. For Task 1 it does not have tools or an agentic loop yet, so the output always includes an empty `tool_calls` array. This gives us the basic plumbing we need before adding wiki tools in Task 2 and backend API access in Task 3.

## Architecture

```
User → agent.py (CLI) → OpenAI-compatible LLM API → JSON response
```

## LLM Provider

- **Provider:** OpenRouter
- **Model:** read from `LLM_MODEL`
- **API:** OpenAI-compatible `/v1/chat/completions` endpoint

## Configuration

The agent reads configuration from `.env.agent.secret`:

| Variable       | Purpose                  |
| -------------- | ------------------------ |
| `LLM_API_KEY`  | API key for the LLM provider |
| `LLM_API_BASE` | Base URL of the API      |
| `LLM_MODEL`    | Model name to use        |

Environment variables already exported in the shell take precedence, and the `.env.agent.secret` file fills in missing values for local development. The CLI normalizes the base URL, sends a minimal system prompt plus the user question, and expects a standard chat completions response with `choices[0].message.content`.

## Usage

```bash
# Set up environment
cp .env.agent.example .env.agent.secret
# Edit .env.agent.secret with your credentials

# Run the agent
uv run agent.py "What does REST stand for?"
```

## Output Format

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "Representational State Transfer.",
  "tool_calls": []
}
```

- `answer` (string): The LLM's response
- `tool_calls` (array): Empty in Task 1, populated in Tasks 2-3

## Error Handling

- Missing config values → exit 1 with a short message to stderr
- Network or timeout errors → exit 1 with a short message to stderr
- HTTP errors from the provider → exit 1 with status code and provider response
- No question provided → print usage, exit 1

All errors are printed to stderr.

## Testing

The regression test runs `agent.py` as a subprocess, but it does not call the real provider. Instead, it starts a tiny local HTTP server that returns a fixed OpenAI-compatible response. That keeps the test deterministic, fast, and free, which matters when using OpenRouter credits. The test then parses stdout as JSON and verifies that the required `answer` and `tool_calls` fields are present.

Run the Task 1 test with:

```bash
uv run pytest tests/test_agent_task1.py -v
```
