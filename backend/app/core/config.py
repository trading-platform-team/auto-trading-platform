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

    # 키움 REST API (팀 키, .env에만). 가상계좌 연습 시세·실시간 시세·개발용 모의 주문이 같이 쓴다
    kiwoom_app_key: str = ""
    kiwoom_secret_key: str = ""
    kiwoom_base_url: str = "https://mockapi.kiwoom.com"
    kiwoom_rest_per_sec: float = 4.0  # 키 하나당 REST 초당 호출 수 (공식 한도 확인 후 조정)
    kiwoom_max_realtime: int = 100  # 실시간 구독 종목 상한 (공식 한도 확인 후 조정)
    kiwoom_default_symbols: str = "005930,000660,035420,005380,035720"  # 항상 구독할 종목
    kiwoom_execution_ws: bool = True  # 실거래 켠 사용자의 체결 실시간 통보(WebSocket 00)
    kiwoom_dev_use_team_key: bool = False  # 사용자 키 등록 기능 전까지 팀 모의 키로 실거래 메뉴 주문 테스트

    # 타임머신 외부 사건 수집 (OpenDART 공시 + NAVER API HUB 뉴스)
    external_events_enabled: bool = False
    opendart_api_key: str = ""
    naver_news_client_id: str = ""
    naver_news_client_secret: str = ""


settings = Settings()
