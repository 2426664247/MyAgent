# AGENTS.md

This guide is for future agents maintaining AgentV2.

## Purpose

AgentV2 is a local coding-agent project. It provides:

- a Click CLI runner
- a FastAPI web backend
- a React/Vite frontend served by FastAPI
- OpenAI-compatible function calling
- sandboxed local tools for files and shell commands

## Repository Layout

```text
.
├── agent_v2/          # Python package and web assets
│   ├── builtins/      # list/read/write/run tools
│   ├── static/        # built frontend output
│   └── web_ui/        # React frontend source
├── tests/             # Python tests
├── pyproject.toml
├── README.md
└── AGENTS.md
```

Keep this layout clean. Do not move Python modules back to the repository root.

## Do Not Commit

- `.env`
- API keys, tokens, or private credentials
- `~/.agent_v2/sessions/`
- `node_modules/`
- `__pycache__/`, `.pytest_cache/`, `*.pyc`
- `*.egg-info/`
- `*.tsbuildinfo`
- local absolute paths, usernames, or machine-specific notes

## Common Commands

Install:

```bash
pip install -e .
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

Run web app:

```bash
python -m agent_v2.web --host 127.0.0.1 --port 8000
```

Run CLI:

```bash
python -m agent_v2 /absolute/path/to/project
```

Rebuild frontend:

```bash
cd agent_v2/web_ui
npm install
npm run build
```

## Backend Rules

- New web sessions must require an existing absolute project directory.
- Do not add a default workspace or infer one from the repository.
- Keep file and command operations inside `PathSandbox`.
- Keep `run_command` confirmation mandatory.
- Preserve stop behavior through `/api/sessions/{id}/stop`.
- Keep `.env` reads and writes at the repository root.
- Keep session JSON in `~/.agent_v2/sessions/`.

## Streaming Rules

The web transcript depends on event separation:

- `assistant_delta` streams visible assistant text.
- `reasoning_delta` streams reasoning content separately.
- `assistant_message_complete` persists one assistant bubble.
- `final` updates status only. Do not persist `final` as a merged assistant bubble.
- Tool events should be available to the backend/session log but should not be dumped into the main chat bubble stream.

## Frontend Rules

- Main transcript: user and assistant bubbles only.
- Reasoning: separate compact/collapsible block.
- Command confirmation: explicit dialog before shell execution.
- New session UI: ask for an existing absolute directory.
- After editing `agent_v2/web_ui/`, run `npm run build` so `agent_v2/static/` is updated.

## Architecture Map

- `agent_v2/settings.py`: environment-based runtime settings.
- `agent_v2/env_config.py`: repository-root `.env` read/write/masking.
- `agent_v2/llm.py`: OpenAI-compatible client, streaming, tool-call fallback, reasoning extraction.
- `agent_v2/registry.py`: `@tool()` registration and JSON schema generation.
- `agent_v2/runner.py`: synchronous CLI ReAct loop.
- `agent_v2/web_runner.py`: async web runner, SSE events, confirmation broker.
- `agent_v2/web.py`: FastAPI routes and SPA/static hosting.
- `agent_v2/sessions.py`: JSON session persistence.
- `agent_v2/sandbox.py`: path containment checks.
- `agent_v2/builtins/`: built-in tools.

## Before Push

Run:

```bash
pip install -e .
python -m unittest discover -s tests -v
cd agent_v2/web_ui
npm run build
```

Then check:

```bash
git status --short --ignored
git diff --cached --name-only
```

Make sure ignored local files are not staged and that documentation matches the current layout.
