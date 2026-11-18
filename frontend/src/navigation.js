import { BookOpen, Bot, History, Wallet } from 'lucide-react'


export const PAGES = [
  { id: 'education', icon: BookOpen, eyebrow: '배우기', title: '교육', description: '용어와 전략을 단계별로 학습합니다' },
  { id: 'paper', icon: Wallet, eyebrow: '가상자금', title: '모의투자', description: '실시간 모의 시세로 안전하게 연습합니다' },
  { id: 'live', icon: Bot, eyebrow: '자동매매', title: '실거래', description: '키움 계좌 연결 후 실시간 전략을 관리합니다' },
  { id: 'timemachine', icon: History, eyebrow: '과거시장', title: '타임머신', description: '과거 시세로 전략을 검증합니다' },
]

export const PAGE_INFO = Object.fromEntries(PAGES.map((page) => [page.id, page]))