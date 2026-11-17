from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수에서 설정값을 읽어온다. (.env 또는 docker-compose environment)"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "auto-trading-backend"

    kafka_bootstrap_servers: str = "localhost:9092"
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql://trader:change-me@localhost:5432/trading"
    vault_addr: str = "http://localhost:8200"
    vault_token: str = "dev-root-token"
    jwt_secret: str = ""  # Vault에 연결할 수 없을 때만 사용
    ai_service_url: str = "http://localhost:8001"

    # 시세 파이프라인
    market_source: str = "mock"  # mock | kiwoom
    price_topic: str = "stock.price"
    tick_interval_sec: float = 1.0
    enable_consumer: bool = True
    enable_engine: bool = True  # 자동매매 엔진

    kiwoom_app_key: str = ""
    kiwoom_secret_key: str = ""
    kiwoom_base_url: str = "https://mockapi.kiwoom.com"

    # 타임머신 외부 사건 수집 (OpenDART 공시 + NAVER API HUB 뉴스)
    external_events_enabled: bool = False
    opendart_api_key: str = ""
    naver_news_client_id: str = ""
    naver_news_client_secret: str = ""


settings = Settings()
