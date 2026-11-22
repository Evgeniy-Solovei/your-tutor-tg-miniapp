"""Модуль защиты от накрутки, ботов и аномальной активности (Anti-Cheat)."""

import logging
from django.core.cache import cache
from rest_framework.exceptions import Throttled

logger = logging.getLogger(__name__)

# Лимиты скорости и частоты
VELOCITY_COOLDOWN_SECONDS = 1  # Минимальная пауза между отправками ответов (1 сек)
MAX_SUBMISSIONS_PER_MINUTE = 30  # Максимум 30 ответов в минуту на одного ученика
SUSPICIOUS_SPEED_SECONDS = 2  # Слишком быстрый ответ (менее 2 сек)
MAX_CONSECUTIVE_SPEED_ANSWERS = 10  # Максимум быстрых правильных ответов подряд до алерта


async def check_submission_velocity(student_id: int) -> None:
    """
    Проверяет человеческую скорость ответов.
    Выбрасывает Throttled (HTTP 429), если ответы отправляются быстрее 1 сек
    или если превышен лимит 30 ответов в минуту.
    """
    # 1. Атомарная проверка минимального интервала в кэше
    velocity_key = f'anti_cheat:vel:{student_id}'
    # cache.add атомарен в Redis: возвращает True только если ключа не было
    was_added = cache.add(velocity_key, 1, timeout=VELOCITY_COOLDOWN_SECONDS)
    if not was_added:
        logger.warning('Velocity violation: student %s submitted answer too fast (< %ss)', student_id, VELOCITY_COOLDOWN_SECONDS)
        raise Throttled(detail='Слишком быстрый ответ. Внимательно читайте задания перед отправкой.')

    # 2. Проверка лимита ответов в минуту
    minute_key = f'anti_cheat:rate_min:{student_id}'
    count = await cache.aget(minute_key, 0)
    if count >= MAX_SUBMISSIONS_PER_MINUTE:
        logger.warning('Rate limit exceeded: student %s > %s answers/min', student_id, MAX_SUBMISSIONS_PER_MINUTE)
        raise Throttled(detail=f'Превышен лимит отправки: максимум {MAX_SUBMISSIONS_PER_MINUTE} ответов в минуту. Сделайте небольшую паузу.')

    try:
        await cache.aset(minute_key, count + 1, timeout=60)
    except Exception:
        pass


async def record_answer_speed_and_detect_anomaly(
    student_id: int,
    is_correct: bool,
    time_spent_seconds: float = 0,
) -> bool:
    """
    Отслеживает серию сверхбыстрых правильных ответов (поведение бота).
    Возвращает True, если зафиксирована аномальная активность.
    """
    if not is_correct:
        try:
            await cache.adelete(f'anti_cheat:fast_streak:{student_id}')
        except Exception:
            pass
        return False

    if 0 < time_spent_seconds < SUSPICIOUS_SPEED_SECONDS:
        streak_key = f'anti_cheat:fast_streak:{student_id}'
        streak = (await cache.aget(streak_key, 0)) + 1
        try:
            await cache.aset(streak_key, streak, timeout=180)
        except Exception:
            pass

        if streak >= MAX_CONSECUTIVE_SPEED_ANSWERS:
            logger.error(
                'SECURITY ALERT: Ученик %s дал %s верных ответов подряд быстрее %s сек! Возможен бот/скрипт.',
                student_id,
                streak,
                SUSPICIOUS_SPEED_SECONDS,
            )
            return True
    else:
        try:
            await cache.adelete(f'anti_cheat:fast_streak:{student_id}')
        except Exception:
            pass

    return False
