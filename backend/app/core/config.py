from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    app_domain: str = "http://localhost:8000"
    database_url: str | None = None
    db_user: str = "as_console"
    db_password: str | None = None
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "as_api_console"

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if self.database_url:
            return self
        if not self.db_password:
            raise ValueError("Set DATABASE_URL or DB_PASSWORD in .env")
        encoded_password = quote_plus(self.db_password)
        self.database_url = (
            f"mariadb+mariadbconnector://{self.db_user}:{encoded_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
