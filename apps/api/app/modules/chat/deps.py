from app.core.config import settings
from app.modules.chat.llm import LLMProvider, OpenAICompatibleLLMProvider


def get_llm_provider() -> LLMProvider:
    return OpenAICompatibleLLMProvider(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        reasoning_effort=settings.LLM_REASONING_EFFORT,
    )
