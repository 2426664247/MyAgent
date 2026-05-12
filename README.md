# AgentV2

AgentV2 is a local coding agent with a CLI and a Codex-style web workspace. It talks to OpenAI-compatible chat completion APIs, uses function calling for tools, and keeps file and command operations inside an explicit project sandbox.

## Highlights

- CLI REPL and FastAPI web app.
- React + TypeScript frontend served by the same FastAPI process.
- Multiple web sessions, each with its own explicit working directory.
- Local JSON session history in `~/.agent_v2/sessions/`.
- DeepSeek-friendly defaults with quick model switching between flash and pro variants.
- Token streaming over SSE.
- Separate reasoning display when the provider returns reasoning content.
- Built-in tools for listing files, reading files, writing files, and confirmed shell commands.
- No default workspace for new sessions. Users must choose an existing absolute directory.

## Clean Layout

```text
.
├── agent_v2/                 # Python package
│   ├── builtins/             # Built-in tool implementations
│   ├── static/               # Built web assets served by FastAPI
│   ├── web_ui/               # React/Vite frontend source
│   ├── cli.py                # CLI entry point
│   ├── env_config.py         # .env read/write helpers
│   ├── llm.py                # OpenAI-compatible LLM client
│   ├── registry.py           # Tool registration and JSON schema generation
│   ├── runner.py             # Synchronous CLI runner
│   ├── sessions.py           # JSON session store
│   ├── web.py                # FastAPI app and API routes
│   └── web_runner.py         # Async streaming web runner
├── tests/                    # Python unit tests
├── .env.example              # Safe placeholder configuration
├── pyproject.toml            # Python package metadata
├── README.md
└── AGENTS.md
```

The repository root is intentionally small. Runtime Python code, frontend source, and built web assets all live under `agent_v2/`.

## Installation

Use Python 3.12 or newer.

```bash
pip install -e .
```

If you want to rebuild the web UI, Node.js and npm are also required:

```bash
cd agent_v2/web_ui
npm install
npm run build
```

The Vite build writes to `agent_v2/static/`, which is included as package data.

## Model Configuration

Copy the example file:

```bash
cp .env.example .env
```

DeepSeek example:

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
LLM_THINKING=enabled
```

API key priority:

1. `LLM_API_KEY`
2. `DEEPSEEK_API_KEY`
3. `OPENROUTER_API_KEY`
4. `OPENAI_API_KEY`

Other environment variables:

- `LLM_BASE_URL`: OpenAI-compatible base URL.
- `LLM_MODEL`: model name.
- `LLM_THINKING`: `enabled` or `disabled`.

When `DEEPSEEK_API_KEY` is set and no base URL/model is provided, AgentV2 defaults to `https://api.deepseek.com` and `deepseek-v4-flash`.

The web model settings dialog writes `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_THINKING` to the repository-root `.env`.

## Run The Web App

```bash
python -m agent_v2.web --host 127.0.0.1 --port 8000
```

or:

```bash
agent-v2-web --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Create a session from the sidebar and enter an existing absolute project directory. Empty paths, relative paths, missing directories, and file paths are rejected.

## Run The CLI

```bash
python -m agent_v2 /absolute/path/to/project
```

Optional model and step limit:

```bash
python -m agent_v2 /absolute/path/to/project --model deepseek-v4-pro --max-steps 20
```

Exit with `/exit`, `/quit`, `exit`, or `quit`.

## Built-In Tools

| Tool | Purpose | Confirmation |
| --- | --- | --- |
| `list_files` | Render the selected project tree | No |
| `read_file` | Read a text file inside the sandbox | No |
| `write_file` | Write a text file inside the sandbox | No |
| `run_command` | Run a shell command from the sandbox root | Yes |

All file paths are resolved by `PathSandbox`. Commands run with `cwd` set to the session project directory.

## Web API

- `GET /api/sessions`
- `POST /api/sessions`
- `GET /api/sessions/{id}`
- `DELETE /api/sessions/{id}`
- `POST /api/sessions/{id}/messages/stream`
- `POST /api/sessions/{id}/stop`
- `POST /api/tool-confirmations/{confirmation_id}`
- `GET /api/settings`
- `POST /api/settings`

Important SSE events:

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

`assistant_message_complete` persists one completed assistant reply. `final` only marks the run complete.

## Tests

Backend:

```bash
python -m unittest discover -s tests -v
```

Frontend build:

```bash
cd agent_v2/web_ui
npm run build
```

Recommended release check:

```bash
pip install -e .
python -m unittest discover -s tests -v
cd agent_v2/web_ui
npm run build
```

## Privacy And Safety

Do not commit:

- `.env`
- real API keys or tokens
- local session JSON from `~/.agent_v2/sessions/`
- `node_modules/`
- Python caches and test caches
- TypeScript build info
- local absolute paths or personal machine/user names

The repository includes `.env.example` only, with placeholders.
