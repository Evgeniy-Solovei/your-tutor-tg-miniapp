"""Регистрация и обновление профиля ученика (бот + Mini App)."""

from __future__ import annotations

from knowledge.models import ExamTrack, Subject
from students.models import Student

GOAL_TO_TRACK = {
    Student.Goal.CT: ExamTrack.TrackType.CT_11,
    Student.Goal.CE: ExamTrack.TrackType.CE_11,
    Student.Goal.ATTESTAT: ExamTrack.TrackType.ATTESTAT_9,
    Student.Goal.IMPROVE: ExamTrack.TrackType.GENERAL,
}

VALID_GRADES = set(range(1, 12))
VALID_GOALS = {c.value for c in Student.Goal}

# Какие цели доступны по классу (остальные отсекаем при регистрации)
GOALS_BY_GRADE: dict[int, set[str]] = {
    **{g: {Student.Goal.IMPROVE} for g in range(1, 9)},
    9: {Student.Goal.ATTESTAT, Student.Goal.IMPROVE},
    10: {Student.Goal.CT, Student.Goal.CE, Student.Goal.IMPROVE},
    11: {Student.Goal.CT, Student.Goal.CE, Student.Goal.IMPROVE},
}


async def resolve_subject_and_track(
    grade: int,
    *,
    subject_id: int | None = None,
    goal: str | None = None,
    exam_track_id: int | None = None,
) -> tuple[Subject, ExamTrack]:
    """Выбрать предмет и трек. Если БД пустая — автоматически создаётся 'Русский язык'."""
    if subject_id:
        subject = await Subject.objects.filter(id=subject_id, is_active=True).afirst()
    else:
        subject = await Subject.objects.filter(is_active=True).order_by('order').afirst()

    if not subject:
        subject, _ = await Subject.objects.aget_or_create(
            slug='russian',
            defaults={
                'name': 'Русский язык',
                'description': 'Подготовка к ЦТ/ЦЭ и аттестату (Беларусь)',
                'order': 1,
                'is_active': True,
            },
        )

    # 1–8 класс: только школьная программа (GENERAL), не ЦТ/ЦЭ
    if grade <= 8:
        goal = Student.Goal.IMPROVE

    if exam_track_id:
        track = await ExamTrack.objects.filter(
            id=exam_track_id, subject=subject, is_active=True
        ).afirst()
        if track:
            return subject, track

    preferred = GOAL_TO_TRACK.get(goal) if goal else None
    if preferred:
        track = await (
            ExamTrack.objects.filter(
                subject=subject,
                is_active=True,
                track_type=preferred,
                grade_from__lte=grade,
                grade_to__gte=grade,
            )
            .order_by('id')
            .afirst()
        )
        if not track:
            track = await ExamTrack.objects.filter(
                subject=subject, is_active=True, track_type=preferred
            ).afirst()
        if track:
            return subject, track

    track = await (
        ExamTrack.objects.filter(
            subject=subject,
            is_active=True,
            grade_from__lte=grade,
            grade_to__gte=grade,
        )
        .order_by('id')
        .afirst()
    )
    if not track:
        track = await ExamTrack.objects.filter(subject=subject, is_active=True).afirst()

    if not track:
        track, _ = await ExamTrack.objects.aget_or_create(
            subject=subject,
            track_type=ExamTrack.TrackType.GENERAL,
            defaults={
                'name': 'Школьная программа (1–11 классы)',
                'grade_from': 1,
                'grade_to': 11,
                'is_active': True,
            },
        )

    return subject, track


def validate_registration_payload(data: dict, *, require_geo: bool = True) -> dict:
    """Нормализовать и проверить поля регистрации/профиля. Raises ValueError."""
    display_name = (data.get('display_name') or '').strip()[:100]
    if not display_name:
        raise ValueError('Укажи имя для рейтинга')

    try:
        grade = int(data.get('grade'))
    except (TypeError, ValueError) as exc:
        raise ValueError('Класс: от 1 до 11') from exc
    if grade not in VALID_GRADES:
        raise ValueError('Класс: от 1 до 11')

    goal = (data.get('goal') or '').strip()
    if goal in ('school', 'general', 'improve_grades'):
        goal = Student.Goal.IMPROVE
    allowed_goals = GOALS_BY_GRADE.get(grade, VALID_GOALS)
    if goal not in VALID_GOALS:
        raise ValueError('Выбери цель подготовки')
    if goal not in allowed_goals:
        # мягко подставляем доступную цель
        goal = next(iter(allowed_goals))

    subject_id = data.get('subject_id')
    if subject_id in ('', None):
        subject_id = None
    else:
        try:
            subject_id = int(subject_id)
        except (TypeError, ValueError) as exc:
            raise ValueError('Некорректный предмет') from exc

    exam_track_id = data.get('exam_track_id')
    if exam_track_id in ('', None):
        exam_track_id = None
    else:
        try:
            exam_track_id = int(exam_track_id)
        except (TypeError, ValueError) as exc:
            raise ValueError('Некорректный трек') from exc

    city_id = data.get('city_id')
    if city_id in ('', None):
        city_id = None
    else:
        try:
            city_id = int(city_id)
        except (TypeError, ValueError) as exc:
            raise ValueError('Некорректный город') from exc

    school_id = data.get('school_id')
    if school_id in ('', None):
        school_id = None
    else:
        try:
            school_id = int(school_id)
        except (TypeError, ValueError) as exc:
            raise ValueError('Некорректная школа') from exc

    if require_geo:
        if not city_id:
            raise ValueError('Выбери город')
        if not school_id:
            raise ValueError('Выбери школу')

    return {
        'display_name': display_name,
        'grade': grade,
        'goal': goal,
        'subject_id': subject_id,
        'exam_track_id': exam_track_id,
        'city_id': city_id,
        'school_id': school_id,
    }


async def register_or_update_student(
    *,
    tg_id: int,
    username: str = '',
    payload: dict,
    require_geo: bool = True,
) -> Student:
    """Создать/обновить ученика и отметить регистрацию завершённой."""
    existing_student = await Student.objects.filter(tg_id=tg_id).afirst()
    merged_payload = dict(payload or {})
    if existing_student:
        if not merged_payload.get('display_name'):
            merged_payload['display_name'] = existing_student.display_name or username or f'Ученик {tg_id}'
        if not merged_payload.get('grade'):
            merged_payload['grade'] = existing_student.grade or 11
        if not merged_payload.get('goal'):
            merged_payload['goal'] = existing_student.goal or 'school'
        if 'city_id' not in merged_payload and existing_student.city_id:
            merged_payload['city_id'] = existing_student.city_id
        if 'school_id' not in merged_payload and existing_student.school_id:
            merged_payload['school_id'] = existing_student.school_id
        if 'subject_id' not in merged_payload and existing_student.subject_id:
            merged_payload['subject_id'] = existing_student.subject_id
        if 'exam_track_id' not in merged_payload and existing_student.exam_track_id:
            merged_payload['exam_track_id'] = existing_student.exam_track_id

    clean = validate_registration_payload(merged_payload, require_geo=require_geo and not existing_student)
    subject, track = await resolve_subject_and_track(
        clean['grade'],
        subject_id=clean['subject_id'],
        goal=clean['goal'],
        exam_track_id=clean['exam_track_id'],
    )

    city_id = clean['city_id']
    school_id = clean['school_id']
    school_name = (payload.get('school_name') or '').strip()

    if school_id:
        from core.models import School

        school = await School.objects.filter(id=school_id, is_active=True).afirst()
        if school:
            city_id = school.city_id
    elif school_name and city_id:
        from core.models import School

        school, _ = await School.objects.aget_or_create(
            city_id=city_id,
            name=school_name[:255],
            defaults={'is_active': True},
        )
        school_id = school.id

    if city_id:
        from core.models import City

        if not await City.objects.filter(id=city_id, is_active=True).aexists():
            raise ValueError('Выбранный город не найден')

    defaults = {
        'username': username or (existing_student.username if existing_student else '') or '',
        'display_name': clean['display_name'],
        'grade': clean['grade'],
        'goal': clean['goal'],
        'subject_id': subject.id,
        'exam_track_id': track.id,
        'city_id': city_id,
        'school_id': school_id,
        'registration_completed': True,
    }
    if 'notifications_enabled' in payload:
        defaults['notifications_enabled'] = bool(payload['notifications_enabled'])

    student, _ = await Student.objects.aupdate_or_create(
        tg_id=tg_id,
        defaults=defaults,
    )
    return student
