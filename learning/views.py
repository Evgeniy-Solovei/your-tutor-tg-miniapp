from adrf.views import APIView
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from core.api import aget_student_by_tg, telegram_auth_classes
from core.services import student_can_practice, student_can_request_ai
from knowledge.izlozhenie import task_payload_for_api
from knowledge.models import TaskOption
from learning.ai_service import explain_mistake
from learning.models import DailySession, SessionTask, TaskAttempt
from learning.services import (
    create_exam_simulator_session,
    create_izlozhenie_session,
    get_next_session_task,
    list_izlozhenie_catalog,
    submit_answer,
    submit_exam_simulator,
)


async def serialize_current_task(next_task: SessionTask | None) -> dict | None:
    if not next_task:
        return None
    task = next_task.task
    options = []
    async for o in TaskOption.objects.filter(task_id=task.id).order_by('order'):
        img = ''
        try:
            if o.image:
                img = o.image.url
        except ValueError:
            img = ''
        options.append({'id': o.id, 'text': o.text, 'image_url': img})
    payload = task_payload_for_api(task)
    return {
        'session_task_id': next_task.id,
        'purpose': next_task.purpose,
        'order': next_task.order,
        **payload,
        'options': options,
    }


class SubmitAnswerView(APIView):
    """Отправка ответа из Mini App."""

    authentication_classes = telegram_auth_classes()

    @extend_schema(request={'application/json': {'type': 'object', 'properties': {
        'session_task_id': {'type': 'integer'},
        'answer_text': {'type': 'string'},
    }}})
    async def post(self, request, tg_id: int):
        student, err = await aget_student_by_tg(request, tg_id)
        if err:
            return err

        can, reason = await student_can_practice(student)
        if not can:
            return Response({'detail': reason}, status=status.HTTP_403_FORBIDDEN)

        session_task_id = request.data.get('session_task_id')
        answer_text = request.data.get('answer_text', '').strip()
        if not session_task_id or not answer_text:
            return Response({'detail': 'session_task_id и answer_text обязательны'}, status=status.HTTP_400_BAD_REQUEST)

        session_task = await SessionTask.objects.select_related('task', 'session').aget(
            id=session_task_id,
            session__student=student,
        )
        if session_task.is_answered:
            return Response({'detail': 'Задание уже выполнено'}, status=status.HTTP_400_BAD_REQUEST)

        attempt = await submit_answer(student, session_task, answer_text)
        can_ai, use_llm, ai_reason = await student_can_request_ai(student)

        response = {
            'is_correct': attempt.is_correct,
            'points_earned': attempt.points_earned,
            'max_points': attempt.max_points,
            'can_request_ai': can_ai,
            'ai_use_llm': use_llm,
            'ai_reason': ai_reason if not attempt.is_correct else '',
        }

        # Для изложений не отдаём полный эталон в ленту — только короткую подсказку.
        payload = task_payload_for_api(session_task.task, topic_name='')
        if payload.get('is_izlozhenie'):
            response['hint'] = (
                'Сравни своё изложение с текстом выше: все ли ключевые факты на месте? '
                'Проверь сложные предложения и пунктуацию.'
            )
            response['show_etalon'] = False
        elif not attempt.is_correct:
            try:
                from knowledge.models import TaskSolution

                solution = await TaskSolution.objects.aget(task_id=session_task.task_id)
                answer = solution.correct_answer or ''
                if len(answer.split()) > 80:
                    response['hint'] = 'Эталон длинный — открой разбор, если нужна помощь.'
                    response['show_etalon'] = False
                else:
                    response['correct_answer'] = answer
                    response['show_etalon'] = True
            except Exception:
                pass

        return Response(response)


class AIExplainView(APIView):
    """Запрос ИИ-разбора для последней попытки."""

    authentication_classes = telegram_auth_classes()

    async def post(self, request, tg_id: int):
        student, err = await aget_student_by_tg(request, tg_id)
        if err:
            return err

        can, use_llm, reason = await student_can_request_ai(student)
        if not can:
            return Response({'detail': reason}, status=status.HTTP_403_FORBIDDEN)

        session_task_id = request.data.get('session_task_id')
        attempt = await (
            TaskAttempt.objects.filter(
                student=student,
                session_task_id=session_task_id,
            )
            .select_related('task', 'task__topic')
            .order_by('-created_at')
            .afirst()
        )
        if not attempt:
            return Response({'detail': 'Попытка не найдена'}, status=status.HTTP_404_NOT_FOUND)

        explanation = await explain_mistake(attempt, use_llm=use_llm)
        return Response({'explanation': explanation, 'used_llm': use_llm})


class IzlozheniyaCatalogView(APIView):
    """Каталог текстов официального сборника изложений."""

    authentication_classes = telegram_auth_classes()

    async def get(self, request, tg_id: int):
        student, err = await aget_student_by_tg(request, tg_id)
        if err:
            return err
        q = (request.query_params.get('q') or '').strip()
        items = await list_izlozhenie_catalog(q=q)
        return Response(
            {
                'count': len(items),
                'source': 'Сборник материалов для выпускного экзамена (НИО): тексты для изложений',
                'items': items,
                'student_grade': student.grade,
            }
        )


class IzlozheniyaStartView(APIView):
    """Старт тренировки по сборнику изложений (подменяет текущую практику)."""

    authentication_classes = telegram_auth_classes()

    @extend_schema(request={'application/json': {'type': 'object', 'properties': {
        'task_id': {'type': 'integer'},
        'count': {'type': 'integer'},
    }}})
    async def post(self, request, tg_id: int):
        student, err = await aget_student_by_tg(request, tg_id)
        if err:
            return err

        can, reason = await student_can_practice(student)
        if not can:
            return Response({'detail': reason}, status=status.HTTP_403_FORBIDDEN)

        task_id = request.data.get('task_id')
        count = int(request.data.get('count') or 3)
        count = max(1, min(count, 10))
        if task_id is not None:
            try:
                task_id = int(task_id)
            except (TypeError, ValueError):
                return Response({'detail': 'Некорректный task_id'}, status=status.HTTP_400_BAD_REQUEST)

        # закрываем незавершённые тренировки, чтобы Mini App видел новую сессию
        await (
            DailySession.objects.filter(
                student=student,
                status=DailySession.Status.IN_PROGRESS,
                kind=DailySession.Kind.TRAIN,
            )
            .aupdate(status=DailySession.Status.COMPLETED)
        )

        session = await create_izlozhenie_session(
            student,
            task_id=task_id,
            count=count,
        )
        next_task = await get_next_session_task(session)
        task_data = await serialize_current_task(next_task)
        return Response(
            {
                'can_practice': True,
                'session_id': session.id,
                'session_date': session.session_date,
                'status': session.status,
                'tasks_completed': session.tasks_completed,
                'tasks_total': session.tasks_total,
                'xp_earned': session.xp_earned,
                'primary_score': session.primary_score,
                'max_primary': session.max_primary,
                'test_score': session.test_score,
                'current_task': task_data,
                'mode': 'izlozhenie',
            }
        )


class ExamStartView(APIView):
    """Старт симулятора ЦТ/ЦЭ (40 вопросов, 180 минут)."""

    authentication_classes = telegram_auth_classes()

    async def post(self, request, tg_id: int):
        student, err = await aget_student_by_tg(request, tg_id)
        if err:
            return err

        can, reason = await student_can_practice(student)
        if not can:
            return Response({'detail': reason}, status=status.HTTP_403_FORBIDDEN)

        variant_id = request.data.get('variant_id')
        if variant_id:
            try:
                variant_id = int(variant_id)
            except (ValueError, TypeError):
                variant_id = None

        session = await create_exam_simulator_session(student, variant_id=variant_id)

        session_tasks = [
            st async for st in SessionTask.objects.filter(session=session).select_related('task').order_by('order')
        ]
        tasks_payload = []
        for st in session_tasks:
            task_data = await serialize_current_task(st)
            tasks_payload.append(task_data)

        return Response({
            'session_id': session.id,
            'title': 'Симулятор ЦТ/ЦЭ (40 вопросов)',
            'time_limit_seconds': session.time_limit_seconds,
            'tasks_total': len(session_tasks),
            'tasks': tasks_payload,
        })


class ExamSubmitView(APIView):
    """Сдача бланка ответов симулятора ЦТ/ЦЭ."""

    authentication_classes = telegram_auth_classes()

    async def post(self, request, tg_id: int):
        student, err = await aget_student_by_tg(request, tg_id)
        if err:
            return err

        session_id = request.data.get('session_id')
        answers = request.data.get('answers') or []
        time_spent_seconds = int(request.data.get('time_spent_seconds') or 0)

        try:
            session = await DailySession.objects.aget(
                id=session_id,
                student=student,
                kind=DailySession.Kind.EXAM,
            )
        except DailySession.DoesNotExist:
            return Response({'detail': 'Сессия симулятора не найдена'}, status=status.HTTP_404_NOT_FOUND)

        protocol = await submit_exam_simulator(student, session, answers, time_spent_seconds=time_spent_seconds)
        return Response(protocol)
