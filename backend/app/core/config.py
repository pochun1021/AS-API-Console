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
    test_database_url: str | None = None
    test_db_user: str | None = None
    test_db_password: str | None = None
    test_db_host: str | None = None
    test_db_port: int | None = None
    test_db_name: str = "as_api_console_test"
    research_list_api_url: str | None = None
    research_list_timeout_seconds: float = 3.0
    research_list_allowed_title_codes: str = ""
    api_key_encryption_secret: str = "dev-only-change-me"
    api_key_kek_version: str = "v1"

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if not self.database_url:
            if not self.db_password:
                raise ValueError("Set DATABASE_URL or DB_PASSWORD in .env")
            encoded_password = quote_plus(self.db_password)
            self.database_url = (
                f"mariadb+mariadbconnector://{self.db_user}:{encoded_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        if not self.test_database_url:
            test_user = self.test_db_user or self.db_user
            test_password = self.test_db_password or self.db_password
            test_host = self.test_db_host or self.db_host
            test_port = self.test_db_port or self.db_port
            if test_password:
                encoded_test_password = quote_plus(test_password)
                self.test_database_url = (
                    f"mariadb+mariadbconnector://{test_user}:{encoded_test_password}"
                    f"@{test_host}:{test_port}/{self.test_db_name}"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
