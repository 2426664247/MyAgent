from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


DEFAULT_ARK_IMAGE_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
DEFAULT_ARK_IMAGE_MODEL = "doubao-seedream-5-0-260128"
DEFAULT_ARK_IMAGE_SIZE = "2K"


@dataclass
class ArkImageSettings:
    api_key: str
    base_url: str = DEFAULT_ARK_IMAGE_BASE_URL
    model: str = DEFAULT_ARK_IMAGE_MODEL
    size: str = DEFAULT_ARK_IMAGE_SIZE
    watermark: bool = True

    @classmethod
    def from_env(cls) -> "ArkImageSettings":
        load_dotenv()
        api_key = os.getenv("ARK_IMAGE_API_KEY", "").strip()
        if not api_key:
            raise ValueError("未找到火山方舟生图 Key。请在设置中配置 ARK_IMAGE_API_KEY。")
        watermark_value = os.getenv("ARK_IMAGE_WATERMARK", "true").strip().lower()
        return cls(
            api_key=api_key,
            base_url=os.getenv("ARK_IMAGE_BASE_URL", DEFAULT_ARK_IMAGE_BASE_URL).strip() or DEFAULT_ARK_IMAGE_BASE_URL,
            model=os.getenv("ARK_IMAGE_MODEL", DEFAULT_ARK_IMAGE_MODEL).strip() or DEFAULT_ARK_IMAGE_MODEL,
            size=os.getenv("ARK_IMAGE_SIZE", DEFAULT_ARK_IMAGE_SIZE).strip() or DEFAULT_ARK_IMAGE_SIZE,
            watermark=watermark_value not in ("0", "false", "off", "disabled", "no"),
        )


def generate_image_feedback(prompt: str, settings: ArkImageSettings | None = None) -> list[str]:
    cfg = settings or ArkImageSettings.from_env()
    body = {
        "model": cfg.model,
        "prompt": _compact_prompt(prompt),
        "sequential_image_generation": "disabled",
        "response_format": "url",
        "size": cfg.size,
        "stream": False,
        "watermark": cfg.watermark,
    }
    request = Request(
        cfg.base_url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.api_key}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"火山方舟生图失败：HTTP {exc.code} {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"火山方舟生图失败：{exc.reason}") from exc

    urls = _extract_urls(payload)
    if not urls:
        raise RuntimeError("火山方舟生图没有返回图片 URL。")
    return urls


def build_feedback_prompt(user_input: str, assistant_content: str) -> str:
    return (
        "请根据用户的图像需求生成一张图片。优先严格遵循用户需求；"
        "助手回答只作为补充语境，不要把助手的道歉、能力说明、代码建议、工具说明画进图片。"
        "避免文字排版和界面截图。\n\n"
        f"用户需求：{user_input.strip()}\n\n"
        f"助手补充语境：{assistant_content.strip()}"
    )


def _extract_urls(payload: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    data = payload.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                urls.append(item["url"])
    if isinstance(payload.get("url"), str):
        urls.append(payload["url"])
    return urls


def _compact_prompt(prompt: str, limit: int = 4000) -> str:
    compact = " ".join(prompt.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip()
