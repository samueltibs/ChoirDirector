from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_anon_key: str = ""
    kits_ai_api_key: str = "RTLlerJ.iX3JZHJNU6e47IGbnIAc3pWd"
    jwt_secret: str = ""
    environment: str = "development"
    cors_origins: List[str] = ["http://localhost:3000"]
    api_base_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
