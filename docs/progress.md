# 팀 프로젝트 진행 상황 정리

> 보조지표 기반 지능형 자동매매 플랫폼 · 오픈소스SW실습 팀 프로젝트
> 저장소: https://github.com/trading-platform-team/auto-trading-platform

---

## 1. 프로젝트 개요 (9주차 주제 발표 기획안)

사용자가 직접 설정한 투자 전략을 실시간 시세에 따라 자동으로 실행하고, 과거 시점으로 돌아가 검증하며, 이상 거래까지 감지하는 통합 투자 플랫폼. 키움증권 REST API를 활용하며, 모든 거래는 모의투자 기반으로 동작한다.

### 핵심 기능 3가지

| 기능 | 내용 |
|---|---|
| 1. 자동매매 엔진 | 보조지표(볼린저밴드, RSI, 이동평균 등)로 매수·매도 조건을 설정하면 실시간 시세를 받아 조건 충족 시 자동으로 모의 주문 실행. 결과를 실시간 및 음성으로 알림 |
| 2. 이상 거래 탐지 | 실시간 시세·거래량·호가 데이터를 분석해 거래량 급증, 가격 급변, 호가 불균형 등 이상 징후를 탐지하고 경보. AI 기반 이상탐지 모델 활용 |
| 3. 과거 시점 투자 (타임머신 트레이딩) | 과거 특정 시점의 시세를 재생하며 전략 검증. 자동 백테스트 모드와 직접 매매 모드 |

### 기획안의 오픈소스

Apache Kafka(실시간 시세 스트림), Redis(전략 조건 매칭·캐싱), TA-Lib(보조지표), k6(부하 테스트), HashiCorp Vault(API 키 보안), 키움증권 REST API(시세·모의 주문)

### 역할 분담

| 이름 | 역할 |
|---|---|
| 전창완 | 백엔드 |
| 임세은 | 백엔드 |
| 김호 | 프론트엔드 |
| 정재영 | 보안 |
| 이종한 | AI |

---

## 2. 평가 기준

### 교수님 기술 평가항목

1. **Git**
   - Git Branch 전략을 잘 활용하여 개발하였는가? (계층적으로 Branch를 관리하였는가?)
   - Pull Request를 활용해서 소스코드를 원활히 업데이트하였는가?
2. **Docker, Kubernetes**
   - Docker Compose를 통해 적어도 3종류 이상의 Container를 활용하는 어플리케이션인가?
   - 또는 Kubernetes를 통해 컨테이너가 3종류 이상, Pod이 2개 이상인 클러스터로 구성된 어플리케이션인가?
   - 컨테이너 간 통신이 이루어지며, 볼륨을 활용하고 있는가?
3. **수업시간에 배운 오픈소스를 제외하고 1개 이상의 오픈소스를 활용하였는가?** (Python 등 프로그래밍 언어, MySQL 등 오픈소스 DB는 제외)
4. **GitHub Actions**: Workflow를 5개 이상 활용하여 다양한 테스트를 진행하였는가?

### 학생 상호평가 항목 (발표 후, 1~5점)

1. 사회에 배포했을 때 높은 실용성 또는 연구적 가치를 가진 프로젝트인가
2. 주제의 창의성이 높은가 (이미 있는 기술이 아닌가)
3. 기술적 난이도가 높은가
4. 팀 인원 전체가 필요한 규모인가 (바이브 코딩을 고려해도)
5. 중간발표 때 계획한 내용을 대부분 구현했는가
6. 명확하고 설득력 있게 발표했는가 (대본만 읽지 않았는가)
7. 확장 가능성과 지속 가능성이 있는가
8. 배포되었을 때 사용 또는 지속적인 관심을 가질 계획이 있는가
9. 수업시간에 배운 오픈소스 프레임워크를 기반으로 논리적이며 체계적으로 설계했는가
10. 전반적으로 성공적인가

### 평가 기준을 반영한 개발 방향

- 중간발표 때 말한 핵심 기능 3개를 모두 실제로 동작하게 만드는 것을 최우선으로 한다 (상호평가 5, 10번)
- "증권사에 이미 있는 기능 아닌가?"라는 질문에 답할 차별점을 준비한다 (상호평가 2번)
- Kafka, Redis, Vault, Docker, Actions가 각각 왜 필요한지 구조도로 설명한다 (교수 2·3번, 상호평가 3·9번)
- 발표는 라이브 데모 위주로 한다 (상호평가 6번)
- 팀원 전원의 브랜치·PR 기록을 남긴다 (교수 Git 항목, 상호평가 4번)

---

## 3. 평가항목 대응 현황

| 평가항목 | 현재 상태 |
|---|---|
| Git 브랜치 계층 관리 | main / develop / feature 사용 중. release, hotfix는 아직 사용 전 (아래 7번 참고) |
| PR 활용 | main·develop 직접 push 금지, PR + 승인 1명 필수. PR #33 ~ #37 머지 |
| Docker Compose 3종 이상 | 컨테이너 8종: frontend, backend, collector, ai, kafka, redis, postgres, vault |
| 컨테이너 간 통신 | collector → kafka → backend → redis, kafka → ai → redis, frontend(nginx) → backend 등 |
| 볼륨 | pg-data(전략·주문), redis-data, kafka-data, ai-models(학습된 AI 모델) |
| 수업 외 오픈소스 | Kafka, Redis, Vault, TA-Lib, nginx, gitleaks, scikit-learn (k6는 예정) |
| GitHub Actions 5개 이상 | 7개 (아래 6번 참고) |
| Kubernetes | 선택 사항. 핵심 기능 완성 후 진행 예정 |

자세한 대응표: `docs/evaluation-checklist.md`

---

## 4. GitHub 설정 (완료)

- Organization: `trading-platform-team`
- Repository: `auto-trading-platform` (Public)
- 브랜치: `main`, `develop` (Default branch = `develop`)
- 브랜치 보호 규칙(Ruleset) `protect-main-develop`: main·develop 대상, PR 필수, 승인 1명, 삭제·force push 금지
- 팀원 4명 초대 완료, 팀원에게 Write 권한 부여 (Write 권한이 없으면 승인해도 머지가 안 풀림)
- Issue #1 ~ #32 등록

### 참고

- Issue와 PR은 같은 번호를 이어서 쓴다. 그래서 첫 PR이 #33이 됨
- PR을 만든 본인은 자기 PR을 승인할 수 없다. 쓰기 권한이 있는 팀원 누구나 승인 가능 (리뷰어로 지정하지 않아도 됨)
- PR 본문에 `closes #번호`를 쓰면 develop에 머지될 때 해당 Issue가 자동으로 닫힌다 (Default branch가 develop이라서 가능)

---

## 5. 지금까지 머지된 작업

| PR | 브랜치 | 내용 | 관련 Issue |
|---|---|---|---|
| #33 | feature/init-project-setup | 폴더 구조, README, 협업 규칙, docker-compose, PR·Issue 템플릿, Actions 워크플로 7개 | #1, #2, #5, #6, #28, #29 내용 포함 |
| #34 | feature/backend-market-pipeline | 모의 시세 수집기(collector) → Kafka → Redis 캐싱, 시세 조회 API, 시세 표 | #7, #8 |
| #35 | feature/backend-strategy-engine | TA-Lib 보조지표, 전략 CRUD, 조건 매칭 엔진, 모의 주문, 알림 기록 | #10, #12, #13, #14 |
| #36 | feature/ai-realtime-anomaly | 룰 + LOF 실시간 이상탐지, 모델 비교 평가, `/anomalies` API | #11, #16, #17, #18, #19 |
| #37 | feature/frontend-dashboard | 대시보드, 차트, 전략 설정 UI, 이상거래 경보, WebSocket·음성 알림 | #15, #23, #24, #25 |
| (진행 중) | feature/timemachine | 과거 일봉(가상), 자동 백테스트, 직접 매매 세션, 결과 비교, 타임머신 화면 | #9, #20, #21, #22, #26 |

> #33의 Issue들(#1, #2, #5, #6, #28, #29)은 내용은 구현됐지만 PR 본문에 `closes`로 연결하지 않았을 수 있다. Issue 목록에서 열려 있으면 직접 닫아야 한다.

---

## 6. 현재 시스템 구조

```
collector ──시세──> Kafka(stock.price) ──┬──> backend ──> Redis(시세 캐시)
                                         │       │
                                         │       ├─ 자동매매 엔진: 지표 계산 → 전략 조건 평가 → 모의 주문 → PostgreSQL
                                         │       └─ API, WebSocket(/ws/alerts)
                                         │
                                         └──> ai ──> 이상탐지(룰 + LOF) ──> Kafka(stock.anomaly), Redis(anomalies, alerts)

frontend(nginx) ──/api──> backend
Vault: API 키 보관용 (컨테이너만 실행 중, 연동은 아직)

타임머신: backend가 PostgreSQL의 과거 일봉으로 백테스트·직접 매매 세션 처리 (세션 상태는 Redis)
          → 화면 구간의 이상거래 표시는 ai 컨테이너 /detect 호출
```

### 컨테이너

| 컨테이너 | 역할 | 포트 |
|---|---|---|
| frontend | React 화면 (nginx) | 3000 |
| backend | FastAPI, Kafka 소비, 자동매매 엔진, API | 8000 |
| collector | 시세 수집 → Kafka 전송 (backend 이미지 재사용) | - |
| ai | 실시간 이상탐지 | 8001 |
| kafka | 메시지 스트림 | 9092 |
| redis | 시세 캐시, 쿨다운, 알림 Pub/Sub | 6379 |
| postgres | 전략·주문 저장 | 5432 |
| vault | 민감정보 관리 | 8200 |

### 주요 API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/health`, `/health/deps` | 상태, 다른 컨테이너 연결 확인 |
| GET | `/market/prices` | 전 종목 최신 시세 |
| GET | `/market/ticks/{종목코드}` | 종목별 최근 시세 |
| GET | `/market/chart/{종목코드}` | 차트용 시세 + 지표 시계열 |
| GET | `/indicators/{종목코드}` | SMA·RSI·볼린저밴드 최신값 |
| POST / GET | `/strategies` | 전략 등록 / 목록 |
| GET / PUT / DELETE | `/strategies/{id}` | 전략 조회 / 수정 / 삭제 |
| GET | `/orders` | 모의 주문 내역 |
| GET | `/alerts` | 최근 알림 (주문 + 이상거래) |
| GET | `/anomalies` | AI 이상거래 경보 |
| WS | `/ws/alerts` | 실시간 알림 |

API 문서는 실행 후 http://localhost:8000/docs 에서 확인할 수 있다.

### 시세 데이터

키움 API 키가 아직 없어서 **모의 시세(MockSource)** 로 동작한다. 5종목(삼성전자, SK하이닉스, NAVER, 현대차, 카카오)을 1초마다 생성하며, 이상탐지 시연을 위해 가끔 거래량 급증·가격 급변·호가 쏠림·복합 이상을 섞는다. 키움 연동 후에는 `.env`의 `MARKET_SOURCE=kiwoom`으로 바꾼다 (`KiwoomSource`는 아직 미구현).

### 자동매매 전략

- 지표: `PRICE`, `SMA`, `EMA`, `RSI`, `BB_UPPER`, `BB_MIDDLE`, `BB_LOWER`
- 연산자: `<`, `<=`, `>`, `>=`, `cross_up`(상향 돌파), `cross_down`(하향 돌파)
- 조건은 모두 만족(AND)해야 주문 실행. 같은 전략의 연속 주문은 쿨다운(Redis)으로 막음
- 주문은 현재가로 즉시 체결되는 모의 주문 (키움 모의투자 주문 연동은 아직)

### AI 이상탐지 요약 (자세한 내용: `docs/anomaly-detection.md`)

- 룰 기반(거래량 3배, 가격 ±3%, 호가 불균형 0.6)과 AI 모델(LOF)을 동시에 사용. 둘 다 잡으면 경보 수준 `high`
- 특징: 수익률, 거래량 배수, 호가 불균형 (volatility는 반복 오탐 때문에 제외)
- 모델 비교 (합성 데이터, seed 10개 평균)

| 모델 | Precision | Recall | F1 |
|---|---|---|---|
| 룰 기반 | 1.00 | 0.75 | 0.85 |
| Isolation Forest | 0.88 | 0.88 | 0.87 |
| Elliptic Envelope | 0.89 | 0.93 | 0.90 |
| **LOF (채택)** | **1.00** | **1.00** | **1.00** |

- 복합 이상(각 지표가 룰 기준 미만이지만 동시에 발생)을 룰은 3%, LOF는 100% 탐지
- 한계: 합성 데이터 기준 결과. 키움 연동 후 실제 데이터로 재평가 필요

### GitHub Actions 워크플로 (7개)

| 워크플로 | 내용 |
|---|---|
| backend-test.yml | 백엔드 pytest |
| ai-test.yml | 이상탐지 pytest |
| frontend-test.yml | 프론트 vitest + 빌드 |
| lint.yml | ruff 파이썬 코드 검사 |
| docker-build.yml | compose 문법 검사 + 이미지 빌드 |
| integration-test.yml | 컨테이너 8개 실행 후 통신·시세·자동매매 주문·이상탐지 검사 |
| secret-scan.yml | gitleaks로 API 키 유출 검사 |

---

## 7. 협업 방법

### 브랜치 전략 (3주차 수업 자료의 5가지 브랜치)

```
main                  ← 배포·발표용 안정 버전
 ├─ hotfix/<내용>     ← main에서 급하게 고칠 때 (main, develop 둘 다에 머지)
 └─ release/<버전>    ← 발표 전 develop을 묶어 최종 점검
     └─ develop       ← 통합 브랜치
         ├─ feature/<파트>-<기능>
         └─ fix/<내용>
```

- main, develop은 계속 유지하고 feature, release, hotfix는 필요할 때 만들고 머지 후 삭제한다
- 평가에서 "계층적 관리"를 보여주려면 프로젝트가 끝날 때까지 5종류가 모두 한 번씩은 사용된 기록이 있어야 한다
  - release: 발표 전에 `release/v1.0`을 만들어 main으로 PR
  - hotfix: main에 올라간 뒤 버그를 `hotfix/...`로 고쳐 main, develop 양쪽에 PR

### 작업 순서

```bash
git checkout develop
git pull
git checkout -b feature/<파트>-<기능>

# 작업 후
git add .
git commit -m "feat: 작업 내용"
git push -u origin feature/<파트>-<기능>
```

1. GitHub에서 PR 생성 (base: `develop`), 본문에 `closes #이슈번호`
2. Actions가 모두 ✅인지 확인 (PR 화면 아래쪽 또는 Actions 탭)
3. 팀원 1명 승인: PR → Files changed → Review changes → Approve → Submit review
4. Merge pull request → Confirm merge → Delete branch
5. 로컬 정리: `git checkout develop`, `git pull`, `git branch -d <브랜치>`

커밋 메시지 형식은 `CONTRIBUTING.md` 참고 (feat, fix, docs, refactor, test, chore)

### Windows에서 자주 보는 메시지

- `LF will be replaced by CRLF` 경고: 줄바꿈 방식 차이 안내, 무시해도 됨
- clone할 때 같은 이름 폴더가 있으면 실패하므로 `git clone <주소> <다른폴더이름>`으로 받는다

### 보안 규칙

- 키움 API 앱키·시크릿, 계좌번호는 절대 커밋하지 않는다 (`.env`는 `.gitignore`에 포함)
- 단톡방에도 올리지 않고 Vault에 저장할 예정
- 실수로 push되면 즉시 팀에 알리고 키를 재발급한다

---

## 8. 실행 방법

```bash
git checkout develop
git pull
cp .env.example .env          # 필요 시 (PowerShell: Copy-Item .env.example .env)
docker compose up -d --build  # 처음엔 5~10분
docker compose ps             # 8개가 모두 Up인지 확인
```

- 화면: http://localhost:3000
- API 문서: http://localhost:8000/docs
- AI 모델 상태: http://localhost:8001/model/status
- 안 될 때: Docker Desktop이 실행 중인지 확인, `docker compose logs <컨테이너> --tail 50`
- AI 모델 비교 평가: `cd ai && python evaluate.py --seeds 10`

---

## 9. 앞으로 해야 할 것

### 바로 할 것

- [ ] **로컬에서 Docker로 직접 실행 확인** (지금까지는 GitHub Actions에서만 실행됨. 현재 localhost:3000 접속이 안 되는 상태로, 확인 중)
- [ ] **키움 REST API 모의투자 신청 및 앱키 발급** (Step 0. 진행 여부 확인 필요)
- [ ] 브랜치 보호 규칙에 **Require status checks to pass** 추가: `python-lint`, `build`, `compose-up`, `gitleaks` 4개만 (Backend·AI·Frontend Test는 해당 폴더가 바뀔 때만 실행돼서 넣으면 PR이 멈춤)
- [ ] 구현됐지만 열려 있을 수 있는 Issue 닫기: #1, #2, #5, #6, #28, #29

### 핵심 기능 3: 타임머신 트레이딩 (feature/timemachine PR)

- [x] #9 과거 시세 DB 저장 (지금은 가상 일봉 2023-01-02 ~ 2025-12-31, 키움 일봉 연동은 아래 '키움 연동'에서)
- [x] #20 과거 시세 재생 (하루씩 / +5일 / 자동 재생 1·2·5일/초)
- [x] #21 자동 백테스트 모드 및 수익률·MDD·승률 등 성과 지표
- [x] #22 직접 매매 모드 (과거 시점 수동 주문, 종료 후 단순 보유·대표 전략과 순위 비교)
- [x] #26 타임머신 트레이딩 화면

### 키움 연동 (키 발급 후)

- [ ] #3 키움 REST API 연결 테스트, `KiwoomSource` 구현 (실제 시세)
- [ ] 키움 일봉 조회로 과거 시세 적재 (지금은 가상 일봉, `backend/app/history/`)
- [ ] #4 Vault에 API 키 저장, 백엔드에서 불러오기
- [ ] 키움 모의투자 주문 API 연동 (지금은 자체 모의 체결)
- [ ] 실제 시세로 AI 이상탐지 재평가

### 보안·검증

- [ ] #27 사용자 인증(JWT) 및 API 접근 제어
- [ ] #30 k6 부하 테스트 (워크플로로 추가하면 Actions 8개)
- [ ] #31 전체 통합 테스트 및 버그 수정

### 마무리

- [ ] release 브랜치로 main에 머지, hotfix 브랜치 사용 기록 남기기
- [ ] (선택) Kubernetes: compose 구성을 매니페스트(Deployment, Service, PVC)로 옮기고 backend·ai를 Pod 2개 이상으로 실행, minikube로 시연. 핵심 기능 완성 후 진행
- [ ] #32 최종 발표자료 및 시연 영상 준비. 시스템 구조도, AI 모델 비교 결과, 라이브 데모 중심

---

## 10. 수정하고 싶은 부분이 있으면

- 담당자 배정(Issue Assignee)은 역할 분담표를 기준으로 임의로 나눈 것이라 팀 회의에서 조정 가능
- 시세 종목·전략 지표·이상탐지 기준값 등은 코드에서 바꿀 수 있다
  - 모의 시세 종목: `backend/app/market/sources.py`
  - 지원 지표·연산자: `backend/app/strategy/`
  - 룰 기준값: `ai/anomaly/rules.py` (RuleConfig)
  - LOF 설정: `ai/anomaly/model.py`
- 바꾸고 싶은 점이 있으면 Issue로 올리고 feature 브랜치 → PR 순서로 진행
