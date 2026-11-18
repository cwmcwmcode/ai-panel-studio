"""运行环境配置。

统一加载 backend/.env，并把路径、模型参数与并发调度参数集中到一处，
避免各模块散落读取 os.environ。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH") or (DATA_DIR / "panel_studio.db"))
SCHEMA_PATH = BASE_DIR / "schema.sql"

LLM_API_KEY = (os.getenv("LLM_API_KEY") or "").strip()
LLM_BASE_URL = (os.getenv("LLM_BASE_URL") or "https://api.deepseek.com").strip()
LLM_MODEL = (os.getenv("LLM_MODEL") or "deepseek-chat").strip()

#: 常见占位符写法，出现任意一种都视为「未配置有效 Key」
_PLACEHOLDER_KEYS = {
    "your-api-key",
    "your_api_key",
    "your-deepseek-key",
    "your_deepseek_key",
    "yourdeepseekkey",
    "deepseek-api-key",
    "changeme",
    "none",
    "null",
}


def _is_placeholder_key(key: str) -> bool:
    lowered = key.strip().lower()
    return (
        not lowered
        or lowered in _PLACEHOLDER_KEYS
        or "your" in lowered
        or "placeholder" in lowered
        or "你的" in lowered
        or lowered.startswith(("sk-your", "sk-xxx", "sk-test"))
    )


#: 未配置真实 Key（或仍是占位符）时启用 Mock 流式演示
DEMO_MODE = _is_placeholder_key(LLM_API_KEY)

MAX_SPEECHES = int(os.getenv("DISCUSSION_MAX_SPEECHES", "8"))
INSIGHT_INTERVAL = int(os.getenv("INSIGHT_INTERVAL", "3"))
MOCK_TOKEN_DELAY = float(os.getenv("MOCK_TOKEN_DELAY", "0.025"))

CORS_ORIGINS = [
    origin.strip()
    for origin in (
        os.getenv("CORS_ORIGINS") or "http://127.0.0.1:5173,http://localhost:5173"
    ).split(",")
    if origin.strip()
]
