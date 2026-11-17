# 키움 연동 (시세 + 실거래)

## 구조

```
[팀 키 (.env KIWOOM_APP_KEY)] ── KiwoomClient (app/kiwoom/client.py, 주문 메서드 없음)
      │  프로세스마다 하나만 만들어 같이 씀 (app/kiwoom/platform.py) → 토큰·호출 간격 공유
      │  backend:   StockService — 종목 목록(ka10099)·현재가(ka10095)·일봉(ka10081)
      │             가상계좌 연습(/stocks/*)과 실거래 화면(/market/quote)이 같이 사용
      │  collector: MARKET_SOURCE=kiwoom이면 실시간 WebSocket(0B 체결, 0D 호가) → 1초 단위로 묶어 Kafka
      ▼
Kafka → 전략 엔진 / AI 이상탐지 / 화면  (모의 시세와 같은 형식이라 뒤쪽 코드는 그대로)

[사용자 본인 키] ── KiwoomTradeApi(계좌·주문, KiwoomClient 위에서 동작)
      전략 account="kiwoom" 또는 /trading/kiwoom/orders
      → 위험 제한(활성화, 1회 한도, 일일 손실) → 키움 주문 → kiwoom_orders 기록 → 체결 동기화
```

### 실시간 구독 종목 (전 종목 검색 + 필요한 것만 실시간)

- 검색: `GET /stocks/search?q=삼성` (가상계좌 연습과 같은 전 종목 목록)
- 종목 열기: `GET /market/quote/{코드}` → 현재가 + 실시간 구독 대상에 추가
- 보는 동안: 화면에서 60초마다 `POST /market/watch/{코드}` (90초 동안 안 오면 구독 해제)
- 우선순위: 활성 전략 종목 > 기본 5종목 > 최근 본 종목, 최대 `KIWOOM_MAX_REALTIME`개

## 키 받은 뒤 실행 순서

1. 키움 포털에 내 컴퓨터 IP 등록 (안 하면 8010 오류). `.env`에 키 넣기 (`.env.example` 참고, 커밋 금지)
   ```
   KIWOOM_APP_KEY=...
   KIWOOM_SECRET_KEY=...
   KIWOOM_BASE_URL=https://mockapi.kiwoom.com
   KIWOOM_DEV_USE_TEAM_KEY=true   # 사용자 키 등록 기능 전까지 실거래 메뉴(모의)에서 팀 키로 주문
   MARKET_SOURCE=kiwoom           # 실시간 시세까지 볼 때 (아니면 mock 그대로)
   ```
2. `docker compose up -d --build`
3. 시세 확인: `docker compose logs collector --tail 50` (토큰 발급·실시간 접속 로그)
   - `curl "http://localhost:8000/stocks/search?q=삼성"`
   - `curl http://localhost:8000/market/quote/005930`
4. 주문 확인 (모의 서버): 로그인 후
   - `PUT /trading/kiwoom/settings` `{"env":"mock","max_order_amount":1000000,"daily_loss_limit":100000}`
   - `POST /trading/kiwoom/activate` `{"confirm":"모의투자를 시작합니다"}`
   - `GET /trading/kiwoom/account`, `POST /trading/kiwoom/orders`, `GET /trading/kiwoom/orders`

## 키 받으면 꼭 확인할 것

공개 자료로 맞춘 부분이라 실제 응답과 다를 수 있다. 다르면 `app/kiwoom/`과 `tests/kiwoom_fake.py`만 고치면 된다.

| 확인 항목 | 위치 |
|---|---|
| backend와 collector가 같은 키로 토큰을 따로 받아도 둘 다 쓸 수 있는지 | `platform.py` |
| 실시간 FID: 0B `10` 현재가·`15` 거래량, 0D `121`·`125` 총잔량 | `realtime.py` |
| 실시간 등록 가능 종목 수 상한 (오류 1702) | `KIWOOM_MAX_REALTIME` |
| REST 초당 호출 한도 | `KIWOOM_REST_PER_SEC` |
| kt00018 `prsm_dpst_aset_amt`, 보유 목록 필드 | `api/trading.py` `account()`, `risk.py` |
| kt00001 예수금 필드 `entr`, `ord_alow_amt`, `d2_entra` | `api/trading.py` `account()` |
| kt00009 요청 필드, 응답 `acnt_ord_cntr_prst_array`, `cntr_qty`·`cntr_uv` | `client.py`, `trading/broker.py` |
| kt10003 취소 요청 필드 (`orig_ord_no`, `cncl_qty`) | `client.py` `cancel()` |
| 실시간 00 주문체결 FID: 9203 주문번호, 909 체결번호, 911 체결량, 910 체결가, 902 미체결수량 | `trading/executions.py` |
| 00 등록 형식 (item 빈 값, 그룹 번호) | `realtime.py` `subscribe_account()` |
| 같은 종목 현재가가 HTS와 같은지 | `/market/quote` |

실제 응답을 테스트 데이터로 저장할 때는 계좌번호·토큰을 지우고 커밋한다.

## 사용자 키 등록 담당자와의 약속

`app/trading/credentials.py`

```python
get_credentials(user_id: int, env: "mock" | "real") -> KiwoomCredentials | None
```

키 등록 기능(Vault 저장)을 만들면 앱 시작 시 `credentials.set_provider(내_함수)`로 연결한다.
그 전까지는 `KIWOOM_DEV_USE_TEAM_KEY=true`이면 모든 사용자가 팀 키(.env)를 쓴다 (팀 키가 모의 서버일 때만, 실전은 불가).

## 체결 실시간 통보

- 실거래를 켠 사용자의 키마다 WebSocket을 하나 열고 00(주문체결)을 등록한다 (backend, `KIWOOM_EXECUTION_WS=true`)
- 체결이 오면 주문 상태를 바로 갱신하고 주문 주인에게 알림 → 화면 알림·음성 알림
- 같은 체결이 두 번 와도 (주문번호, 체결번호)로 한 번만 반영. 체결 수량은 `주문수량 - 미체결수량`
- 연결이 끊겨도 1초~60초 간격으로 다시 접속하고, 주문 내역 조회 때 체결 현황(kt00009)으로 한 번 더 맞춘다

## 위험 제한

- 실거래는 기본 꺼짐. 서버별 확인 문구(모의: `모의투자를 시작합니다`, 실전: `실거래를 시작합니다`)와 잔고 조회 성공 후 켜짐
- 서버나 한도를 바꾸면 자동으로 꺼짐 → 다시 활성화
- 1회 주문 금액 > 한도 → 차단 (`BLOCKED`, 키움으로 주문이 나가지 않음)
- 오늘 손실(그날 첫 추정예탁자산 − 현재) ≥ 한도 → 차단 + 실거래 자동 꺼짐. 그날 입출금이 있으면 손실로 계산될 수 있음
- `POST /trading/kiwoom/deactivate`: 긴급 정지
