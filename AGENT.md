# Agent Documentation

## Overview

This agent is a CLI documentation assistant for the repository. It accepts one question as a command-line argument, sends that question to an OpenAI-compatible chat completions API, and returns a single JSON object to stdout. In Task 2 the agent stops being just a chatbot and becomes an actual agent: it can inspect the repository with tools, feed tool results back into the model, and then produce a grounded answer with a source reference.

The agent is designed to answer documentation questions from the project wiki first. Instead of relying on the model's memory, it asks the model to discover files with `list_files`, inspect relevant documents with `read_file`, and only then produce a final answer. The final output includes the answer text, the source path with a section anchor, and the full list of tool calls made during reasoning.

## Architecture

```text
User -> agent.py -> LLM with tool schemas
                 -> tool call(s): list_files / read_file
                 -> tool result(s) appended to message history
                 -> final JSON answer with source
```

The main loop works like this:

1. Load `.env.agent.secret` if present.
2. Read the user question from the CLI.
3. Send the system prompt, user question, and tool schemas to the LLM.
4. If the LLM returns tool calls, execute them locally and append the tool results as `tool` messages.
5. Repeat until the model returns a final answer or the maximum tool-call limit is reached.
6. Print a single JSON line to stdout.

## Tools

### `list_files`

- Input: repository-relative directory path
- Output: newline-separated files and directories
- Purpose: help the model discover where relevant documentation lives

### `read_file`

- Input: repository-relative file path
- Output: file contents as text
- Purpose: let the model inspect the actual documentation before answering

Both tools enforce path security. Paths must be relative to the repository root, absolute paths are rejected, and traversal outside the repository is blocked after path resolution. If a path is invalid, the tool returns an error string instead of crashing the process.

## System Prompt Strategy

The system prompt tells the model to:

- use repository tools instead of guessing
- start with `wiki/` for documentation questions
- use `list_files("wiki")` for discovery
- use `read_file(...)` for the most relevant file
- return final output as JSON with `answer` and `source`

This keeps the model focused and reduces token waste, which matters when using limited OpenRouter credits.

## Configuration

The agent reads configuration from `.env.agent.secret`:

| Variable       | Purpose |
| -------------- | ------- |
| `LLM_API_KEY`  | API key for the LLM provider |
| `LLM_API_BASE` | Base URL of the OpenAI-compatible API |
| `LLM_MODEL`    | Model name |

Already-exported shell variables take precedence. The file is only a local convenience and must not be committed.

## Output Format

The agent prints a single JSON object to stdout:

```json
{
  "answer": "Edit the conflicting file, choose the changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

Debug and error messages go to stderr only.

## Testing

The regression tests do not call the real LLM provider. Instead, they start a tiny local HTTP server that mimics an OpenAI-compatible API and returns scripted tool-calling responses. That makes the tests deterministic, free, and safe to run repeatedly while developing.

Run the local tests with:

```bash
uv run pytest tests/test_agent_task1.py tests/test_agent_task2.py -v
```
