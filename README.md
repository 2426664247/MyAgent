# AgentV2

AgentV2 is a local coding agent with two interfaces:

- a terminal REPL for direct command-line use
- a FastAPI + React web workspace inspired by Codex-style agent sessions

It uses OpenAI-compatible chat completions and native function calling where available. The project is configured to work well with DeepSeek by default, while still supporting OpenRouter, OpenAI, and other compatible providers.

## What It Does

AgentV2 lets you create a sandboxed coding-agent session for a specific local project directory. Inside that directory the agent can inspect files, read source code, write files, and request permission to run shell commands.

The web UI supports multiple independent sessions. Each session has its own working directory, transcript, tool history, run status, and command confirmation flow. Session data is saved locally as JSON so browser refreshes do not erase history.

## Features

- OpenAI-compatible LLM client with native `tools` / `tool_calls` support.
- Fallback parsing for models that return text-form tool calls.
- DeepSeek-friendly defaults: `DEEPSEEK_API_KEY` uses `https://api.deepseek.com` and `deepseek-v4-flash` unless overridden.
- Optional model settings UI that writes local `.env` values.
- Thinking mode toggle through `LLM_THINKING`.
- CLI interface with command confirmation.
- Web interface with SSE streaming, separate reasoning display, chat bubbles, stop button, and command confirmation dialog.
- Multiple web sessions with local JSON persistence.
- Explicit per-session working directory. The web API rejects empty or relative paths.
- `PathSandbox` enforcement for file tools and shell execution.
- Built-in tools: `list_files`, `read_file`, `write_file`, and `run_command`.

## Safety Model

AgentV2 is intentionally local-first, but it can edit files and run commands after confirmation, so treat it like a coding assistant with access to the selected project.

- The web UI does not create a default working directory. A session cannot start until the user provides an existing absolute path.
- File tools resolve paths through `PathSandbox` and reject paths outside the session directory.
- Shell commands run with `cwd` set to the session directory and require confirmation.
- Session JSON is stored under the current user's home directory at `~/.agent_v2/sessions/`.
- API keys are stored only in the local `.env` file when saved through the settings UI.
- Never commit `.env`, local session JSON, `node_modules`, caches, or machine-specific paths.

## Repository Layout

```text
agent_v2/
  __init__.py              Package export
  __main__.py              `python -m agent_v2` entry point
  cli.py                   Click-based terminal interface
  env_config.py            Read, mask, and write local `.env` settings
  llm.py                   OpenAI-compatible client, streaming, tool-call fallback
  prompt.py                System prompt template
  protocol.py              Agent step and tool result data models
  registry.py              `@tool()` registration and JSON Schema generation
  runner.py                CLI ReAct loop
  sandbox.py               Path sandbox enforcement
  sessions.py              JSON-backed web session store
  settings.py              Environment-based runtime settings
  web.py                   FastAPI app, REST API, SSE endpoint, static hosting
  web_runner.py            Async streaming web runner and command confirmation
  builtins/
    fs.py                  `list_files`, `read_file`, `write_file`
    shell.py               `run_command`
  static/                  Built React assets served by FastAPI
  tests/                   Python unit tests
  web_ui/                  Vite + React + TypeScript frontend source
```

## Requirements

- Python 3.12+
- Node.js and npm only if you want to rebuild the frontend
- An OpenAI-compatible API key

Python dependencies are declared in `pyproject.toml`. Frontend dependencies are declared in `web_ui/package.json`.

## Configure The Model

Copy the example environment file and fill in your key:

```bash
cp .env.example .env
```

For DeepSeek:

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
LLM_THINKING=enabled
```

Recognized API key variables, in priority order:

1. `LLM_API_KEY`
2. `DEEPSEEK_API_KEY`
3. `OPENROUTER_API_KEY`
4. `OPENAI_API_KEY`

Other settings:

- `LLM_BASE_URL`: OpenAI-compatible base URL. DeepSeek default is `https://api.deepseek.com` when `DEEPSEEK_API_KEY` is used and no base URL is set.
- `LLM_MODEL`: model name. Defaults to `deepseek-v4-flash` for `DEEPSEEK_API_KEY`, otherwise `openai/gpt-4o-mini`.
- `LLM_THINKING`: `enabled` or `disabled`.

The web settings dialog can also save `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_THINKING` into `.env`.

## Install

From the repository root:

```bash
pip install -e .
```

If you want to rebuild the React app:

```bash
cd web_ui
npm install
npm run build
```

The Vite build writes files into `static/`, which FastAPI serves directly.

## Run The CLI

Pass the project directory explicitly:

```bash
python -m agent_v2 /absolute/path/to/project
```

Optional model override:

```bash
python -m agent_v2 /absolute/path/to/project --model deepseek-v4-pro --max-steps 20
```

Exit with `/exit`, `/quit`, `exit`, or `quit`.

## Run The Web App

```bash
python -m agent_v2.web --host 127.0.0.1 --port 8000
```

or, after installing the package:

```bash
agent-v2-web --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Create a new session from the sidebar and provide an existing absolute directory. The backend rejects empty, missing, file, or relative project paths.

## Web API

- `GET /api/sessions`: list session summaries.
- `POST /api/sessions`: create a session with `name` and `project_dir`.
- `GET /api/sessions/{id}`: read full session history.
- `DELETE /api/sessions/{id}`: delete a session.
- `POST /api/sessions/{id}/messages/stream`: send a message and receive SSE events.
- `POST /api/sessions/{id}/stop`: stop a running session.
- `POST /api/tool-confirmations/{confirmation_id}`: approve or reject a pending command.
- `GET /api/settings`: read masked model settings.
- `POST /api/settings`: save local model settings.

Important SSE event types:

- `user_message`
- `step`
- `assistant_delta`
- `reasoning_delta`
- `tool_call`
- `confirmation_required`
- `tool_result`
- `assistant_message_complete`
- `final`
- `stopped`
- `error`

`assistant_message_complete` is the event used to persist one completed assistant bubble. `final` only marks the run complete and should not merge all previous assistant deltas into a single bubble.

## Test

Run Python tests from the repository root after installing the package in editable mode:

```bash
pip install -e .
python -m unittest discover -s tests -v
```

Run the frontend build from the package directory:

```bash
cd web_ui
npm run build
```

## Publishing Checklist

Before pushing or packaging:

- Confirm `.env` is not staged.
- Confirm `web_ui/node_modules/`, `__pycache__/`, `.pytest_cache/`, and `*.tsbuildinfo` are not staged.
- Rebuild the frontend after UI changes.
- Run the Python unit tests after backend or runner changes.
- Avoid committing local absolute paths, personal names, real API keys, session JSON, or temporary experiment files.
