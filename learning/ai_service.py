"""ИИ-сервис: разбор ошибок.

Free / без ключа: короткий эталон, без свалки конспекта.
Pro + LLM: короткий персональный разбор строго по контексту из БД.
"""

from __future__ import annotations

import re

from knowledge.models import TaskSolution
from learning.llm_client import chat_completion, get_llm_config
from learning.models import AIExplanationLog, TaskAttempt
from learning.services import build_ai_context

def get_system_prompt_for_grade(grade: int | None = None) -> str:
    """Генерирует адаптивный системный промпт для DeepSeek в зависимости от возраста/класса."""
    if grade and grade <= 4:
        return (
            "Ты дружелюбный и добрый репетитор по русскому языку для детей 1–4 классов.\n\n"
            "ЖЁСТКИЕ ПРАВИЛА:\n"
            "1) Говори очень просто, тепло и понятно, как заботливый школьный учитель.\n"
            "2) БЕЗ сложных терминов! Объясни ошибку 3–4 простыми предложениями.\n"
            "3) Обязательно дай 1 очень простой и наглядный пример.\n"
            "4) Не перегружай лишней теорией."
        )
    elif grade and grade <= 8:
        return (
            "Ты отличный и понятный репетитор по русскому языку для учащихся 5–8 классов.\n\n"
            "ЖЁСТКИЕ ПРАВИЛА:\n"
            "1) Объясняй легко, без воды, понятным школьным языком.\n"
            "2) Объем — 4–6 предложений: что не так → простое правило → 1 наглядный пример.\n"
            "3) Не цитируй длинные заумные определения."
        )
    else:
        return (
            "Ты топовый репетитор по подготовке к ЦЭ и ЦТ по русскому языку в Беларуси (9–11 классы).\n\n"
            "ЖЁСТКИЕ ПРАВИЛА:\n"
            "1) Объясняй строго по делу и правилам РИКЗ.\n"
            "2) Формат (5–7 предложений): суть ошибки → ключевое правило РИКЗ → ловушка/исключение → 1 короткий пример.\n"
            "3) Без размытых формулировок и без лишней теории."
        )


def short_local_explanation(
    *,
    student_answer: str,
    correct_answer: str,
    solution_explanation: str = '',
    grade: int | None = None,
) -> str:
    """Короткий, понятный разбор ответа без простыни конспекта темы."""
    lines = ['🤖 Разбор ответа:']
    lines.append(f'• Твой ответ: {student_answer or "—"}')
    lines.append(f'• Правильный ответ: {correct_answer or "—"}')

    expl = (solution_explanation or '').strip()
    if expl:
        if len(expl) > 500:
            expl = expl[:500].rstrip() + '…'
        lines.append(f'\n💡 Правило и разбор:\n{expl}')
    else:
        if grade and grade <= 4:
            lines.append('\n💡 Подсказка: Вспомни правило из урока и проверь буквы в слове!')
        else:
            lines.append('\n💡 Подсказка: Сравни свой ответ с верным и вспомни главное правило!')
    return '\n'.join(lines)


async def explain_mistake(attempt: TaskAttempt, *, use_llm: bool = True) -> str:
    """
    use_llm=True: DeepSeek/Yandex/GigaChat с адаптацией под возраст/класс ученика.
    use_llm=False: понятный разбор по эталону базы.
    """
    task = attempt.task
    student_grade = attempt.student.grade if hasattr(attempt, 'student') and attempt.student else None

    solution = None
    try:
        solution = await TaskSolution.objects.aget(task_id=task.id)
    except TaskSolution.DoesNotExist:
        pass

    correct_answer = solution.correct_answer if solution else ''
    solution_explanation = solution.explanation if solution else ''

    local = short_local_explanation(
        student_answer=attempt.answer_text,
        correct_answer=correct_answer,
        solution_explanation=solution_explanation,
        grade=student_grade,
    )

    cfg = get_llm_config()
    model_name = 'local-short'
    prompt_context = local[:2000]
    response_text = local

    if not use_llm:
        pass
    elif not cfg:
        # Режим без API ключа — выдаём понятный готовый разбор из базы
        response_text = local
        model_name = 'local-no-key'
    else:
        context = await build_ai_context(task)
        prompt_context = context[:5000]
        base_explanation = ''
        if solution:
            base_explanation = (
                f'Правильный ответ: {solution.correct_answer}\n\n'
                f'{solution.explanation}'
            )
            if solution.common_mistakes:
                base_explanation += f'\n\nТипичные ошибки:\n{solution.common_mistakes}'

        if not _has_enough_grounding(context, base_explanation):
            response_text = local
            model_name = 'local-weak-context'
        else:
            system_prompt = get_system_prompt_for_grade(student_grade)
            user_prompt = (
                'КОНТЕКСТ (единственный источник правил):\n'
                f'{context}\n\n'
                'ЭТАЛОН:\n'
                f'{base_explanation}\n\n'
                f'ЗАДАНИЕ:\n{task.question}\n\n'
                f'ОТВЕТ УЧЕНИКА: {attempt.answer_text}\n'
                f'ПРАВИЛЬНЫЙ ОТВЕТ: {correct_answer}\n\n'
                'Сделай понятный разбор именно этой ошибки ученика с 1 простым примером.'
            )
            llm_text, model_name = await chat_completion(
                system=system_prompt,
                user=user_prompt,
                temperature=0.0,
                max_tokens=700,
            )
            if llm_text and len(llm_text.strip()) > 20:
                if re.search(
                    r'(?:задание\s*№?\s*\d+|придума[йе]м|новый тест)',
                    llm_text,
                    re.I,
                ):
                    response_text = local
                    model_name = 'local-guard'
                else:
                    response_text = '🤖 Разбор от ИИ-Репетитора:\n\n' + llm_text.strip()
            else:
                response_text = local
                model_name = 'local-llm-empty'

    await AIExplanationLog.objects.acreate(
        attempt=attempt,
        prompt_context=prompt_context,
        ai_response=response_text,
        model_name=model_name,
    )
    return response_text
