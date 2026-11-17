"""실거래 (사용자 본인 키움 키로 모의투자 또는 실전 계좌 주문)

- models.py      설정(서버·한도·활성화)과 주문 기록
- credentials.py 사용자 키 조회 (키 등록 기능 담당자가 provider를 연결)
- risk.py        주문 전 위험 제한 (1회 주문 한도, 일일 손실 한도)
- broker.py      KiwoomBroker: 위험 제한 → 키움 주문 → 기록, 체결 동기화
"""
