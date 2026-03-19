# Task 2 Plan: The Documentation Agent

## Goal

Extend the Task 1 CLI into a documentation agent that can inspect the repository through two tools:

- `list_files(path)` for discovery
- `read_file(path)` for reading relevant documentation

The final response must include:

- `answer`
- `source`
- `tool_calls`

## Tool Schemas

The LLM request will include two function-calling tool schemas:

1. `list_files`
   - input: `path` (string)
   - output: newline-separated directory listing

2. `read_file`
   - input: `path` (string)
   - output: file contents as text

Both tools will be described as repository tools. The system prompt will tell the model to explore `wiki/` first for documentation questions.

## Agentic Loop

1. Load environment variables and parse the CLI question.
2. Send the system prompt, user question, and tool schemas to the LLM.
3. If the LLM returns `tool_calls`:
   - execute each tool
   - append the assistant tool call message and tool result messages
   - store every call in the output `tool_calls` array
   - repeat
4. If the LLM returns a normal assistant message without tool calls:
   - parse the answer text
   - parse the source reference from the message
   - return JSON and exit
5. Stop after at most 10 tool calls.

## Path Security

Tool paths must stay inside the repository root.

Implementation rules:

- resolve paths relative to the project root
- reject absolute paths
- reject any path that escapes the repository after resolution
- return an error string instead of crashing

## Response Strategy

The system prompt will instruct the LLM to:

- use `list_files` to discover relevant wiki files
- use `read_file` to inspect the most relevant documentation file
- cite the source as `path#anchor`
- avoid answering from memory when the wiki can be checked

## Testing

Tests will use a local mock HTTP server instead of the real LLM provider.

Planned regression tests:

1. Merge conflict question:
   - LLM first calls `read_file("wiki/git-workflow.md")`
   - final output must contain `read_file` in `tool_calls`
   - final `source` must point to `wiki/git-workflow.md`

2. Wiki listing question:
   - LLM first calls `list_files("wiki")`
   - final output must contain `list_files` in `tool_calls`

This keeps tests deterministic and avoids spending OpenRouter credits.
