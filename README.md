# 보조지표 기반 지능형 자동매매 플랫폼

사용자가 직접 설정한 투자 전략을 실시간 시세에 따라 자동으로 실행하고, 과거 시점으로 돌아가 검증하며, 이상 거래까지 감지하는 통합 투자 플랫폼입니다.
키움증권 REST API를 활용하며, **모든 거래는 모의투자 기반**으로 동작합니다.

## 핵심 기능

| 기능 | 설명 |
|---|---|
| 자동매매 엔진 | 볼린저밴드·RSI·이동평균 등 보조지표로 매수·매도 조건을 설정하면 실시간 시세에 맞춰 모의 주문을 자동 실행하고 실시간·음성 알림 제공 |
| 이상 거래 탐지 | 시세·거래량·호가 데이터를 분석해 거래량 급증, 가격 급변, 호가 불균형 등 이상 징후를 탐지하고 경보 제공 |
| 타임머신 트레이딩 | 과거 특정 시점의 시세를 재생하며 자동 백테스트 모드와 직접 매매 모드로 전략 검증 |

## 시스템 구성

```
키움 REST API ──> [Backend: Kafka Producer] ──> Kafka (stock.price)
                                                  │
                    ┌─────────────────────────────┼──────────────────────┐
                    ▼                             ▼                      ▼
          [전략 매칭 엔진 + Redis]        [AI 이상탐지 서비스]      [타임머신 재생기]
                    │                             │                      │
                    └──────── 모의 주문 / 알림 ───┴──────── 결과 ────────┘
                                                  │
                                           [Frontend: React]
          민감정보(API 키) ── HashiCorp Vault
```

## 기술 스택

| 구분 | 사용 기술 |
|---|---|
| Backend | Python, FastAPI |
| Frontend | React (Vite) |
| AI | scikit-learn, pandas (이상탐지) |
| 메시징·캐시 | Apache Kafka, Redis |
| 보조지표 | TA-Lib |
| 보안 | HashiCorp Vault |
| 성능 테스트 | k6 |
| 데이터 | PostgreSQL (과거 시세 저장) |
| 인프라 | Docker, Docker Compose, nginx |
| CI | GitHub Actions (워크플로 7개) |

## 폴더 구조

```
auto-trading-platform/
├── backend/        # FastAPI 서버 (시세 수집, 전략 엔진, 주문, 백테스트)
├── frontend/       # React 웹 화면
├── ai/             # 이상거래 탐지 모델 및 추론
├── docs/           # 설계 문서, 평가항목 체크리스트
├── .github/        # PR·Issue 템플릿, Actions 워크플로
├── docker-compose.yml
└── .env.example
```

## 실행 방법

```bash
# 1. 환경 변수 파일 만들기 (실제 키는 절대 커밋하지 않기)
cp .env.example .env

# 2. 전체 실행 (컨테이너 8개)
docker compose up -d --build

# 3. 컨테이너 간 통신·실시간 시세 확인
curl http://localhost:8000/health/deps
curl http://localhost:8000/market/prices

# 4. (선택) 프론트엔드 개발 서버
cd frontend
npm install
npm run dev     # http://localhost:5173
```

| 서비스 | 주소 |
|---|---|
| Backend API 문서 | http://localhost:8000/docs |
| Frontend (Docker) | http://localhost:3000 |
| Frontend (개발 서버) | http://localhost:5173 |
| AI 이상탐지 API | http://localhost:8001/docs |
| Vault UI | http://localhost:8200 |
| Kafka | localhost:9092 |
| Redis | localhost:6379 |

## 팀원 및 역할

| 이름 | 역할 |
|---|---|
| 전창완 | 백엔드 |
| 임세은 | 백엔드 |
| 김호 | 프론트엔드 |
| 정재영 | 보안 |
| 이종한 | AI |

## 협업 규칙

브랜치 전략, 커밋 메시지, PR 규칙은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참고하세요.
