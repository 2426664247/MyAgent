from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

import click
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .env_config import masked_config, write_env_config
from .sessions import SessionRecord, SessionStore, validate_project_dir
from .settings import Settings
from .web_runner import ConfirmationBroker, WebAgentRunner


STATIC_DIR = Path(__file__).resolve().parent / "static"
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


class CreateSessionRequest(BaseModel):
    name: str = ""
    project_dir: str = ""


class SendMessageRequest(BaseModel):
    content: str
    max_steps: int = 999
    model: str | None = None
    image_feedback: bool = False


class ConfirmationRequest(BaseModel):
    approved: bool


class SettingsRequest(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    thinking_enabled: bool = True
    ark_image_api_key: str = ""
    ark_image_base_url: str = ""
    ark_image_model: str = ""
    ark_image_size: str = ""
    ark_image_watermark: bool = True


class RuntimeState:
    def __init__(self):
        self.store = SessionStore()
        self.confirmations = ConfirmationBroker()
        self.stop_events: dict[str, asyncio.Event] = {}
        self.running_tasks: dict[str, asyncio.Task[Any]] = {}

    def stop(self, session_id: str) -> bool:
        event = self.stop_events.get(session_id)
        task = self.running_tasks.get(session_id)
        stopped = False
        if event is not None:
            event.set()
            stopped = True
        if task is not None and not task.done():
            task.cancel()
            stopped = True
        self.confirmations.cancel_all()
        return stopped


state = RuntimeState()
app = FastAPI(title="AgentV2 Web")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/project-root")
def get_project_root() -> dict[str, str]:
    return {
        "project_root": str(REPOSITORY_ROOT),
    }


@app.get("/api/sessions")
def list_sessions() -> dict[str, Any]:
    return {"sessions": [record.summary() for record in state.store.list()]}


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    data = masked_config()
    return {
        "settings": {
            "api_key_masked": data.get("LLM_API_KEY_MASKED", ""),
            "base_url": data.get("LLM_BASE_URL", ""),
            "model": data.get("LLM_MODEL", ""),
            "thinking_enabled": (data.get("LLM_THINKING") or "enabled") != "disabled",
            "ark_image_api_key_masked": data.get("ARK_IMAGE_API_KEY_MASKED", ""),
            "ark_image_base_url": data.get("ARK_IMAGE_BASE_URL", ""),
            "ark_image_model": data.get("ARK_IMAGE_MODEL", ""),
            "ark_image_size": data.get("ARK_IMAGE_SIZE", ""),
            "ark_image_watermark": (data.get("ARK_IMAGE_WATERMARK") or "true").lower() not in ("0", "false", "off", "disabled", "no"),
        }
    }


@app.post("/api/settings")
def update_settings(payload: SettingsRequest) -> dict[str, Any]:
    current = masked_config()
    values = {
        "LLM_BASE_URL": payload.base_url,
        "LLM_MODEL": payload.model,
        "LLM_THINKING": "enabled" if payload.thinking_enabled else "disabled",
        "ARK_IMAGE_BASE_URL": payload.ark_image_base_url,
        "ARK_IMAGE_MODEL": payload.ark_image_model,
        "ARK_IMAGE_SIZE": payload.ark_image_size,
        "ARK_IMAGE_WATERMARK": "true" if payload.ark_image_watermark else "false",
    }
    if payload.api_key.strip():
        values["LLM_API_KEY"] = payload.api_key
    elif not current.get("LLM_API_KEY_MASKED"):
        values["LLM_API_KEY"] = ""
    if payload.ark_image_api_key.strip():
        values["ARK_IMAGE_API_KEY"] = payload.ark_image_api_key
    elif not current.get("ARK_IMAGE_API_KEY_MASKED"):
        values["ARK_IMAGE_API_KEY"] = ""
    write_env_config(values)
    data = masked_config()
    return {
        "settings": {
            "api_key_masked": data.get("LLM_API_KEY_MASKED", ""),
            "base_url": data.get("LLM_BASE_URL", ""),
            "model": data.get("LLM_MODEL", ""),
            "thinking_enabled": (data.get("LLM_THINKING") or "enabled") != "disabled",
            "ark_image_api_key_masked": data.get("ARK_IMAGE_API_KEY_MASKED", ""),
            "ark_image_base_url": data.get("ARK_IMAGE_BASE_URL", ""),
            "ark_image_model": data.get("ARK_IMAGE_MODEL", ""),
            "ark_image_size": data.get("ARK_IMAGE_SIZE", ""),
            "ark_image_watermark": (data.get("ARK_IMAGE_WATERMARK") or "true").lower() not in ("0", "false", "off", "disabled", "no"),
        }
    }


@app.post("/api/sessions")
def create_session(payload: CreateSessionRequest) -> dict[str, Any]:
    try:
        requested_project_dir = payload.project_dir.strip()
        if not requested_project_dir:
            raise ValueError("必须先指定一个本机工作目录。")
        raw_project_dir = Path(requested_project_dir).expanduser()
        if not raw_project_dir.is_absolute():
            raise ValueError("工作目录必须使用绝对路径，避免误写到未知位置。")
        project_dir = validate_project_dir(requested_project_dir)
        record = state.store.create(name=payload.name, project_dir=str(project_dir))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"session": record.to_dict()}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    try:
        record = state.store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    return {"session": record.to_dict()}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, Any]:
    state.stop(session_id)
    try:
        state.store.delete(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    return {"ok": True}


@app.post("/api/sessions/{session_id}/stop")
def stop_session(session_id: str) -> dict[str, Any]:
    stopped = state.stop(session_id)
    try:
        record = state.store.set_status(session_id, "stopped")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    return {"ok": stopped, "session": record.summary()}


@app.post("/api/tool-confirmations/{confirmation_id}")
def confirm_tool(confirmation_id: str, payload: ConfirmationRequest) -> dict[str, Any]:
    ok = state.confirmations.resolve(confirmation_id, payload.approved)
    if not ok:
        raise HTTPException(status_code=404, detail="Confirmation not found")
    return {"ok": True}


@app.post("/api/sessions/{session_id}/messages/stream")
async def stream_message(session_id: str, payload: SendMessageRequest) -> StreamingResponse:
    try:
        record = state.store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc

    if session_id in state.running_tasks and not state.running_tasks[session_id].done():
        raise HTTPException(status_code=409, detail="Session is already running")

    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message content is required")

    try:
        project_dir = validate_project_dir(record.project_dir)
        settings = Settings.from_env(model=payload.model, max_steps=payload.max_steps)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user_message = _new_message("user", content=content)
    record.messages.append(user_message)
    record.status = "running"
    state.store.save(record)

    stop_event = asyncio.Event()
    state.stop_events[session_id] = stop_event
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def run_agent() -> None:
        try:
            runner = WebAgentRunner(
                settings=settings,
                project_dir=project_dir,
                confirmation_broker=state.confirmations,
                stop_event=stop_event,
                image_feedback_enabled=payload.image_feedback,
            )
            async for event in runner.run(content, history=record.messages[:-1]):
                await _persist_event(session_id, event)
                await queue.put(event)
                if event["type"] in {"final", "stopped", "error"}:
                    break
        except asyncio.CancelledError:
            await _persist_event(session_id, {"type": "stopped", "message": "任务已停止。"})
            await queue.put({"type": "stopped", "message": "任务已停止。"})
        except Exception as exc:
            event = {"type": "error", "message": str(exc)}
            await _persist_event(session_id, event)
            await queue.put(event)
        finally:
            await queue.put(None)
            state.running_tasks.pop(session_id, None)
            state.stop_events.pop(session_id, None)

    task = asyncio.create_task(run_agent())
    state.running_tasks[session_id] = task

    async def event_stream() -> AsyncIterator[str]:
        yield _format_sse({"type": "user_message", "message": user_message})
        while True:
            event = await queue.get()
            if event is None:
                break
            yield _format_sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _persist_event(session_id: str, event: dict[str, Any]) -> None:
    record = state.store.get(session_id)
    kind = event["type"]
    if kind in ("assistant_delta", "reasoning_delta"):
        return
    if kind == "step":
        record.messages.append(_new_message("step", content=event["message"], step=event.get("step")))
    elif kind == "tool_call":
        record.messages.append(_new_message("tool_call", **{
            "tool_call_id": event["tool_call_id"],
            "name": event["name"],
            "arguments": event["arguments"],
            "step": event.get("step"),
        }))
    elif kind == "confirmation_required":
        record.status = "waiting_confirmation"
        record.messages.append(_new_message("confirmation", **{
            "confirmation_id": event["confirmation_id"],
            "name": event["name"],
            "arguments": event["arguments"],
            "project_dir": event["project_dir"],
            "step": event.get("step"),
        }))
    elif kind == "tool_result":
        record.status = "running"
        record.messages.append(_new_message("tool_result", **{
            "tool_call_id": event["tool_call_id"],
            "name": event["name"],
            "arguments": event["arguments"],
            "result": event["result"],
            "success": event["success"],
            "step": event.get("step"),
        }))
    elif kind == "assistant_message_complete":
        record.status = "idle"
        record.messages.append(_new_message(
            "assistant_final",
            content=event["content"],
            reasoning_content=event.get("reasoning_content", ""),
            step=event.get("step"),
        ))
    elif kind == "image_feedback":
        record.status = "idle"
        record.messages.append(_new_message(
            "image_feedback",
            prompt=event.get("prompt", ""),
            urls=event.get("urls", []),
            error=event.get("error", ""),
            step=event.get("step"),
        ))
    elif kind == "final":
        record.status = "idle"
    elif kind == "stopped":
        record.status = "stopped"
        record.messages.append(_new_message("stopped", content=event["message"]))
    elif kind == "error":
        record.status = "error"
        record.messages.append(_new_message("error", content=event["message"]))
    else:
        return
    state.store.save(record)


def _new_message(kind: str, **data: Any) -> dict[str, Any]:
    return {"id": _message_id(), "type": kind, "created_at": _utc_now(), **data}


def _message_id() -> str:
    import uuid

    return uuid.uuid4().hex


def _utc_now() -> str:
    from .sessions import utc_now

    return utc_now()


def _format_sse(event: dict[str, Any]) -> str:
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str) -> FileResponse:
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    target = STATIC_DIR / full_path
    if target.exists() and target.is_file():
        return FileResponse(target)
    return FileResponse(STATIC_DIR / "index.html")


@click.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
def main(host: str, port: int) -> None:
    """启动 AgentV2 Web 前端。"""
    uvicorn.run("agent_v2.web:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
