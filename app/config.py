from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Mini AI Tutor"
    debug: bool = False

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3"
    provider: str = "azure"
    prompt_version: str = "v1"

    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-02-01"
    azure_openai_chat_deployment: str = ""
    azure_openai_embedding_deployment: str = ""

    index_dir: str = "storage/faiss_index"
    review_store_file: str = "storage/reviews.json"
    evaluation_store_file: str = "storage/evaluations.json"
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 50
    confidence_threshold: float = 0.7
    cohere_api_key: str = ""
    cohere_rerank_model: str = "rerank-v3.5"
    rerank_enabled: bool = True
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
