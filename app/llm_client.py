from openai import AzureOpenAI, OpenAI

from app.config import settings


def _normalize(value: str) -> str:
    return value.strip().strip("\"'")


def get_chat_client() -> tuple[OpenAI | AzureOpenAI, str]:
    provider = settings.provider.lower().strip()
    if provider == "azure":
        client = AzureOpenAI(
            api_key=settings.azure_openai_api_key or settings.openai_api_key or None,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
        )
        model = _normalize(settings.azure_openai_chat_deployment or settings.openai_model)
        if not model:
            raise ValueError(
                "Missing Azure chat deployment. Set AZURE_OPENAI_CHAT_DEPLOYMENT in .env."
            )
        if "embedding" in model.lower():
            raise ValueError(
                "AZURE_OPENAI_CHAT_DEPLOYMENT points to an embedding deployment. "
                "Set it to a chat deployment (e.g., gpt-4o-mini deployment name)."
            )
        return client, model

    client = OpenAI(api_key=settings.openai_api_key or None)
    return client, _normalize(settings.openai_model)


def get_embedding_client() -> tuple[OpenAI | AzureOpenAI, str]:
    provider = settings.provider.lower().strip()
    if provider == "azure":
        client = AzureOpenAI(
            api_key=settings.azure_openai_api_key or settings.openai_api_key or None,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
        )
        model = _normalize(settings.azure_openai_embedding_deployment or settings.embedding_model)
        if not model:
            raise ValueError(
                "Missing Azure embedding deployment. Set AZURE_OPENAI_EMBEDDING_DEPLOYMENT in .env."
            )
        return client, model

    client = OpenAI(api_key=settings.openai_api_key or None)
    return client, _normalize(settings.embedding_model)
