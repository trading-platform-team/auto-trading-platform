# 기술 평가항목 대응표

## 1. Git

| 평가 항목 | 대응 | 상태 |
|---|---|---|
| 계층적 Branch 관리 | main → release → develop → feature 구조 ([CONTRIBUTING.md](../CONTRIBUTING.md)) | 진행 중 |
| PR로 소스코드 업데이트 | main·develop 직접 push 금지, 리뷰 1명 승인 후 머지, PR 템플릿 | 진행 중 |

> 팀원 전원이 각자 브랜치를 만들고 PR을 올린 기록이 남아야 합니다.

## 2. Docker / Kubernetes

| 평가 항목 | 대응 | 상태 |
|---|---|---|
| 컨테이너 3종 이상 | frontend, backend, ai, kafka, redis, postgres, vault (7종) | 완료 |
| 컨테이너 간 통신 | frontend(nginx) → backend → kafka·redis·postgres·vault·ai, `/health/deps`로 확인 | 완료 |
| 볼륨 활용 | pg-data, redis-data, kafka-data, ai-models | 완료 |
| (선택) Kubernetes | 시간 여유 시 k8s 매니페스트 추가 | 미정 |

## 3. 수업 외 오픈소스 (언어·DB 제외)

| 오픈소스 | 용도 |
|---|---|
| Apache Kafka | 실시간 시세 스트림 |
| Redis | 전략 조건 매칭, 캐싱 |
| HashiCorp Vault | API 키 등 민감정보 관리 |
| TA-Lib | 보조지표 계산 |
| k6 | 부하 테스트 |
| nginx | 프론트 정적 파일 서빙, API 리버스 프록시 |
| gitleaks | 민감정보 커밋 검사 |

## 4. GitHub Actions (5개 이상)

| # | 워크플로 | 내용 |
|---|---|---|
| 1 | backend-test.yml | 백엔드 pytest |
| 2 | ai-test.yml | 이상탐지 로직·API pytest |
| 3 | frontend-test.yml | vitest 단위 테스트 + 빌드 |
| 4 | lint.yml | ruff 파이썬 코드 검사 |
| 5 | docker-build.yml | compose 문법 검사 + 이미지 빌드 |
| 6 | integration-test.yml | 전체 컨테이너 실행 후 컨테이너 간 통신 테스트 |
| 7 | secret-scan.yml | gitleaks로 API 키 유출 검사 |
| 8 | (예정) load-test.yml | k6 부하 테스트 |
