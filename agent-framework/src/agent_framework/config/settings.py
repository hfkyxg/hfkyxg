from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ollama_api_base: str = "http://localhost:11434"
    brave_api_key: str = ""
    default_model: str = "anthropic/claude-sonnet-4-6"
    default_workspace: str = "."
    max_bash_timeout: int = 30

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
