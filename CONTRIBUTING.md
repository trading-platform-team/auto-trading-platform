# 협업 규칙

## 브랜치 전략 (Git Flow)

```
main                  ← 배포·발표용 안정 버전
 ├─ hotfix/<내용>     ← main에서 급하게 고칠 때 (main, develop 둘 다에 머지)
 └─ release/<버전>    ← 발표 전 develop을 묶어 최종 점검 (예: release/v1.0)
     └─ develop       ← 통합 브랜치
         ├─ feature/<파트>-<기능>   예) feature/ai-anomaly-rule
         └─ fix/<내용>              예) fix/kafka-consumer-offset
```

| 브랜치 | 어디서 만드나 | 어디로 PR |
|---|---|---|
| feature/*, fix/* | develop | develop |
| release/* | develop | main (머지 후 develop에도 반영) |
| hotfix/* | main | main, develop |

- `main`, `develop`에는 직접 push하지 않습니다. 반드시 PR로 머지합니다.
- 기능 브랜치는 항상 최신 `develop`에서 만듭니다.
- 머지가 끝난 브랜치는 삭제합니다.

## 작업 순서

```bash
git checkout develop
git pull origin develop
git checkout -b feature/backend-kafka-producer

# 작업 후
git add .
git commit -m "feat: 실시간 시세 Kafka Producer 구현"
git push -u origin feature/backend-kafka-producer
```

GitHub에서 **base: develop** 으로 PR을 만들고 리뷰어 1명 이상을 지정합니다.

## 커밋 메시지

`<타입>: <내용>` 형식으로 한글로 작성합니다.

| 타입 | 용도 |
|---|---|
| feat | 새 기능 |
| fix | 버그 수정 |
| docs | 문서 |
| refactor | 동작 변화 없는 코드 개선 |
| test | 테스트 추가·수정 |
| chore | 설정, 빌드, 패키지 |

예) `feat: RSI 매수 조건 매칭 추가`, `fix: 호가 데이터 파싱 오류 수정`

## PR 규칙

- PR 본문에 관련 Issue를 적습니다. 예) `closes #7`
- 리뷰어 1명 이상 승인 후 머지합니다.
- PR 하나에는 기능 하나만 담습니다.

## 보안 규칙

- 키움 API 앱키·시크릿, 계좌번호 등은 **절대 커밋하지 않습니다.**
- 로컬에서는 `.env`에, 공유가 필요하면 Vault에 저장합니다.
- 실수로 키가 push되면 즉시 팀에 알리고 키를 재발급합니다.
