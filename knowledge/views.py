from adrf.views import APIView
from django.conf import settings
from django.db.models import Count, Q
from rest_framework.response import Response

from core.api import telegram_auth_classes
from knowledge.models import ExamTrack, ExamVariant, Subject, Task, Topic, TopicExtraTask
from knowledge.textbook_tasks import filter_school_textbook_tasks


class SubjectListView(APIView):
    async def get(self, request):
        subjects = [
            {'id': s.id, 'name': s.name, 'slug': s.slug}
            async for s in Subject.objects.filter(is_active=True).order_by('order')
        ]
        if not subjects:
            s, _ = await Subject.objects.aget_or_create(
                slug='russian',
                defaults={
                    'name': 'Русский язык',
                    'description': 'Подготовка к ЦТ/ЦЭ и аттестату (Беларусь)',
                    'order': 1,
                    'is_active': True,
                },
            )
            subjects = [{'id': s.id, 'name': s.name, 'slug': s.slug}]
        return Response(subjects)


class ExamTrackListView(APIView):
    async def get(self, request, subject_id: int):
        tracks = [
            {
                'id': t.id,
                'name': t.name,
                'track_type': t.track_type,
                'grade_from': t.grade_from,
                'grade_to': t.grade_to,
            }
            async for t in ExamTrack.objects.filter(subject_id=subject_id, is_active=True)
        ]
        return Response(tracks)


class CatalogView(APIView):
    """Каталог: предметы × классы × сколько заданий (для страницы «Курсы»)."""

    authentication_classes = []
    permission_classes = []

    async def get(self, request):
        grade_hints = {
            1: 'Буквы, слоги, первые слова — с картинками',
            2: 'Состав слова, предложение — с картинками',
            3: 'Части речи, корень и приставка — с картинками',
            4: 'Орфография, главное в предложении — база начальной школы',
            5: 'Фонетика, лексика, существительное, прилагательное',
            6: 'Глагол, местоимение, числительное, стили речи',
            7: 'Причастие, деепричастие, наречие, предлоги',
            8: 'Синтаксис простого предложения, тире и двоеточие',
            9: 'Сложное предложение + подготовка к изложению (экзамен)',
            10: 'Систематизация орфографии и синтаксиса для старшей школы',
            11: 'Полный банк заданий ЦТ и ЦЭ (А1–А18, Б1–Б10)',
        }
        subjects = [
            subject
            async for subject in Subject.objects.filter(is_active=True).order_by('order', 'name')
        ]
        base_task_qs = Task.objects.filter(
            is_active=True,
            topic__section__exam_track__subject_id__in=[s.id for s in subjects],
            topic__grade_level__range=(1, 11),
        )
        counts = {
            (row['topic__section__exam_track__subject_id'], row['topic__grade_level']): row
            async for row in base_task_qs.values(
                'topic__section__exam_track__subject_id', 'topic__grade_level'
            ).annotate(task_count=Count('id'), topic_count=Count('topic_id', distinct=True))
        }
        textbook_counts = {
            (row['topic__section__exam_track__subject_id'], row['topic__grade_level']): row[
                'task_count'
            ]
            async for row in filter_school_textbook_tasks(base_task_qs)
            .values('topic__section__exam_track__subject_id', 'topic__grade_level')
            .annotate(task_count=Count('id'))
        }
        res = []
        for subject in subjects:
            grades_data = []
            for g in range(1, 12):
                count_row = counts.get(
                    (subject.id, g),
                    {'task_count': 0, 'topic_count': 0},
                )
                task_count = count_row['task_count']
                if g <= 10:
                    task_count = textbook_counts.get((subject.id, g), 0) or task_count
                topic_count = count_row['topic_count']
                grades_data.append({
                    'grade': g,
                    # Поля ниже — публичный контракт страницы «Курсы».
                    'title': f'{g} класс',
                    'badge': 'Доступно' if task_count else 'Скоро',
                    'available': task_count > 0,
                    'tasks': task_count,
                    'topics': topic_count,
                    # Оставляем прежнее имя для обратной совместимости API.
                    'task_count': task_count,
                    'hint': grade_hints.get(g, ''),
                })
            res.append({
                'id': subject.id,
                'name': subject.name,
                'slug': subject.slug,
                'grades': grades_data,
            })
        return Response({
            'items': res,
            # Старые клиенты использовали subjects, не ломаем их.
            'subjects': res,
            'how_it_works': [
                '1. Выбери свой класс и тему.',
                '2. Решай задания из учебника (шаг «Учебник»).',
                '3. Закрепляй тему в доп. тренажёре и смотри разбор с ИИ, если ошибся.',
            ],
        })


class GradeCurriculumView(APIView):
    """Детальный обзор разделов и тем выбранного класса (1-11 класс + ЦТ/ЦЭ)."""

    authentication_classes = telegram_auth_classes()

    async def get(self, request, grade: int):
        from learning.models import TaskAttempt, TopicMastery

        student = None
        tg_id_param = request.query_params.get('tg_id')
        if tg_id_param and str(tg_id_param).isdigit():
            from core.api import aget_student_by_tg
            student_obj, _ = await aget_student_by_tg(request, int(tg_id_param))
            student = student_obj

        topics_qs = Topic.objects.filter(is_active=True).select_related('section', 'summary')
        if grade == 11:
            topics_qs = topics_qs.filter(
                Q(grade_level=11) | Q(section__exam_track__track_type__in=['ct_11', 'ce_11'])
            )
        else:
            topics_qs = topics_qs.filter(grade_level=grade)

        topics = [t async for t in topics_qs.order_by('section__order', 'order', 'name')]
        topic_ids = [t.id for t in topics]
        task_counts = {}
        extra_counts = {}
        if topic_ids:
            task_qs = Task.objects.filter(is_active=True, topic_id__in=topic_ids)
            if grade <= 10:
                task_qs = filter_school_textbook_tasks(task_qs)
            async for row in task_qs.values('topic_id').annotate(cnt=Count('id')):
                task_counts[row['topic_id']] = row['cnt']
            async for row in TopicExtraTask.objects.filter(is_active=True, topic_id__in=topic_ids).values('topic_id').annotate(cnt=Count('id')):
                extra_counts[row['topic_id']] = row['cnt']

        solved_counts = {}
        masteries = {}
        if student and topic_ids:
            async for row in (
                TaskAttempt.objects.filter(
                    student=student,
                    is_correct=True,
                    task__topic_id__in=topic_ids,
                )
                .values('task__topic_id')
                .annotate(solved=Count('task_id', distinct=True))
            ):
                solved_counts[row['task__topic_id']] = row['solved']

            async for m in TopicMastery.objects.filter(student=student, topic_id__in=topic_ids):
                masteries[m.topic_id] = m.correct_count

        sections_map = {}
        for t in topics:
            sec_id = t.section_id
            if sec_id not in sections_map:
                sections_map[sec_id] = {
                    'id': sec_id,
                    'name': t.section.name,
                    'order': t.section.order,
                    'topics': [],
                }

            t_count = task_counts.get(t.id, 0)
            s_count = solved_counts.get(t.id, 0)
            if not s_count and t.id in masteries:
                s_count = min(t_count, masteries[t.id])
            pct = min(100, round((s_count / t_count) * 100)) if t_count > 0 else 0

            has_sum = hasattr(t, 'summary') and t.summary is not None
            sections_map[sec_id]['topics'].append({
                'id': t.id,
                'name': t.name,
                'exam_weight': t.exam_weight,
                'task_count': t_count,
                'extra_task_count': extra_counts.get(t.id, 0),
                'solved_count': s_count,
                'progress_percent': pct,
                'mastery_score': pct,
                'has_summary': has_sum,
                'summary_title': t.summary.title if has_sum else '',
                'summary_key_points': t.summary.key_points if has_sum else '',
            })

        sorted_sections = sorted(sections_map.values(), key=lambda s: (s['order'], s['name']))

        total_tasks = sum(task_counts.values())
        total_extra_tasks = sum(extra_counts.values())
        total_topics = len(topics)
        school_textbook_tasks_count = total_tasks
        if grade == 11 and topic_ids:
            school_textbook_tasks_count = await filter_school_textbook_tasks(
                Task.objects.filter(is_active=True, topic_id__in=topic_ids)
            ).acount()

        extra_stats = {}
        if grade == 9:
            izlo_cnt = await Task.objects.filter(
                is_active=True, topic_id__in=topic_ids, source__startswith='Сборник изложений'
            ).acount()
            extra_stats = {
                'has_izlozheniya': True,
                'izlozheniya_count': izlo_cnt,
                'school_tasks_count': max(0, total_tasks - izlo_cnt),
            }
        elif grade == 11:
            from django.core.cache import cache

            try:
                cached_stats = await cache.aget('g11_curriculum_extra_stats')
            except Exception:
                cached_stats = None

            if cached_stats:
                part_a_cnt, part_b_cnt, years_stats = cached_stats
            else:
                part_a_cnt = await Task.objects.filter(
                    is_active=True,
                    topic_id__in=topic_ids,
                    answer_format__in=['single_choice', 'multiple_choice'],
                ).acount()
                part_b_cnt = await Task.objects.filter(
                    is_active=True, topic_id__in=topic_ids, answer_format='text'
                ).acount()

                recent_years = [2025, 2024, 2023, 2022, 2021, 2020]
                years_stats = []
                for y in recent_years:
                    y_filter = Q(source__icontains=str(y)) | Q(variant_links__variant__year=y)
                    y_total = await Task.objects.filter(y_filter, is_active=True).distinct().acount()
                    y_part_a = await Task.objects.filter(
                        y_filter, is_active=True, answer_format__in=['single_choice', 'multiple_choice']
                    ).distinct().acount()
                    y_part_b = await Task.objects.filter(
                        y_filter, is_active=True, answer_format='text'
                    ).distinct().acount()
                    y_vars = await ExamVariant.objects.filter(year=y, is_active=True).acount()
                    years_stats.append({
                        'year': y,
                        'total_tasks': y_total,
                        'part_a_count': y_part_a,
                        'part_b_count': y_part_b,
                        'variants_count': y_vars,
                    })
                try:
                    await cache.aset('g11_curriculum_extra_stats', (part_a_cnt, part_b_cnt, years_stats), 3600)
                except Exception:
                    pass

            extra_stats = {
                'has_ct_ce': True,
                'part_a_count': part_a_cnt,
                'part_b_count': part_b_cnt,
                'available_years': years_stats,
                'school_tasks_count': school_textbook_tasks_count,
            }

        # Дополнительные сборники и спецматериалы формируются только при их реальном наличии
        collections = []
        if grade == 9 and extra_stats.get('has_izlozheniya'):
            collections = [
                {
                    'id': 'c_g9_izlo',
                    'title': 'Сборник материалов для выпускного экзамена (НИО)',
                    'description': '166 официальных художественных текстов для подробных изложений',
                    'tasks_count': extra_stats.get('izlozheniya_count', 0),
                    'status': 'available',
                    'badge': 'Экзамен 9 кл',
                    'action': 'izlozhenie',
                },
            ]
        elif grade == 11 and extra_stats.get('has_ct_ce'):
            collections = [
                {
                    'id': 'c_g11_ct_bank',
                    'title': 'Официальный банк заданий ЦТ и ЦЭ (РИКЗ 2003–2025)',
                    'description': '13 345 заданий: Часть А, Часть Б, фильтрация по годам и полные варианты',
                    'tasks_count': total_tasks,
                    'status': 'available',
                    'badge': 'РИКЗ',
                    'action': 'ct_ce',
                },
            ]

        has_extra_materials = bool(
            extra_stats.get('has_ct_ce')
            or extra_stats.get('has_izlozheniya')
            or len(collections) > 0
        )

        return Response({
            'grade': grade,
            'title': f'{grade} класс' if grade <= 10 else '11 класс / ЦТ и ЦЭ',
            'total_topics': total_topics,
            'total_tasks': total_tasks,
            'school_textbook_tasks_count': school_textbook_tasks_count,
            'total_extra_tasks': total_extra_tasks,
            'sections': sorted_sections,
            'collections': collections,
            'has_extra_materials': has_extra_materials,
            **extra_stats,
        })


class TopicExtraTasksView(APIView):
    """Список дополнительных заданий по выбранной теме."""

    authentication_classes = telegram_auth_classes()

    async def get(self, request, topic_id: int):
        topic = await Topic.objects.filter(id=topic_id, is_active=True).select_related('section').afirst()
        if not topic:
            return Response({'detail': 'Тема не найдена'}, status=404)

        tg_id_param = request.query_params.get('tg_id')
        student = None
        if tg_id_param:
            try:
                from core.api import aget_student_by_tg
                student, _ = await aget_student_by_tg(request, int(tg_id_param))
            except Exception:
                pass
        if not student:
            user = getattr(request, 'telegram_user', None)
            if user:
                from students.models import Student
                student = await Student.objects.filter(tg_id=user.id).afirst()
            elif tg_id_param and settings.DEBUG:
                from students.models import Student
                student = await Student.objects.filter(tg_id=int(tg_id_param)).afirst()

        FREE_LIMIT = 10
        total_completed_all = 0
        is_pro = False
        if student:
            is_pro = bool(student.is_pro)
            from learning.models import TaskAttempt
            total_completed_all = await TaskAttempt.objects.filter(
                student=student, extra_task__isnull=False
            ).values('extra_task_id').distinct().acount()

        paywall_active = (not is_pro) and (total_completed_all >= FREE_LIMIT)
        if paywall_active:
            return Response({
                'paywall_required': True,
                'free_limit': FREE_LIMIT,
                'total_completed_all': total_completed_all,
                'detail': 'Ты выполнил 10 бесплатных заданий! Все 50 заданий по каждой теме доступны по подписке «Твой Репетитор PRO».',
                'topic_id': topic.id,
                'topic_name': topic.name,
                'count': 0,
                'tasks': [],
            })

        extra_tasks_qs = TopicExtraTask.objects.filter(topic=topic, is_active=True).order_by('order', 'id')
        tasks = []
        async for item in extra_tasks_qs:
            tasks.append({
                'id': item.id,
                'topic_id': topic.id,
                'topic_name': topic.name,
                'question': item.question,
                'reading_text': item.reading_text,
                'image': item.get_image_url,
                'options': item.options,
                'difficulty': item.difficulty,
                'source': item.source,
                'has_explanation': bool(item.explanation),
            })

        return Response({
            'topic_id': topic.id,
            'topic_name': topic.name,
            'section_name': topic.section.name if topic.section else '',
            'grade_level': topic.grade_level,
            'count': len(tasks),
            'tasks': tasks,
            'is_pro': is_pro,
            'free_limit': FREE_LIMIT,
            'total_completed_all': total_completed_all,
            'free_tasks_left': max(0, FREE_LIMIT - total_completed_all) if not is_pro else None,
        })


class GradeExtraTasksSummaryView(APIView):
    """Сводка тем с дополнительными заданиями по классу."""

    authentication_classes = telegram_auth_classes()

    async def get(self, request):
        grade_param = request.query_params.get('grade', 1)
        try:
            grade = int(grade_param)
        except (ValueError, TypeError):
            grade = 1

        tg_id_param = request.query_params.get('tg_id')
        student = None
        if tg_id_param:
            try:
                from core.api import aget_student_by_tg
                student, _ = await aget_student_by_tg(request, int(tg_id_param))
            except Exception:
                pass
        if not student:
            user = getattr(request, 'telegram_user', None)
            if user:
                from students.models import Student
                student = await Student.objects.filter(tg_id=user.id).afirst()
            elif tg_id_param and settings.DEBUG:
                from students.models import Student
                student = await Student.objects.filter(tg_id=int(tg_id_param)).afirst()

        from django.db.models import Count, Q
        topics_qs = (
            Topic.objects.filter(is_active=True, grade_level=grade)
            .select_related('section')
            .annotate(extra_tasks_count=Count('extra_tasks', filter=Q(extra_tasks__is_active=True)))
            .filter(extra_tasks_count__gt=0)
            .order_by('section__order', 'order', 'id')
        )

        solved_counts = {}
        mastery_scores = {}
        total_completed_all = 0
        is_pro = False
        FREE_LIMIT = 10
        if student:
            is_pro = bool(student.is_pro)
            from learning.models import TaskAttempt, TopicMastery
            total_completed_all = await TaskAttempt.objects.filter(
                student=student, extra_task__isnull=False
            ).values('extra_task_id').distinct().acount()

            async for att in TaskAttempt.objects.filter(
                student=student, extra_task__isnull=False, extra_task__topic__grade_level=grade, is_correct=True
            ).values('extra_task__topic_id').annotate(c=Count('extra_task_id', distinct=True)):
                solved_counts[att['extra_task__topic_id']] = att['c']

            async for m in TopicMastery.objects.filter(student=student, topic__grade_level=grade):
                mastery_scores[m.topic_id] = round(m.mastery_score * 100)

        paywall_active = (not is_pro) and (total_completed_all >= FREE_LIMIT)

        topics_data = []
        total_tasks = 0
        total_solved = 0
        async for topic in topics_qs:
            cnt = topic.extra_tasks_count
            total_tasks += cnt
            solved = solved_counts.get(topic.id, 0)
            total_solved += solved
            mastery = mastery_scores.get(topic.id, 0)
            topics_data.append({
                'id': topic.id,
                'topic_id': topic.id,
                'name': topic.name,
                'topic_name': topic.name,
                'section_id': topic.section_id,
                'section_name': topic.section.name if topic.section else 'Общие темы',
                'extra_tasks_count': cnt,
                'solved_count': solved,
                'mastery_score': mastery,
            })

        return Response({
            'grade': grade,
            'total_topics': len(topics_data),
            'total_extra_tasks': total_tasks,
            'total_solved': total_solved,
            'total_completed_all': total_completed_all,
            'free_limit': FREE_LIMIT,
            'is_pro': is_pro,
            'paywall_active': paywall_active,
            'topics': topics_data,
        })


class TopicExtraTaskSubmitView(APIView):
    """Проверка ответа на дополнительное задание по теме."""

    authentication_classes = telegram_auth_classes()

    async def post(self, request, task_id: int):
        tg_id = request.data.get('tg_id')
        if not tg_id:
            user = getattr(request, 'telegram_user', None)
            tg_id = user.id if user else None

        if not tg_id:
            return Response({'detail': 'tg_id обязателен'}, status=400)

        from core.api import aget_student_by_tg
        student, err = await aget_student_by_tg(request, int(tg_id))
        if (err or not student) and settings.DEBUG:
            from students.models import Student
            student = await Student.objects.filter(tg_id=int(tg_id)).afirst()
            err = None
        if err or not student:
            return err or Response({'detail': 'Ученик не найден'}, status=404)

        task = await TopicExtraTask.objects.select_related('topic').filter(id=task_id, is_active=True).afirst()
        if not task:
            return Response({'detail': 'Задание не найдено'}, status=404)

        FREE_LIMIT = 10
        is_pro = bool(student.is_pro)
        if not is_pro:
            from learning.models import TaskAttempt
            total_completed = await TaskAttempt.objects.filter(
                student=student, extra_task__isnull=False
            ).values('extra_task_id').distinct().acount()
            if total_completed >= FREE_LIMIT:
                return Response({
                    'paywall_required': True,
                    'detail': 'Ты выполнил 10 бесплатных заданий! Все 50 заданий по каждой теме доступны по подписке «Твой Репетитор PRO».',
                }, status=403)

        user_answer = str(request.data.get('answer', '')).strip()
        correct_answer = str(task.correct_answer or '').strip()

        # Check answer: normalize whitespace and lower
        def normalize(s):
            return ' '.join(s.lower().replace('ё', 'е').split())

        is_correct = False
        norm_user = normalize(user_answer)
        norm_correct = normalize(correct_answer)

        if norm_user == norm_correct:
            is_correct = True
        elif task.options:
            for idx, opt in enumerate(task.options, 1):
                if str(opt).strip() == correct_answer and (norm_user == str(idx) or norm_user == normalize(str(opt))):
                    is_correct = True
                    break

        xp_earned = 10 if is_correct else 2
        student.xp = (student.xp or 0) + xp_earned
        await student.asave(update_fields=['xp'])

        from learning.models import TaskAttempt, TopicMastery
        await TaskAttempt.objects.acreate(
            student=student,
            task=None,
            extra_task=task,
            answer_text=user_answer,
            is_correct=is_correct,
            points_earned=1 if is_correct else 0,
            max_points=1,
        )

        mastery, _ = await TopicMastery.objects.aget_or_create(student=student, topic=task.topic)
        if is_correct:
            mastery.correct_count += 1
        else:
            mastery.wrong_count += 1
        mastery.recalculate_score()
        await mastery.asave()

        free_tasks_left = None
        if not is_pro:
            new_distinct = await TaskAttempt.objects.filter(
                student=student, extra_task__isnull=False
            ).values('extra_task_id').distinct().acount()
            free_tasks_left = max(0, FREE_LIMIT - new_distinct)

        return Response({
            'is_correct': is_correct,
            'correct_answer': task.correct_answer,
            'explanation': task.explanation or '',
            'xp_earned': xp_earned,
            'user_xp': student.xp,
            'mastery_score': round(mastery.mastery_score * 100),
            'is_pro': is_pro,
            'free_tasks_left': free_tasks_left,
        })


