from __future__ import annotations

import os
from pathlib import Path


ENV_KEYS = (
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_THINKING",
    "ARK_IMAGE_API_KEY",
    "ARK_IMAGE_BASE_URL",
    "ARK_IMAGE_MODEL",
    "ARK_IMAGE_SIZE",
    "ARK_IMAGE_WATERMARK",
)


def default_env_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".env"


def read_env_config(path: Path | None = None) -> dict[str, str]:
    env_path = path or default_env_path()
    data = _parse_env_file(env_path)
    return {key: os.getenv(key) or data.get(key, "") for key in ENV_KEYS}


def write_env_config(values: dict[str, str], path: Path | None = None) -> dict[str, str]:
    env_path = path or default_env_path()
    existing = _parse_env_file(env_path)
    for key in ENV_KEYS:
        if key in values:
            existing[key] = values[key].strip()

    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={_escape_env_value(existing.get(key, ''))}" for key in ENV_KEYS]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    for key in ENV_KEYS:
        value = existing.get(key, "")
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)
    return {key: existing.get(key, "") for key in ENV_KEYS}


def masked_config(path: Path | None = None) -> dict[str, str]:
    data = read_env_config(path)
    api_key = data.get("LLM_API_KEY", "")
    if api_key:
        data["LLM_API_KEY_MASKED"] = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
    else:
        data["LLM_API_KEY_MASKED"] = ""
    data["LLM_API_KEY"] = ""
    ark_key = data.get("ARK_IMAGE_API_KEY", "")
    if ark_key:
        data["ARK_IMAGE_API_KEY_MASKED"] = f"{ark_key[:4]}...{ark_key[-4:]}" if len(ark_key) > 8 else "***"
    else:
        data["ARK_IMAGE_API_KEY_MASKED"] = ""
    data["ARK_IMAGE_API_KEY"] = ""
    return data


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        result[key] = value
    return result


def _escape_env_value(value: str) -> str:
    if any(ch.isspace() for ch in value):
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'
    return value
