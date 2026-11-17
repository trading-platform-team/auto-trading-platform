# 디자인 가이드

화면을 새로 만들거나 고칠 때 이 기준을 따라 주세요.
변수 정의 위치: `frontend/src/styles.css`의 `:root`

## 1. 기본 원칙

- 다크 테마, 글꼴은 Pretendard
- 상승·수익 = 빨강 `var(--up)`, 하락·손실 = 파랑 `var(--down)` (국내 증시 관례)
- 포인트 색은 보라 `var(--accent)` 하나. 주요 버튼, 선택된 메뉴·탭에만 사용
- 색·크기·간격은 숫자 대신 변수로 쓴다

## 2. 자주 쓰는 변수

| 용도 | 변수 |
|---|---|
| 페이지 / 카드 / 카드 안 영역 배경 | `--bg` / `--card` / `--card-2` |
| 테두리 | `--line` (강조: `--line-strong`) |
| 본문 / 보조 / 흐린 글자 | `--text` / `--text-sub` / `--muted` |
| 상승 / 하락 (옅은 배경) | `--up` / `--down` (`--up-soft` / `--down-soft`) |
| 포인트 색 / 보라 글자 / 선택 배경 | `--accent` / `--accent-text` / `--accent-soft` |
| 성공 / 주의 / 교육 보상 | `--ok` / `--warn` / `--gold` |
| 글자 크기 | `--fs-xs`(11) `--fs-sm`(12) `--fs-md`(14) `--fs-lg`(16) `--fs-xl`(20) `--fs-2xl`(28) |
| 모서리 | `--radius-sm`(6) `--radius-md`(8) `--radius`(10) `--radius-lg`(16) `--radius-pill` |
| 간격 | `--space-1`(4) ~ `--space-6`(32) |

## 3. 예시

```css
.my-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: var(--space-4);
}
.profit { color: var(--up); }
.badge-new {
  background: var(--accent-soft);
  color: var(--accent-text);
  border-radius: var(--radius-pill);
}
```

## 4. 하지 말 것

- `#f2555a`처럼 색 코드를 직접 쓰기 (나중에 한 곳에서 바꿀 수 없음)
- 초록을 상승 색으로 쓰기 (초록 `--ok`은 성공·연결됨 전용)
- 보라 외에 포인트 색 추가하기

## 5. 남은 작업

- Recharts 차트 색(JSX 안)은 아직 직접 적혀 있음. 다음 PR에서 공통 색 파일로 정리 예정