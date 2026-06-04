from functools import lru_cache
import os
from urllib.parse import quote_plus, urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_env_file() -> str:
    """Resolve env file path for both deploy and local dev."""
    env_file_override = os.environ.get("ENV_FILE")
    if env_file_override:
        return env_file_override

    deploy_env_file = "/home/app/config/.env"
    if os.path.exists(deploy_env_file):
        return deploy_env_file

    local_env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    return os.path.abspath(local_env_file)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_resolve_env_file(),
        extra="ignore",
    )

    app_env: str = "dev"
    app_domain: str = "http://localhost:8000"
    database_url: str | None = None
    db_user: str = "as_api_console"
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
    persnl_soap_url: str | None = None
    persnl_soap_wsdl_url: str | None = None
    persnl_soap_user: str | None = None
    persnl_soap_password: str | None = None
    persnl_soap_timeout_seconds: float = 3.0
    api_key_encryption_secret: str = "dev-only-change-me"
    api_key_kek_version: str = "v1"
    provider_base_url: str | None = None
    provider_master_key: str | None = None
    provider_team_id: str | None = None
    provider_timeout_seconds: float = 3.0
    provider_debug_logging: bool = False
    issuance_provider_mode: str = "external"
    mail_enabled: bool = False
    mail_server: str | None = None
    mail_port: int = 587
    mail_username: str | None = None
    mail_password: str | None = None
    mail_from: str | None = None
    mail_from_name: str = "AS API Console"
    mail_starttls: bool = True
    mail_ssl_tls: bool = False
    mail_validate_certs: bool = True
    session_secret_key: str = "dev-session-secret-change-me"
    oauth_provider: str = "fisa"
    oauth_auth_uri: str | None = None
    oauth_token_uri: str | None = None
    oauth_basic_uri: str | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    oauth_redirect_uri: str | None = None
    oauth_scope: str = "basic"
    login_allowed_title_codes: str = ""
    dev_login_account: str | None = None
    dev_login_name: str | None = None
    dev_login_email: str | None = None
    dev_login_department: str | None = None
    dev_login_sysid: int | None = None
    dev_login_role: str = "user"
    allow_header_auth: bool | None = None
    session_cookie_name: str = "as_api_console_session"
    session_max_age_seconds: int = 8 * 60 * 60
    csrf_header_name: str = "x-csrf-token"
    csrf_safe_methods: str = "GET,HEAD,OPTIONS"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    allowed_origins: str = ""
    require_https_outbound: bool = True
    allow_private_outbound_hosts: bool = False
    login_rate_limit: str = "10/minute"
    application_rate_limit: str = "10/hour"
    reveal_rate_limit: str = "5/hour"
    admin_mutation_rate_limit: str = "20/hour"

    @field_validator("provider_base_url")
    @classmethod
    def validate_provider_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("PROVIDER_BASE_URL must be a valid http(s) URL")
        return normalized


    @field_validator(
        "persnl_soap_url",
        "persnl_soap_wsdl_url",
        "oauth_auth_uri",
        "oauth_token_uri",
        "oauth_basic_uri",
        "oauth_redirect_uri",
    )
    @classmethod
    def validate_optional_urls(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("configured URL must be a valid http(s) URL")
        return normalized

    @property
    def header_auth_enabled(self) -> bool:
        if self.allow_header_auth is not None:
            return self.allow_header_auth
        return self.app_env.lower() in {"dev", "test"}

    @property
    def session_https_only(self) -> bool:
        return self.app_env.lower() not in {"dev", "test"}

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if not self.database_url:
            if not self.db_password:
                raise ValueError("Set DATABASE_URL or DB_PASSWORD in environment config")
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
