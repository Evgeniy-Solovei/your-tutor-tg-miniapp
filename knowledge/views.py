from adrf.views import APIView
from django.db.models import Count, Q
from rest_framework.response import Response

from core.api import telegram_auth_classes
from knowledge.models import ExamTrack, ExamVariant, Subject, Task, Topic


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
        counts = {
            (row['topic__section__exam_track__subject_id'], row['topic__grade_level']): row
            async for row in Task.objects.filter(
                is_active=True,
                topic__section__exam_track__subject_id__in=[s.id for s in subjects],
                topic__grade_level__range=(1, 11),
            )
            .values('topic__section__exam_track__subject_id', 'topic__grade_level')
            .annotate(task_count=Count('id'), topic_count=Count('topic_id', distinct=True))
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
                'Выбери предмет и класс.',
                'Классы с заданиями можно открыть сразу.',
                'После выбора практика подстроится под новый класс.',
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
        if topic_ids:
            async for row in Task.objects.filter(is_active=True, topic_id__in=topic_ids).values('topic_id').annotate(cnt=Count('id')):
                task_counts[row['topic_id']] = row['cnt']

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
                'solved_count': s_count,
                'progress_percent': pct,
                'mastery_score': pct,
                'has_summary': has_sum,
                'summary_title': t.summary.title if has_sum else '',
                'summary_key_points': t.summary.key_points if has_sum else '',
            })

        sorted_sections = sorted(sections_map.values(), key=lambda s: (s['order'], s['name']))

        total_tasks = sum(task_counts.values())
        total_topics = len(topics)

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
            'sections': sorted_sections,
            'collections': collections,
            'has_extra_materials': has_extra_materials,
            **extra_stats,
        })

