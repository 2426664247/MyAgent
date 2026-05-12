import os
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv


@dataclass
class Settings:
    model: str
    api_key: str
    base_url: str | None
    thinking_enabled: bool = True
    max_steps: int = 999

    @classmethod
    def from_env(cls, *, model: str | None = None, max_steps: int = 999) -> "Settings":
        load_dotenv()

        key_candidates = [
            ("LLM_API_KEY", os.getenv("LLM_API_KEY")),
            ("DEEPSEEK_API_KEY", os.getenv("DEEPSEEK_API_KEY")),
            ("OPENROUTER_API_KEY", os.getenv("OPENROUTER_API_KEY")),
            ("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY")),
        ]
        key_source, api_key = next(((name, value) for name, value in key_candidates if value), ("", None))
        if not api_key:
            raise ValueError(
                "未找到 API Key。请在 .env 中配置 LLM_API_KEY，"
                "或使用 DEEPSEEK_API_KEY / OPENROUTER_API_KEY / OPENAI_API_KEY。"
            )

        using_deepseek_key = key_source == "DEEPSEEK_API_KEY"
        resolved_model = model or os.getenv("LLM_MODEL") or (
            "deepseek-v4-flash" if using_deepseek_key else "openai/gpt-4o-mini"
        )
        raw_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENROUTER_BASE_URL")
        if raw_url is None and using_deepseek_key:
            raw_url = "https://api.deepseek.com"
        base_url = _normalize_base_url(raw_url)
        thinking_value = (os.getenv("LLM_THINKING") or "enabled").strip().lower()
        thinking_enabled = thinking_value not in ("0", "false", "off", "disabled", "no")

        return cls(
            model=resolved_model,
            api_key=api_key,
            base_url=base_url,
            thinking_enabled=thinking_enabled,
            max_steps=max_steps,
        )


def _normalize_base_url(url: str | None) -> str | None:
    if not url:
        return None

    cleaned = url.strip().rstrip("/")
    parsed = urlparse(cleaned)
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/")

    if host == "openrouter.ai" and path in ("", "/api"):
        return urlunparse(parsed._replace(path="/api/v1"))

    if host == "api.openai.com" and path in ("", "/"):
        return urlunparse(parsed._replace(path="/v1"))

    return cleaned
