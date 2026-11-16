"""학습 진도: 잠금 해제, 별점, XP, 연속 학습일, 레벨, 배지"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.edu import curriculum as cur
from app.edu.models import EduLessonResult, EduProgress, EduTrade

KST = ZoneInfo("Asia/Seoul")
LEVELS = [0, 50, 120, 220, 350, 520, 750, 1000]  # 레벨 n이 되기 위한 누적 XP


class LessonLocked(Exception):
    pass


def today() -> date:
    return datetime.now(KST).date()


def stars_for(correct: int, total: int) -> int:
    """틀린 개수로 별점: 0개 ★3, 1~2개 ★2, 그 이상 ★1"""
    wrong = max(0, total - correct)
    return 3 if wrong == 0 else 2 if wrong <= 2 else 1


def level_info(xp: int) -> dict:
    lvl = max(i + 1 for i, need in enumerate(LEVELS) if xp >= need)
    cur_need = LEVELS[lvl - 1]
    next_need = LEVELS[lvl] if lvl < len(LEVELS) else None
    return {
        "level": lvl,
        "xp_in_level": xp - cur_need,
        "xp_for_next": None if next_need is None else next_need - cur_need,
    }


def _progress(s: Session, user_id: int) -> EduProgress:
    p = s.get(EduProgress, user_id)
    if not p:
        p = EduProgress(user_id=user_id, xp=0, streak=0, best_streak=0)
        s.add(p)
        s.flush()
    return p


def _update_streak(p: EduProgress, day: date) -> None:
    if p.last_study_date == day:
        return
    p.streak = p.streak + 1 if p.last_study_date == day - timedelta(days=1) else 1
    p.best_streak = max(p.best_streak, p.streak)
    p.last_study_date = day


def is_unlocked(lesson_id: str, done: set[str]) -> bool:
    prev = cur.previous(lesson_id)
    return prev is None or prev in done


def complete_lesson(
    s: Session, user_id: int, lesson_id: str, correct: int, total: int, day: date | None = None
) -> dict:
    meta = cur.lesson(lesson_id)
    if not meta or not meta["available"]:
        raise KeyError(lesson_id)
    results = {r.lesson_id: r for r in s.scalars(select(EduLessonResult).where(EduLessonResult.user_id == user_id))}
    if not is_unlocked(lesson_id, set(results)):
        raise LessonLocked(lesson_id)

    p = _progress(s, user_id)
    stars = stars_for(correct, total)
    prev = results.get(lesson_id)
    first_time = prev is None
    # 처음 완료하면 기본 XP, 다시 하면 절반 (복습 보상), 만점이면 보너스
    gained = (cur.LESSON_XP if first_time else cur.LESSON_XP // 2) + (cur.PERFECT_BONUS if stars == 3 else 0)
    before = set(badges(s, user_id, p))

    if first_time:
        s.add(EduLessonResult(user_id=user_id, lesson_id=lesson_id, stars=stars))
    else:
        prev.stars = max(prev.stars, stars)
        prev.attempts += 1
    p.xp += gained
    _update_streak(p, day or today())
    s.commit()

    new_badges = [b for b in badges(s, user_id, p) if b not in before]
    return {
        "stars": stars,
        "xp_gained": gained,
        "first_time": first_time,
        "new_badges": new_badges,
        **summary(s, user_id),
    }


BADGES = {
    "first_lesson": ("첫 걸음", "첫 레슨 완료"),
    "perfect": ("완벽주의자", "한 번도 틀리지 않고 레슨 완료"),
    "streak_3": ("작심삼일 돌파", "3일 연속 학습"),
    "streak_7": ("일주일 개근", "7일 연속 학습"),
    "unit_u1": ("주식 입문자", "유닛 1 '주식 첫걸음' 완료"),
    "unit_u2": ("차트 리더", "유닛 2 '차트 읽기' 완료"),
    "unit_u3": ("지표 탐정", "유닛 3 '기술적 지표' 완료"),
    "unit_u4": ("전략가", "유닛 4 '유명 매매 전략' 완료"),
    "unit_u5": ("리스크 매니저", "유닛 5 '리스크 관리' 완료"),
    "unit_u6": ("자동매매 수료생", "유닛 6 '자동매매 설정' 완료 · 교육 과정 수료"),
    "first_trade": ("첫 거래", "교육용 계좌로 첫 매매"),
    "first_profit": ("첫 수익 실현", "교육용 계좌로 이익을 보고 매도"),
}


def badges(s: Session, user_id: int, p: EduProgress | None = None) -> list[str]:
    p = p or s.get(EduProgress, user_id)
    results = list(s.scalars(select(EduLessonResult).where(EduLessonResult.user_id == user_id)))
    done = {r.lesson_id for r in results}
    trades = list(s.scalars(select(EduTrade).where(EduTrade.user_id == user_id)))
    got = []
    if done:
        got.append("first_lesson")
    if any(r.stars == 3 for r in results):
        got.append("perfect")
    if p and p.best_streak >= 3:
        got.append("streak_3")
    if p and p.best_streak >= 7:
        got.append("streak_7")
    for u in cur.UNITS:
        ids = [x["id"] for x in u["lessons"]]
        if f"unit_{u['id']}" in BADGES and all(i in done for i in ids):
            got.append(f"unit_{u['id']}")
    if trades:
        got.append("first_trade")
    if any((t.realized_pnl or 0) > 0 for t in trades):
        got.append("first_profit")
    return got


def summary(s: Session, user_id: int) -> dict:
    p = s.get(EduProgress, user_id)
    results = {
        r.lesson_id: r.stars for r in s.scalars(select(EduLessonResult).where(EduLessonResult.user_id == user_id))
    }
    done = set(results)
    xp = p.xp if p else 0
    streak = p.streak if p and p.last_study_date and p.last_study_date >= today() - timedelta(days=1) else 0
    owned = set(badges(s, user_id, p))
    units = []
    for u in cur.UNITS:
        lessons = [{**x, "stars": results.get(x["id"]), "unlocked": is_unlocked(x["id"], done)} for x in u["lessons"]]
        units.append(
            {
                **{k: v for k, v in u.items() if k != "lessons"},
                "lessons": lessons,
                "completed": sum(1 for x in lessons if x["stars"]),
                "total": len(lessons),
            }
        )
    return {
        "xp": xp,
        **level_info(xp),
        "streak": streak,
        "best_streak": p.best_streak if p else 0,
        "studied_today": bool(p and p.last_study_date == today()),
        "units": units,
        "badges": [{"id": k, "name": n, "description": d, "owned": k in owned} for k, (n, d) in BADGES.items()],
    }
