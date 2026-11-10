from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_key: str
    supabase_jwt_secret: str          # Settings → API → JWT Secret in Supabase dashboard
    model_path: str = "./ml/artifacts/sepnova_model.pkl"
    allowed_origins: str = "http://localhost:3000"

    # LLM
    llm_provider: str = "anthropic"   # "anthropic" or "openai"
    llm_api_key: str = ""             # Anthropic or OpenAI API key

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
