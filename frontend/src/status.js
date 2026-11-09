// 백엔드 /health/deps 응답을 화면 표시용으로 변환
export function toStatusRows(deps = {}) {
  return Object.entries(deps).map(([name, ok]) => ({ name, label: ok ? '정상' : '연결 안 됨', ok }))
}
