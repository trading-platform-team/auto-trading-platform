from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수에서 설정값을 읽어온다. (.env 또는 docker-compose environment)"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "auto-trading-backend"

    kafka_bootstrap_servers: str = "localhost:9092"
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql://trader:change-me@localhost:5432/trading"
    vault_addr: str = "http://localhost:8200"
    ai_service_url: str = "http://localhost:8001"

    kiwoom_app_key: str = ""
    kiwoom_secret_key: str = ""
    kiwoom_base_url: str = "https://mockapi.kiwoom.com"


settings = Settings()
