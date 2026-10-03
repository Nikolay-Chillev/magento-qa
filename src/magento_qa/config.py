"""Settings for the environment under test, read from QA_* variables or a .env file."""

from functools import lru_cache

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Where the store and Mailpit run, and how long to wait for them.

    Defaults match docker-compose.yml, so a local run needs no configuration.
    """

    model_config = SettingsConfigDict(env_prefix="QA_", env_file=".env", extra="ignore")

    base_url: HttpUrl = HttpUrl("http://localhost:8080/")
    mailpit_url: HttpUrl = HttpUrl("http://localhost:8025/")
    request_timeout: float = Field(default=30.0, gt=0, description="Seconds per HTTP request")
    wait_timeout: float = Field(
        default=60.0, gt=0, description="Seconds to wait for an asynchronous outcome"
    )
    # Public defaults of the magento2-in-a-box image; override them for any other store.
    admin_username: str = "exampleuser"
    admin_password: SecretStr = SecretStr("examplepassword123")


@lru_cache
def get_settings() -> Settings:
    """Return the settings, loaded once per test session."""
    return Settings()
