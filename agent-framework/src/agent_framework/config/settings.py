"""Central configuration — all API keys and runtime defaults via pydantic-settings."""
from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Anthropic ────────────────────────────────────────────────────────────
    anthropic_api_key: str = ""

    # ── OpenAI ───────────────────────────────────────────────────────────────
    openai_api_key: str = ""

    # ── Azure OpenAI ─────────────────────────────────────────────────────────
    azure_api_key: str = ""
    azure_api_base: str = ""       # https://<resource>.openai.azure.com/
    azure_api_version: str = "2024-02-01"

    # ── Google / Gemini ───────────────────────────────────────────────────────
    google_api_key: str = ""       # used for both Gemini and Google Custom Search
    google_cse_id: str = ""        # Custom Search Engine ID (for web_search)
    gemini_api_key: str = ""       # alias; falls back to google_api_key if empty

    # ── Mistral AI ────────────────────────────────────────────────────────────
    mistral_api_key: str = ""

    # ── Groq ─────────────────────────────────────────────────────────────────
    groq_api_key: str = ""

    # ── Cohere ───────────────────────────────────────────────────────────────
    cohere_api_key: str = ""

    # ── Together AI ───────────────────────────────────────────────────────────
    together_api_key: str = ""

    # ── Replicate ────────────────────────────────────────────────────────────
    replicate_api_key: str = ""

    # ── Hugging Face ─────────────────────────────────────────────────────────
    huggingface_api_key: str = ""

    # ── Ollama (local) ────────────────────────────────────────────────────────
    ollama_api_base: str = "http://localhost:11434"

    # ── Search backends ───────────────────────────────────────────────────────
    brave_api_key: str = ""        # Brave Search API
    serper_api_key: str = ""       # Serper.dev (Google Search proxy)

    # ── Notification channels ─────────────────────────────────────────────────
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""
    teams_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ── Memory / storage ──────────────────────────────────────────────────────
    memory_db_path: str = ""       # defaults to ~/.apathy/memory.db when empty

    # ── Runtime defaults ──────────────────────────────────────────────────────
    default_model: str = "anthropic/claude-sonnet-4-6"
    default_workspace: str = "."
    max_bash_timeout: int = 30
    default_num_workers: int = 4

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
