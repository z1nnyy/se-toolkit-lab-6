# Task 1 Plan: Call an LLM from Code

## LLM Provider

- **Provider:** OpenRouter
- **Model:** configured through `LLM_MODEL` in `.env.agent.secret`
- **API:** OpenAI-compatible `/v1/chat/completions` endpoint

## Architecture

1. Read environment variables from `.env.agent.secret`:
   - `LLM_API_KEY` — API key for authentication
   - `LLM_API_BASE` — base URL (for OpenRouter: `https://openrouter.ai/api/v1`)
   - `LLM_MODEL` — model name

2. Parse CLI argument (question) using `sys.argv[1]`

3. Send POST request to `{LLM_API_BASE}/chat/completions` with:
   - `model`: LLM_MODEL
   - `messages`: system prompt + user question
   - `temperature`: 0

4. Parse response, extract `choices[0].message.content`

5. Output JSON to stdout:
   ```json
   {"answer": "<llm response>", "tool_calls": []}
   ```

## Error Handling

- No API key → exit 1 with error to stderr
- HTTP error → exit 1 with error to stderr
- No CLI argument → print usage to stderr, exit 1
- Timeout > 60s → exit 1

## Dependencies

- `httpx` — HTTP client for the OpenAI-compatible API

## Testing

- One regression test: run `agent.py` as a subprocess against a local mock HTTP server, then parse JSON and check `answer` and `tool_calls`
